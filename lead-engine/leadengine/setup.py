"""Interactieve key-setup.

Bestaat omdat `.env` handmatig aanmaken op Windows onnodig lastig is: Verkenner
verbergt extensies en Kladblok maakt er stilletjes `.env.txt` van. Dit commando
vraagt je key, schrijft 'm goed weg en test 'm meteen.

De key wordt niet geëchood en komt niet in je command-history terecht — dat is
het verschil met `setx GEMINI_API_KEY "..."`.
"""

from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path

import httpx

from .config import PROJECT_ROOT, SETTINGS

ENV_PAD = PROJECT_ROOT / ".env"

# Welke keys kun je zetten, met uitleg en waar je ze haalt
BEKENDE_KEYS: dict[str, tuple[str, str]] = {
    "GEMINI_API_KEY": (
        "Gemini — ICP-analyse + bronnen via Google Search grounding",
        "https://aistudio.google.com/apikey",
    ),
    "GOOGLE_CSE_KEY": (
        "Google Programmable Search — echte Google-resultaten",
        "https://developers.google.com/custom-search",
    ),
    "GOOGLE_CSE_CX": (
        "Google Programmable Search — engine-ID (de 'cx')",
        "https://programmablesearchengine.google.com",
    ),
    "GOOGLE_PLACES_API_KEY": (
        "Google Places — lokale NL-bedrijven met telefoon en reviews",
        "https://console.cloud.google.com  (zet 'Places API (New)' aan)",
    ),
    "ANTHROPIC_API_KEY": ("Claude — alternatief voor Gemini", "https://console.anthropic.com"),
    "SERPER_API_KEY": ("Serper — zoekmachine zonder dagquotum", "https://serper.dev"),
    "HUNTER_API_KEY": ("Hunter — domein naar e-mailadressen", "https://hunter.io"),
    "KVK_API_KEY": ("KvK Handelsregister", "https://developers.kvk.nl"),
    "APOLLO_API_KEY": ("Apollo — B2B-contacten op functietitel", "https://apollo.io"),
    "YOUTUBE_API_KEY": ("YouTube Data API", "https://console.cloud.google.com"),
    "ZEROBOUNCE_API_KEY": ("ZeroBounce — e-mailvalidatie", "https://zerobounce.net"),
}


def _lees_env() -> list[str]:
    if not ENV_PAD.exists():
        return []
    return ENV_PAD.read_text(encoding="utf-8-sig").splitlines()


def schrijf_sleutel(naam: str, waarde: str) -> Path:
    """Zet of vervang één regel in .env, met de rest ongemoeid."""
    regels = _lees_env()
    nieuwe_regel = f"{naam}={waarde}"

    vervangen = False
    uit: list[str] = []
    for regel in regels:
        kaal = regel.strip()
        if kaal.startswith(f"{naam}=") or kaal.startswith(f"#{naam}="):
            if not vervangen:
                uit.append(nieuwe_regel)
                vervangen = True
            continue                      # eventuele duplicaten vallen weg
        uit.append(regel)

    if not vervangen:
        if uit and uit[-1].strip():
            uit.append("")
        uit.append(nieuwe_regel)

    # Expliciet LF en geen BOM: python-dotenv struikelt over een BOM.
    ENV_PAD.write_text("\n".join(uit) + "\n", encoding="utf-8", newline="\n")
    return ENV_PAD


def test_gemini(key: str, model: str | None = None) -> tuple[bool, str]:
    """Doe één minimale call om te bevestigen dat de key werkt."""
    model = model or SETTINGS.gemini_model
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                url,
                params={"key": key},
                json={
                    "contents": [{"role": "user", "parts": [{"text": "Antwoord met exact: OK"}]}],
                    "generationConfig": {"maxOutputTokens": 10, "temperature": 0},
                },
            )
    except Exception as fout:
        return False, f"Geen verbinding met Google: {fout}"

    if resp.status_code == 200:
        return True, f"Werkt — model {model} antwoordde."
    if resp.status_code in (400, 401, 403):
        melding = ""
        try:
            melding = (resp.json().get("error") or {}).get("message", "")
        except Exception:
            melding = resp.text[:200]
        if "API_KEY_INVALID" in melding or "not valid" in melding.lower():
            return False, (
                "Google accepteert deze key niet.\n"
                "     Let op: een key uit AI Studio begint met 'AIza'. Begint die van jou\n"
                "     met 'AQ.', dan heb je waarschijnlijk een tijdelijk token in plaats van\n"
                "     een API-key — maak er een aan op https://aistudio.google.com/apikey"
            )
        if "SERVICE_DISABLED" in melding or "has not been used" in melding:
            return False, (
                "De Generative Language API staat uit voor dit project.\n"
                f"     Zet 'm aan in de Google Cloud console. Melding: {melding[:160]}"
            )
        return False, f"Google gaf {resp.status_code}: {melding[:220]}"
    if resp.status_code == 404:
        return False, (
            f"Model '{model}' bestaat niet voor deze key.\n"
            "     Zet een ander model met GEMINI_MODEL, bijv. gemini-2.5-flash."
        )
    if resp.status_code == 429:
        return False, "Quotum bereikt (429). De key zelf is geldig."
    return False, f"Onverwachte status {resp.status_code}: {resp.text[:200]}"


def _vraag_key(console) -> str | None:
    """Vraag de key. Geeft None terug bij annuleren.

    `getpass` leest op Windows rechtstreeks van de console via msvcrt en
    negeert gepipete invoer — in een IDE-terminal of een script blijft het
    dan hangen op toetsaanslagen die nooit komen. Daarom eerst controleren
    of we echt aan een terminal hangen.
    """
    interactief = sys.stdin is not None and sys.stdin.isatty()

    if interactief:
        console.print("\n[dim]Plak je key en druk op Enter. Je typt onzichtbaar — dat is normaal.[/]")
        console.print("[dim]Leeg laten en Enter = annuleren.[/]")
        lees = lambda: getpass.getpass("Key: ")
    else:
        console.print("\n[yellow]Geen terminal gedetecteerd[/] — de key wordt zichtbaar ingelezen.")
        console.print("[dim]Draai dit liever in een gewoon terminalvenster, dan blijft 'ie verborgen.[/]")
        lees = lambda: sys.stdin.readline()

    try:
        waarde = (lees() or "").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[yellow]Geannuleerd.[/]")
        return None

    if not waarde:
        console.print("[yellow]Geannuleerd — niets gewijzigd.[/]")
        return None

    # Aanhalingstekens die per ongeluk zijn meegeplakt
    if len(waarde) > 1 and waarde[0] == waarde[-1] and waarde[0] in "\"'":
        waarde = waarde[1:-1].strip()
    return waarde or None


def zet_sleutel(naam: str, *, console) -> int:
    naam = naam.upper().strip()
    omschrijving, waar = BEKENDE_KEYS.get(naam, ("", ""))

    console.print(f"\n[bold]{naam}[/]")
    if omschrijving:
        console.print(f"[dim]{omschrijving}[/]")
        console.print(f"[dim]Key ophalen: {waar}[/]")

    huidig = os.getenv(naam, "").strip()
    if huidig:
        console.print(f"[dim]Er staat al een waarde (eindigt op …{huidig[-4:]}).[/]")

    waarde = _vraag_key(console)
    if waarde is None:
        return 1

    if naam == "GEMINI_API_KEY":
        console.print("\n[cyan]Key testen bij Google…[/]")
        goed, melding = test_gemini(waarde)
        if goed:
            console.print(f"  [green]✓[/] {melding}")
        else:
            console.print(f"  [red]✗[/] {melding}")
            console.print("\n[yellow]Niet opgeslagen.[/] Los het bovenstaande op en probeer opnieuw.")
            return 1

    pad = schrijf_sleutel(naam, waarde)
    os.environ[naam] = waarde
    setattr(SETTINGS, _veld_voor(naam), waarde)

    console.print(f"\n[green]Opgeslagen[/] in {pad}")
    console.print("[dim].env staat in .gitignore — deze key komt nooit in de repo.[/]")
    console.print("\nControleren met: [bold]python -m leadengine status[/]")
    return 0


def _veld_voor(naam: str) -> str:
    return {
        "GEMINI_API_KEY": "gemini_key",
        "ANTHROPIC_API_KEY": "anthropic_key",
        "SERPER_API_KEY": "serper_key",
        "BRAVE_API_KEY": "brave_key",
        "GOOGLE_CSE_KEY": "google_cse_key",
        "GOOGLE_CSE_CX": "google_cse_cx",
        "GOOGLE_PLACES_API_KEY": "places_key",
        "KVK_API_KEY": "kvk_key",
        "YOUTUBE_API_KEY": "youtube_key",
        "APOLLO_API_KEY": "apollo_key",
        "HUNTER_API_KEY": "hunter_key",
        "ZEROBOUNCE_API_KEY": "zerobounce_key",
    }.get(naam, "_onbekend")


def toon_keys(console) -> None:
    from rich.table import Table

    tabel = Table(title="Keys die je kunt zetten", show_header=True)
    tabel.add_column("Naam")
    tabel.add_column("Waarvoor", max_width=44)
    tabel.add_column("Status", justify="center")
    for naam, (omschrijving, _) in BEKENDE_KEYS.items():
        gezet = bool(os.getenv(naam, "").strip())
        tabel.add_row(naam, omschrijving, "[green]gezet[/]" if gezet else "[dim]leeg[/]")
    console.print(tabel)
    console.print("\nZetten met: [bold]python -m leadengine sleutel GEMINI_API_KEY[/]")
