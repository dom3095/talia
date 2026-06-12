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
        return self._esito(
            Stato.ROSSO,
            "Nessuna menzione della comunicazione di avvio del procedimento "
            "(art. 7 L. 241/1990) nei confronti dei partecipanti: da verificare.",
        )


def _art7_241(testo: str) -> re.Match | None:
    """Match di 'art. 7' solo se '241' compare nelle vicinanze."""
    for m in _RE_ART7.finditer(testo):
        inizio = max(0, m.start() - _FINESTRA_ART7_241)
        fine = min(len(testo), m.end() + _FINESTRA_ART7_241)
        if _RE_241.search(testo, inizio, fine):
            return m
    return None


registra(CheckComunicazioneAvvio())
