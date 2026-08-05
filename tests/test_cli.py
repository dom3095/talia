"""Test della CLI `talia analizza`."""

from pathlib import Path

from talia.modulo1_fascicolo.cli import main

_SAMPLES = Path(__file__).resolve().parents[1] / "data" / "samples"


def test_cli_analizza_cartella_stdout(capsys):
    codice = main(["analizza", str(_SAMPLES / "fascicolo_coerente")])
    assert codice == 0
    out = capsys.readouterr().out
    assert "Report TALIA" in out


def test_cli_scrive_html_su_file(tmp_path, capsys):
    out_file = tmp_path / "report.html"
    codice = main(
        [
            "analizza",
            str(_SAMPLES / "fascicolo_critico"),
            "--formato",
            "html",
            "--out",
            str(out_file),
        ]
    )
    assert codice == 0
    assert out_file.exists()
    assert "<html" in out_file.read_text(encoding="utf-8")


def test_cli_percorso_senza_file(tmp_path):
    # Cartella vuota → nessun file analizzabile → codice di errore.
    assert main(["analizza", str(tmp_path)]) == 1


def test_cli_llm_non_disponibile_da_errore_pulito(monkeypatch, capsys):
    # Regressione code review: LLMNonDisponibile (--llm senza Ollama attivo)
    # non era catturata attorno ad analizza_testi e usciva come traceback grezzo
    # invece di seguire lo stesso percorso "Errore: ..." / codice 2 usato sopra.
    from talia.engine import llm as llm_mod
    from talia.engine.checklist import check3_motivazione as check3_mod

    def _fallisce(*_args, **_kwargs):
        raise llm_mod.LLMNonDisponibile("Ollama non raggiungibile (test)")

    monkeypatch.setattr(check3_mod, "genera", _fallisce)
    codice = main(["analizza", str(_SAMPLES / "fascicolo_critico"), "--llm"])
    assert codice == 2
    assert "Errore" in capsys.readouterr().err
