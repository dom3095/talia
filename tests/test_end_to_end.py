"""Test end-to-end del Modulo 1 sui fascicoli campione anonimizzati."""

from pathlib import Path

import pytest

from talia.engine.pdf_text import da_testo
from talia.modulo1_fascicolo.analisi import analizza_testi

_SAMPLES = Path(__file__).resolve().parents[1] / "data" / "samples"


def _carica_fascicolo(nome: str):
    cartella = _SAMPLES / nome
    file = sorted(cartella.glob("*.txt"))
    return [da_testo(f.read_text(encoding="utf-8"), percorso=f.name) for f in file]


def _esiti_per_id(report):
    return {e.id: e.stato.value for e in report.esiti}


def test_fascicolo_coerente_tutto_verde():
    report = analizza_testi(_carica_fascicolo("fascicolo_coerente"))
    esiti = _esiti_per_id(report)
    assert esiti["check-1"] == "verde"
    assert esiti["check-2"] == "verde"
    assert esiti["check-5"] == "verde"
    assert esiti["check-6"] == "verde"


def test_fascicolo_critico_segnala_red_flags():
    report = analizza_testi(_carica_fascicolo("fascicolo_critico"))
    esiti = _esiti_per_id(report)
    assert esiti["check-1"] == "rosso"  # 21-nonies ma motivazione da revoca
    assert esiti["check-2"] == "rosso"  # oltre 12 mesi
    assert esiti["check-5"] == "rosso"  # nessuna comunicazione di avvio
    assert esiti["check-6"] == "giallo"  # stesso firmatario


def test_ogni_red_flag_ha_citazione():
    """DoD: ogni esito rosso/giallo deve essere esplicabile (citazione)."""
    report = analizza_testi(_carica_fascicolo("fascicolo_critico"))
    for esito in report.esiti:
        if esito.stato.value in {"rosso", "giallo"} and esito.id != "check-5":
            # check-5 segnala un'assenza: non ha un passaggio da citare.
            assert esito.citazioni, f"{esito.id} senza citazione"


@pytest.mark.parametrize("nome", ["fascicolo_coerente", "fascicolo_critico"])
def test_report_renderizza_in_ogni_formato(nome):
    report = analizza_testi(_carica_fascicolo(nome))
    assert report.to_markdown()
    assert report.to_json()
    assert report.to_html()
