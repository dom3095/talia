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

        # Indicizza per nome normalizzato per individuare le sovrapposizioni.
        per_nome_orig = {nome_normalizzato(e.valore): e for e in firmatari_orig}
        per_nome_autt = {nome_normalizzato(e.valore): e for e in firmatari_autt}
        comuni = set(per_nome_orig) & set(per_nome_autt)

        if not comuni:
            return self._esito(
                Stato.VERDE,
                "I firmatari dell'atto originario e dell'annullamento non coincidono.",
            )

        citazioni = []
        nomi = []
        for chiave in comuni:
            ent_orig = per_nome_orig[chiave]
            ent_autt = per_nome_autt[chiave]
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


registra(CheckCoerenzaFirmatari())
