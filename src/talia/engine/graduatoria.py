"""TAL-53 — Individuazione della data di approvazione della graduatoria.

Serve al check 6 (coerenza firmatari) per incrociare la sovrapposizione dei
firmatari con la tempistica: un annullamento a ridosso dell'approvazione della
graduatoria è un segnale più forte di uno distante nel tempo.

Euristica deterministica, non normativa: cerca una data vicina a una menzione
di "graduatoria" **in cui compare anche "approvat[ao]"** nella stessa finestra
di testo, in entrambe le direzioni (copre sia "graduatoria approvata... del
gg/mm/aaaa" sia "determina di approvazione della graduatoria n. X del
gg/mm/aaaa"). Nessuna pretesa di individuare *quale* graduatoria, tra più
menzionate: prende la corrispondenza più vicina testualmente.
"""

from __future__ import annotations

import re

from .models import Entita, TestoAtto

_RE_GRADUATORIA = re.compile(r"graduatoria", re.IGNORECASE)
_RE_APPROVATA = re.compile(r"approvat[ao]|approvazione", re.IGNORECASE)

# Finestra (caratteri, per lato) entro cui "approvat[ao]" deve comparire
# rispetto alla menzione di "graduatoria", perché la menzione conti come
# "approvazione della graduatoria" e non un uso generico della parola.
_FINESTRA_GRADUATORIA = 150

# Finestra (caratteri) in cui cercare la data rispetto alla parola di
# approvazione: il pattern reale è quasi sempre "approvat[ao]... del
# gg/mm/aaaa", quindi si cerca prima **dopo** "approvat[ao]" (finestra più
# stretta, il caso di gran lunga più comune) e solo se non c'è nulla lì si
# guarda **prima** di "graduatoria" (pattern raro: "in data X è stata
# approvata la graduatoria").
_FINESTRA_DATA_DOPO_APPROVATA = 80
_FINESTRA_DATA_PRIMA_GRADUATORIA = 80


def estrai_data_graduatoria(atto: TestoAtto) -> Entita | None:
    """Data di approvazione della graduatoria, se citata nell'atto.

    `None` se non c'è corrispondenza (nessuna menzione di "graduatoria", o
    menzione senza "approvat[ao]"/data nelle vicinanze) — mai un errore.
    Non pretende di individuare *quale* graduatoria, tra più menzionate:
    prende la prima corrispondenza valida trovata.
    """
    from .entita import estrai_date  # import locale: evita ciclo con entita.py

    date_entita = estrai_date(atto)
    if not date_entita:
        return None

    for m_grad in _RE_GRADUATORIA.finditer(atto.testo):
        finestra_ini = max(0, m_grad.start() - _FINESTRA_GRADUATORIA)
        finestra_fine = min(len(atto.testo), m_grad.end() + _FINESTRA_GRADUATORIA)
        match_approvata = list(_RE_APPROVATA.finditer(atto.testo, finestra_ini, finestra_fine))
        if not match_approvata:
            continue

        dopo = min(ma.end() for ma in match_approvata)
        ent = _data_in_finestra(date_entita, dopo, dopo + _FINESTRA_DATA_DOPO_APPROVATA)
        if ent is not None:
            return ent

        prima = max(0, m_grad.start() - _FINESTRA_DATA_PRIMA_GRADUATORIA)
        ent = _data_in_finestra(date_entita, prima, m_grad.start())
        if ent is not None:
            return ent

    return None


def _data_in_finestra(date_entita: list[Entita], ini: int, fine: int) -> Entita | None:
    """La data più vicina all'inizio della finestra [ini, fine), se ce n'è una."""
    candidate = [d for d in date_entita if ini <= d.offset_inizio < fine]
    if not candidate:
        return None
    return min(candidate, key=lambda d: d.offset_inizio)


__all__ = ["estrai_data_graduatoria"]
