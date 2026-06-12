"""Infrastruttura comune della checklist: esito, interfaccia Check, registry.

Ogni check produce un `EsitoCheck` con stato a semaforo, spiegazione, citazioni
(esplicabilità) e riferimenti normativi. I check sono registrati in modo che il
Modulo 1 possa eseguirli tutti in sequenza.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..fascicolo import ContestoFascicolo
from ..models import Citazione, Stato


@dataclass
class EsitoCheck:
    """Risultato dell'esecuzione di un check su un fascicolo."""

    id: str  # identificatore stabile, es. "check-1"
    titolo: str
    stato: Stato
    spiegazione: str
    citazioni: list[Citazione] = field(default_factory=list)
    riferimenti_normativi: list[str] = field(default_factory=list)


class Check:
    """Interfaccia di un controllo della checklist.

    Le sottoclassi impostano `id`, `titolo`, `riferimenti` e implementano
    `valuta`. `applicabile` permette di saltare i check non pertinenti (es. il
    termine dei 12 mesi non si applica a una revoca).
    """

    id: str = ""
    titolo: str = ""
    riferimenti: tuple[str, ...] = ()

    def applicabile(self, contesto: ContestoFascicolo) -> bool:  # noqa: D401
        return True

    def valuta(self, contesto: ContestoFascicolo) -> EsitoCheck:
        raise NotImplementedError

    # Helper per costruire esiti in modo conciso e uniforme.
    def _esito(
        self,
        stato: Stato,
        spiegazione: str,
        citazioni: list[Citazione] | None = None,
    ) -> EsitoCheck:
        return EsitoCheck(
            id=self.id,
            titolo=self.titolo,
            stato=stato,
            spiegazione=spiegazione,
            citazioni=citazioni or [],
            riferimenti_normativi=list(self.riferimenti),
        )


# Registry dei check, popolato dai moduli check*.py via `registra`.
_REGISTRY: list[Check] = []


def registra(check: Check) -> Check:
    """Aggiunge un check al registry globale (idempotente per id)."""
    if any(c.id == check.id for c in _REGISTRY):
        return check
    _REGISTRY.append(check)
    return check


def check_registrati() -> list[Check]:
    """I check registrati, ordinati per id."""
    return sorted(_REGISTRY, key=lambda c: c.id)


def esegui_checklist(contesto: ContestoFascicolo) -> list[EsitoCheck]:
    """Esegue tutti i check registrati sul contesto e raccoglie gli esiti.

    I check non applicabili producono comunque un esito NON_APPLICABILE, così il
    report resta completo e trasparente su cosa è stato (o non) valutato.
    """
    esiti: list[EsitoCheck] = []
    for check in check_registrati():
        if not check.applicabile(contesto):
            esiti.append(
                EsitoCheck(
                    id=check.id,
                    titolo=check.titolo,
                    stato=Stato.NON_APPLICABILE,
                    spiegazione="Check non applicabile a questo fascicolo.",
                    riferimenti_normativi=list(check.riferimenti),
                )
            )
            continue
        esiti.append(check.valuta(contesto))
    return esiti
