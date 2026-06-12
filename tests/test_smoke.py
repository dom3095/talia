"""Smoke test: il pacchetto si importa e le API principali sono raggiungibili."""

import talia
from talia.engine.checklist import check_registrati
from talia.modulo1_fascicolo.analisi import analizza_testi


def test_versione_e_disclaimer():
    assert talia.__version__
    assert "verificare" in talia.DISCLAIMER.lower()


def test_check_registrati_non_vuoto():
    ids = {c.id for c in check_registrati()}
    assert {"check-1", "check-2", "check-5", "check-6"} <= ids


def test_api_analisi_importabile():
    assert callable(analizza_testi)
