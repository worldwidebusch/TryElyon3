"""De motor: ICP -> bronnen -> oogsten -> valideren -> ontdubbelen -> CSV."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from rich.console import Console
from rich.progress import (
    BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn,
)
from rich.table import Table

from . import connectors, dedupe, enrich, export, icp as icp_mod, relevance, sources
from .config import SETTINGS
from .connectors import apis
from .http import Fetcher
from .models import ICP, Bron, Lead, OOGST_HANDMATIG
from .search import Zoeker

console = Console()


def toon_capabilities() -> None:
    tabel = Table(title="Beschikbare bronnen", show_header=True, header_style="bold")
    tabel.add_column("Onderdeel")
    tabel.add_column("Status", justify="center")
    tabel.add_column("Toelichting", style="dim")
    for naam, (aan, uitleg) in SETTINGS.capabilities().items():
        tabel.add_row(naam, "[green]aan[/]" if aan else "[yellow]uit[/]", uitleg)
    console.print(tabel)
    for tip in SETTINGS.waarschuwingen():
        console.print(f"[yellow]![/] [dim]{tip}[/]")


def toon_icp(icp: ICP) -> None:
    tabel = Table(title="Vastgesteld ICP", show_header=False, box=None)
    tabel.add_row("[bold]Samenvatting[/]", icp.omschrijving)
    for label, waarde in [
        ("Branches", icp.branches),
        ("Functies", icp.functietitels),
        ("Regio's", icp.regios),
        ("Pijnpunten", icp.pijnpunten),
        ("Koopsignalen", icp.koopsignalen),
        ("Verenigingen", icp.branchverenigingen),
        ("Uitsluiten", icp.uitsluiten),
    ]:
        if waarde:
            tabel.add_row(f"[bold]{label}[/]", ", ".join(str(w) for w in waarde))
    if icp.bedrijfsgrootte:
        tabel.add_row("[bold]Grootte[/]", icp.bedrijfsgrootte)
    console.print(tabel)


def toon_bronnen(bronnen: list[Bron]) -> None:
    tabel = Table(title=f"Bronnenlijst ({len(bronnen)} catalyst databases)", show_header=True)
    tabel.add_column("#", justify="right", width=3)
    tabel.add_column("Bron", max_width=42)
    tabel.add_column("Type", max_width=18)
    tabel.add_column("Modus", justify="center")
    tabel.add_column("Pri", justify="center", width=3)
    for i, bron in enumerate(bronnen, 1):
        kleur = {"auto": "green", "api": "cyan", "handmatig": "yellow"}.get(bron.oogstmodus, "white")
        tabel.add_row(str(i), bron.naam, bron.type, f"[{kleur}]{bron.oogstmodus}[/]", str(bron.prioriteit))
    console.print(tabel)


Melder = Callable[[str, dict], None]


def _maak_meld(meld: Melder | None) -> Melder:
    """Voortgangsmeldingen naar buiten. De CLI geeft niets mee, de web-UI wel.

    Een kapotte melder mag een run nooit laten klappen — vandaar het vangnet.
    """
    def _meld(soort: str, data: dict | None = None) -> None:
        if meld is None:
            return
        try:
            meld(soort, data or {})
        except Exception:
            pass
    return _meld


async def draai(
    *,
    omschrijving: str = "",
    website: str = "",
    uitvoermap: Path,
    max_bronnen: int = 40,
    max_bedrijven_per_bron: int = 60,
    max_paginas_per_bron: int = 3,
    max_per_domein: int = 3,
    min_score: int = 0,
    min_relevantie: int = 30,
    gelijktijdige_bronnen: int = 4,
    alleen_bronnen: bool = False,
    valideer_diep: bool = False,
    icp_bestand: Path | None = None,
    meld: Melder | None = None,
) -> None:
    start = datetime.now(timezone.utc)
    _meld = _maak_meld(meld)
    if meld is None:
        toon_capabilities()
    _meld("fase", {"tekst": "ICP bepalen"})

    async with Fetcher() as fetcher:
        zoeker = Zoeker(fetcher)

        # ── 1. ICP ──────────────────────────────────────────────────────────
        if icp_bestand and icp_bestand.exists():
            icp = ICP.from_dict(json.loads(icp_bestand.read_text(encoding="utf-8")))
            console.print(f"[dim]ICP geladen uit {icp_bestand}[/]")
        else:
            with console.status("[cyan]ICP bepalen…[/]"):
                icp = await icp_mod.bepaal_icp(fetcher, omschrijving=omschrijving, website=website)
        toon_icp(icp)
        _meld("icp", {"icp": icp.to_dict()})

        uitvoermap.mkdir(parents=True, exist_ok=True)
        (uitvoermap / "icp.json").write_text(
            json.dumps(icp.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # ── 2. Bronnen ──────────────────────────────────────────────────────
        _meld("fase", {"tekst": "Catalyst databases zoeken"})
        with console.status("[cyan]Catalyst databases zoeken…[/]"):
            bronnenlijst = await sources.ontdek(zoeker, icp, max_bronnen=max_bronnen)
        toon_bronnen(bronnenlijst)
        _meld("bronnen", {"bronnen": [b.to_dict() for b in bronnenlijst]})

        if alleen_bronnen:
            export._schrijf(
                uitvoermap / "bronnen.csv",
                export.BRON_KOLOMMEN,
                [b.to_dict() for b in bronnenlijst],
            )
            console.print(f"\n[green]Bronnenlijst weggeschreven:[/] {uitvoermap / 'bronnen.csv'}")
            _meld("bronnen_klaar", {
                "aantal": len(bronnenlijst),
                "map": str(uitvoermap.resolve()),
                "duur": str(datetime.now(timezone.utc) - start).split(".")[0],
            })
            return

        # ── 3. Oogsten ──────────────────────────────────────────────────────
        te_oogsten = [b for b in bronnenlijst if b.oogstmodus != OOGST_HANDMATIG]
        handmatig = [b for b in bronnenlijst if b.oogstmodus == OOGST_HANDMATIG]

        alle_leads: list[Lead] = []
        sem = asyncio.Semaphore(gelijktijdige_bronnen)
        _meld("fase", {"tekst": f"Oogsten uit {len(te_oogsten)} bronnen"})
        gedaan = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as voortgang:
            taak = voortgang.add_task("Bronnen oogsten", total=len(te_oogsten))

            async def _oogst(bron: Bron) -> list[Lead]:
                async with sem:
                    try:
                        gevonden = await connectors.oogst(
                            fetcher, bron, icp,
                            max_bedrijven=max_bedrijven_per_bron,
                            max_paginas=max_paginas_per_bron,
                        )
                    except Exception as fout:
                        voortgang.console.print(f"  [red]x[/] {bron.naam}: {type(fout).__name__}")
                        gevonden = []
                    kleur = "green" if gevonden else "dim"
                    voortgang.console.print(f"  [{kleur}]•[/] {bron.naam}: {len(gevonden)} ruwe leads")
                    voortgang.advance(taak)
                    nonlocal gedaan
                    gedaan += 1
                    _meld("bron_klaar", {
                        "naam": bron.naam,
                        "type": bron.type,
                        "aantal": len(gevonden),
                        "gedaan": gedaan,
                        "totaal": len(te_oogsten),
                    })
                    return gevonden

            for groep in await asyncio.gather(
                *(_oogst(b) for b in te_oogsten), return_exceptions=True
            ):
                if isinstance(groep, list):
                    alle_leads.extend(groep)

        console.print(f"\n[bold]{len(alle_leads)}[/] ruwe leads geoogst uit {len(te_oogsten)} bronnen.")
        if not alle_leads:
            console.print("[yellow]Niets gevonden. Probeer een bredere ICP of zet een zoek-API-key.[/]")
            _meld("leeg", {"tekst": "Geen leads gevonden. Probeer een bredere ICP of zet een zoek-API-key."})
            return

        _meld("fase", {"tekst": f"{len(alle_leads)} ruwe leads verrijken en valideren"})

        # ── 4. Verrijken & valideren ────────────────────────────────────────
        with console.status("[cyan]Normaliseren…[/]"):
            enrich.normaliseer(alle_leads)

        if SETTINGS.hunter_key:
            with console.status("[cyan]Ontbrekende e-mails aanvullen via Hunter…[/]"):
                aangevuld = await apis.vul_aan_met_hunter(fetcher, alle_leads)
            console.print(f"  Hunter vulde [bold]{aangevuld}[/] e-mailadressen aan.")

        with console.status("[cyan]E-mails controleren (MX + syntax)…[/]"):
            await enrich.controleer_mx(alle_leads)

        if valideer_diep and SETTINGS.zerobounce_key:
            with console.status("[cyan]Diepe e-mailvalidatie (ZeroBounce)…[/]"):
                gecontroleerd = await enrich.valideer_zerobounce(fetcher, alle_leads)
            console.print(f"  ZeroBounce controleerde [bold]{gecontroleerd}[/] adressen.")

        # ── 5. ICP-relevantie, ontdubbelen & scoren ─────────────────────────
        alle_leads, afgewezen = relevance.filter_op_relevantie(
            alle_leads, icp, drempel=min_relevantie
        )
        if afgewezen:
            afgewezen, _ = dedupe.ontdubbel(afgewezen, max_per_domein=1)
            dedupe.scoor(afgewezen)
            export._schrijf(
                uitvoermap / "afgewezen_buiten_icp.csv",
                export.KOLOMMEN,
                [l.to_dict() for l in sorted(afgewezen, key=lambda l: -l.relevantie)],
            )
            console.print(
                f"  [dim]{len(afgewezen)} leads buiten het ICP gefilterd "
                f"(relevantie < {min_relevantie}) -> afgewezen_buiten_icp.csv[/]"
            )

        schoon, statistiek = dedupe.ontdubbel(
            alle_leads, max_per_domein=max_per_domein, icp_uitsluitingen=icp.uitsluiten
        )
        dedupe.scoor(schoon)

        if statistiek:
            tabel = Table(title="Opschoning", show_header=True)
            tabel.add_column("Reden")
            tabel.add_column("Aantal", justify="right")
            for reden, aantal in sorted(statistiek.items(), key=lambda kv: -kv[1]):
                tabel.add_row(reden, str(aantal))
            console.print(tabel)

        # ── 6. Export ───────────────────────────────────────────────────────
        resultaat = export.exporteer(uitvoermap, schoon, bronnenlijst, min_score=min_score)
        _schrijf_avg_notitie(uitvoermap, icp, bronnenlijst, start)
        _schrijf_handmatige_bronnen(uitvoermap, handmatig)

        samenvatting = Table(title="Resultaat", show_header=False, box=None)
        samenvatting.add_row("Leads (na opschoning)", f"[bold green]{resultaat['leads']}[/]")
        samenvatting.add_row("Met e-mail", str(resultaat["met_email"]))
        samenvatting.add_row("Met telefoon", str(resultaat["met_telefoon"]))
        samenvatting.add_row("Segmenten (campagnes)", str(resultaat["segmenten"]))
        samenvatting.add_row("Zoekopdrachten gebruikt", str(zoeker.aantal_queries))
        samenvatting.add_row("Duur", str(datetime.now(timezone.utc) - start).split(".")[0])
        console.print(samenvatting)

        if fetcher.geblokkeerd_door_robots:
            console.print(
                f"[dim]robots.txt blokkeerde {len(fetcher.geblokkeerd_door_robots)} domein(en) "
                f"— overgeslagen.[/]"
            )

        _meld("klaar", {
            "resultaat": resultaat,
            "map": str(uitvoermap.resolve()),
            "duur": str(datetime.now(timezone.utc) - start).split(".")[0],
            "segmenten": _segmentoverzicht(schoon),
        })

        console.print(f"\n[bold green]Klaar.[/] Alles staat in: [bold]{uitvoermap.resolve()}[/]")
        console.print("  • [bold]overzicht.csv[/] — volume per segment (begin hier)")
        console.print("  • [bold]instantly/[/] — direct importeerbaar per campagne")
        console.print("  • [bold]bronnen.csv[/] — je complete bronnenlijst")
        if handmatig:
            console.print("  • [bold]handmatige_bronnen.md[/] — recepten voor LinkedIn/FB/Skool")


def _segmentoverzicht(leads: list[Lead]) -> list[dict]:
    """Per segment de cijfers die de web-UI toont, gesorteerd op omvang."""
    from collections import defaultdict

    per_segment: dict[str, list[Lead]] = defaultdict(list)
    for lead in leads:
        per_segment[lead.segment or lead.bron_naam or "overig"].append(lead)

    uit = []
    for segment, groep in per_segment.items():
        uit.append({
            "segment": segment,
            "bron": groep[0].bron_naam,
            "totaal": len(groep),
            "met_email": sum(1 for l in groep if l.email and l.email_status != "ongeldig"),
            "met_telefoon": sum(1 for l in groep if l.telefoon),
            "persoonlijk": sum(1 for l in groep if l.email_type == "persoonlijk"),
            "gem_score": round(sum(l.score for l in groep) / len(groep)),
            "bestand": f"segmenten/{export._veilige_naam(segment)}.csv",
            "instantly": f"instantly/{export._veilige_naam(segment)}.csv",
        })
    return sorted(uit, key=lambda s: -s["totaal"])


def _schrijf_avg_notitie(map_pad: Path, icp: ICP, bronnen: list[Bron], start: datetime) -> None:
    tekst = f"""# Verwerkingsnotitie (AVG art. 30)

Bewaar dit bij je leadbestand. Als iemand bezwaar maakt of de AP vraagt ernaar,
heb je hiermee je verhaal op orde.

- **Datum verzameling:** {start.astimezone().strftime('%d-%m-%Y %H:%M')}
- **Doel:** zakelijke acquisitie (B2B) op de Nederlandse markt
- **ICP:** {icp.omschrijving}
- **Grondslag:** gerechtvaardigd belang (art. 6 lid 1 sub f AVG) — direct
  marketing richting zakelijke contactpersonen in hun beroepsrol
- **Herkomst:** uitsluitend openbaar toegankelijke zakelijke bronnen
  ({len(bronnen)} bronnen, zie `bronnen.csv`)
- **Categorieën:** zakelijke contactgegevens (naam, functie, zakelijk e-mailadres,
  zakelijk telefoonnummer, bedrijfsgegevens). Geen bijzondere persoonsgegevens.
- **Bewaartermijn:** verwijder leads die niet reageren binnen 12 maanden.

## Wat je vóór de eerste mail moet regelen
1. **Afmeldlink in elke mail.** Verplicht (art. 11.7 Telecommunicatiewet).
   Eén klik, geen inlog.
2. **Identificeer je afzender.** Bedrijfsnaam, adres en KvK-nummer in de voettekst.
3. **Verwerk afmeldingen direct** in `uitsluitlijst.txt` in deze map — de motor
   filtert die bij elke volgende run automatisch weg.
4. **Geen privé-adressen.** Rijen met gmail.com/hotmail.nl e.d. zijn vaker
   privépersonen dan bedrijven: controleer die apart of laat ze staan.
5. **Bel-je-niet:** ga je bellen, controleer zakelijke nummers eerst tegen het
   Bel-me-niet-register waar dat van toepassing is.

## Wat deze tool bewust NIET doet
Geen geautomatiseerd scrapen van LinkedIn, Facebook, Instagram, Discord of Skool.
Dat schendt hun voorwaarden en levert persoonsgegevens op die niet als zakelijk
contactgegeven bedoeld zijn. Die bronnen staan wel op je bronnenlijst, met een
handmatig recept dat wél binnen de regels blijft.
"""
    (map_pad / "AVG_verwerkingsnotitie.md").write_text(tekst, encoding="utf-8")


def _schrijf_handmatige_bronnen(map_pad: Path, bronnen: list[Bron]) -> None:
    if not bronnen:
        return
    regels = [
        "# Handmatige bronnen\n",
        "Deze platforms staan geautomatiseerd oogsten niet toe. Hieronder per bron",
        "de route die wél werkt. Wat je oplevert kun je terugvoeren met:\n",
        "```bash\npython -m leadengine importeer mijn_lijst.csv --uit uitvoer/run\n```\n",
    ]
    for bron in bronnen:
        regels.append(f"\n## {bron.naam}")
        regels.append(f"- **Type:** {bron.type}")
        if bron.url:
            regels.append(f"- **URL:** {bron.url}")
        if bron.signaal:
            regels.append(f"- **Waarom relevant:** {bron.signaal}")
        if bron.aanpak:
            regels.append(f"\n{bron.aanpak.strip()}")
    (map_pad / "handmatige_bronnen.md").write_text("\n".join(regels) + "\n", encoding="utf-8")


async def draai_import(
    *,
    csv_pad: Path,
    uitvoermap: Path,
    bron_naam: str,
    max_per_domein: int = 3,
) -> None:
    """Voer een handmatig samengestelde lijst bedrijven in en verrijk die."""
    ruwe = export.lees_csv_leads(csv_pad, bron_naam=bron_naam)
    if not ruwe:
        console.print("[red]Geen bruikbare rijen gevonden (verwacht een kolom website/domein/bedrijfsnaam).[/]")
        return
    console.print(f"[cyan]{len(ruwe)} rijen ingelezen uit {csv_pad.name}[/]")

    bron = Bron(naam=bron_naam, type="handmatige import", segment=bron_naam, connector="website")
    gevonden: list[Lead] = list(ruwe)

    async with Fetcher() as fetcher:
        doelen = [l for l in ruwe if l.website]
        sem = asyncio.Semaphore(SETTINGS.max_concurrency)

        async def _site(lead: Lead) -> list[Lead]:
            async with sem:
                try:
                    return await connectors.oogst_domein(fetcher, lead.website, bron)
                except Exception:
                    return []

        with console.status(f"[cyan]{len(doelen)} websites verrijken…[/]"):
            for groep in await asyncio.gather(*(_site(l) for l in doelen), return_exceptions=True):
                if isinstance(groep, list):
                    gevonden.extend(groep)

        enrich.normaliseer(gevonden)
        if SETTINGS.hunter_key:
            await apis.vul_aan_met_hunter(fetcher, gevonden)
        await enrich.controleer_mx(gevonden)

    schoon, _ = dedupe.ontdubbel(gevonden, max_per_domein=max_per_domein)
    dedupe.scoor(schoon)
    resultaat = export.exporteer(uitvoermap, schoon, [bron])
    console.print(
        f"[green]{resultaat['leads']} leads[/] ({resultaat['met_email']} met e-mail) "
        f"-> {uitvoermap.resolve()}"
    )
