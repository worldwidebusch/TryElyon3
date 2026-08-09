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
    "GEMINI_MODEL": (
        "Welk Gemini-model — laat leeg voor automatisch",
        "python -m leadengine sleutel --modellen  (toont wat jouw key heeft)",
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


# Welk model pakken we als de gebruiker niets kiest? Eerste match wint.
VOORKEUR_MODELLEN = [
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-2.0-flash-001",
    "gemini-pro-latest",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]


def lijst_modellen(key: str) -> tuple[list[str], str]:
    """(modellen die generateContent ondersteunen, foutmelding).

    Dit valideert de key én vertelt welke modellen er voor déze key bestaan —
    dat verschilt per account, regio en of het een gratis of betaald project is.
    """
    modellen: list[str] = []
    token = ""
    try:
        with httpx.Client(timeout=30.0) as client:
            for _ in range(5):                      # paginering, ruim genoeg
                params = {"key": key, "pageSize": 200}
                if token:
                    params["pageToken"] = token
                resp = client.get(
                    "https://generativelanguage.googleapis.com/v1beta/models",
                    params=params,
                )
                if resp.status_code != 200:
                    return [], _uitleg_fout(resp)
                data = resp.json()
                for model in data.get("models", []) or []:
                    if "generateContent" in (model.get("supportedGenerationMethods") or []):
                        modellen.append(str(model.get("name", "")).removeprefix("models/"))
                token = data.get("nextPageToken", "")
                if not token:
                    break
    except Exception as fout:
        return [], f"Geen verbinding met Google: {fout}"
    return modellen, ""


def kies_model(beschikbaar: list[str]) -> str:
    """Beste bruikbare model uit wat deze key aanbiedt."""
    for voorkeur in VOORKEUR_MODELLEN:
        if voorkeur in beschikbaar:
            return voorkeur
    # Geen bekende naam: pak een flash-variant, anders het eerste gewone model
    for model in beschikbaar:
        if "flash" in model and "thinking" not in model and "image" not in model:
            return model
    gewoon = [
        m for m in beschikbaar
        if not any(w in m for w in ("embedding", "aqa", "image", "vision", "tts", "learnlm"))
    ]
    return gewoon[0] if gewoon else (beschikbaar[0] if beschikbaar else "")


def _uitleg_fout(resp: httpx.Response) -> str:
    try:
        melding = (resp.json().get("error") or {}).get("message", "")
    except Exception:
        melding = resp.text[:200]
    return _uitleg(resp.status_code, melding)


def _uitleg(status: int, melding: str, *, model: str = "") -> str:
    """Zet een Google-fout om in iets waar je wat mee kunt."""
    if status == 0:
        return melding or "Geen verbinding met Google."

    if status == 404:
        kern = (
            f"Model '{model}' is niet bereikbaar via generateContent."
            if model else "Endpoint niet gevonden."
        )
        return f"{kern}\n     Google zei: {melding[:200]}"

    if status in (400, 401, 403):
        if "API_KEY_INVALID" in melding or "not valid" in melding.lower():
            return (
                "Google accepteert deze key niet.\n"
                "     Een key uit AI Studio begint met 'AIza'. Begint die van jou met\n"
                "     'AQ.', dan is het een tijdelijk token in plaats van een API-key —\n"
                "     maak er een aan op https://aistudio.google.com/apikey"
            )
        if "SERVICE_DISABLED" in melding or "has not been used" in melding:
            return (
                "De Generative Language API staat uit voor dit project.\n"
                f"     Zet 'm aan in de Google Cloud console. Melding: {melding[:160]}"
            )
        if "location is not supported" in melding.lower():
            return "Gemini is niet beschikbaar in de regio van dit project."
        return f"Google gaf {status}: {melding[:220]}"
    if status == 429:
        return "Quotum bereikt (429). De key zelf is geldig — probeer het later opnieuw."
    return f"Onverwachte status {status}: {melding[:200]}"


API_VERSIES = ("v1beta", "v1")


def _probeer_generate(key: str, model: str, versie: str) -> tuple[bool, int, str]:
    """Eén generateContent-poging. Geeft (gelukt, statuscode, ruwe melding)."""
    url = f"https://generativelanguage.googleapis.com/{versie}/models/{model}:generateContent"
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            resp = client.post(
                url,
                params={"key": key},
                json={
                    "contents": [{"role": "user", "parts": [{"text": "Antwoord met exact: OK"}]}],
                    "generationConfig": {"maxOutputTokens": 512, "temperature": 0},
                },
            )
    except Exception as fout:
        return False, 0, f"Geen verbinding met Google: {fout}"

    if resp.status_code == 200:
        return True, 200, ""
    try:
        melding = (resp.json().get("error") or {}).get("message", "") or resp.text[:300]
    except Exception:
        melding = resp.text[:300]
    return False, resp.status_code, melding


def test_gemini(
    key: str,
    model: str | None = None,
    *,
    versies: tuple[str, ...] = API_VERSIES,
) -> tuple[bool, str, str]:
    """Test één model. Geeft (gelukt, melding, werkende_api_versie).

    Probeert beide API-versies: welke werkt hangt af van het model en het
    account, en een 404 op v1beta betekent niet dat v1 ook faalt.
    """
    model = model or SETTINGS.gemini_model
    laatste_status, laatste_melding = 0, "Niet geprobeerd."
    for versie in versies:
        gelukt, status, melding = _probeer_generate(key, model, versie)
        if gelukt:
            return True, f"Werkt — {model} via {versie}.", versie
        laatste_status, laatste_melding = status, melding
        if status == 0:
            break                          # netwerkfout: andere versie helpt niet
        if status in (400, 401, 403) and (
            "API_KEY_INVALID" in melding or "not valid" in melding.lower()
        ):
            break                          # key zelf is fout
    return False, _uitleg(laatste_status, laatste_melding, model=model), ""


def _kandidaten(beschikbaar: list[str], *, hoeveel: int = 6) -> list[str]:
    """Modellen om te proberen, beste eerst.

    Dat de modellenlijst een model noemt betekent niet dat generateContent er
    ook echt mee werkt: dat verschilt per account en per API-versie. Dus
    proberen we er een paar, in plaats van bij de eerste teleurstelling te stoppen.
    """
    ongeschikt = ("embedding", "aqa", "-tts", "image", "vision", "learnlm", "veo", "imagen")
    schoon = [m for m in beschikbaar if not any(w in m for w in ongeschikt)]

    volgorde = [m for m in VOORKEUR_MODELLEN if m in schoon]
    volgorde += [m for m in schoon if m not in volgorde and "preview" not in m and "exp" not in m]
    volgorde += [m for m in schoon if m not in volgorde]
    return volgorde[:hoeveel]


def _eerste_werkende_model(
    key: str, beschikbaar: list[str], *, console
) -> tuple[str, str, list[str]]:
    """Probeer kandidaten tot er één antwoordt. (model, api_versie, fouten)."""
    fouten: list[str] = []
    for model in _kandidaten(beschikbaar):
        console.print(f"[cyan]Testen met {model}…[/]")
        gelukt, melding, versie = test_gemini(key, model)
        if gelukt:
            console.print(f"  [green]v[/] {melding}")
            return model, versie, fouten
        console.print(f"  [dim]x {model}: {melding[:150]}[/]")
        fouten.append(f"{model} -> {melding[:200]}")
    return "", "", fouten


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

    return _schoon_key(waarde) or None


# Onzichtbare tekens die meeliften bij kopiëren uit een browser, PDF of terminal.
# Eén BOM vooraan maakt je key ongeldig zonder dat je iets ziet — een klassieke
# oorzaak van "mijn key werkt niet, maar hij ziet er goed uit".
_ONZICHTBAAR = dict.fromkeys(
    [0xFEFF, 0x200B, 0x200C, 0x200D, 0x2060, 0x00A0, 0x180E, 0x061C] +
    list(range(0x200E, 0x2010)) + list(range(0x202A, 0x202F)),
    None,
)


def _schoon_key(waarde: str) -> str:
    waarde = waarde.translate(_ONZICHTBAAR).strip()
    # Aanhalingstekens die per ongeluk zijn meegeplakt
    if len(waarde) > 1 and waarde[0] == waarde[-1] and waarde[0] in "\"'":
        waarde = waarde[1:-1].strip()
    # Mensen plakken soms 'GEMINI_API_KEY=AIza...' in z'n geheel
    for prefix in ("GEMINI_API_KEY=", "GOOGLE_API_KEY=", "key=", "Bearer "):
        if waarde.startswith(prefix):
            waarde = waarde[len(prefix):].strip()
    return waarde


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

    gekozen_model = ""
    gekozen_versie = ""
    if naam == "GEMINI_API_KEY":
        if not waarde.startswith("AIza"):
            console.print(
                f"\n[yellow]Let op:[/] deze waarde begint met '{waarde[:3]}…', niet met 'AIza'."
            )
            console.print(
                "[dim]API-keys uit AI Studio beginnen altijd met 'AIza'. Een waarde die met\n"
                "'AQ.' begint is een tijdelijk token voor de Live API: die authenticeert wel,\n"
                "maar mag generateContent niet aanroepen — precies de aanroep die wij doen.\n"
                "Ik probeer het toch, maar houd hier rekening mee als het misgaat.[/]"
            )

        console.print("\n[cyan]Key controleren en beschikbare modellen opvragen…[/]")
        beschikbaar, fout = lijst_modellen(waarde)
        if fout:
            console.print(f"  [red]x[/] {fout}")
            console.print("\n[yellow]Niet opgeslagen.[/] Los het bovenstaande op en probeer opnieuw.")
            return 1
        if not beschikbaar:
            console.print("  [red]x[/] Deze key heeft geen modellen die generateContent ondersteunen.")
            return 1
        console.print(f"  [green]v[/] Key geldig — {len(beschikbaar)} model(len) beschikbaar.")

        gekozen_model, gekozen_versie, fouten = _eerste_werkende_model(
            waarde, beschikbaar, console=console
        )
        if not gekozen_model:
            console.print("\n[red]Geen enkel model reageerde op generateContent.[/]")
            if not waarde.startswith("AIza"):
                console.print(
                    "\n[bold]Dit is vrijwel zeker het probleem:[/] je gebruikt geen API-key.\n"
                    "De lijst met modellen ophalen lukte (dus je token is echt), maar tekst\n"
                    "genereren mag ermee niet. Dat is precies hoe een tijdelijk Live-API-token\n"
                    "zich gedraagt.\n"
                )
                console.print(
                    "Haal een echte API-key op — die begint met 'AIza':\n"
                    "  [bold]https://aistudio.google.com/apikey[/]\n"
                    "  Klik op [bold]Create API key[/], niet op iets met 'token' of 'ephemeral'."
                )
            console.print("\n[dim]Wat Google per model terugstuurde:[/]")
            for regel in fouten:
                console.print(f"  [dim]{regel}[/]")
            console.print("\n[yellow]Niet opgeslagen.[/]")
            return 1

    pad = schrijf_sleutel(naam, waarde)
    if gekozen_model:
        schrijf_sleutel("GEMINI_MODEL", gekozen_model)
        os.environ["GEMINI_MODEL"] = gekozen_model
        SETTINGS.gemini_model = gekozen_model
        if gekozen_versie and gekozen_versie != SETTINGS.gemini_api_version:
            schrijf_sleutel("GEMINI_API_VERSION", gekozen_versie)
            os.environ["GEMINI_API_VERSION"] = gekozen_versie
            SETTINGS.gemini_api_version = gekozen_versie
            console.print(f"[dim]API-versie op {gekozen_versie} gezet.[/]")
    os.environ[naam] = waarde
    setattr(SETTINGS, _veld_voor(naam), waarde)

    console.print(f"\n[green]Opgeslagen[/] in {pad}")
    console.print("[dim].env staat in .gitignore — deze key komt nooit in de repo.[/]")
    console.print("\nControleren met: [bold]python -m leadengine status[/]")
    return 0


def _veld_voor(naam: str) -> str:
    return {
        "GEMINI_API_KEY": "gemini_key",
        "GEMINI_MODEL": "gemini_model",
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
