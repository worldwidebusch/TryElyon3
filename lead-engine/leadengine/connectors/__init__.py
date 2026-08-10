"""Connector-register en dispatch."""

from __future__ import annotations

from ..http import Fetcher
from ..models import Bron, ICP, Lead, OOGST_HANDMATIG
from . import apis
from .listing import oogst_lijst
from .website import oogst_domein

__all__ = ["oogst", "oogst_domein", "oogst_lijst", "apis"]


async def oogst(
    fetcher: Fetcher,
    bron: Bron,
    icp: ICP,
    *,
    max_bedrijven: int = 60,
    max_paginas: int = 3,
) -> list[Lead]:
    """Voer één bron uit met de juiste connector."""
    if bron.oogstmodus == OOGST_HANDMATIG:
        return []

    if bron.connector == "google_places":
        return await apis.oogst_places(fetcher, bron, icp)
    if bron.connector == "kvk":
        return await apis.oogst_kvk(fetcher, bron, icp)
    if bron.connector == "youtube":
        return await apis.oogst_youtube(fetcher, bron, icp)
    if bron.connector == "apollo":
        return await apis.oogst_apollo(fetcher, bron, icp)
    if bron.connector == "podcast":
        return await apis.oogst_podcasts(fetcher, bron, icp)
    if bron.connector == "hunter":
        return []          # Hunter draait als verrijkingsstap, niet als bron
    if bron.connector == "website":
        return await oogst_domein(fetcher, bron.url, bron)
    return await oogst_lijst(
        fetcher, bron, max_bedrijven=max_bedrijven, max_paginas=max_paginas
    )
