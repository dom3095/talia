"""Test TAL-4: estrazione di date, importi, CIG, CUP (con casi negativi)."""

from datetime import date
from decimal import Decimal

from talia.engine.entita import (
    estrai_cig,
    estrai_cig_gerarchia,
    estrai_cup,
    estrai_date,
    estrai_importi,
)
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
    assert atto.testo[ent.offset_inizio : ent.offset_fine] == "10/03/2024"
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


def test_cig_padre_e_derivato_distinti():
    # TAL-65: un accordo quadro cita sia il CIG padre sia quello derivato —
    # vanno riconosciuti come due codici distinti, non confusi tra loro.
    atto = da_testo("Adesione all'accordo quadro, CIG PADRE 8986139C7B E CIG DERIVATO 9200965C81.")
    trovati = {e.valore for e in estrai_cig(atto)}
    assert trovati == {"8986139C7B", "9200965C81"}

    proprio, padre = estrai_cig_gerarchia(atto.testo)
    assert proprio == "9200965C81"
    assert padre == "8986139C7B"


def test_cig_originario_non_scambiato_per_codice():
    # Bug reale: "CIG ORIGINARIO" è 10 lettere, un fallback ingenuo lo
    # scambiava per un codice vero invece di leggerlo come etichetta.
    atto = da_testo("Proroga adesione CIG ORIGINARIO N.7726942399 - CIG DERIVATO Z232F5EB88.")
    trovati = {e.valore for e in estrai_cig(atto)}
    assert "ORIGINARIO" not in trovati
    assert trovati == {"7726942399", "Z232F5EB88"}

    proprio, padre = estrai_cig_gerarchia(atto.testo)
    assert proprio == "Z232F5EB88"
    assert padre == "7726942399"


def test_cig_padre_senza_derivato_non_genera_falso_proprio():
    # Se il testo cita solo il CIG padre (nessun derivato/semplice), il CIG
    # "proprio" dell'atto resta None — non va confuso col padre.
    proprio, padre = estrai_cig_gerarchia("Determina nell'ambito del CIG PADRE 8986139C7B.")
    assert proprio is None
    assert padre == "8986139C7B"


def test_cup_etichettato():
    atto = da_testo("Progetto CUP B12C34567890123 finanziato")
    cup = estrai_cup(atto)
    assert len(cup) == 1
    assert cup[0].valore == "B12C34567890123"
    assert len(cup[0].valore) == 15
