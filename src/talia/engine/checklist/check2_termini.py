"""TAL-7 — Check 2: termini dell'autotutela (≤ 12 mesi).

L'annullamento d'ufficio di provvedimenti attributivi di vantaggi economici deve
intervenire entro un **termine ragionevole**, fissato dall'art. 21-nonies
L. 241/1990 (come modificato) in **12 mesi** dall'adozione dell'atto.

Si applica **solo** agli annullamenti (non alle revoche). In caso di date
mancanti o ambigue l'esito è 🟡 con spiegazione, mai un errore.

Assunzione documentata sulle date (da validare con ⚖️ LEX):
- *data dell'atto originario* = data più antica rilevata nell'atto originario,
  oppure, se il fascicolo ha il solo atto di autotutela, la data più antica in
  esso citata (tipicamente il riferimento all'atto annullato);
- *data dell'annullamento* = data più recente rilevata nell'atto di autotutela
  (proxy della sua adozione/sottoscrizione).
"""

from __future__ import annotations

import re
from datetime import date

from ..fascicolo import ContestoFascicolo
from ..models import Citazione, Entita, Stato
from .base import Check, EsitoCheck, registra

_RIFERIMENTI = ("Art. 21-nonies L. 241/1990 (termine di 12 mesi)",)

# 12 mesi ≈ 365 giorni: approssimazione documentata per il calcolo del delta.
SOGLIA_GIORNI = 365
# Tolleranza attorno alla soglia entro cui l'esito è 🟡 ("al limite") invece di 🔴.
TOLLERANZA_GIORNI = 30

# Trattino opzionale: negli atti reali si trova anche "21 nonies" / "21nonies".
_RE_ANNULLAMENTO = re.compile(r"21\s*-?\s*nonies", re.IGNORECASE)

# Date vicine a riferimenti CCNL non riguardano il procedimento di autotutela.
_RE_CCNL = re.compile(
    r"(CCNL|contratto\s+collettivo|accordo\s+quadro)",
    re.IGNORECASE,
)
# Finestra di esclusione: ±N caratteri dal centro della data.
_FINESTRA_CCNL = 120


class CheckTerminiAutotutela(Check):
    id = "check-2"
    titolo = "Termini dell'autotutela (≤ 12 mesi)"
    riferimenti = _RIFERIMENTI

    def applicabile(self, contesto: ContestoFascicolo) -> bool:
        # Pertinente solo se l'atto si qualifica come annullamento d'ufficio.
        return bool(_RE_ANNULLAMENTO.search(contesto.atto_autotutela.testo.testo))

    def valuta(self, contesto: ContestoFascicolo) -> EsitoCheck:
        data_originario, ent_orig = self._data_originario(contesto)
        data_annull, ent_annull = self._data_annullamento(contesto)

        if data_originario is None or data_annull is None:
            return self._esito(
                Stato.GIALLO,
                "Impossibile determinare con certezza la data dell'atto originario "
                "e/o dell'annullamento: termine non verificabile, da controllare a mano.",
                self._citazioni(contesto, [ent_orig, ent_annull]),
            )

        delta = (data_annull - data_originario).days
        citazioni = self._citazioni(contesto, [ent_orig, ent_annull])

        if delta < 0:
            return self._esito(
                Stato.GIALLO,
                "Le date rilevate sono incongruenti (annullamento precedente "
                "all'atto originario): da verificare.",
                citazioni,
            )

        mesi = self._mesi_approssimati(delta)
        if delta <= SOGLIA_GIORNI:
            return self._esito(
                Stato.VERDE,
                f"Annullamento entro il termine: ~{mesi} mesi dall'atto originario.",
                citazioni,
            )
        if delta <= SOGLIA_GIORNI + TOLLERANZA_GIORNI:
            return self._esito(
                Stato.GIALLO,
                f"Annullamento al limite del termine: ~{mesi} mesi dall'atto originario "
                "(soglia 12 mesi).",
                citazioni,
            )
        return self._esito(
            Stato.ROSSO,
            f"Annullamento oltre il termine ragionevole: ~{mesi} mesi dall'atto "
            "originario, oltre i 12 mesi previsti dall'art. 21-nonies.",
            citazioni,
        )

    # --- estrazione delle due date di riferimento ---------------------------

    def _data_originario(
        self, contesto: ContestoFascicolo
    ) -> tuple[date | None, Entita | None]:
        if contesto.atto_originario is not None:
            date_orig = _filtra_date_ccnl(
                contesto.atto_originario.entita.date,
                contesto.atto_originario.testo.testo,
            )
            return _data_estrema(date_orig, piu_recente=False)
        # Solo atto di autotutela: la data più antica in esso citata è il proxy
        # del riferimento all'atto annullato.
        date_autotutela = _filtra_date_ccnl(
            contesto.atto_autotutela.entita.date,
            contesto.atto_autotutela.testo.testo,
        )
        if len(_valori_distinti(date_autotutela)) < 2:
            return None, None
        return _data_estrema(date_autotutela, piu_recente=False)

    def _data_annullamento(
        self, contesto: ContestoFascicolo
    ) -> tuple[date | None, Entita | None]:
        date_aut = _filtra_date_ccnl(
            contesto.atto_autotutela.entita.date,
            contesto.atto_autotutela.testo.testo,
        )
        return _data_estrema(date_aut, piu_recente=True)

    @staticmethod
    def _mesi_approssimati(giorni: int) -> int:
        # 30.44 = giorni medi per mese; arrotondamento all'intero più vicino.
        return round(giorni / 30.44)

    @staticmethod
    def _citazioni(
        contesto: ContestoFascicolo, entita: list[Entita | None]
    ) -> list[Citazione]:
        citazioni: list[Citazione] = []
        for ent in entita:
            if ent is None:
                continue
            atto = _atto_di(contesto, ent)
            citazioni.append(ent.come_citazione(atto.testo if atto else None))
        return citazioni


def _filtra_date_ccnl(date_entita: list[Entita], testo: str) -> list[Entita]:
    """Rimuove date che seguono immediatamente un riferimento CCNL (entro _FINESTRA_CCNL caratteri).

    Il pattern ricorrente è "CCNL del 16.11.2022" o "accordo quadro del 01.03.2021":
    la data appare alla destra del keyword. Filtrare solo in quella direzione evita di
    scartare la data dell'annullamento che precede il riferimento CCNL nella stessa frase.
    """
    posizioni_ccnl = [m.start() for m in _RE_CCNL.finditer(testo)]
    if not posizioni_ccnl:
        return date_entita
    filtrate = []
    for ent in date_entita:
        # Escludi se un keyword CCNL appare entro _FINESTRA_CCNL caratteri PRIMA della data.
        vicino_ccnl = any(
            0 <= ent.offset_inizio - pos <= _FINESTRA_CCNL
            for pos in posizioni_ccnl
        )
        if not vicino_ccnl:
            filtrate.append(ent)
    return filtrate


def _valori_distinti(date_entita: list[Entita]) -> set[date]:
    return {e.valore for e in date_entita}


def _data_estrema(
    date_entita: list[Entita], *, piu_recente: bool
) -> tuple[date | None, Entita | None]:
    """Restituisce l'entità data più recente o più antica e il suo valore."""
    candidate = [e for e in date_entita if isinstance(e.valore, date)]
    if not candidate:
        return None, None
    scelta = (max if piu_recente else min)(candidate, key=lambda e: e.valore)
    return scelta.valore, scelta


def _atto_di(contesto: ContestoFascicolo, ent: Entita):
    """Individua a quale atto appartiene un'entità (per costruire la citazione).

    Confronto per **identità** (`is`), non per uguaglianza: due atti possono
    contenere entità uguali campo per campo (stessa data allo stesso offset) e
    l'uguaglianza attribuirebbe la citazione all'atto sbagliato.
    """
    for atto in (contesto.atto_autotutela, contesto.atto_originario):
        if atto is not None and any(e is ent for e in atto.entita.entita):
            return atto
    return None


registra(CheckTerminiAutotutela())
