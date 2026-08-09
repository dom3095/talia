"""TAL-9/TAL-53 — Check 6: coerenza dei firmatari.

Confronta i firmatari dell'atto originario (indizione/aggiudicazione) con quelli
dell'atto di autotutela. La sovrapposizione — lo stesso soggetto che firma sia
l'atto sia il suo annullamento — è l'anomalia da verificare (auto-annullamento).

Prudenza: nei piccoli comuni un unico dirigente firma spesso tutti gli atti, il
che è fisiologico. L'esito di sovrapposizione è quindi 🟡 (da verificare) di
default, non un giudizio di illegittimità.

TAL-53 aggiunge due arricchimenti, entrambi degradano senza errore se il dato
non è disponibile (nessuna regressione sul comportamento precedente):
- il **ruolo** del firmatario (via `attori.py`, TAL-13), quando individuabile;
- l'**incrocio con la tempistica della graduatoria** (via `graduatoria.py`):
  se l'annullamento cade entro `SOGLIA_GIORNI_GRADUATORIA` giorni dalla data di
  approvazione della graduatoria, l'esito sale a 🔴 (segnale più forte di un
  annullamento distante nel tempo). Soglia euristica di prodotto, non un
  termine di legge — da validare con ⚖️ LEX (vedi TAL-53).
"""

from __future__ import annotations

from ..attori import Attore, estrai_attori
from ..fascicolo import ContestoFascicolo
from ..firmatari import nome_normalizzato
from ..graduatoria import estrai_data_graduatoria
from ..models import Entita, Stato, TestoAtto
from ._date_utils import data_estrema, filtra_date_ccnl
from .base import Check, EsitoCheck, registra

# "A ridosso" della graduatoria: soglia euristica, non normativa (vedi Note).
SOGLIA_GIORNI_GRADUATORIA = 60


class CheckCoerenzaFirmatari(Check):
    id = "check-6"
    titolo = "Coerenza dei firmatari (indizione vs annullamento)"

    def applicabile(self, contesto: ContestoFascicolo) -> bool:
        # Serve sia l'atto originario sia almeno un firmatario per parte.
        if contesto.atto_originario is None:
            return False
        return bool(
            contesto.atto_originario.entita.firmatari and contesto.atto_autotutela.entita.firmatari
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

        attori_autt = estrai_attori(contesto.atto_autotutela.testo)
        attori_orig = estrai_attori(contesto.atto_originario.testo)

        citazioni = []
        descrizioni = []
        for ent_orig, ent_autt in coppie:
            ruolo = _ruolo_di(ent_autt.valore, attori_autt) or _ruolo_di(
                ent_orig.valore, attori_orig
            )
            descrizioni.append(f"il {ruolo} {ent_autt.valore}" if ruolo else str(ent_autt.valore))
            citazioni.append(ent_orig.come_citazione(contesto.atto_originario.testo))
            citazioni.append(ent_autt.come_citazione(contesto.atto_autotutela.testo))

        elenco = ", ".join(sorted(descrizioni))

        esito_graduatoria = self._esito_graduatoria(contesto)
        if esito_graduatoria is not None:
            giorni, ent_graduatoria, testo_graduatoria = esito_graduatoria
            citazioni.append(ent_graduatoria.come_citazione(testo_graduatoria))
            return self._esito(
                Stato.ROSSO,
                f"Stesso firmatario in entrambi gli atti ({elenco}) e annullamento a "
                f"{giorni} giorni dall'approvazione della graduatoria: sovrapposizione "
                "e tempistica insieme rafforzano il sospetto di auto-annullamento "
                "strumentale, da verificare.",
                citazioni,
            )

        return self._esito(
            Stato.GIALLO,
            f"Lo stesso firmatario compare in entrambi gli atti ({elenco}): possibile "
            "auto-annullamento, da verificare (può essere fisiologico nei piccoli comuni).",
            citazioni,
        )

    def _esito_graduatoria(
        self, contesto: ContestoFascicolo
    ) -> tuple[int, Entita, TestoAtto] | None:
        """Giorni tra approvazione graduatoria e annullamento, se entrambi noti e vicini.

        Cerca la graduatoria prima nell'atto di autotutela (dove tipicamente si
        richiama l'atto approvato), poi nell'originario. L'atto di provenienza è
        tenuto esplicito (non ridedotto dopo) perché `estrai_data_graduatoria`
        richiama internamente `estrai_date` su un nuovo `TestoAtto`: l'entità
        risultante non è la stessa istanza già presente in `atto.entita.entita`,
        quindi un controllo di appartenenza per identità fallirebbe sempre e
        produrrebbe una citazione con gli offset sbagliati.
        """
        ent_graduatoria = estrai_data_graduatoria(contesto.atto_autotutela.testo)
        testo_graduatoria = contesto.atto_autotutela.testo
        if ent_graduatoria is None:
            ent_graduatoria = estrai_data_graduatoria(contesto.atto_originario.testo)
            testo_graduatoria = contesto.atto_originario.testo
        if ent_graduatoria is None:
            return None

        date_aut = filtra_date_ccnl(
            contesto.atto_autotutela.entita.date,
            contesto.atto_autotutela.testo.testo,
        )
        if testo_graduatoria is contesto.atto_autotutela.testo:
            # Escludere la stessa menzione testuale usata per ent_graduatoria:
            # senza questo, se la data della graduatoria è anche la più
            # recente data non-CCNL dell'atto (comune: spesso è l'unica data
            # citata), data_annullamento collassa sulla stessa entità e delta
            # diventa 0 — un 🔴 "annullamento a 0 giorni dalla graduatoria"
            # fuorviante, perché non misura davvero due eventi distinti
            # (bug trovato in code review). Confronto per offset, non per
            # identità: stesso motivo del bug già corretto sopra.
            date_aut = [
                e
                for e in date_aut
                if (e.offset_inizio, e.offset_fine)
                != (ent_graduatoria.offset_inizio, ent_graduatoria.offset_fine)
            ]
        data_annullamento, _ = data_estrema(date_aut, piu_recente=True)
        if data_annullamento is None:
            return None

        delta = (data_annullamento - ent_graduatoria.valore).days
        if 0 <= delta <= SOGLIA_GIORNI_GRADUATORIA:
            return delta, ent_graduatoria, testo_graduatoria
        return None


def _ruolo_di(nome: str, attori: list[Attore]) -> str | None:
    """Ruolo istituzionale del firmatario `nome`, se un attore corrispondente è noto.

    Stesso criterio di matching di `_stesso_firmatario` (sottoinsieme di token):
    un attore rilevato da `attori.py` può avere un nome con secondo nome omesso o
    ordine invertito rispetto al firmatario.
    """
    fn = nome_normalizzato(nome)
    for a in attori:
        if a.nome and _stesso_firmatario(fn, nome_normalizzato(a.nome)):
            return a.ruolo
    return None


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
