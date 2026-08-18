"""Test per talia.modulo2_scraping.utils (TAL-65: estrai_cig/estrai_cig_padre)."""

from talia.modulo2_scraping.utils import estrai_cig, estrai_cig_padre


def test_estrai_cig_semplice():
    assert estrai_cig("Affidamento CIG: A1B2C3D4E5 alla ditta X") == "A1B2C3D4E5"


def test_estrai_cig_nessun_match():
    assert estrai_cig("nessun codice qui") is None


def test_estrai_cig_e_cig_padre_distinti():
    testo = "Adesione CIG PADRE 8986139C7B E CIG DERIVATO 9200965C81 - liquidazione."
    assert estrai_cig(testo) == "9200965C81"
    assert estrai_cig_padre(testo) == "8986139C7B"


def test_estrai_cig_padre_none_se_assente():
    assert estrai_cig_padre("Affidamento CIG: A1B2C3D4E5 alla ditta X") is None
