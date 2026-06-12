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

# Parole che qualificano un atto come autotutela (revoca/annullamento d'ufficio).
_SEGNALI_AUTOTUTELA = re.compile(
    r"21\s*-\s*(?:quinquies|nonies)|annullament\w*\s+d'?\s*ufficio|in\s+autotutela|"
    r"\brevoc\w+\b|\bannullament\w+\b",
    re.IGNORECASE,
)
# Parole che qualificano un atto come originario (indizione/aggiudicazione).
_SEGNALI_ORIGINARIO = re.compile(
    r"indizion\w*|bando di concorso|determina\w*\s+a\s+contrarre|aggiudicazion\w*|"
    r"approvazione del bando",
    re.IGNORECASE,
)


def classifica_ruolo(testo: TestoAtto) -> RuoloAtto:
    """Euristica deterministica sul ruolo di un atto nel fascicolo.

    Conta i segnali di autotutela vs originario; in pareggio o assenza ritorna
    SCONOSCIUTO (la selezione del contesto applica poi un fallback).
    """
    n_aut = len(_SEGNALI_AUTOTUTELA.findall(testo.testo))
    n_orig = len(_SEGNALI_ORIGINARIO.findall(testo.testo))
    if n_aut > n_orig:
        return RuoloAtto.AUTOTUTELA
    if n_orig > n_aut:
        return RuoloAtto.ORIGINARIO
    return RuoloAtto.SCONOSCIUTO


def costruisci_contesto(atti: list[AttoAnalizzato]) -> ContestoFascicolo:
    """Seleziona atto di autotutela e atto originario dal fascicolo.

    Autotutela: il primo atto con ruolo AUTOTUTELA; in mancanza, l'ultimo atto
    fornito (per il caso d'uso, di solito è l'atto in esame). Originario: il
    primo atto ORIGINARIO diverso dall'autotutela.
    """
    if not atti:
        raise ValueError("Il fascicolo non contiene atti.")

    autotutela = next(
        (a for a in atti if a.ruolo is RuoloAtto.AUTOTUTELA), atti[-1]
    )
    originario = next(
        (
            a
            for a in atti
            if a.ruolo is RuoloAtto.ORIGINARIO and a is not autotutela
        ),
        None,
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
