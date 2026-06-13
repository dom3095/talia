"""TAL-14 — Check 7: data breach GDPR non notificato.

Quando un atto di autotutela descrive la divulgazione di dati personali
(es. bozza di graduatoria, atti interni riservati), la PA è tenuta a:
- notificare il Garante entro 72 ore (art. 33 GDPR);
- informare gli interessati se la violazione comporta alto rischio (art. 34 GDPR).

Il check è deterministico: cerca menzione di divulgazione di dati personali
e verifica l'assenza di riferimento alla notifica al Garante.

Limite noto: l'assenza di menzione non prova l'omissione (la notifica può
essere avvenuta in altro atto); è però un segnale da approfondire (🔴).
"""

from __future__ import annotations

import re

from ..fascicolo import ContestoFascicolo
from ..models import Citazione, Stato
from .base import Check, EsitoCheck, registra

_RIFERIMENTI = (
    "Art. 33 GDPR (notifica violazione dati all'Autorità di controllo entro 72h)",
    "Art. 34 GDPR (comunicazione violazione agli interessati ad alto rischio)",
    "Art. 4(12) GDPR (definizione di violazione dei dati personali)",
)

# Termini che descrivono una divulgazione/fuga di informazioni.
_RE_DIVULGAZIONE = re.compile(
    r"\b(?:"
    r"divulga(?:zione|to|ta|re)"
    r"|fuga\s+di\s+notizie?"
    r"|trapelat[oa]"
    r"|diffusion[ei]\s+(?:non\s+autorizzata|indebita|abusiva)"
    r"|comunicat[oa]\s+(?:a\s+terzi|all'esterno|impropriamente)"
    r"|resa?\s+(?:nota?|pubblica)\s+(?:a\s+terzi|prematuramente)"
    r"|violazione\s+della\s+riservatezza"
    r")\b",
    re.IGNORECASE,
)

# Dati personali il cui trattamento è regolato da GDPR nel contesto di gare/concorsi.
_RE_DATI_PERSONALI = re.compile(
    r"\b(?:"
    r"graduatoria"
    r"|bozza\s+(?:di\s+)?graduatoria"
    r"|classifica"
    r"|punteggi[oa]?\s+(?:dei\s+)?candidat"
    r"|dati\s+(?:personali|dei\s+candidati|sensibili)"
    r"|atti?\s+interni?\s+(?:riservati?|confidenziali?)"
    r"|verbale\s+(?:di\s+)?(?:valutazione|selezione|commissione)"
    r")\b",
    re.IGNORECASE,
)

# Finestra (in caratteri) entro cui divulgazione + dati personali si considerano
# riferiti allo stesso evento.
_FINESTRA_BREACH = 400

# Riferimenti alla notifica GDPR o a un procedimento di accertamento formale.
_RE_NOTIFICA_GARANTE = re.compile(
    r"\b(?:"
    r"Garante\s+(?:per\s+la\s+protezione\s+dei\s+dati|Privacy|GPDP)"
    r"|art(?:icolo)?\.?\s*33\b[^.]{0,40}\bGDPR\b"
    r"|notifica\s+(?:al\s+)?Garante"
    r"|data\s+breach\s+notification"
    r"|violazione\s+dei\s+dati\s+(?:personali\s+)?notificata"
    r"|segnalazione\s+al\s+Garante"
    r")\b",
    re.IGNORECASE,
)


class CheckGdprBreach(Check):
    id = "check-7"
    titolo = "Data breach GDPR: notifica al Garante"
    riferimenti = _RIFERIMENTI

    def applicabile(self, contesto: ContestoFascicolo) -> bool:
        # Applicabile solo se troviamo evidenza di un evento di divulgazione.
        testo = contesto.atto_autotutela.testo.testo
        return _breach_descritto(testo) is not None

    def valuta(self, contesto: ContestoFascicolo) -> EsitoCheck:
        atto = contesto.atto_autotutela.testo
        testo = atto.testo

        match_breach = _breach_descritto(testo)
        if match_breach is None:
            return self._esito(Stato.NON_APPLICABILE, "Nessuna descrizione di divulgazione di dati personali rilevata.")

        citazione_breach = Citazione(
            testo=atto.estratto(match_breach.start(), match_breach.end()),
            offset_inizio=match_breach.start(),
            offset_fine=match_breach.end(),
            pagina=atto.pagina_per_offset(match_breach.start()),
        )

        match_notifica = _RE_NOTIFICA_GARANTE.search(testo)
        if match_notifica:
            return self._esito(
                Stato.VERDE,
                "L'atto descrive una violazione di dati personali e menziona la notifica al Garante.",
                [
                    citazione_breach,
                    Citazione(
                        testo=atto.estratto(match_notifica.start(), match_notifica.end()),
                        offset_inizio=match_notifica.start(),
                        offset_fine=match_notifica.end(),
                        pagina=atto.pagina_per_offset(match_notifica.start()),
                    ),
                ],
            )

        return self._esito(
            Stato.ROSSO,
            "L'atto descrive la divulgazione di dati personali (potenziale data breach "
            "ai sensi dell'art. 4(12) GDPR) ma non menziona la notifica al Garante "
            "entro 72 ore (art. 33 GDPR) né un procedimento di accertamento interno. "
            "Da verificare: la notifica potrebbe essere avvenuta in atto separato.",
            [citazione_breach],
        )


def _breach_descritto(testo: str) -> re.Match | None:
    """Trova il primo match di divulgazione con dati personali nelle vicinanze."""
    for m_div in _RE_DIVULGAZIONE.finditer(testo):
        inizio = max(0, m_div.start() - _FINESTRA_BREACH)
        fine = min(len(testo), m_div.end() + _FINESTRA_BREACH)
        if _RE_DATI_PERSONALI.search(testo, inizio, fine):
            return m_div
    return None


registra(CheckGdprBreach())
