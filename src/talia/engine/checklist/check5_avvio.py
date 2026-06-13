"""TAL-8 — Check 5: comunicazione di avvio del procedimento (art. 7 L. 241/1990).

L'autotutela su un procedimento concorsuale/di gara dovrebbe essere preceduta
dalla comunicazione di avvio del procedimento ai partecipanti (art. 7 L. 241/1990).
Il check è deterministico: cerca la **menzione** della comunicazione nell'atto.

Limite noto: la presenza della menzione non prova l'effettivo invio; l'assenza è
però un segnale concreto da verificare (🔴).
"""

from __future__ import annotations

import re

from ..fascicolo import ContestoFascicolo
from ..models import Citazione, Stato
from .base import Check, EsitoCheck, registra

_RIFERIMENTI = ("Art. 7 L. 241/1990 (comunicazione di avvio del procedimento)",)

# Distanza massima (in caratteri) entro cui "art. 7" e "241" si considerano
# riferiti allo stesso istituto.
_FINESTRA_ART7_241 = 60

_RE_AVVIO = re.compile(r"avvio\s+del\s+procedimento", re.IGNORECASE)
_RE_COMUNICAZIONE = re.compile(r"comunicazione\s+(?:di\s+)?avvio", re.IGNORECASE)
_RE_ART7 = re.compile(r"art(?:icolo)?\.?\s*7\b", re.IGNORECASE)
_RE_241 = re.compile(r"\b241\b")

# PA che sostituisce la notifica individuale con la pubblicazione sul sito.
# Rilevante quando i partecipanti sono noti (selezioni interne, concorsi avviati).
_RE_PUBBL_SITO = re.compile(
    r"pubblicazione\s+sul\s+sito.{0,60}valore?\s+di\s+notifica",
    re.IGNORECASE | re.DOTALL,
)


class CheckComunicazioneAvvio(Check):
    id = "check-5"
    titolo = "Comunicazione di avvio del procedimento (art. 7)"
    riferimenti = _RIFERIMENTI

    def valuta(self, contesto: ContestoFascicolo) -> EsitoCheck:
        atto = contesto.atto_autotutela.testo
        testo = atto.testo

        match = _RE_COMUNICAZIONE.search(testo) or _RE_AVVIO.search(testo) or _art7_241(testo)
        if match is not None:
            return self._esito(
                Stato.VERDE,
                "L'atto menziona la comunicazione/avvio del procedimento (art. 7).",
                [
                    Citazione(
                        testo=atto.estratto(match.start(), match.end()),
                        offset_inizio=match.start(),
                        offset_fine=match.end(),
                        pagina=atto.pagina_per_offset(match.start()),
                    )
                ],
            )
        # Cerca se l'atto dichiara esplicitamente di notificare via pubblicazione
        # sul sito invece della comunicazione individuale.
        match_pubbl = _RE_PUBBL_SITO.search(testo)
        citazioni_extra = (
            [
                Citazione(
                    testo=atto.estratto(match_pubbl.start(), match_pubbl.end()),
                    offset_inizio=match_pubbl.start(),
                    offset_fine=match_pubbl.end(),
                    pagina=atto.pagina_per_offset(match_pubbl.start()),
                )
            ]
            if match_pubbl
            else []
        )
        spiegazione = (
            "Nessuna comunicazione individuale di avvio del procedimento "
            "(art. 7 L. 241/1990) nei confronti dei partecipanti. "
            + (
                "L'atto prevede la sola pubblicazione sul sito come forma di notifica: "
                "per procedure con candidati noti (selezioni interne, concorsi già "
                "avviati), questa scelta è da verificare con un esperto legale."
                if match_pubbl
                else "Da verificare: l'assenza di menzione non prova l'omissione, "
                "ma è un segnale da approfondire."
            )
        )
        return self._esito(Stato.ROSSO, spiegazione, citazioni_extra)


def _art7_241(testo: str) -> re.Match | None:
    """Match di 'art. 7' solo se '241' compare nelle vicinanze."""
    for m in _RE_ART7.finditer(testo):
        inizio = max(0, m.start() - _FINESTRA_ART7_241)
        fine = min(len(testo), m.end() + _FINESTRA_ART7_241)
        if _RE_241.search(testo, inizio, fine):
            return m
    return None


registra(CheckComunicazioneAvvio())
