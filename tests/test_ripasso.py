"""Test del ripasso a fine run degli scraper falliti per cause transitorie (TAL-75).

Scraper finti su DB in memoria, nessuna rete: si verifica quali errori vengono
ritentati, che il recupero risulti OK in `scraper_runs` e che il budget di
tempo fermi il ripasso.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from talia.modulo2_scraping.db import EnteMetadato, connetti, inizializza_db, upsert_ente
from talia.modulo2_scraping.run_report import e_transitorio

_ROOT = Path(__file__).resolve().parents[1]

# Righe d'eccezione prese da `scraper_runs` reale (settimana 12-19/10/2026).
_TIMEOUT = "TimeoutError: The read operation timed out\nTraceback (most recent call last):"
_HANDSHAKE = "urllib.error.URLError: <urlopen error _ssl.c:983: The handshake operation timed out>"
_RESET = "urllib.error.URLError: <urlopen error [Errno 54] Connection reset by peer>"
_TRONCATA = "http.client.IncompleteRead: IncompleteRead(7173 bytes read, 82681 more expected)"
_DNS = "urllib.error.URLError: <urlopen error [Errno 8] nodename nor servname provided>"
_CERT = (
    "urllib.error.URLError: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate"
    " verify failed: unable to get local issuer certificate (_ssl.c:1006)>"
)
_403 = "urllib.error.HTTPError: HTTP Error 403: Forbidden"


@pytest.mark.parametrize("errore", [_TIMEOUT, _HANDSHAKE, _RESET, _TRONCATA, _DNS])
def test_errori_di_rete_sono_transitori(errore):
    assert e_transitorio(errore)


_HANDSHAKE_FAILURE = (
    "ssl.SSLError: [SSL: SSLV3_ALERT_HANDSHAKE_FAILURE] sslv3 alert handshake failure"
)


@pytest.mark.parametrize("errore", [_CERT, _403, _HANDSHAKE_FAILURE, None, ""])
def test_errori_strutturali_non_si_ritentano(errore):
    assert not e_transitorio(errore)


def test_cert_con_timeout_nel_traceback_resta_strutturale():
    """Conta la riga dell'eccezione, non un `timeout=30` nei frame."""
    errore = f'{_CERT}\n  File "x.py", line 3, in _get\n    urlopen(req, timeout=30)'
    assert not e_transitorio(errore)


@pytest.fixture(scope="module")
def rs():
    spec = importlib.util.spec_from_file_location(
        "run_scrapers_ripasso_test", _ROOT / "scripts" / "run_scrapers.py"
    )
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture()
def conn():
    c = connetti(":memory:")
    inizializza_db(c)
    return c


def _instabile():
    """Scraper che fallisce per timeout al primo tentativo e riesce al secondo."""
    chiamate = {"n": 0}

    def _fn(conn, **_kwargs):
        chiamate["n"] += 1
        if chiamate["n"] == 1:
            raise TimeoutError("The read operation timed out")
        return {"inseriti": 0, "n_trovati": 4, "duplicati": 4}

    _fn.chiamate = chiamate
    return _fn


def _cert_rotto(conn, **_kwargs):
    raise OSError("[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")


def _ultimo_run(conn, nome):
    return conn.execute(
        "SELECT * FROM scraper_runs WHERE scraper_id=? ORDER BY id DESC LIMIT 1", (nome,)
    ).fetchone()


def test_ripasso_recupera_il_fallito_transitorio(rs, conn):
    fn = _instabile()
    stato, esito = rs.esegui_scraper(conn, "catania", fn, {}, None)
    assert stato == "errore"

    ripasso = rs.ripassa_transitori(
        conn, {"catania": esito["errore"]}, {"catania": fn}, {}, None, 3600
    )

    assert ripasso["catania"][0] == "ok"
    assert fn.chiamate["n"] == 2
    # Il report legge l'ultima riga: ora è un successo, la prima resta in storico.
    assert _ultimo_run(conn, "catania")["errore"] is None
    n = conn.execute("SELECT COUNT(*) FROM scraper_runs WHERE scraper_id='catania'")
    assert n.fetchone()[0] == 2


def test_ripasso_ignora_gli_errori_strutturali(rs, conn):
    _, esito = rs.esegui_scraper(conn, "condro", _cert_rotto, {}, None)
    ripasso = rs.ripassa_transitori(
        conn, {"condro": esito["errore"]}, {"condro": _cert_rotto}, {}, None, 3600
    )
    assert ripasso == {}


def test_budget_esaurito_ferma_il_ripasso(rs, conn):
    tempi = iter([0, 0, 4000])  # inizio, primo controllo, secondo controllo
    scrapers = {"a": _instabile(), "b": _instabile()}
    falliti = {"a": _TIMEOUT, "b": _TIMEOUT}

    ripasso = rs.ripassa_transitori(
        conn, falliti, scrapers, {}, None, 3600, orologio=lambda: next(tempi)
    )

    assert list(ripasso) == ["a"]
    assert scrapers["b"].chiamate["n"] == 0


def _main(rs, tmp_path, monkeypatch, scrapers, *extra):
    monkeypatch.setattr(rs, "_registro_e_scrapers", lambda: ([], scrapers, list(scrapers)))
    db = tmp_path / "t.db"
    c = connetti(db)
    inizializza_db(c)
    upsert_ente(c, EnteMetadato(denominazione="Comune di Test", codice_istat="999999"))
    c.close()
    monkeypatch.setattr(sys, "argv", ["run_scrapers.py", "--db", str(db), "--no-red-flags", *extra])
    return rs.main()


def test_main_recupero_al_ripasso_non_rende_il_run_fallito(rs, tmp_path, monkeypatch):
    assert _main(rs, tmp_path, monkeypatch, {"catania": _instabile()}) == 0


def test_main_senza_ripasso_resta_fallito(rs, tmp_path, monkeypatch):
    scrapers = {"catania": _instabile()}
    assert _main(rs, tmp_path, monkeypatch, scrapers, "--budget-ripasso", "0") == 1
    assert scrapers["catania"].chiamate["n"] == 1


def test_main_errore_strutturale_resta_fallito(rs, tmp_path, monkeypatch):
    assert _main(rs, tmp_path, monkeypatch, {"condro": _cert_rotto}) == 1
