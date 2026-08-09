"""Configuratie en capability-detectie.

De motor draait altijd. Welke bronnen beschikbaar zijn hangt af van welke
API-keys aanwezig zijn; `Settings.capabilities()` vertelt precies wat aan staat.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent

load_dotenv(PROJECT_ROOT / ".env")


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "ja", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


@dataclass
class Settings:
    gemini_key: str = field(
        default_factory=lambda: (
            os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
        ).strip()
    )
    anthropic_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", "").strip())
    serper_key: str = field(default_factory=lambda: os.getenv("SERPER_API_KEY", "").strip())
    brave_key: str = field(default_factory=lambda: os.getenv("BRAVE_API_KEY", "").strip())
    google_cse_key: str = field(default_factory=lambda: os.getenv("GOOGLE_CSE_KEY", "").strip())
    google_cse_cx: str = field(default_factory=lambda: os.getenv("GOOGLE_CSE_CX", "").strip())
    places_key: str = field(default_factory=lambda: os.getenv("GOOGLE_PLACES_API_KEY", "").strip())
    kvk_key: str = field(default_factory=lambda: os.getenv("KVK_API_KEY", "").strip())
    youtube_key: str = field(default_factory=lambda: os.getenv("YOUTUBE_API_KEY", "").strip())
    apollo_key: str = field(default_factory=lambda: os.getenv("APOLLO_API_KEY", "").strip())
    hunter_key: str = field(default_factory=lambda: os.getenv("HUNTER_API_KEY", "").strip())
    zerobounce_key: str = field(default_factory=lambda: os.getenv("ZEROBOUNCE_API_KEY", "").strip())

    user_agent: str = field(
        default_factory=lambda: os.getenv(
            "LEADENGINE_UA",
            "lead-engine/1.0 (+zakelijk contactonderzoek)",
        )
    )
    max_concurrency: int = field(default_factory=lambda: _int("LEADENGINE_MAX_CONCURRENCY", 8))
    delay_per_domain: float = field(default_factory=lambda: _float("LEADENGINE_DELAY_PER_DOMAIN", 1.5))
    respect_robots: bool = field(default_factory=lambda: _bool("LEADENGINE_RESPECT_ROBOTS", True))

    # ── LLM ─────────────────────────────────────────────────────────────────
    # 'auto' kiest Gemini als die key er is (die kan Google Search grounding),
    # anders Claude. Forceer met LEADENGINE_LLM_PROVIDER=gemini|anthropic.
    llm_provider: str = field(default_factory=lambda: os.getenv("LEADENGINE_LLM_PROVIDER", "auto"))
    gemini_model: str = field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
    )
    # Welke API-versie het model bedient verschilt per account; `leadengine
    # sleutel` detecteert dit en zet 'm hier vast.
    gemini_api_version: str = field(
        default_factory=lambda: os.getenv("GEMINI_API_VERSION", "v1beta").strip() or "v1beta"
    )
    anthropic_model: str = field(
        default_factory=lambda: os.getenv("ANTHROPIC_MODEL", "claude-opus-5").strip()
    )

    def search_provider(self) -> str:
        """Welke zoekmachine gebruiken we voor bronontdekking?

        Volgorde: expliciete keuze > Google CSE > Serper > Brave >
        Gemini-grounding > DuckDuckGo.
        """
        keuze = os.getenv("LEADENGINE_SEARCH_PROVIDER", "").strip().lower()
        if keuze in {"google_cse", "serper", "brave", "gemini", "duckduckgo"}:
            return keuze
        if self.google_cse_key and self.google_cse_cx:
            return "google_cse"
        if self.serper_key:
            return "serper"
        if self.brave_key:
            return "brave"
        if self.gemini_key:
            return "gemini"
        return "duckduckgo"

    def actieve_llm(self) -> str:
        keuze = self.llm_provider.lower().strip()
        if keuze == "gemini" and self.gemini_key:
            return "gemini"
        if keuze == "anthropic" and self.anthropic_key:
            return "anthropic"
        if self.gemini_key:
            return "gemini"
        if self.anthropic_key:
            return "anthropic"
        return ""

    def capabilities(self) -> dict[str, tuple[bool, str]]:
        """Naam -> (aan/uit, uitleg in het Nederlands)."""
        llm = self.actieve_llm()
        llm_label = {
            "gemini": f"Gemini ({self.gemini_model})",
            "anthropic": f"Claude ({self.anthropic_model})",
        }.get(llm, "geen")
        zoek = self.search_provider()
        zoek_uitleg = {
            "google_cse": "Google Programmable Search — echte Google-resultaten",
            "serper": "Serper.dev (Google-proxy)",
            "brave": "Brave Search API",
            "gemini": "Gemini met Google Search grounding",
            "duckduckgo": "DuckDuckGo-fallback — zet GOOGLE_CSE_KEY voor echte Google",
        }[zoek]

        return {
            f"LLM: {llm_label}": (
                bool(llm),
                "ICP bepalen + bronnen bedenken. Zonder dit alleen het statische register",
            ),
            "Google Search grounding": (
                llm == "gemini",
                "Gemini zoekt écht op Google -> bronnen met geverifieerde URL's",
            ),
            f"Zoekmachine: {zoek}": (True, zoek_uitleg),
            "Website-crawl": (True, "altijd aan — de werkpaard-bron"),
            "Google Places (lokaal MKB)": (bool(self.places_key), "GOOGLE_PLACES_API_KEY"),
            "KvK Handelsregister": (bool(self.kvk_key), "KVK_API_KEY"),
            "YouTube-kanalen/podcasts": (bool(self.youtube_key), "YOUTUBE_API_KEY"),
            "Apollo (B2B-contacten)": (bool(self.apollo_key), "APOLLO_API_KEY"),
            "Hunter (domein -> e-mail)": (bool(self.hunter_key), "HUNTER_API_KEY"),
            "E-mailvalidatie (ZeroBounce)": (
                bool(self.zerobounce_key),
                "ZEROBOUNCE_API_KEY — zonder dit alleen MX/syntax-controle",
            ),
        }

    def waarschuwingen(self) -> list[str]:
        """Concrete tips als er iets belangrijks ontbreekt."""
        tips: list[str] = []
        if not self.actieve_llm():
            tips.append(
                "Geen LLM-key. Zet GEMINI_API_KEY (gratis tier) — dat verbetert "
                "zowel het ICP als de bronnen enorm."
            )
        elif self.actieve_llm() != "gemini":
            tips.append(
                "Gemini staat uit, dus geen Google Search grounding. Met "
                "GEMINI_API_KEY worden bronnen op echte Google-resultaten gebaseerd."
            )
        if self.search_provider() == "duckduckgo":
            tips.append(
                "Zoekmachine valt terug op DuckDuckGo. Zet GOOGLE_CSE_KEY + "
                "GOOGLE_CSE_CX voor echte Google-resultaten."
            )
        if not self.places_key:
            tips.append(
                "Zonder GOOGLE_PLACES_API_KEY vind je lokale bedrijven "
                "(praktijken, garages, salons) veel moeilijker."
            )
        return tips


SETTINGS = Settings()
