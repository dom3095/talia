"""Modelli dati condivisi del motore di analisi TALIA.

Tutti i moduli (estrazione testo, entità, checklist, report) parlano questi tipi.
Principio guida del progetto: **esplicabilità**. Ogni informazione estratta o
ogni esito di un check deve poter essere ricondotto a una posizione precisa nel
documento sorgente (pagina + offset di carattere) → vedi `Citazione`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Stato(StrEnum):
    """Esito a semaforo di un check della checklist.

    L'ordine riflette la gravità crescente: utile per ordinare/aggregare.
    """

    VERDE = "verde"
    GIALLO = "giallo"
    ROSSO = "rosso"
    NON_APPLICABILE = "non_applicabile"

    @property
    def emoji(self) -> str:
        return {
            Stato.VERDE: "🟢",
            Stato.GIALLO: "🟡",
            Stato.ROSSO: "🔴",
            Stato.NON_APPLICABILE: "⚪",
        }[self]


class FonteTesto(StrEnum):
    """Da dove proviene il testo estratto da un PDF."""

    NATIVO = "nativo"  # testo già presente nel PDF (PDF digitale)
    OCR = "ocr"  # ricavato da scansione tramite Tesseract
    MISTO = "misto"  # alcune pagine native, altre via OCR


class TipoEntita(StrEnum):
    DATA = "data"
    IMPORTO = "importo"
    CIG = "cig"
    CUP = "cup"
    NORMA = "norma"
    FIRMATARIO = "firmatario"


@dataclass(frozen=True)
class PaginaTesto:
    """Una pagina del documento, con la sua collocazione nel testo concatenato.

    `offset_inizio`/`offset_fine` indicano dove inizia e finisce il testo di
    questa pagina dentro `TestoAtto.testo` (estremo finale escluso).
    """

    numero: int  # 1-based
    testo: str
    offset_inizio: int
    offset_fine: int
    fonte: FonteTesto = FonteTesto.NATIVO


@dataclass
class TestoAtto:
    """Testo completo di un atto, con mapping verso le pagine sorgente.

    È l'output dello stadio 1 del motore (TAL-3) e l'input degli stadi
    successivi. Conserva il legame testo→pagina necessario per le citazioni.
    """

    testo: str
    pagine: list[PaginaTesto] = field(default_factory=list)
    fonte: FonteTesto = FonteTesto.NATIVO
    percorso: str | None = None  # path del PDF sorgente, se disponibile
    metadati: dict[str, str] = field(default_factory=dict)

    def pagina_per_offset(self, offset: int) -> int | None:
        """Numero di pagina (1-based) che contiene l'offset di carattere dato."""
        for pagina in self.pagine:
            if pagina.offset_inizio <= offset < pagina.offset_fine:
                return pagina.numero
        return None

    def estratto(self, offset_inizio: int, offset_fine: int, contesto: int = 40) -> str:
        """Snippet di testo intorno a un intervallo, con un po' di contesto.

        Usato per produrre citazioni leggibili nel report. Gli spazi/newline
        vengono compattati per la resa visiva.
        """
        inizio = max(0, offset_inizio - contesto)
        fine = min(len(self.testo), offset_fine + contesto)
        frammento = self.testo[inizio:fine]
        return " ".join(frammento.split())


@dataclass(frozen=True)
class Citazione:
    """Riferimento esplicito a una porzione del documento sorgente.

    È il mattone dell'esplicabilità: ogni red flag deve portarne almeno una.
    """

    testo: str  # passaggio citato (eventualmente con contesto)
    offset_inizio: int
    offset_fine: int
    pagina: int | None = None


@dataclass(frozen=True)
class Entita:
    """Entità estratta dal testo, sempre risalibile alla sua posizione."""

    tipo: TipoEntita
    valore: object  # valore normalizzato (date, Decimal, str, ...)
    testo_originale: str
    offset_inizio: int
    offset_fine: int
    pagina: int | None = None

    def come_citazione(self, atto: TestoAtto | None = None, contesto: int = 40) -> Citazione:
        testo = self.testo_originale
        if atto is not None:
            testo = atto.estratto(self.offset_inizio, self.offset_fine, contesto)
        return Citazione(
            testo=testo,
            offset_inizio=self.offset_inizio,
            offset_fine=self.offset_fine,
            pagina=self.pagina,
        )


@dataclass
class EntitaEstratte:
    """Contenitore delle entità estratte da un atto, indicizzate per tipo."""

    entita: list[Entita] = field(default_factory=list)

    def per_tipo(self, tipo: TipoEntita) -> list[Entita]:
        return [e for e in self.entita if e.tipo == tipo]

    @property
    def date(self) -> list[Entita]:
        return self.per_tipo(TipoEntita.DATA)

    @property
    def importi(self) -> list[Entita]:
        return self.per_tipo(TipoEntita.IMPORTO)

    @property
    def cig(self) -> list[Entita]:
        return self.per_tipo(TipoEntita.CIG)

    @property
    def cup(self) -> list[Entita]:
        return self.per_tipo(TipoEntita.CUP)

    @property
    def norme(self) -> list[Entita]:
        return self.per_tipo(TipoEntita.NORMA)

    @property
    def firmatari(self) -> list[Entita]:
        return self.per_tipo(TipoEntita.FIRMATARIO)

    def aggiungi(self, *entita: Entita) -> None:
        self.entita.extend(entita)


__all__ = [
    "Stato",
    "FonteTesto",
    "TipoEntita",
    "PaginaTesto",
    "TestoAtto",
    "Citazione",
    "Entita",
    "EntitaEstratte",
]
