"""Test TAL-11: wiring del check 3 (LLM) in `analizza_fascicolo`/`analizza_testi`.

`genera` è monkeypatchato: nessuna chiamata di rete reale nella suite.
"""

from __future__ import annotations

from talia.engine.checklist import check3_motivazione as mod
from talia.engine.models import Stato
from talia.engine.pdf_text import da_testo
from talia.modulo1_fascicolo.analisi import analizza_testi


def _testo_autotutela() -> object:
    return da_testo(
        "si dispone l'annullamento della procedura senza altra indicazione "
        "normativa, considerato che urge ripristinare la legalità in via "
        "generale e senza ulteriori precisazioni sul caso concreto."
    )


def test_check3_assente_di_default():
    report = analizza_testi([_testo_autotutela()])
    assert not any(e.id == mod.ID for e in report.esiti)


def test_check3_presente_con_valuta_llm(monkeypatch):
    monkeypatch.setattr(
        mod, "genera", lambda prompt: '{"giudizio": "generica", "spiegazione": "boilerplate"}'
    )
    report = analizza_testi([_testo_autotutela()], valuta_llm=True)
    esiti_check3 = [e for e in report.esiti if e.id == mod.ID]
    assert len(esiti_check3) == 1
    # Check-1 (base giuridica) flagga già questo atto (nessun 21-quinquies/nonies)
    # → check-3 deve essere eseguito, non NON_APPLICABILE.
    assert esiti_check3[0].stato is Stato.ROSSO
