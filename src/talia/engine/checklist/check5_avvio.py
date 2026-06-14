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

# Indicatori che la procedura è un concorso/selezione interna al personale dell'ente.
# Per i concorsi interni la pubblicazione all'albo pretorio/sito sostituisce la
# pubblicità legale (art. 32 L. 69/2009), quindi l'assenza di notifica individuale
# è meno critica che per procedure aperte a candidati esterni.
_RE_CONCORSO_INTERNO = re.compile(
    r"(?:concorso|selezione|avviso|procedura)\s+intern[oa]"
    r"|personale\s+(?:intern[oa]|dipendente)"
    r"|riservat[oa]\s+al\s+personale"
    r"|mobilit[àa]\s+intern[ao]",
    re.IGNORECASE,
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
        if match_pubbl:
            cit_pubbl = Citazione(
                testo=atto.estratto(match_pubbl.start(), match_pubbl.end()),
                offset_inizio=match_pubbl.start(),
                offset_fine=match_pubbl.end(),
                pagina=atto.pagina_per_offset(match_pubbl.start()),
            )
            if _RE_CONCORSO_INTERNO.search(testo):
                # Concorso interno: pubblicazione albo/sito è forma di pubblicità
                # legale sufficiente (art. 32 L. 69/2009). Segnaliamo comunque
                # per verifica dell'effettiva conoscenza da parte dei candidati.
                return self._esito(
                    Stato.GIALLO,
                    "Concorso interno: la pubblicazione sul sito sostituisce la "
                    "pubblicità legale (art. 32 L. 69/2009). Verificare che i "
                    "candidati abbiano avuto effettiva conoscenza dell'atto.",
                    [cit_pubbl],
                )
            return self._esito(
                Stato.ROSSO,
                "L'atto prevede la sola pubblicazione sul sito come forma di "
                "notifica. Per procedure con candidati noti (concorsi già avviati, "
                "non interni), la comunicazione individuale ex art. 7 L. 241/1990 "
                "è da verificare con un esperto legale.",
                [cit_pubbl],
            )
        return self._esito(
            Stato.ROSSO,
            "Nessuna comunicazione individuale di avvio del procedimento "
            "(art. 7 L. 241/1990) nei confronti dei partecipanti. "
            "Da verificare: l'assenza di menzione non prova l'omissione, "
            "ma è un segnale da approfondire.",
            [],
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
