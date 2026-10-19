"""Test del riepilogo stato run scraper (TAL-66)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from talia.modulo2_scraping.db import connetti, inizializza_db
from talia.modulo2_scraping.run_report import (
    GIORNI_PERDITA_DATI,
    MAX_ELENCO,
    StatoScraper,
    causa_errore,
    formatta_markdown,
    riepiloga,
    sintesi_errore,
    trova_causa_dominante,
)


def _giorni_fa(n: float) -> str:
    return (datetime.now(UTC) - timedelta(days=n)).replace(tzinfo=None).isoformat()


def _run(
    conn,
    scraper_id: str,
    *,
    giorni_fa: float = 0.1,
    trovati: int = 10,
    inseriti: int = 5,
    errore: str | None = None,
    completato: bool = True,
) -> None:
    avviato = _giorni_fa(giorni_fa)
    conn.execute(
        """INSERT INTO scraper_runs
           (scraper_id, avviato_a, completato_a, n_trovati, n_inseriti, n_duplicati, errore)
           VALUES (?, ?, ?, ?, ?, 0, ?)""",
        (scraper_id, avviato, avviato if completato else None, trovati, inseriti, errore),
    )
    conn.commit()


@pytest.fixture()
def conn():
    c = connetti(":memory:")
    inizializza_db(c)
    return c


# ---------------------------------------------------------------------------
# Classificazione degli esiti
# ---------------------------------------------------------------------------


def test_run_ok(conn):
    _run(conn, "alfa")
    r = riepiloga(conn)
    assert (r.totale, r.ok) == (1, 1)
    assert not r.ha_problemi


def test_run_fallito(conn):
    _run(conn, "alfa", errore="ConnectionRefusedError: [Errno 61]")
    r = riepiloga(conn)
    assert [s.scraper_id for s in r.falliti] == ["alfa"]
    assert r.ok == 0
    assert r.ha_problemi


def test_run_muto_e_distinto_da_fallito(conn):
    """0 atti trovati senza eccezione: parsing rotto in silenzio, non un errore."""
    _run(conn, "alfa", trovati=0, inseriti=0)
    r = riepiloga(conn)
    assert [s.scraper_id for s in r.muti] == ["alfa"]
    assert r.falliti == []


def test_run_incompleto_non_e_muto(conn):
    """Un run mai terminato (processo ucciso) non va contato come 0 atti."""
    _run(conn, "alfa", trovati=0, inseriti=0, completato=False)
    r = riepiloga(conn)
    assert r.muti == []


def test_scraper_fermo(conn):
    _run(conn, "alfa", giorni_fa=10)
    _run(conn, "beta", giorni_fa=0.1)
    r = riepiloga(conn, giorni_stale=3)
    assert [s.scraper_id for s in r.fermi] == ["alfa"]


def test_solo_ultimo_run_per_scraper(conn):
    _run(conn, "alfa", giorni_fa=5, errore="vecchio errore")
    _run(conn, "alfa", giorni_fa=0.1, trovati=7, inseriti=7)
    r = riepiloga(conn)
    assert r.totale == 1
    assert r.falliti == []
    assert r.atti_inseriti == 7


def test_mai_eseguiti(conn):
    _run(conn, "alfa")
    r = riepiloga(conn, scraper_attesi=["alfa", "beta", "gamma"])
    assert r.mai_eseguiti == ["beta", "gamma"]
    assert r.ha_problemi


def test_rischio_perdita_dati(conn):
    _run(conn, "alfa", giorni_fa=GIORNI_PERDITA_DATI + 1)
    assert riepiloga(conn).rischio_perdita_dati


def test_nessun_rischio_se_run_recente(conn):
    _run(conn, "alfa", giorni_fa=1)
    assert not riepiloga(conn).rischio_perdita_dati


def test_db_vuoto(conn):
    r = riepiloga(conn)
    assert (r.totale, r.ok, r.giorni_da_ultimo_run) == (0, 0, None)
    assert "Nessun problema" in formatta_markdown(r)


# ---------------------------------------------------------------------------
# Sintesi dell'errore
# ---------------------------------------------------------------------------


def test_sintesi_errore_trova_l_eccezione_in_coda():
    tb = (
        'Traceback (most recent call last):\n  File "x.py", line 1\n'
        "    fn()\nTimeoutError: timed out\n"
    )
    assert sintesi_errore(tb) == "TimeoutError: timed out"


def test_sintesi_errore_trova_l_eccezione_in_testa():
    """Formato nuovo (TAL-66): l'eccezione è messa in testa prima di troncare."""
    tb = 'urllib.error.URLError: <urlopen error>\nTraceback (most recent call last):\n  File "x.py"'
    assert sintesi_errore(tb) == "urllib.error.URLError: <urlopen error>"


def test_sintesi_errore_traceback_troncato_senza_eccezione():
    """Formato vecchio già in DB: traccia tagliata prima della riga utile."""
    tb = 'Traceback (most recent call last):\n  File "x.py", line 1, in run\n    esito = fn(conn)'
    assert sintesi_errore(tb) == "esito = fn(conn)"


def test_sintesi_errore_vuoto():
    assert sintesi_errore(None) == "errore non registrato"


# ---------------------------------------------------------------------------
# Formattazione
# ---------------------------------------------------------------------------


def test_markdown_elenca_i_problemi(conn):
    _run(conn, "alfa", errore="TimeoutError: timed out")
    _run(conn, "beta", trovati=0, inseriti=0)
    testo = formatta_markdown(riepiloga(conn))
    assert "`alfa`" in testo and "TimeoutError: timed out" in testo
    assert "`beta`" in testo
    assert "Nessun problema" not in testo


def test_markdown_tronca_gli_elenchi_lunghi(conn):
    for i in range(MAX_ELENCO + 5):
        _run(conn, f"s{i:02d}", giorni_fa=10)
    testo = formatta_markdown(riepiloga(conn, giorni_stale=3))
    assert "e altri 5" in testo


def test_markdown_avvisa_del_rischio_perdita_dati(conn):
    _run(conn, "alfa", giorni_fa=GIORNI_PERDITA_DATI + 1)
    assert "non sono più recuperabili" in formatta_markdown(riepiloga(conn))


def test_markdown_tronca_anche_i_mai_eseguiti(conn):
    _run(conn, "alfa")
    attesi = ["alfa"] + [f"s{i:02d}" for i in range(MAX_ELENCO + 3)]
    testo = formatta_markdown(riepiloga(conn, scraper_attesi=attesi))
    assert "e altri 3" in testo


# ---------------------------------------------------------------------------
# Scraper non previsti dal run automatico (TAL-68)
# ---------------------------------------------------------------------------


def test_scraper_non_previsto_non_e_un_problema(conn):
    """Corleone/Messina sono `bloccato` nel registro, ANAC richiede --anac-file.

    Il loro ultimo run è vecchio e fallito *per definizione*: contarli farebbe
    scattare la notifica ogni singola notte.
    """
    _run(conn, "alfa")
    _run(conn, "corleone", giorni_fa=12, errore="URLError: host unreachable")
    _run(conn, "anac", giorni_fa=41, trovati=0, inseriti=0)

    r = riepiloga(conn, scraper_attesi=["alfa"])
    assert not r.ha_problemi
    assert [s.scraper_id for s in r.non_previsti] == ["anac", "corleone"]
    assert r.falliti == [] and r.muti == [] and r.fermi == []
    assert r.totale == 1  # solo gli attesi


def test_scraper_non_previsti_elencati_come_informativi(conn):
    _run(conn, "alfa")
    _run(conn, "corleone", giorni_fa=12, errore="URLError")
    testo = formatta_markdown(riepiloga(conn, scraper_attesi=["alfa"]))
    assert "Nessun problema" in testo
    assert "Non previsti dal run automatico (1)" in testo
    assert "`corleone`" in testo


def test_extra_scraper_atteso_torna_monitorato(conn):
    """Agrigento è `escluso_default` ma il run notturno lo include: i suoi
    fallimenti devono essere segnalati."""
    _run(conn, "alfa")
    _run(conn, "agrigento", errore="TimeoutError: timed out")
    assert not riepiloga(conn, scraper_attesi=["alfa"]).ha_problemi
    r = riepiloga(conn, scraper_attesi=["alfa", "agrigento"])
    assert [s.scraper_id for s in r.falliti] == ["agrigento"]


def test_senza_scraper_attesi_non_si_filtra_nulla(conn):
    _run(conn, "corleone", giorni_fa=12, errore="URLError")
    r = riepiloga(conn)
    assert r.non_previsti == []
    assert [s.scraper_id for s in r.falliti] == ["corleone"]


# ---------------------------------------------------------------------------
# TAL-72 — interruzioni per tetto di tempo e causa dominante
# ---------------------------------------------------------------------------

_DNS_MAC = (
    "urllib.error.URLError: <urlopen error [Errno 8] nodename nor servname provided, or not known>"
)
_DNS_LINUX = "urllib.error.URLError: <urlopen error [Errno -2] Name or service not known>"
_TETTO = "TettoTempoSuperato: interrotto dopo 1200s (tetto per scraper, TAL-72)\nfermo in: recv"


def test_interrotto_distinto_da_fallito(conn):
    _run(conn, "adrano", trovati=32, inseriti=32, errore=_TETTO)
    r = riepiloga(conn)
    assert [s.scraper_id for s in r.interrotti] == ["adrano"]
    assert r.falliti == []


def test_interrotto_non_e_un_problema(conn):
    """Un host lento interrotto non deve far suonare la notifica ogni notte."""
    _run(conn, "ok1")
    _run(conn, "baucina", trovati=0, inseriti=0, errore=_TETTO)
    assert not riepiloga(conn).ha_problemi


def test_markdown_interrotto_che_inseriva_segnala_tetto_basso(conn):
    _run(conn, "adrano", trovati=32, inseriti=32, errore=_TETTO)
    _run(conn, "baucina", trovati=0, inseriti=0, errore=_TETTO)
    md = formatta_markdown(riepiloga(conn))
    assert "Interrotti per tetto di tempo" in md
    riga_adrano = next(r for r in md.splitlines() if "`adrano`" in r)
    riga_baucina = next(r for r in md.splitlines() if "`baucina`" in r)
    assert "tetto è troppo basso" in riga_adrano
    assert "tetto è troppo basso" not in riga_baucina


def test_causa_errore_raggruppa_dns_macos_e_linux():
    assert causa_errore(_DNS_MAC) == causa_errore(_DNS_LINUX)
    assert causa_errore(_DNS_MAC).locale


def test_causa_errore_timeout_con_ssl_nei_frame_non_e_ssl():
    """Si classifica sulla riga dell'eccezione, non sui frame del traceback."""
    errore = (
        "TimeoutError: The read operation timed out\n"
        'File "/usr/lib/python3.12/ssl.py", line 1103, in read'
    )
    assert causa_errore(errore).descrizione == "timeout di rete"


def test_causa_errore_sconosciuta_resta_raggruppabile():
    a = causa_errore("ValueError: tabella senza colonne")
    b = causa_errore("ValueError: tabella senza colonne")
    assert a == b
    assert not a.locale


def test_giornata_con_guasto_dns(conn):
    """Il 31/08: 225 errori DNS su 232 — un guasto, non 225 portali rotti."""
    for i in range(225):
        _run(conn, f"dns{i:03d}", trovati=0, inseriti=0, errore=_DNS_MAC)
    for i in range(7):
        _run(conn, f"ssl{i}", trovati=0, inseriti=0, errore="ssl.SSLError: [SSL] handshake")
    r = riepiloga(conn)
    assert r.causa_dominante is not None
    assert r.causa_dominante.descrizione == "risoluzione DNS fallita"
    assert [s.scraper_id for s in r.falliti_per_altra_causa] == [f"ssl{i}" for i in range(7)]

    md = formatta_markdown(r)
    assert "225 dei 232 falliti hanno la stessa causa: risoluzione DNS fallita" in md
    assert "rete locale" in md
    # Le rotture vere sono elencate; le 225 righe DNS no.
    assert "Falliti per altre cause (7)" in md
    assert "`dns000`" not in md
    # È comunque un problema: la giornata è persa.
    assert r.ha_problemi


def test_giornata_con_rotture_vere_nessuna_causa_dominante(conn):
    cause = [
        _DNS_MAC,
        "ssl.SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]",
        "TimeoutError: timed out",
        "ConnectionRefusedError: [Errno 61] Connection refused",
        "ValueError: pagina corrotta",
    ]
    for i in range(15):
        _run(conn, f"s{i:02d}", trovati=0, inseriti=0, errore=cause[i % len(cause)])
    r = riepiloga(conn)
    assert r.causa_dominante is None
    md = formatta_markdown(r)
    assert "stessa causa" not in md
    assert "## ❌ Falliti (15)" in md


def test_pochi_falliti_uguali_non_fanno_causa_dominante(conn):
    for i in range(3):
        _run(conn, f"s{i}", trovati=0, inseriti=0, errore=_DNS_MAC)
    assert riepiloga(conn).causa_dominante is None


def test_interrotti_esclusi_dal_calcolo_della_causa_dominante():
    stati = [StatoScraper(f"s{i}", None, "x", 0, 0, _TETTO, 0.1) for i in range(20)] + [
        StatoScraper(f"d{i}", None, "x", 0, 0, _DNS_MAC, 0.1) for i in range(2)
    ]
    falliti = [s for s in stati if s.fallito]
    assert len(falliti) == 2
    assert trova_causa_dominante(falliti) is None
