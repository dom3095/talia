"""Test TAL-53: estrazione della data di approvazione della graduatoria."""

from datetime import date

from talia.engine.graduatoria import estrai_data_graduatoria
from talia.engine.pdf_text import da_testo


def test_graduatoria_approvata_con_determina():
    atto = da_testo("vista la graduatoria approvata con determinazione n. 45 del 12/03/2025")
    ent = estrai_data_graduatoria(atto)
    assert ent is not None
    assert ent.valore == date(2025, 3, 12)


def test_determina_di_approvazione_della_graduatoria():
    # "approvazione" precede "graduatoria": la finestra deve coprire entrambe le direzioni.
    atto = da_testo(
        "vista la determina di approvazione della graduatoria n. 45/2025 del 12/03/2025"
    )
    ent = estrai_data_graduatoria(atto)
    assert ent is not None
    assert ent.valore == date(2025, 3, 12)


def test_nessuna_menzione_graduatoria():
    atto = da_testo("annullamento ai sensi dell'art. 21-nonies del 30/06/2024")
    assert estrai_data_graduatoria(atto) is None


def test_graduatoria_senza_approvazione_vicina():
    # "graduatoria" c'è, ma senza "approvat[ao]"/"approvazione" nella finestra.
    atto = da_testo("si attende la pubblicazione della graduatoria entro il 12/03/2025")
    assert estrai_data_graduatoria(atto) is None


def test_graduatoria_approvata_senza_data_vicina():
    atto = da_testo("la graduatoria è stata approvata. " + "x" * 200 + " altre note del 12/03/2025")
    assert estrai_data_graduatoria(atto) is None


def test_sceglie_la_data_piu_vicina_tra_piu_menzioni():
    atto = da_testo(
        "graduatoria approvata con atto del 01/01/2020; "
        "nota estranea. "
        "seconda graduatoria approvata con determina n. 9 del 12/03/2025"
    )
    ent = estrai_data_graduatoria(atto)
    assert ent is not None
    assert ent.valore in {date(2020, 1, 1), date(2025, 3, 12)}


def test_approvata_estranea_precedente_non_scavalca_quella_della_graduatoria():
    # Regressione (code review): con due "approvat[ao]" nella finestra, la
    # prima in ordine assoluto veniva scelta anche se estranea alla
    # graduatoria — qui la data giusta (20/06/2024) segue "approvata" più
    # vicina a "graduatoria", non la prima "approvata" del testo (05/01/2024,
    # riferita alla determina di indizione).
    atto = da_testo(
        "Premesso che la determina di indizione è stata approvata il 05/01/2024. "
        "Vista la graduatoria del concorso, approvata con atto separato del 20/06/2024, "
        "si dispone quanto segue."
    )
    ent = estrai_data_graduatoria(atto)
    assert ent is not None
    assert ent.valore == date(2024, 6, 20)
