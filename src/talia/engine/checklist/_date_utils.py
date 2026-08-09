"""Helper condivisi per il confronto tra date estratte da un atto.

Estratti da `check2_termini.py` (TAL-7) quando `check6_firmatari.py` (TAL-53) ha
iniziato a servirsene per calcolare la data dell'annullamento: stessa logica,
un solo posto da mantenere.
"""

from __future__ import annotations

import re
from datetime import date

from ..models import Entita

# Date vicine a riferimenti CCNL non riguardano il procedimento di autotutela.
_RE_CCNL = re.compile(
    r"(CCNL|contratto\s+collettivo|accordo\s+quadro)",
    re.IGNORECASE,
)
# Finestra di esclusione: ±N caratteri dal centro della data.
_FINESTRA_CCNL = 120


def filtra_date_ccnl(date_entita: list[Entita], testo: str) -> list[Entita]:
    """Rimuove date che seguono immediatamente un riferimento CCNL (entro _FINESTRA_CCNL caratteri).

    Il pattern ricorrente è "CCNL del 16.11.2022" o "accordo quadro del 01.03.2021":
    la data appare alla destra del keyword. Filtrare solo in quella direzione evita di
    scartare una data del procedimento che precede il riferimento CCNL nella stessa frase.
    """
    posizioni_ccnl = [m.start() for m in _RE_CCNL.finditer(testo)]
    if not posizioni_ccnl:
        return date_entita
    filtrate = []
    for ent in date_entita:
        # Escludi se un keyword CCNL appare entro _FINESTRA_CCNL caratteri PRIMA della data.
        vicino_ccnl = any(0 <= ent.offset_inizio - pos <= _FINESTRA_CCNL for pos in posizioni_ccnl)
        if not vicino_ccnl:
            filtrate.append(ent)
    return filtrate


def data_estrema(
    date_entita: list[Entita], *, piu_recente: bool
) -> tuple[date | None, Entita | None]:
    """Restituisce l'entità data più recente o più antica e il suo valore."""
    candidate = [e for e in date_entita if isinstance(e.valore, date)]
    if not candidate:
        return None, None
    scelta = (max if piu_recente else min)(candidate, key=lambda e: e.valore)
    return scelta.valore, scelta


__all__ = ["filtra_date_ccnl", "data_estrema"]
