"""TAL-9 — Check 6: coerenza dei firmatari.

Confronta i firmatari dell'atto originario (indizione/aggiudicazione) con quelli
dell'atto di autotutela. La sovrapposizione — lo stesso soggetto che firma sia
l'atto sia il suo annullamento — è l'anomalia da verificare (auto-annullamento).

Prudenza: nei piccoli comuni un unico dirigente firma spesso tutti gli atti, il
che è fisiologico. L'esito di sovrapposizione è quindi 🟡 (da verificare), non un
giudizio di illegittimità.
"""

from __future__ import annotations

from ..fascicolo import ContestoFascicolo
from ..firmatari import nome_normalizzato
from ..models import Stato
from .base import Check, EsitoCheck, registra


class CheckCoerenzaFirmatari(Check):
    id = "check-6"
    titolo = "Coerenza dei firmatari (indizione vs annullamento)"

    def applicabile(self, contesto: ContestoFascicolo) -> bool:
        # Serve sia l'atto originario sia almeno un firmatario per parte.
        if contesto.atto_originario is None:
            return False
        return bool(
            contesto.atto_originario.entita.firmatari
            and contesto.atto_autotutela.entita.firmatari
        )

    def valuta(self, contesto: ContestoFascicolo) -> EsitoCheck:
        firmatari_orig = contesto.atto_originario.entita.firmatari
        firmatari_autt = contesto.atto_autotutela.entita.firmatari

        # Confronto a coppie con matching per sottoinsieme: "Pietro Amorosia" e
        # "Pietro Nicola Amorosia" sono la stessa persona (secondo nome omesso).
        # Lezione dal primo fascicolo reale: l'uguaglianza esatta dei token
        # produceva un falso verde.
        coppie: list[tuple] = []
        visti_autt: set[int] = set()
        for ent_orig in firmatari_orig:
            for j, ent_autt in enumerate(firmatari_autt):
                if j in visti_autt:
                    continue
                if _stesso_firmatario(
                    nome_normalizzato(ent_orig.valore),
                    nome_normalizzato(ent_autt.valore),
                ):
                    coppie.append((ent_orig, ent_autt))
                    visti_autt.add(j)
                    break

        if not coppie:
            return self._esito(
                Stato.VERDE,
                "I firmatari dell'atto originario e dell'annullamento non coincidono.",
            )

        citazioni = []
        nomi = []
        for ent_orig, ent_autt in coppie:
            nomi.append(ent_autt.valore)
            citazioni.append(ent_orig.come_citazione(contesto.atto_originario.testo))
            citazioni.append(ent_autt.come_citazione(contesto.atto_autotutela.testo))

        elenco = ", ".join(sorted(nomi))
        return self._esito(
            Stato.GIALLO,
            f"Lo stesso firmatario compare in entrambi gli atti ({elenco}): possibile "
            "auto-annullamento, da verificare (può essere fisiologico nei piccoli comuni).",
            citazioni,
        )


def _stesso_firmatario(a: frozenset[str], b: frozenset[str]) -> bool:
    """Due nomi normalizzati indicano la stessa persona?

    Criterio prudente: almeno 2 token in comune (nome+cognome) e uno dei due
    insiemi contenuto nell'altro (gestisce il secondo nome omesso). Evita falsi
    match su singolo cognome condiviso (omonimie parziali frequenti nei piccoli
    comuni).
    """
    if not a or not b:
        return False
    return len(a & b) >= 2 and (a <= b or b <= a)


registra(CheckCoerenzaFirmatari())
