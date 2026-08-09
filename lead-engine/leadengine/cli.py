"""CLI — Nederlandse leadmotor.

    python -m leadengine zoek --icp "tandartspraktijken in de Randstad"
    python -m leadengine zoek --website https://tryelyon.com
    python -m leadengine bronnen --icp "..."           (alleen de bronnenlijst)
    python -m leadengine importeer lijst.csv
    python -m leadengine status
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from datetime import datetime
from pathlib import Path

from .config import PROJECT_ROOT
from .pipeline import console, draai, draai_import, toon_capabilities


def _forceer_utf8_uitvoer() -> None:
    """Zet stdout/stderr op UTF-8.

    Een oudere Windows-console draait op cp1252; daar crasht het schrijven van
    tekens als ✓ of → met een UnicodeEncodeError midden in een run. Met
    errors='replace' gaat er in het ergste geval één teken verloren in plaats
    van dat de hele run klapt.
    """
    for stroom in (sys.stdout, sys.stderr):
        try:
            stroom.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_forceer_utf8_uitvoer()


def _standaard_map(label: str) -> Path:
    stempel = datetime.now().strftime("%Y%m%d-%H%M")
    schoon = re.sub(r"[^\w\-]+", "-", label.lower()).strip("-")[:40] or "run"
    return PROJECT_ROOT / "uitvoer" / f"{stempel}_{schoon}"


def bouw_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="leadengine",
        description="Vindt waar je ideale klant online samenkomt en oogst daar leads. NL-markt.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""voorbeelden:
  python -m leadengine zoek --icp "installatiebedrijven met 5-30 man in Noord-Brabant"
  python -m leadengine zoek --website https://tryelyon.com --max-bronnen 25
  python -m leadengine bronnen --icp "tandartspraktijken Randstad"
  python -m leadengine importeer sales-navigator-export.csv --bron "LinkedIn SN"
  python -m leadengine status
""",
    )
    sub = parser.add_subparsers(dest="commando", required=True)

    # ── zoek ────────────────────────────────────────────────────────────────
    zoek = sub.add_parser("zoek", help="volledige run: ICP -> bronnen -> leads -> CSV")
    doel = zoek.add_mutually_exclusive_group(required=True)
    doel.add_argument("--icp", metavar="TEKST", help="beschrijf je ideale klant in gewoon Nederlands")
    doel.add_argument("--website", metavar="URL", help="leid het ICP af uit een bestaande website")
    zoek.add_argument("--uit", type=Path, help="uitvoermap (standaard: uitvoer/<datum>_<label>)")
    zoek.add_argument("--icp-bestand", type=Path, help="hergebruik een eerder icp.json")
    zoek.add_argument("--max-bronnen", type=int, default=40, help="max aantal bronnen (40)")
    zoek.add_argument("--max-bedrijven", type=int, default=60, help="max bedrijven per bron (60)")
    zoek.add_argument("--max-paginas", type=int, default=3, help="paginering per lijstbron (3)")
    zoek.add_argument("--max-per-domein", type=int, default=3, help="max leads per bedrijf (3)")
    zoek.add_argument("--min-score", type=int, default=0, help="filter leads onder deze score (0)")
    zoek.add_argument("--min-relevantie", type=int, default=30,
                      help="ICP-relevantiedrempel 0-100 (30). Hoger = strenger, minder ruis.")
    zoek.add_argument("--gelijktijdig", type=int, default=4, help="bronnen tegelijk (4)")
    zoek.add_argument("--diep-valideren", action="store_true", help="ZeroBounce-validatie (kost credits)")

    # ── bronnen ─────────────────────────────────────────────────────────────
    bronnen = sub.add_parser("bronnen", help="alleen de bronnenlijst, nog niet oogsten")
    doel_b = bronnen.add_mutually_exclusive_group(required=True)
    doel_b.add_argument("--icp", metavar="TEKST")
    doel_b.add_argument("--website", metavar="URL")
    bronnen.add_argument("--uit", type=Path)
    bronnen.add_argument("--max-bronnen", type=int, default=60)

    # ── importeer ───────────────────────────────────────────────────────────
    imp = sub.add_parser("importeer", help="verrijk een eigen CSV met bedrijven")
    imp.add_argument("bestand", type=Path, help="CSV met kolom website/domein/bedrijfsnaam")
    imp.add_argument("--bron", default="Handmatige import", help="bronlabel voor deze lijst")
    imp.add_argument("--uit", type=Path)
    imp.add_argument("--max-per-domein", type=int, default=3)

    sub.add_parser("status", help="laat zien welke bronnen aanstaan op basis van je keys")

    # ── sleutel ─────────────────────────────────────────────────────────────
    sleutel = sub.add_parser(
        "sleutel",
        help="API-key instellen zonder .env met de hand te bewerken",
    )
    sleutel.add_argument(
        "naam", nargs="?",
        help="bijv. GEMINI_API_KEY. Laat leeg voor een overzicht van alle keys.",
    )
    sleutel.add_argument("--test", action="store_true",
                         help="test alleen de huidige GEMINI_API_KEY, wijzig niets")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = bouw_parser().parse_args(argv)

    if args.commando == "status":
        toon_capabilities()
        console.print(
            "\n[dim]Key instellen? [/][bold]python -m leadengine sleutel GEMINI_API_KEY[/]"
        )
        return 0

    if args.commando == "sleutel":
        from . import setup

        if args.test:
            from .config import SETTINGS

            if not SETTINGS.gemini_key:
                console.print("[yellow]Geen GEMINI_API_KEY gevonden om te testen.[/]")
                return 1
            goed, melding = setup.test_gemini(SETTINGS.gemini_key)
            console.print(f"  {'[green]✓[/]' if goed else '[red]✗[/]'} {melding}")
            return 0 if goed else 1

        if not args.naam:
            setup.toon_keys(console)
            return 0
        return setup.zet_sleutel(args.naam, console=console)

    if args.commando == "importeer":
        if not args.bestand.exists():
            console.print(f"[red]Bestand niet gevonden:[/] {args.bestand}")
            return 1
        uit = args.uit or _standaard_map(args.bron)
        asyncio.run(draai_import(
            csv_pad=args.bestand,
            uitvoermap=uit,
            bron_naam=args.bron,
            max_per_domein=args.max_per_domein,
        ))
        return 0

    label = args.icp or args.website or "run"
    uit = args.uit or _standaard_map(label)

    asyncio.run(draai(
        omschrijving=args.icp or "",
        website=args.website or "",
        uitvoermap=uit,
        max_bronnen=args.max_bronnen,
        max_bedrijven_per_bron=getattr(args, "max_bedrijven", 60),
        max_paginas_per_bron=getattr(args, "max_paginas", 3),
        max_per_domein=getattr(args, "max_per_domein", 3),
        min_score=getattr(args, "min_score", 0),
        min_relevantie=getattr(args, "min_relevantie", 30),
        gelijktijdige_bronnen=getattr(args, "gelijktijdig", 4),
        alleen_bronnen=(args.commando == "bronnen"),
        valideer_diep=getattr(args, "diep_valideren", False),
        icp_bestand=getattr(args, "icp_bestand", None),
    ))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Afgebroken.[/]")
        sys.exit(130)
