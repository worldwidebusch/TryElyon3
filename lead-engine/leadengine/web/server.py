"""Lokale web-interface.

Draait op je eigen machine (localhost). Er gaat niets naar buiten behalve de
API-aanroepen die de motor sowieso al doet, en je keys blijven in .env staan.

Starten:  python -m leadengine web
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel

from .. import setup as key_setup
from ..config import PROJECT_ROOT, SETTINGS
from ..pipeline import draai

STATIC = Path(__file__).resolve().parent / "static"
UITVOER = PROJECT_ROOT / "uitvoer"

app = FastAPI(title="lead-engine")


# ── Runregistratie ──────────────────────────────────────────────────────────

@dataclass
class Run:
    id: str
    label: str
    map_pad: Path
    gestart: str
    status: str = "bezig"              # bezig | klaar | mislukt | leeg
    gebeurtenissen: list[dict] = field(default_factory=list)
    abonnees: list[asyncio.Queue] = field(default_factory=list)
    taak: asyncio.Task | None = None

    def zend(self, soort: str, data: dict) -> None:
        gebeurtenis = {"soort": soort, "data": data}
        self.gebeurtenissen.append(gebeurtenis)
        for wachtrij in list(self.abonnees):
            try:
                wachtrij.put_nowait(gebeurtenis)
            except Exception:
                pass


RUNS: dict[str, Run] = {}


class StartVerzoek(BaseModel):
    icp: str = ""
    website: str = ""
    max_bronnen: int = 40
    max_bedrijven: int = 60
    max_paginas: int = 3
    max_per_domein: int = 3
    min_relevantie: int = 30
    alleen_bronnen: bool = False


class KeyVerzoek(BaseModel):
    naam: str
    waarde: str


def _veilig_label(tekst: str) -> str:
    schoon = re.sub(r"[^\w\- ]+", "", tekst).strip().replace(" ", "-").lower()
    return schoon[:40] or "run"


# ── Pagina ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return (STATIC / "index.html").read_text(encoding="utf-8")


# ── Status en keys ──────────────────────────────────────────────────────────

@app.get("/api/status")
async def status() -> dict:
    return {
        "capabilities": [
            {"naam": naam, "aan": aan, "uitleg": uitleg}
            for naam, (aan, uitleg) in SETTINGS.capabilities().items()
        ],
        "waarschuwingen": SETTINGS.waarschuwingen(),
        "keys": [
            {
                "naam": naam,
                "omschrijving": omschrijving,
                "waar": waar,
                "gezet": bool(getattr(SETTINGS, key_setup._veld_voor(naam), "")),
            }
            for naam, (omschrijving, waar) in key_setup.BEKENDE_KEYS.items()
        ],
    }


@app.post("/api/key")
async def zet_key(verzoek: KeyVerzoek) -> dict:
    naam = verzoek.naam.upper().strip()
    if naam not in key_setup.BEKENDE_KEYS:
        raise HTTPException(400, f"Onbekende key: {naam}")

    waarde = key_setup._schoon_key(verzoek.waarde)
    if not waarde:
        raise HTTPException(400, "Lege waarde.")

    lus = asyncio.get_running_loop()
    model = ""
    if naam == "GEMINI_API_KEY":
        beschikbaar, fout = await lus.run_in_executor(None, key_setup.lijst_modellen, waarde)
        if fout:
            return {"ok": False, "melding": fout}
        if not beschikbaar:
            return {"ok": False, "melding": "Deze key heeft geen bruikbare modellen."}
        for kandidaat in key_setup._kandidaten(beschikbaar):
            gelukt, melding, versie = await lus.run_in_executor(
                None, key_setup.test_gemini, waarde, kandidaat
            )
            if gelukt:
                model = kandidaat
                key_setup.schrijf_sleutel("GEMINI_MODEL", kandidaat)
                SETTINGS.gemini_model = kandidaat
                if versie != SETTINGS.gemini_api_version:
                    key_setup.schrijf_sleutel("GEMINI_API_VERSION", versie)
                    SETTINGS.gemini_api_version = versie
                break
        if not model:
            return {"ok": False, "melding": "Geen enkel model reageerde op generateContent."}

    key_setup.schrijf_sleutel(naam, waarde)
    setattr(SETTINGS, key_setup._veld_voor(naam), waarde)
    melding = f"{naam} opgeslagen."
    if model:
        melding += f" Model: {model}."
    return {"ok": True, "melding": melding}


# ── Runs ────────────────────────────────────────────────────────────────────

@app.post("/api/run")
async def start_run(verzoek: StartVerzoek) -> dict:
    if not verzoek.icp.strip() and not verzoek.website.strip():
        raise HTTPException(400, "Geef een ICP-omschrijving of een website op.")

    run_id = uuid.uuid4().hex[:12]
    label = _veilig_label(verzoek.icp or verzoek.website)
    map_pad = UITVOER / f"{datetime.now().strftime('%Y%m%d-%H%M')}_{label}"

    run = Run(
        id=run_id,
        label=verzoek.icp or verzoek.website,
        map_pad=map_pad,
        gestart=datetime.now().isoformat(timespec="seconds"),
    )
    RUNS[run_id] = run

    async def _draai() -> None:
        try:
            await draai(
                omschrijving=verzoek.icp,
                website=verzoek.website,
                uitvoermap=map_pad,
                max_bronnen=verzoek.max_bronnen,
                max_bedrijven_per_bron=verzoek.max_bedrijven,
                max_paginas_per_bron=verzoek.max_paginas,
                max_per_domein=verzoek.max_per_domein,
                min_relevantie=verzoek.min_relevantie,
                alleen_bronnen=verzoek.alleen_bronnen,
                meld=run.zend,
            )
            if run.status == "bezig":
                afgerond = {"klaar", "bronnen_klaar"}
                run.status = "klaar" if any(
                    g["soort"] in afgerond for g in run.gebeurtenissen
                ) else "leeg"
        except asyncio.CancelledError:
            run.status = "mislukt"
            run.zend("fout", {"tekst": "Run afgebroken."})
            raise
        except Exception as fout:
            run.status = "mislukt"
            run.zend("fout", {"tekst": f"{type(fout).__name__}: {fout}"})
        finally:
            run.zend("einde", {"status": run.status})

    run.taak = asyncio.create_task(_draai())
    return {"run_id": run_id}


@app.post("/api/run/{run_id}/stop")
async def stop_run(run_id: str) -> dict:
    run = RUNS.get(run_id)
    if not run:
        raise HTTPException(404, "Run niet gevonden.")
    if run.taak and not run.taak.done():
        run.taak.cancel()
    return {"ok": True}


@app.get("/api/run/{run_id}/stream")
async def stream(run_id: str) -> StreamingResponse:
    run = RUNS.get(run_id)
    if not run:
        raise HTTPException(404, "Run niet gevonden.")

    wachtrij: asyncio.Queue = asyncio.Queue()
    run.abonnees.append(wachtrij)

    async def _gebeurtenissen():
        # Eerst alles wat al gebeurd is, zodat een herladen tabblad niets mist.
        for gebeurtenis in list(run.gebeurtenissen):
            yield f"data: {json.dumps(gebeurtenis, ensure_ascii=False)}\n\n"
        if run.status != "bezig":
            yield f"data: {json.dumps({'soort': 'einde', 'data': {'status': run.status}})}\n\n"
            return
        try:
            while True:
                try:
                    gebeurtenis = await asyncio.wait_for(wachtrij.get(), timeout=20.0)
                except asyncio.TimeoutError:
                    yield ": ping\n\n"          # verbinding openhouden
                    continue
                yield f"data: {json.dumps(gebeurtenis, ensure_ascii=False)}\n\n"
                if gebeurtenis["soort"] == "einde":
                    return
        finally:
            if wachtrij in run.abonnees:
                run.abonnees.remove(wachtrij)

    return StreamingResponse(
        _gebeurtenissen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/runs")
async def lijst_runs() -> list[dict]:
    """Eerdere runs uit de uitvoermap, ook die van vóór deze serverstart."""
    uit = []
    if UITVOER.exists():
        for map_pad in sorted(UITVOER.iterdir(), reverse=True):
            if not map_pad.is_dir():
                continue
            volledig = (map_pad / "overzicht.csv").exists()
            # Een 'alleen bronnen'-run heeft geen overzicht.csv maar is wel een run.
            if not volledig and not (map_pad / "bronnen.csv").exists():
                continue
            uit.append({
                "naam": map_pad.name,
                "pad": str(map_pad),
                "bestanden": len(list(map_pad.rglob("*.csv"))),
                "volledig": volledig,
            })
    return uit[:40]


@app.get("/api/bestand/{map_naam}/{bestand:path}")
async def download(map_naam: str, bestand: str) -> FileResponse:
    doel = (UITVOER / map_naam / bestand).resolve()
    # Padtraversal blokkeren: alles moet binnen de uitvoermap blijven.
    if not str(doel).startswith(str(UITVOER.resolve())) or not doel.is_file():
        raise HTTPException(404, "Bestand niet gevonden.")
    return FileResponse(doel, filename=doel.name)


def start(host: str = "127.0.0.1", poort: int = 8100, open_browser: bool = True) -> None:
    import uvicorn

    if open_browser:
        import threading
        import webbrowser

        threading.Timer(1.2, lambda: webbrowser.open(f"http://{host}:{poort}")).start()

    uvicorn.run(app, host=host, port=poort, log_level="warning")
