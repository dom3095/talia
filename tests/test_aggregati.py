"""Test aggregati temporali della dashboard (TAL-67).

Funzioni pure di query: nessuno Streamlit coinvolto, quindi niente
`importorskip` — girano sempre.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from talia.modulo2_scraping.db import (
    AttoMetadato,
    EnteMetadato,
    connetti,
    inizializza_db,
    inserisci_atto,
    upsert_ente,
)
from talia.modulo3_dashboard import aggregati as agg

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

_ENTI = [
    ("Comune di Alfa", "084001", "AG"),
    ("Comune di Beta", "084002", "AG"),
    ("Comune di Gamma", "087001", "CT"),
]


def _atto(
    istat: str, n: int, *, data_atto=None, data_pub=None, data_accesso="2026-01-01"
) -> AttoMetadato:
    return AttoMetadato(
        ente_codice_istat=istat,
        tipo="determina",
        url_fonte=f"https://example.com/{istat}/{n}",
        fonte_scraper="test",
        data_accesso=f"{data_accesso}T10:00:00+00:00",
        oggetto=f"Atto {n}",
        data_atto=data_atto,
        data_pub=data_pub,
    )


def _oggi_utc(conn) -> str:
    """ "Oggi" secondo SQLite (UTC), non secondo il fuso locale del runner."""
    return conn.execute("SELECT date('now')").fetchone()[0]


@pytest.fixture()
def conn():
    c = connetti(":memory:")
    inizializza_db(c)
    for denom, istat, prov in _ENTI:
        upsert_ente(c, EnteMetadato(denominazione=denom, codice_istat=istat, provincia=prov))
    return c


@pytest.fixture()
def conn_serie(conn):
    """Atti distribuiti su periodi noti: 2 a gennaio, 1 a marzo, 3 a luglio."""
    calendario = [
        ("084001", "2026-01-05"),
        ("084001", "2026-01-20"),
        ("084002", "2026-03-10"),
        ("087001", "2026-07-01"),
        ("087001", "2026-07-15"),
        ("084001", "2026-07-20"),
    ]
    for i, (istat, giorno) in enumerate(calendario):
        inserisci_atto(conn, _atto(istat, i, data_atto=giorno))
    return conn


# ---------------------------------------------------------------------------
# Granularità
# ---------------------------------------------------------------------------


def test_serie_mensile(conn_serie):
    serie = agg.serie_temporale(conn_serie, granularita="mensile")
    assert [(p.periodo, p.n_atti) for p in serie] == [
        ("2026-01", 2),
        ("2026-03", 1),
        ("2026-07", 3),
    ]


def test_serie_trimestrale(conn_serie):
    serie = agg.serie_temporale(conn_serie, granularita="trimestrale")
    assert [(p.periodo, p.inizio, p.n_atti) for p in serie] == [
        ("2026-T1", "2026-01-01", 3),
        ("2026-T3", "2026-07-01", 3),
    ]


def test_serie_semestrale(conn_serie):
    serie = agg.serie_temporale(conn_serie, granularita="semestrale")
    assert [(p.periodo, p.inizio, p.n_atti) for p in serie] == [
        ("2026-S1", "2026-01-01", 3),
        ("2026-S2", "2026-07-01", 3),
    ]


def test_serie_settimanale_ancorata_al_lunedi(conn):
    # 2026-07-15 è un mercoledì; 2026-07-20 il lunedì successivo.
    for i, giorno in enumerate(["2026-07-15", "2026-07-16", "2026-07-20"]):
        inserisci_atto(conn, _atto("084001", i, data_atto=giorno))
    serie = agg.serie_temporale(conn, granularita="settimanale")
    assert [(p.periodo, p.n_atti) for p in serie] == [
        ("2026-07-13", 2),
        ("2026-07-20", 1),
    ]


def test_serie_giornaliera(conn_serie):
    serie = agg.serie_temporale(conn_serie, granularita="giornaliera")
    assert len(serie) == 6
    assert serie[0].periodo == "2026-01-05"


def test_granularita_sconosciuta(conn):
    with pytest.raises(ValueError, match="Granularità sconosciuta"):
        agg.serie_temporale(conn, granularita="quindicinale")


def test_asse_sconosciuto(conn):
    with pytest.raises(ValueError, match="Asse sconosciuto"):
        agg.serie_temporale(conn, asse="data_scadenza")


# ---------------------------------------------------------------------------
# Filtri territoriali e assi
# ---------------------------------------------------------------------------


def test_filtro_provincia(conn_serie):
    serie = agg.serie_temporale(conn_serie, granularita="mensile", provincia="CT")
    assert [(p.periodo, p.n_atti) for p in serie] == [("2026-07", 2)]


def test_filtro_comune(conn_serie):
    ente_id = conn_serie.execute("SELECT id FROM enti WHERE codice_istat = '084001'").fetchone()[0]
    serie = agg.serie_temporale(conn_serie, granularita="mensile", ente_id=ente_id)
    assert sum(p.n_atti for p in serie) == 3


def test_conteggio_enti_distinti(conn_serie):
    serie = agg.serie_temporale(conn_serie, granularita="semestrale")
    # S2: due atti di Gamma + uno di Alfa = 2 comuni distinti.
    assert serie[1].n_enti == 2


def test_asse_atto_usa_data_pub_quando_manca_data_atto(conn):
    """Regressione: l'80% degli atti reali ha `data_atto` NULL (CLAUDE.md)."""
    inserisci_atto(conn, _atto("084001", 1, data_pub="2026-04-10"))
    serie = agg.serie_temporale(conn, granularita="mensile", asse="atto")
    assert [(p.periodo, p.n_atti) for p in serie] == [("2026-04", 1)]


def test_asse_ingestione_ignora_data_atto(conn):
    inserisci_atto(conn, _atto("084001", 1, data_atto="2020-01-01", data_accesso="2026-05-09"))
    per_atto = agg.serie_temporale(conn, granularita="mensile", asse="atto")
    per_ingestione = agg.serie_temporale(conn, granularita="mensile", asse="ingestione")
    assert [p.periodo for p in per_atto] == ["2020-01"]
    assert [p.periodo for p in per_ingestione] == ["2026-05"]


def test_intervallo_da_a(conn_serie):
    serie = agg.serie_temporale(conn_serie, granularita="mensile", da="2026-02-01", a="2026-06-30")
    assert [(p.periodo, p.n_atti) for p in serie] == [("2026-03", 1)]


# ---------------------------------------------------------------------------
# Date corrotte
# ---------------------------------------------------------------------------


def test_date_corrotte_escluse(conn):
    """Sul DB reale esistono anni palesemente errati (es. `0202-06-16`)."""
    inserisci_atto(conn, _atto("084001", 1, data_atto="0202-06-16"))
    inserisci_atto(conn, _atto("084001", 2, data_atto="2026-06-16"))
    serie = agg.serie_temporale(conn, granularita="mensile")
    assert [(p.periodo, p.n_atti) for p in serie] == [("2026-06", 1)]


def test_data_futura_lontana_esclusa(conn):
    lontana = (date.today() + timedelta(days=agg.GIORNI_FUTURO_AMMESSI + 10)).isoformat()
    vicina = (date.today() + timedelta(days=5)).isoformat()
    inserisci_atto(conn, _atto("084001", 1, data_pub=lontana))
    inserisci_atto(conn, _atto("084001", 2, data_pub=vicina))
    serie = agg.serie_temporale(conn, granularita="giornaliera")
    assert [p.periodo for p in serie] == [vicina]


def test_atti_senza_alcuna_data_esclusi(conn):
    inserisci_atto(conn, _atto("084001", 1))
    assert agg.serie_temporale(conn, granularita="mensile") == []


# ---------------------------------------------------------------------------
# Ingestione giornaliera
# ---------------------------------------------------------------------------


def test_ingestione_giornaliera_esplicita_gli_zeri(conn):
    # `date('now')` di SQLite è in UTC, `date.today()` di Python è locale: fra
    # mezzanotte e le 2 in Italia differiscono di un giorno, e un test scritto
    # sull'ora locale fallirebbe solo in quella finestra. Si usa la nozione di
    # "oggi" del DB, la stessa su cui lavora la funzione.
    oggi = _oggi_utc(conn)
    inserisci_atto(conn, _atto("084001", 1, data_accesso=oggi))
    serie = agg.ingestione_giornaliera(conn, giorni=5)
    assert len(serie) == 5
    assert serie[-1].periodo == oggi
    assert serie[-1].n_atti == 1
    assert [p.n_atti for p in serie[:-1]] == [0, 0, 0, 0]


def test_ingestione_giornaliera_filtrata_per_provincia(conn):
    oggi = _oggi_utc(conn)
    inserisci_atto(conn, _atto("084001", 1, data_accesso=oggi))
    inserisci_atto(conn, _atto("087001", 2, data_accesso=oggi))
    serie = agg.ingestione_giornaliera(conn, giorni=3, provincia="AG")
    assert serie[-1].n_atti == 1


# ---------------------------------------------------------------------------
# Classifiche territoriali
# ---------------------------------------------------------------------------


def test_aggregati_per_provincia(conn_serie):
    righe = agg.aggregati_per_provincia(conn_serie)
    per_nome = {r.nome: r for r in righe}
    assert per_nome["AG"].n_atti == 4  # 3 di Alfa + 1 di Beta
    assert per_nome["AG"].n_enti == 2
    assert per_nome["CT"].n_atti == 2
    assert per_nome["CT"].n_enti == 1


def test_aggregati_per_comune_ordinati_e_limitati(conn_serie):
    righe = agg.aggregati_per_comune(conn_serie, limite=2)
    assert len(righe) == 2
    assert righe[0].n_atti >= righe[1].n_atti


def test_aggregati_per_comune_filtrati_per_provincia(conn_serie):
    righe = agg.aggregati_per_comune(conn_serie, provincia="CT")
    assert [r.nome for r in righe] == ["Comune di Gamma"]
    assert righe[0].primo == "2026-07-01"
    assert righe[0].ultimo == "2026-07-15"


def test_province_disponibili(conn_serie):
    assert agg.province_disponibili(conn_serie) == ["AG", "CT"]


def test_ingestione_giornaliera_non_perde_atti_oltre_oggi_utc(conn):
    """L'asse e l'aggregazione devono avere lo stesso limite superiore.

    Senza il limite esplicito sull'aggregazione, un atto con `data_accesso`
    oltre "oggi UTC" veniva contato ma non aveva una casella nell'asse:
    spariva dal grafico in silenzio.
    """
    oggi = _oggi_utc(conn)
    domani = conn.execute("SELECT date('now', '+1 day')").fetchone()[0]
    inserisci_atto(conn, _atto("084001", 1, data_accesso=oggi))
    inserisci_atto(conn, _atto("084001", 2, data_accesso=domani))
    serie = agg.ingestione_giornaliera(conn, giorni=3)
    assert [p.periodo for p in serie][-1] == oggi
    assert sum(p.n_atti for p in serie) == 1  # quello di "domani" resta fuori
