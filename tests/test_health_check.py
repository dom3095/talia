"""Test offline per scripts/health_check_registro.py (TAL-51, PR5).

Nessuna chiamata di rete reale: `urllib.request.urlopen` è mockato per ogni
scenario (200, 404, 405→fallback GET, timeout, DNS/connessione fallita).
"""

from __future__ import annotations

import importlib.util
import json
import sys
import urllib.error
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def hc():
    nome = "health_check_test_target"
    spec = importlib.util.spec_from_file_location(
        nome, _ROOT / "scripts" / "health_check_registro.py"
    )
    modulo = importlib.util.module_from_spec(spec)
    # Registrare in sys.modules PRIMA di exec_module: EsitoCheck è un dataclass
    # con `from __future__ import annotations` — la risoluzione dei tipi cerca
    # il modulo in sys.modules durante la definizione della classe.
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def _entry(hc, **overrides):
    base = dict(
        slug="test",
        denominazione="Comune di Test",
        codice_istat="999999",
        modulo="jcitygov",
        piattaforma_tecnica="Test",
        base_url="https://test.example.com",
        stato="attivo",
    )
    base.update(overrides)
    return hc.EntryRegistro(**base)


class _FintaRisposta:
    def __init__(self, status=200):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


# ---------------------------------------------------------------------------
# _verifica_url — scenari singoli
# ---------------------------------------------------------------------------


def test_verifica_url_200_ok(hc, monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda req, timeout=0, context=None: _FintaRisposta(200)
    )
    esito = hc._verifica_url(_entry(hc))
    assert esito.ok is True
    assert esito.http_status == 200
    assert esito.errore is None


def test_verifica_url_404_fallito(hc, monkeypatch):
    def _urlopen(req, timeout=0, context=None):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)
    esito = hc._verifica_url(_entry(hc))
    assert esito.ok is False
    assert esito.http_status == 404


def test_verifica_url_405_fallback_get_riesce(hc, monkeypatch):
    chiamate = []

    def _urlopen(req, timeout=0, context=None):
        chiamate.append(req.get_method())
        if req.get_method() == "HEAD":
            raise urllib.error.HTTPError(req.full_url, 405, "Method Not Allowed", {}, None)
        return _FintaRisposta(200)

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)
    esito = hc._verifica_url(_entry(hc))
    assert esito.ok is True
    assert esito.http_status == 200
    assert chiamate == ["HEAD", "GET"]


def test_verifica_url_405_fallback_get_fallisce_comunque(hc, monkeypatch):
    def _urlopen(req, timeout=0, context=None):
        raise urllib.error.HTTPError(req.full_url, 405, "Method Not Allowed", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)
    esito = hc._verifica_url(_entry(hc))
    assert esito.ok is False
    assert esito.errore is not None


def test_verifica_url_timeout(hc, monkeypatch):
    def _urlopen(req, timeout=0, context=None):
        raise TimeoutError("timed out")

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)
    esito = hc._verifica_url(_entry(hc))
    assert esito.ok is False
    assert "timed out" in esito.errore


def test_verifica_url_dns_fallito(hc, monkeypatch):
    def _urlopen(req, timeout=0, context=None):
        raise urllib.error.URLError("Name or service not known")

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)
    esito = hc._verifica_url(_entry(hc))
    assert esito.ok is False
    assert "not known" in esito.errore


def test_verifica_url_skip_ssl_passa_contesto(hc, monkeypatch):
    contesti = []

    def _urlopen(req, timeout=0, context=None):
        contesti.append(context)
        return _FintaRisposta(200)

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)
    hc._verifica_url(_entry(hc, skip_ssl=True))
    assert contesti[0] is not None
    assert contesti[0].verify_mode.name == "CERT_NONE"


def test_verifica_url_senza_skip_ssl_nessun_contesto(hc, monkeypatch):
    contesti = []

    def _urlopen(req, timeout=0, context=None):
        contesti.append(context)
        return _FintaRisposta(200)

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)
    hc._verifica_url(_entry(hc, skip_ssl=False))
    assert contesti[0] is None


# ---------------------------------------------------------------------------
# esegui_health_check — parallelismo + filtro base_url vuoto
# ---------------------------------------------------------------------------


def test_esegui_health_check_salta_base_url_vuoto(hc, monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda req, timeout=0, context=None: _FintaRisposta(200)
    )
    entries = [
        _entry(hc, slug="a", base_url="https://a.example.com"),
        _entry(hc, slug="b", base_url=None, modulo="anac"),
    ]
    risultati = hc.esegui_health_check(entries)
    assert len(risultati) == 1
    assert risultati[0].slug == "a"


def test_esegui_health_check_ordina_per_slug(hc, monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda req, timeout=0, context=None: _FintaRisposta(200)
    )
    entries = [
        _entry(hc, slug="zeta", base_url="https://z.example.com"),
        _entry(hc, slug="alfa", base_url="https://a.example.com"),
    ]
    risultati = hc.esegui_health_check(entries)
    assert [r.slug for r in risultati] == ["alfa", "zeta"]


# ---------------------------------------------------------------------------
# Exit code: bloccato/pending non contano, attivo/escluso_default sì
# ---------------------------------------------------------------------------


def test_exit_code_zero_se_tutto_ok(hc, monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda req, timeout=0, context=None: _FintaRisposta(200)
    )
    entries = [_entry(hc, slug="a", stato="attivo")]
    risultati = hc.esegui_health_check(entries)
    assert hc._exit_code(risultati) == 0


def test_exit_code_uno_se_attivo_fallisce(hc, monkeypatch):
    def _urlopen(req, timeout=0, context=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)
    entries = [_entry(hc, slug="a", stato="attivo")]
    risultati = hc.esegui_health_check(entries)
    assert hc._exit_code(risultati) == 1


def test_exit_code_zero_se_solo_bloccato_fallisce(hc, monkeypatch):
    def _urlopen(req, timeout=0, context=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)
    entries = [_entry(hc, slug="messina", stato="bloccato")]
    risultati = hc.esegui_health_check(entries)
    assert hc._exit_code(risultati) == 0


def test_exit_code_zero_se_solo_pending_fallisce(hc, monkeypatch):
    def _urlopen(req, timeout=0, context=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)
    entries = [_entry(hc, slug="c", stato="pending")]
    risultati = hc.esegui_health_check(entries)
    assert hc._exit_code(risultati) == 0


def test_exit_code_uno_se_escluso_default_fallisce(hc, monkeypatch):
    def _urlopen(req, timeout=0, context=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)
    entries = [_entry(hc, slug="agrigento", stato="escluso_default")]
    risultati = hc.esegui_health_check(entries)
    assert hc._exit_code(risultati) == 1


# ---------------------------------------------------------------------------
# Output: summary Markdown + JSON
# ---------------------------------------------------------------------------


def test_scrivi_summary_md_contiene_falliti_critici(hc, monkeypatch, tmp_path):
    def _urlopen(req, timeout=0, context=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)
    entries = [_entry(hc, slug="a", denominazione="Comune di A", stato="attivo")]
    risultati = hc.esegui_health_check(entries)

    percorso = tmp_path / "summary.md"
    hc._scrivi_summary_md(risultati, str(percorso))
    contenuto = percorso.read_text(encoding="utf-8")
    assert "Comune di A" in contenuto
    assert "Falliti inattesi" in contenuto


def test_scrivi_summary_md_nessun_fallimento_critico(hc, monkeypatch, tmp_path):
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda req, timeout=0, context=None: _FintaRisposta(200)
    )
    entries = [_entry(hc, slug="a", stato="attivo")]
    risultati = hc.esegui_health_check(entries)

    percorso = tmp_path / "summary.md"
    hc._scrivi_summary_md(risultati, str(percorso))
    contenuto = percorso.read_text(encoding="utf-8")
    assert "Nessun fallimento inatteso" in contenuto


def test_scrivi_summary_md_falliti_attesi_separati(hc, monkeypatch, tmp_path):
    def _urlopen(req, timeout=0, context=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", _urlopen)
    entries = [_entry(hc, slug="messina", denominazione="Comune di Messina", stato="bloccato")]
    risultati = hc.esegui_health_check(entries)

    percorso = tmp_path / "summary.md"
    hc._scrivi_summary_md(risultati, str(percorso))
    contenuto = percorso.read_text(encoding="utf-8")
    assert "Comune di Messina" in contenuto
    assert "Falliti attesi" in contenuto
    assert "Falliti inattesi" not in contenuto


def test_scrivi_json_serializza_tutti_i_campi(hc, monkeypatch, tmp_path):
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda req, timeout=0, context=None: _FintaRisposta(200)
    )
    entries = [_entry(hc, slug="a", stato="attivo")]
    risultati = hc.esegui_health_check(entries)

    percorso = tmp_path / "report.json"
    hc._scrivi_json(risultati, str(percorso))
    dati = json.loads(percorso.read_text(encoding="utf-8"))
    assert len(dati) == 1
    assert dati[0]["slug"] == "a"
    assert dati[0]["ok"] is True
