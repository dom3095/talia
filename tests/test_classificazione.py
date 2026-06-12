"""Test della classificazione ruoli (analisi.py).

Casi di regressione derivati dal primo fascicolo reale (TAL-12): i testi qui
sono sintetizzati/anonimizzati, ma riproducono i pattern che avevano ingannato
il classificatore.
"""

from talia.engine.fascicolo import AttoAnalizzato, RuoloAtto
from talia.engine.pdf_text import da_testo
from talia.modulo1_fascicolo.analisi import (
    classifica_ruolo,
    costruisci_contesto,
    punteggi_ruolo,
)


def test_bando_con_clausola_di_riserva_non_e_autotutela():
    # Regressione: "si riserva di revocare" è boilerplate dei bandi, non
    # qualifica l'atto come autotutela.
    bando = da_testo(
        "Approvazione dell'avviso di selezione interna. Bando di selezione. "
        "L'amministrazione si riserva la facoltà di revocare la procedura. "
        "Si riserva altresì di revocare il presente avviso."
    )
    assert classifica_ruolo(bando) is RuoloAtto.ORIGINARIO


def test_revoca_in_autotutela_e_autotutela():
    revoca = da_testo(
        "OGGETTO: REVOCA IN AUTOTUTELA DELL'AVVISO DI SELEZIONE INTERNA. "
        "Ritenuto opportuno procedere alla revoca in autotutela della procedura. "
        "DETERMINA la revoca in autotutela dell'avviso di selezione."
    )
    assert classifica_ruolo(revoca) is RuoloAtto.AUTOTUTELA


def test_21quinquies_senza_trattino_conta_come_segnale_forte():
    atto = da_testo("revoca ai sensi dell'art. 21 quinquies della L. 241/1990")
    aut, _ = punteggi_ruolo(atto)
    assert aut >= 3


def test_contesto_sceglie_autotutela_migliore_non_il_primo():
    # Regressione: con più candidati l'ordine dei file non deve contare.
    debole = AttoAnalizzato.da_testo(
        da_testo("nota che richiama una revoca precedente"), RuoloAtto.AUTOTUTELA
    )
    forte = AttoAnalizzato.da_testo(
        da_testo("DETERMINA la revoca in autotutela della selezione, in autotutela"),
        RuoloAtto.AUTOTUTELA,
    )
    contesto = costruisci_contesto([debole, forte])
    assert contesto.atto_autotutela is forte


def test_contesto_sceglie_originario_migliore():
    allegato = AttoAnalizzato.da_testo(
        da_testo("avviso di selezione, attestazione contabile"), RuoloAtto.ORIGINARIO
    )
    determina = AttoAnalizzato.da_testo(
        da_testo("Approvazione dell'avviso di selezione. Indizione della procedura."),
        RuoloAtto.ORIGINARIO,
    )
    autotutela = AttoAnalizzato.da_testo(
        da_testo("revoca in autotutela della selezione"), RuoloAtto.AUTOTUTELA
    )
    contesto = costruisci_contesto([allegato, determina, autotutela])
    assert contesto.atto_originario is determina
