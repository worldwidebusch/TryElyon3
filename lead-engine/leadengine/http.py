"""Nette async HTTP-client: robots.txt, per-domein rate limit, retries, cache."""

from __future__ import annotations

import asyncio
import time
import urllib.robotparser as robotparser
from collections import defaultdict
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from .config import SETTINGS

_HTML_TYPES = ("text/html", "application/xhtml", "text/plain", "application/xml", "text/xml")


class Fetcher:
    """Eén Fetcher per run. Deelt connectiepool, robots-cache en rate limits."""

    def __init__(
        self,
        *,
        concurrency: int | None = None,
        delay_per_domain: float | None = None,
        respect_robots: bool | None = None,
        timeout: float = 20.0,
    ) -> None:
        self.delay = SETTINGS.delay_per_domain if delay_per_domain is None else delay_per_domain
        self.respect_robots = SETTINGS.respect_robots if respect_robots is None else respect_robots
        self._sem = asyncio.Semaphore(concurrency or SETTINGS.max_concurrency)
        self._last_hit: dict[str, float] = defaultdict(float)
        self._domain_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._robots: dict[str, robotparser.RobotFileParser | None] = {}
        self._robots_lock = asyncio.Lock()
        self._client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers={
                "User-Agent": SETTINGS.user_agent,
                "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.6",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            limits=httpx.Limits(max_connections=32, max_keepalive_connections=16),
        )
        self.geblokkeerd_door_robots: set[str] = set()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "Fetcher":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()

    # ── robots ──────────────────────────────────────────────────────────────
    async def _mag(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base not in self._robots:
            async with self._robots_lock:
                if base not in self._robots:
                    self._robots[base] = await self._laad_robots(base)
        rp = self._robots[base]
        if rp is None:
            return True
        toegestaan = rp.can_fetch(SETTINGS.user_agent, url)
        if not toegestaan:
            self.geblokkeerd_door_robots.add(parsed.netloc)
        return toegestaan

    async def _laad_robots(self, base: str) -> robotparser.RobotFileParser | None:
        rp = robotparser.RobotFileParser()
        try:
            resp = await self._client.get(urljoin(base, "/robots.txt"), timeout=8.0)
            if resp.status_code >= 400:
                return None
            rp.parse(resp.text.splitlines())
            return rp
        except Exception:
            return None

    # ── ophalen ─────────────────────────────────────────────────────────────
    async def _wacht(self, host: str) -> None:
        async with self._domain_locks[host]:
            verstreken = time.monotonic() - self._last_hit[host]
            if verstreken < self.delay:
                await asyncio.sleep(self.delay - verstreken)
            self._last_hit[host] = time.monotonic()

    async def get(self, url: str, *, pogingen: int = 2, **kwargs: Any) -> httpx.Response | None:
        if not url.lower().startswith(("http://", "https://")):
            return None
        if not await self._mag(url):
            return None
        host = urlparse(url).netloc
        async with self._sem:
            for poging in range(pogingen + 1):
                await self._wacht(host)
                try:
                    resp = await self._client.get(url, **kwargs)
                except (httpx.TimeoutException, httpx.TransportError):
                    if poging == pogingen:
                        return None
                    await asyncio.sleep(1.2 * (poging + 1))
                    continue
                except Exception:
                    return None
                if resp.status_code in (429, 502, 503, 504) and poging < pogingen:
                    await asyncio.sleep(2.0 * (poging + 1))
                    continue
                return resp
        return None

    async def html(self, url: str, **kwargs: Any) -> tuple[str, str] | None:
        """Geeft (eind-URL, html) terug, of None."""
        resp = await self.get(url, **kwargs)
        if resp is None or resp.status_code >= 400:
            return None
        ctype = resp.headers.get("content-type", "").lower()
        if ctype and not any(t in ctype for t in _HTML_TYPES):
            return None
        if len(resp.content) > 4_000_000:
            return None
        return str(resp.url), resp.text

    async def eind_url(self, url: str) -> str:
        """Volg redirects en geef de uiteindelijke URL.

        Gemini's grounding levert `vertexaisearch.cloud.google.com/...`-redirects
        in plaats van de echte pagina. Dit lost ze op. Bewust zonder
        robots-controle: we halen geen inhoud op, we kijken alleen waar de
        verwijzing heen gaat.
        """
        async with self._sem:
            try:
                resp = await self._client.get(url, timeout=12.0)
                return str(resp.url)
            except Exception:
                return ""

    async def json(self, url: str, **kwargs: Any) -> Any | None:
        resp = await self.get(url, **kwargs)
        if resp is None or resp.status_code >= 400:
            return None
        try:
            return resp.json()
        except Exception:
            return None

    async def post_json(self, url: str, *, json_body: Any, headers: dict | None = None) -> Any | None:
        async with self._sem:
            await self._wacht(urlparse(url).netloc)
            try:
                resp = await self._client.post(url, json=json_body, headers=headers or {})
                if resp.status_code >= 400:
                    return None
                return resp.json()
            except Exception:
                return None
