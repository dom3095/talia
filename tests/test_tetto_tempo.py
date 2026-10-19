"""Test del tetto di tempo per scraper (TAL-72).

Due livelli: il meccanismo (`tetto_tempo`, SIGALRM) e l'orchestratore
(`esegui_scraper` / `main` di `scripts/run_scrapers.py`), con scraper finti che
inseriscono atti in un DB in memoria e poi si appendono. Nessuna rete.
"""

from __future__ import annotations

import importlib.util
import signal
import socket
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from talia.modulo2_scraping.db import (
    AttoMetadato,
    EnteMetadato,
    connetti,
    inizializza_db,
    inserisci_atto,
    upsert_ente,
)
from talia.modulo2_scraping.tetto_tempo import (
    MARCATORE_ERRORE,
    TETTO_SCRAPER_DEFAULT_S,
    TettoTempoSuperato,
    descrivi_interruzione,
    e_interruzione_tetto,
    tetto_supportato,
    tetto_tempo,
)

pytestmark = pytest.mark.skipif(not tetto_supportato(), reason="richiede SIGALRM/setitimer")

_ROOT = Path(__file__).resolve().parents[1]

#: Tetto usato nei test: abbastanza corto da non rallentare la suite,
#: abbastanza lungo da non scattare per caso su una macchina CI lenta.
_TETTO = 0.3


# ---------------------------------------------------------------------------
# Meccanismo
# ---------------------------------------------------------------------------


def test_sotto_il_tetto_non_interrompe():
    with tetto_tempo(5):
        risultato = sum(range(1000))
    assert risultato == 499500


def test_tetto_interrompe_una_sleep():
    t0 = time.monotonic()
    with pytest.raises(TettoTempoSuperato):
        with tetto_tempo(_TETTO):
            time.sleep(10)
    assert time.monotonic() - t0 < 3


def test_tetto_interrompe_una_recv_bloccata():
    """Il caso reale: un host che accetta la connessione e poi non risponde."""
    a, b = socket.socketpair()
    try:
        t0 = time.monotonic()
        with pytest.raises(TettoTempoSuperato):
            with tetto_tempo(_TETTO):
                a.recv(1)  # nessuno scrive mai su `b`
        assert time.monotonic() - t0 < 3
    finally:
        a.close()
        b.close()


def test_except_exception_dello_scraper_non_la_inghiotte():
    """Gli scraper hanno retry con `except Exception`: il tetto deve passarci attraverso."""
    tentativi = 0
    with pytest.raises(TettoTempoSuperato):
        with tetto_tempo(_TETTO):
            while True:
                try:
                    tentativi += 1
                    time.sleep(0.05)
                    raise TimeoutError("host lento")
                except Exception:
                    continue
    assert tentativi > 1


@pytest.mark.parametrize("valore", [None, 0, -5])
def test_tetto_nullo_non_arma_il_timer(valore):
    with tetto_tempo(valore):
        assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)


def test_timer_e_gestore_ripristinati_dopo_uscita_normale():
    precedente = signal.getsignal(signal.SIGALRM)
    with tetto_tempo(5):
        pass
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
    assert signal.getsignal(signal.SIGALRM) is precedente


def test_timer_disarmato_anche_se_il_blocco_solleva_altro():
    with pytest.raises(ValueError):
        with tetto_tempo(5):
            raise ValueError("altro")
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)


def test_descrizione_nomina_il_punto_in_cui_era_fermo():
    def scarica_pagina_lenta():
        time.sleep(10)

    with pytest.raises(TettoTempoSuperato) as info:
        with tetto_tempo(_TETTO):
            scarica_pagina_lenta()
    testo = descrivi_interruzione(info.value)
    assert testo.startswith(MARCATORE_ERRORE)
    assert "scarica_pagina_lenta" in testo
    assert "_scaduto" not in testo
    assert e_interruzione_tetto(testo)


def test_riconoscimento_marcatore():
    assert not e_interruzione_tetto(None)
    assert not e_interruzione_tetto("urllib.error.URLError: timed out")
    assert e_interruzione_tetto("TettoTempoSuperato: interrotto dopo 1200s")


# ---------------------------------------------------------------------------
# Orchestratore
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def rs():
    spec = importlib.util.spec_from_file_location(
        "run_scrapers_tetto_test", _ROOT / "scripts" / "run_scrapers.py"
    )
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture()
def conn():
    c = connetti(":memory:")
    inizializza_db(c)
    upsert_ente(c, EnteMetadato(denominazione="Comune di Test", codice_istat="999999"))
    return c


def _inserisci(conn, n: int, prefisso: str) -> None:
    for i in range(n):
        inserisci_atto(
            conn,
            AttoMetadato(
                ente_codice_istat="999999",
                tipo="determina",
                url_fonte=f"https://albo.example.it/{prefisso}/{i}",
                fonte_scraper="test",
                data_accesso=datetime.now(UTC).isoformat(),
            ),
        )


def _ultimo_run(conn, nome):
    return conn.execute(
        "SELECT * FROM scraper_runs WHERE scraper_id=? ORDER BY id DESC LIMIT 1", (nome,)
    ).fetchone()


def _scraper_che_si_appende(conn, **_kwargs):
    """Inserisce 3 atti, poi resta appeso come un host semi-morto."""
    _inserisci(conn, 3, "lento")
    time.sleep(10)
    return {"inseriti": 3, "n_trovati": 3}


def _scraper_sano(conn, **_kwargs):
    _inserisci(conn, 2, "sano")
    return {"inseriti": 2, "n_trovati": 2, "duplicati": 0}


def _scraper_rotto(conn, **_kwargs):
    raise ConnectionRefusedError("[Errno 61] Connection refused")


def test_scraper_oltre_il_tetto_interrotto_senza_perdere_gli_atti(rs, conn):
    stato, esito = rs.esegui_scraper(conn, "lento", _scraper_che_si_appende, {}, _TETTO)

    assert stato == "interrotto"
    assert esito["inseriti"] == 3
    assert conn.execute("SELECT COUNT(*) FROM atti").fetchone()[0] == 3
    run = _ultimo_run(conn, "lento")
    assert run["completato_a"] is not None
    assert run["n_inseriti"] == 3
    assert e_interruzione_tetto(run["errore"])
    assert "_scraper_che_si_appende" in run["errore"]


def test_scraper_sotto_il_tetto_registrato_ok(rs, conn):
    stato, esito = rs.esegui_scraper(conn, "sano", _scraper_sano, {}, 5)
    assert stato == "ok"
    run = _ultimo_run(conn, "sano")
    assert run["errore"] is None
    assert run["n_inseriti"] == 2


def test_eccezione_resta_distinta_dall_interruzione(rs, conn):
    stato, _ = rs.esegui_scraper(conn, "rotto", _scraper_rotto, {}, 5)
    assert stato == "errore"
    errore = _ultimo_run(conn, "rotto")["errore"]
    assert "ConnectionRefusedError" in errore
    assert not e_interruzione_tetto(errore)


def test_conteggio_inseriti_solo_di_questo_scraper(rs, conn):
    """Gli atti già in DB da scraper precedenti non vanno attribuiti all'interrotto."""
    rs.esegui_scraper(conn, "sano", _scraper_sano, {}, 5)
    _, esito = rs.esegui_scraper(conn, "lento", _scraper_che_si_appende, {}, _TETTO)
    assert esito["inseriti"] == 3


def test_tetto_effettivo(rs):
    assert rs.tetto_effettivo(None, no_stop=False) == TETTO_SCRAPER_DEFAULT_S
    # Backfill storico: deve poter durare ore.
    assert rs.tetto_effettivo(None, no_stop=True) is None
    # Il valore esplicito vince sempre, anche in backfill.
    assert rs.tetto_effettivo(600, no_stop=True) == 600
    assert rs.tetto_effettivo(0, no_stop=False) is None


def test_main_interruzione_non_rende_il_run_fallito(rs, tmp_path, monkeypatch):
    """Uno scraper interrotto non deve far uscire il run con exit non-zero."""
    scrapers = {"lento": _scraper_che_si_appende, "sano": _scraper_sano}
    monkeypatch.setattr(rs, "_registro_e_scrapers", lambda: ([], scrapers, list(scrapers)))
    db = tmp_path / "t.db"
    c = connetti(db)
    inizializza_db(c)
    upsert_ente(c, EnteMetadato(denominazione="Comune di Test", codice_istat="999999"))
    c.close()
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_scrapers.py", "--db", str(db), "--no-red-flags", "--timeout-scraper", "1"],
    )

    assert rs.main() == 0

    c = connetti(db)
    assert e_interruzione_tetto(_ultimo_run(c, "lento")["errore"])
    # Il run è proseguito con lo scraper successivo.
    assert _ultimo_run(c, "sano")["errore"] is None
    assert c.execute("SELECT COUNT(*) FROM atti").fetchone()[0] == 5


def test_main_eccezione_rende_ancora_il_run_fallito(rs, tmp_path, monkeypatch):
    scrapers = {"rotto": _scraper_rotto}
    monkeypatch.setattr(rs, "_registro_e_scrapers", lambda: ([], scrapers, list(scrapers)))
    monkeypatch.setattr(
        sys, "argv", ["run_scrapers.py", "--db", str(tmp_path / "t.db"), "--no-red-flags"]
    )
    assert rs.main() == 1
