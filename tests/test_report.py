"""Test TAL-10: modello Report e rese (markdown, JSON, HTML)."""

import json

from talia.engine.pdf_text import da_testo
from talia.modulo1_fascicolo.analisi import analizza_testi


def _report():
    indizione = da_testo("indizione del concorso\nF.to Dott. Mario Rossi")
    annullamento = da_testo(
        "annullamento d'ufficio art. 21-nonies per illegittimità, "
        "comunicazione di avvio del procedimento\nF.to Dott.ssa Anna Bianchi"
    )
    return analizza_testi([indizione, annullamento])


def test_conteggio_somma_agli_esiti():
    report = _report()
    assert sum(report.conteggio.values()) == len(report.esiti)


def test_markdown_contiene_disclaimer_e_titoli():
    md = _report().to_markdown()
    assert "verificare" in md.lower()
    assert "Base giuridica" in md


def test_json_valido_e_strutturato():
    dati = json.loads(_report().to_json())
    assert "esiti" in dati and "disclaimer" in dati
    assert all("stato" in e for e in dati["esiti"])


def test_html_escaping_e_disclaimer():
    html = _report().to_html()
    assert "<html" in html
    assert "disclaimer" in html
