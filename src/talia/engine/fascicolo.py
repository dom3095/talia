"""Modello di fascicolo: gli atti che compongono un caso di analisi.

Il caso d'uso prioritario (Modulo 1) confronta un **atto originario** (indizione
di concorso o aggiudicazione di gara) con un **atto di autotutela** (revoca o
annullamento d'ufficio). I check della checklist ragionano su questo contesto.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from .entita import estrai_entita
from .models import EntitaEstratte, TestoAtto


class RuoloAtto(StrEnum):
    """Ruolo di un atto all'interno del fascicolo."""

    ORIGINARIO = "originario"  # indizione concorso / aggiudicazione gara
    AUTOTUTELA = "autotutela"  # revoca o annullamento d'ufficio
    SCONOSCIUTO = "sconosciuto"


@dataclass
class AttoAnalizzato:
    """Un atto con il suo testo e le entità estratte."""

    testo: TestoAtto
    ruolo: RuoloAtto = RuoloAtto.SCONOSCIUTO
    entita: EntitaEstratte = field(default_factory=EntitaEstratte)
    etichetta: str | None = None  # nome leggibile per il report

    @classmethod
    def da_testo(
        cls,
        testo: TestoAtto,
        ruolo: RuoloAtto = RuoloAtto.SCONOSCIUTO,
        etichetta: str | None = None,
    ) -> AttoAnalizzato:
        """Crea un atto eseguendo l'estrazione entità sul testo."""
        return cls(
            testo=testo,
            ruolo=ruolo,
            entita=estrai_entita(testo),
            etichetta=etichetta or (testo.percorso if testo.percorso else None),
        )


@dataclass
class ContestoFascicolo:
    """Contesto passato ai check: l'atto in esame e l'eventuale atto originario.

    `atto_autotutela` è l'atto di revoca/annullamento da verificare ed è sempre
    presente. `atto_originario` può mancare (fascicolo con un solo documento):
    i check che lo richiedono lo dichiarano non applicabile.
    """

    atto_autotutela: AttoAnalizzato
    atto_originario: AttoAnalizzato | None = None
