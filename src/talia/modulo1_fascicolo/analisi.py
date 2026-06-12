"""TAL-10 — Orchestrazione dell'analisi di un fascicolo (Modulo 1).

Collega gli stadi del motore: estrazione testo → entità → checklist → report.
Espone funzioni a granularità crescente di comodità:
- `analizza_fascicolo`  : su atti già strutturati (massimo controllo);
- `analizza_testi`      : su `TestoAtto` con classificazione automatica del ruolo;
- `analizza_pdf`        : su percorsi PDF (richiede gli extra `[pdf]`).
"""

from __future__ import annotations

import re
from pathlib import Path

from ..engine.checklist import esegui_checklist
from ..engine.fascicolo import AttoAnalizzato, ContestoFascicolo, RuoloAtto
from ..engine.models import TestoAtto
from ..engine.pdf_text import estrai_testo
from .report import AttoMeta, Report

# Classificazione del ruolo degli atti: punteggio pesato, non semplice conteggio.
# Lezione dal primo fascicolo reale (Palma di Montechiaro): i bandi contengono
# boilerplate come "l'amministrazione si riserva di revocare..." — il verbo
# "revocare" da solo NON può qualificare un atto come autotutela.

# Segnali forti di autotutela (peso 3): formule che compaiono solo in atti che
# *sono* revoche/annullamenti, non che ne parlano in ipotesi.
_FORTI_AUTOTUTELA = re.compile(
    r"in\s+autotutela|annullament\w*\s+d'?\s*ufficio|"
    r"21\s*-?\s*quinquies|21\s*-?\s*nonies",
    re.IGNORECASE,
)
# Segnali deboli (peso 1): il sostantivo "revoca/annullamento" (mai l'infinito
# "revocare", tipico delle clausole di riserva).
_DEBOLI_AUTOTUTELA = re.compile(r"\brevoc[ah]e?\b|\bannullamento\b", re.IGNORECASE)

# Segnali forti di atto originario (peso 2): indizione/approvazione della procedura.
_FORTI_ORIGINARIO = re.compile(
    r"indizion\w*|approvazione\s+(?:del\s+bando|(?:dell')?avviso)|"
    r"determina\w*\s+a\s+contrarre|aggiudicazion\w*",
    re.IGNORECASE,
)
# Segnali deboli (peso 1): menzioni della procedura (compaiono anche nell'atto
# di revoca, che la richiama).
_DEBOLI_ORIGINARIO = re.compile(
    r"bando\s+di\s+(?:concorso|gara|selezione)|avviso\s+di\s+selezione",
    re.IGNORECASE,
)

PESO_FORTE_AUTOTUTELA = 3
PESO_FORTE_ORIGINARIO = 2


def punteggi_ruolo(testo: TestoAtto) -> tuple[int, int]:
    """Punteggi (autotutela, originario) di un atto. Esposto per i test."""
    t = testo.testo
    aut = PESO_FORTE_AUTOTUTELA * len(_FORTI_AUTOTUTELA.findall(t)) + len(
        _DEBOLI_AUTOTUTELA.findall(t)
    )
    orig = PESO_FORTE_ORIGINARIO * len(_FORTI_ORIGINARIO.findall(t)) + len(
        _DEBOLI_ORIGINARIO.findall(t)
    )
    return aut, orig


def classifica_ruolo(testo: TestoAtto) -> RuoloAtto:
    """Euristica deterministica sul ruolo di un atto nel fascicolo.

    Confronta i punteggi pesati; in pareggio o assenza ritorna SCONOSCIUTO
    (la selezione del contesto applica poi un fallback).
    """
    aut, orig = punteggi_ruolo(testo)
    if aut > orig:
        return RuoloAtto.AUTOTUTELA
    if orig > aut:
        return RuoloAtto.ORIGINARIO
    return RuoloAtto.SCONOSCIUTO


def costruisci_contesto(atti: list[AttoAnalizzato]) -> ContestoFascicolo:
    """Seleziona atto di autotutela e atto originario dal fascicolo.

    Autotutela: tra gli atti con ruolo AUTOTUTELA, quello con punteggio massimo
    (l'ordine dei file non deve contare); in mancanza, l'ultimo atto fornito.
    Originario: tra gli atti ORIGINARIO diversi dall'autotutela, quello con
    punteggio massimo.
    """
    if not atti:
        raise ValueError("Il fascicolo non contiene atti.")

    candidati_aut = [a for a in atti if a.ruolo is RuoloAtto.AUTOTUTELA]
    autotutela = (
        max(candidati_aut, key=lambda a: punteggi_ruolo(a.testo)[0])
        if candidati_aut
        else atti[-1]
    )

    candidati_orig = [
        a for a in atti if a.ruolo is RuoloAtto.ORIGINARIO and a is not autotutela
    ]
    originario = (
        max(candidati_orig, key=lambda a: punteggi_ruolo(a.testo)[1])
        if candidati_orig
        else None
    )
    return ContestoFascicolo(atto_autotutela=autotutela, atto_originario=originario)


def analizza_fascicolo(atti: list[AttoAnalizzato]) -> Report:
    """Esegue la checklist sul fascicolo e produce il report."""
    contesto = costruisci_contesto(atti)
    esiti = esegui_checklist(contesto)
    meta = [_meta(a, contesto) for a in atti]
    return Report(esiti=esiti, atti=meta)


def analizza_testi(testi: list[TestoAtto]) -> Report:
    """Come `analizza_fascicolo` ma classifica da sé il ruolo di ogni testo."""
    atti = [
        AttoAnalizzato.da_testo(t, ruolo=classifica_ruolo(t)) for t in testi
    ]
    return analizza_fascicolo(atti)


def analizza_pdf(percorsi: list[str | Path]) -> Report:
    """Analizza un fascicolo a partire dai PDF (richiede gli extra `[pdf]`)."""
    testi = [estrai_testo(p) for p in percorsi]
    return analizza_testi(testi)


def _meta(atto: AttoAnalizzato, contesto: ContestoFascicolo) -> AttoMeta:
    # Il ruolo effettivo nel contesto può differire da quello classificato
    # (fallback): riportiamo quello usato dai check.
    if atto is contesto.atto_autotutela:
        ruolo = RuoloAtto.AUTOTUTELA.value
    elif atto is contesto.atto_originario:
        ruolo = RuoloAtto.ORIGINARIO.value
    else:
        ruolo = atto.ruolo.value
    etichetta = atto.etichetta or "atto senza nome"
    return AttoMeta(
        etichetta=etichetta,
        ruolo=ruolo,
        fonte=atto.testo.fonte.value,
        pagine=len(atto.testo.pagine),
    )
