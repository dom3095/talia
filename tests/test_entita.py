"""Test TAL-4: estrazione di date, importi, CIG, CUP (con casi negativi)."""

from datetime import date
from decimal import Decimal

from talia.engine.entita import estrai_cig, estrai_cup, estrai_date, estrai_importi
from talia.engine.pdf_text import da_testo


def test_date_numeriche_e_testuali():
    atto = da_testo("adottata il 10/03/2024 e pubblicata il 12 giugno 2026")
    valori = {e.valore for e in estrai_date(atto)}
    assert date(2024, 3, 10) in valori
    assert date(2026, 6, 12) in valori


def test_data_invalida_scartata():
    # 31/02 non esiste: non deve essere estratta.
    atto = da_testo("protocollo 31/02/2024")
    assert estrai_date(atto) == []


def test_date_portano_offset_e_pagina():
    atto = da_testo("del 10/03/2024")
    ent = estrai_date(atto)[0]
    assert atto.testo[ent.offset_inizio:ent.offset_fine] == "10/03/2024"
    assert ent.pagina == 1


def test_importi_normalizzati():
    atto = da_testo("per un importo di € 1.234,56 oltre IVA e altri 500 euro")
    valori = {e.valore for e in estrai_importi(atto)}
    assert Decimal("1234.56") in valori
    assert Decimal("500") in valori


def test_importo_richiede_valuta():
    # Un numero senza euro non è un importo.
    atto = da_testo("la pratica n. 1.234 del registro")
    assert estrai_importi(atto) == []


def test_cig_etichettato():
    atto = da_testo("Gara CIG: A1B2C3D4E5 affidata")
    cig = estrai_cig(atto)
    assert len(cig) == 1
    assert cig[0].valore == "A1B2C3D4E5"


def test_cig_non_confonde_protocollo():
    # Numero di 10 cifre senza etichetta CIG → nessun match.
    atto = da_testo("protocollo 1234567890 del registro")
    assert estrai_cig(atto) == []


def test_cup_etichettato():
    atto = da_testo("Progetto CUP B12C34567890123 finanziato")
    cup = estrai_cup(atto)
    assert len(cup) == 1
    assert cup[0].valore == "B12C34567890123"
    assert len(cup[0].valore) == 15
