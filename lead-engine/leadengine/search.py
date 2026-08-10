"""Zoekmachine-abstractie met NL-instellingen (gl=nl, hl=nl).

Volgorde van voorkeur: Serper > Brave > Google CSE > DuckDuckGo-HTML.
Alle providers geven dezelfde vorm terug: {"titel", "url", "omschrijving"}.
"""

from __future__ import annotations

import asyncio
import re
from urllib.parse import quote_plus, unquote, urlparse, parse_qs

from bs4 import BeautifulSoup

from . import llm
from .config import SETTINGS
from .http import Fetcher

Resultaat = dict[str, str]

_GROUNDING_HOSTS = ("vertexaisearch.cloud.google.com", "grounding-api-redirect")


async def los_redirects_op(fetcher: Fetcher, urls: list[str]) -> dict[str, str]:
    """Zet Google-grounding-redirects om naar de echte pagina-URL's."""
    te_doen = [u for u in urls if any(h in u for h in _GROUNDING_HOSTS)]
    direct = {u: u for u in urls if u not in te_doen}
    if not te_doen:
        return direct
    opgelost = await asyncio.gather(
        *(fetcher.eind_url(u) for u in te_doen), return_exceptions=True
    )
    for origineel, eind in zip(te_doen, opgelost):
        direct[origineel] = eind if isinstance(eind, str) and eind else ""
    return direct


class Zoeker:
    def __init__(self, fetcher: Fetcher) -> None:
        self.f = fetcher
        self.provider = SETTINGS.search_provider()
        self._cache: dict[str, list[Resultaat]] = {}
        self.aantal_queries = 0

    async def zoek(self, query: str, *, aantal: int = 20) -> list[Resultaat]:
        sleutel = f"{query}::{aantal}"
        if sleutel in self._cache:
            return self._cache[sleutel]

        self.aantal_queries += 1
        try:
            if self.provider == "serper":
                res = await self._serper(query, aantal)
            elif self.provider == "brave":
                res = await self._brave(query, aantal)
            elif self.provider == "google_cse":
                res = await self._google_cse(query, aantal)
            elif self.provider == "gemini":
                res = await self._gemini(query, aantal)
            else:
                res = await self._duckduckgo(query, aantal)
        except Exception:
            res = []

        # Google CSE heeft een dagquotum; val bij uitputting terug op wat er is.
        if not res and self.provider == "google_cse" and SETTINGS.serper_key:
            res = await self._serper(query, aantal)
        if not res and self.provider not in {"duckduckgo", "gemini"}:
            res = await self._duckduckgo(query, aantal)

        self._cache[sleutel] = res
        return res

    async def zoek_veel(self, queries: list[str], *, aantal: int = 20) -> list[Resultaat]:
        taken = [self.zoek(q, aantal=aantal) for q in queries]
        alles: list[Resultaat] = []
        for groep in await asyncio.gather(*taken, return_exceptions=True):
            if isinstance(groep, list):
                alles.extend(groep)
        gezien, uniek = set(), []
        for r in alles:
            u = r["url"].split("#")[0]
            if u not in gezien:
                gezien.add(u)
                uniek.append(r)
        return uniek

    # ── providers ───────────────────────────────────────────────────────────
    async def _serper(self, query: str, aantal: int) -> list[Resultaat]:
        data = await self.f.post_json(
            "https://google.serper.dev/search",
            json_body={"q": query, "gl": "nl", "hl": "nl", "num": min(aantal, 100)},
            headers={"X-API-KEY": SETTINGS.serper_key, "Content-Type": "application/json"},
        )
        if not data:
            return []
        return [
            {
                "titel": r.get("title", ""),
                "url": r.get("link", ""),
                "omschrijving": r.get("snippet", ""),
            }
            for r in data.get("organic", [])
            if r.get("link")
        ][:aantal]

    async def _brave(self, query: str, aantal: int) -> list[Resultaat]:
        data = await self.f.json(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "country": "nl", "search_lang": "nl", "count": min(aantal, 20)},
            headers={"X-Subscription-Token": SETTINGS.brave_key, "Accept": "application/json"},
        )
        if not data:
            return []
        return [
            {
                "titel": r.get("title", ""),
                "url": r.get("url", ""),
                "omschrijving": re.sub("<[^>]+>", "", r.get("description", "")),
            }
            for r in (data.get("web", {}) or {}).get("results", [])
            if r.get("url")
        ][:aantal]

    async def _google_cse(self, query: str, aantal: int) -> list[Resultaat]:
        uit: list[Resultaat] = []
        for start in range(1, min(aantal, 30), 10):
            data = await self.f.json(
                "https://www.googleapis.com/customsearch/v1",
                params={
                    "key": SETTINGS.google_cse_key,
                    "cx": SETTINGS.google_cse_cx,
                    "q": query,
                    "gl": "nl",
                    "hl": "nl",
                    "num": 10,
                    "start": start,
                },
            )
            if not data or "items" not in data:
                break
            uit.extend(
                {
                    "titel": r.get("title", ""),
                    "url": r.get("link", ""),
                    "omschrijving": r.get("snippet", ""),
                }
                for r in data["items"]
            )
        return uit[:aantal]

    async def _gemini(self, query: str, aantal: int) -> list[Resultaat]:
        """Gemini met Google Search grounding als zoekmachine.

        Trager en duurder per query dan een echte search-API, maar het gebruikt
        wél Google en werkt zonder aparte zoek-key. De URL's zijn
        Google-redirects; die lossen we hier meteen op.
        """
        lus = asyncio.get_running_loop()
        ruw = await lus.run_in_executor(None, llm.zoek_gegrond, query)
        if not ruw:
            return []
        opgelost = await los_redirects_op(self.f, [r["url"] for r in ruw])
        uit: list[Resultaat] = []
        for r in ruw:
            echte_url = opgelost.get(r["url"], r["url"])
            if echte_url:
                uit.append({**r, "url": echte_url})
        return uit[:aantal]

    async def _duckduckgo(self, query: str, aantal: int) -> list[Resultaat]:
        """Fallback zonder key. Beperkt en soms rate-limited — maar gratis."""
        opgehaald = await self.f.html(
            f"https://html.duckduckgo.com/html/?q={quote_plus(query)}&kl=nl-nl"
        )
        if not opgehaald:
            return []
        _, html = opgehaald
        soup = BeautifulSoup(html, "lxml")
        uit: list[Resultaat] = []
        for blok in soup.select(".result, .web-result")[: aantal * 2]:
            link = blok.select_one("a.result__a")
            if not link or not link.get("href"):
                continue
            url = link["href"]
            if "duckduckgo.com/l/?" in url:                 # redirect uitpakken
                qs = parse_qs(urlparse(url).query)
                url = unquote(qs.get("uddg", [url])[0])
            omschrijving = blok.select_one(".result__snippet")
            uit.append({
                "titel": link.get_text(" ", strip=True),
                "url": url,
                "omschrijving": omschrijving.get_text(" ", strip=True) if omschrijving else "",
            })
            if len(uit) >= aantal:
                break
        return uit
