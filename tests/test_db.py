"""Test dello schema DB e degli helper CRUD — SQLite in-memory (nessuna I/O disco)."""

from __future__ import annotations

import json

import pytest

from talia.modulo2_scraping.db import (
    AttoMetadato,
    EnteMetadato,
    _estendi_enti,
    atti_per_ente,
    connetti,
    conta_atti,
    inizializza_db,
    inserisci_atto,
    red_flags_per_ente,
    salva_check_esito,
    salva_red_flag,
    upsert_ente,
)
from talia.modulo2_scraping.registry import EntryRegistro, sincronizza_enti_da_registro

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db():
    conn = connetti(":memory:")
    inizializza_db(conn)
    return conn


@pytest.fixture()
def ente_palermo(db):
    ente = EnteMetadato(
        denominazione="Comune di Palermo",
        codice_istat="082053",
        provincia="PA",
        popolazione=641984,
        sito_web="https://www.comune.palermo.it",
    )
    ente_id = upsert_ente(db, ente)
    return ente_id, ente


def _atto(url: str = "http://albo.pa.it/det001", **kwargs) -> AttoMetadato:
    return AttoMetadato(
        ente_codice_istat="082053",
        tipo=kwargs.get("tipo", "determina"),
        url_fonte=url,
        fonte_scraper="icity",
        data_accesso="2024-01-15T10:00:00",
        **{k: v for k, v in kwargs.items() if k != "tipo"},
    )


# ---------------------------------------------------------------------------
# Schema / inizializzazione
# ---------------------------------------------------------------------------


def test_inizializza_db_idempotente(db):
    inizializza_db(db)
    inizializza_db(db)
    tabelle = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    nomi = {r["name"] for r in tabelle}
    assert {"enti", "atti", "entita_estratte", "check_esiti", "red_flags"} <= nomi


def test_estendi_enti_su_db_nuovo(db):
    """inizializza_db chiama già _estendi_enti: le colonne devono esserci."""
    colonne = {r[1] for r in db.execute("PRAGMA table_info(enti)").fetchall()}
    assert {"modulo", "url_base", "stato_scraper"} <= colonne


def test_estendi_enti_su_schema_vecchio_preserva_righe():
    """Simula un talia.db esistente creato prima che modulo/url_base/stato_scraper
    esistessero: _estendi_enti deve aggiungere le colonne senza perdere dati."""
    conn = connetti(":memory:")
    conn.execute(
        """
        CREATE TABLE enti (
            id            INTEGER PRIMARY KEY,
            denominazione TEXT    NOT NULL,
            codice_istat  TEXT    UNIQUE NOT NULL,
            provincia     TEXT,
            popolazione   INTEGER,
            sito_web      TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO enti (denominazione, codice_istat) VALUES ('Comune Vecchio', '000001')"
    )
    conn.commit()

    _estendi_enti(conn)

    colonne = {r[1] for r in conn.execute("PRAGMA table_info(enti)").fetchall()}
    assert {"modulo", "url_base", "stato_scraper"} <= colonne
    row = conn.execute("SELECT * FROM enti WHERE codice_istat = '000001'").fetchone()
    assert row["denominazione"] == "Comune Vecchio"


def test_estendi_enti_idempotente(db):
    _estendi_enti(db)
    _estendi_enti(db)
    colonne = [r[1] for r in db.execute("PRAGMA table_info(enti)").fetchall()]
    assert colonne.count("modulo") == 1


# ---------------------------------------------------------------------------
# Enti
# ---------------------------------------------------------------------------


def test_upsert_ente_crea(db):
    ente = EnteMetadato(denominazione="Comune di Catania", codice_istat="087015", provincia="CT")
    ente_id = upsert_ente(db, ente)
    assert isinstance(ente_id, int) and ente_id > 0


def test_upsert_ente_aggiorna(db, ente_palermo):
    ente_id_orig, _ = ente_palermo
    ente_v2 = EnteMetadato(
        denominazione="Comune di Palermo (aggiornato)",
        codice_istat="082053",
        provincia="PA",
        popolazione=641999,
    )
    ente_id2 = upsert_ente(db, ente_v2)
    assert ente_id2 == ente_id_orig
    row = db.execute(
        "SELECT denominazione, popolazione FROM enti WHERE codice_istat='082053'"
    ).fetchone()
    assert row["denominazione"] == "Comune di Palermo (aggiornato)"
    assert row["popolazione"] == 641999


def test_upsert_ente_con_modulo_url_base_stato_scraper(db):
    ente = EnteMetadato(
        denominazione="Comune di Vittoria",
        codice_istat="088012",
        modulo="halley",
        url_base="https://trasparenza.comune.vittoria.rg.it",
        stato_scraper="attivo",
    )
    upsert_ente(db, ente)
    row = db.execute(
        "SELECT modulo, url_base, stato_scraper FROM enti WHERE codice_istat='088012'"
    ).fetchone()
    assert row["modulo"] == "halley"
    assert row["url_base"] == "https://trasparenza.comune.vittoria.rg.it"
    assert row["stato_scraper"] == "attivo"


def test_upsert_ente_vecchio_stile_non_azzera_modulo(db):
    """Un upsert 'vecchio stile' (solo denominazione/codice_istat, come fanno i
    runner scraper) non deve azzerare modulo/url_base/stato_scraper già impostati
    da sincronizza_enti_da_registro — altrimenti ogni run scraper li cancellerebbe."""
    upsert_ente(
        db,
        EnteMetadato(
            denominazione="Comune di Vittoria",
            codice_istat="088012",
            modulo="halley",
            url_base="https://trasparenza.comune.vittoria.rg.it",
            stato_scraper="attivo",
        ),
    )
    upsert_ente(db, EnteMetadato(denominazione="Comune di Vittoria", codice_istat="088012"))
    row = db.execute(
        "SELECT modulo, url_base, stato_scraper FROM enti WHERE codice_istat='088012'"
    ).fetchone()
    assert row["modulo"] == "halley"
    assert row["url_base"] == "https://trasparenza.comune.vittoria.rg.it"
    assert row["stato_scraper"] == "attivo"


# ---------------------------------------------------------------------------
# sincronizza_enti_da_registro
# ---------------------------------------------------------------------------


def _entry_registro(**overrides) -> EntryRegistro:
    base = dict(
        slug="vittoria",
        denominazione="Comune di Vittoria",
        codice_istat="088012",
        modulo="halley",
        piattaforma_tecnica="Halley EG",
        base_url="https://trasparenza.comune.vittoria.rg.it",
        stato="attivo",
        provincia="RG",
    )
    base.update(overrides)
    return EntryRegistro(**base)


def test_sincronizza_enti_da_registro_crea_enti(db):
    entries = [_entry_registro()]
    n = sincronizza_enti_da_registro(db, entries)
    assert n == 1
    row = db.execute(
        "SELECT denominazione, provincia, modulo, url_base, stato_scraper "
        "FROM enti WHERE codice_istat='088012'"
    ).fetchone()
    assert row["denominazione"] == "Comune di Vittoria"
    assert row["provincia"] == "RG"
    assert row["modulo"] == "halley"
    assert row["url_base"] == "https://trasparenza.comune.vittoria.rg.it"
    assert row["stato_scraper"] == "attivo"


def test_sincronizza_enti_da_registro_idempotente(db):
    entries = [_entry_registro()]
    sincronizza_enti_da_registro(db, entries)
    n2 = sincronizza_enti_da_registro(db, entries)
    assert n2 == 1
    conteggio = db.execute("SELECT COUNT(*) AS c FROM enti").fetchone()["c"]
    assert conteggio == 1


def test_sincronizza_enti_da_registro_salta_anac(db):
    entries = [_entry_registro(slug="anac", modulo="anac", codice_istat="", base_url=None)]
    n = sincronizza_enti_da_registro(db, entries)
    assert n == 0
    assert db.execute("SELECT COUNT(*) AS c FROM enti").fetchone()["c"] == 0


def test_sincronizza_enti_da_registro_include_bloccato_e_pending(db):
    entries = [
        _entry_registro(slug="messina", codice_istat="083048", stato="bloccato"),
        _entry_registro(slug="comune_pending", codice_istat="000002", stato="pending"),
    ]
    n = sincronizza_enti_da_registro(db, entries)
    assert n == 2
    stati = {
        r["codice_istat"]: r["stato_scraper"]
        for r in db.execute("SELECT codice_istat, stato_scraper FROM enti").fetchall()
    }
    assert stati["083048"] == "bloccato"
    assert stati["000002"] == "pending"


# ---------------------------------------------------------------------------
# Atti
# ---------------------------------------------------------------------------


def test_inserisci_atto_nuovo(db, ente_palermo):
    atto_id = inserisci_atto(db, _atto(cig="A12345678B", importo_euro=9999.0))
    assert atto_id is not None and atto_id > 0


def test_inserisci_atto_idempotente(db, ente_palermo):
    """Re-run sullo stesso url_fonte non duplica."""
    id1 = inserisci_atto(db, _atto())
    id2 = inserisci_atto(db, _atto())
    assert id1 is not None
    assert id2 is None  # già presente
    assert conta_atti(db) == 1


def test_inserisci_atto_url_diverse(db, ente_palermo):
    inserisci_atto(db, _atto("http://albo.pa.it/det001"))
    inserisci_atto(db, _atto("http://albo.pa.it/det002"))
    assert conta_atti(db) == 2


def test_inserisci_atto_ente_mancante(db):
    atto = AttoMetadato(
        ente_codice_istat="999999",
        tipo="determina",
        url_fonte="http://example.com",
        fonte_scraper="test",
        data_accesso="2024-01-01T00:00:00",
    )
    with pytest.raises(ValueError, match="non trovato"):
        inserisci_atto(db, atto)


def test_inserisci_atto_metadati_json(db, ente_palermo):
    atto = _atto("http://x.it/1", metadati={"commissario": True, "note": "urgenza"})
    atto_id = inserisci_atto(db, atto)
    row = db.execute("SELECT metadati FROM atti WHERE id=?", (atto_id,)).fetchone()
    meta = json.loads(row["metadati"])
    assert meta["commissario"] is True


def test_conta_atti_per_ente(db, ente_palermo):
    ente_id, _ = ente_palermo
    for i in range(3):
        inserisci_atto(db, _atto(f"http://albo.pa.it/det00{i}"))
    assert conta_atti(db) == 3
    assert conta_atti(db, ente_id=ente_id) == 3
    assert conta_atti(db, ente_id=9999) == 0


def test_atti_per_ente(db, ente_palermo):
    inserisci_atto(db, _atto("http://x.it/1", cig="AA1111111A"))
    inserisci_atto(db, _atto("http://x.it/2", cig="BB2222222B"))
    rows = atti_per_ente(db, "082053")
    assert len(rows) == 2
    cig_trovati = {r["cig"] for r in rows}
    assert cig_trovati == {"AA1111111A", "BB2222222B"}


def test_atti_per_ente_inesistente(db):
    rows = atti_per_ente(db, "000000")
    assert rows == []


# ---------------------------------------------------------------------------
# Check esiti
# ---------------------------------------------------------------------------


def test_salva_check_esito(db, ente_palermo):
    atto_id = inserisci_atto(db, _atto())
    salva_check_esito(
        db,
        atto_id=atto_id,
        check_id="check1_base_giuridica",
        stato="rosso",
        motivazione="base giuridica assente",
        citazioni=[{"testo": "Visto che…", "pagina": 1}],
        data_check="2024-01-15T10:00:00",
    )
    row = db.execute(
        "SELECT stato, citazioni FROM check_esiti WHERE atto_id=? AND check_id=?",
        (atto_id, "check1_base_giuridica"),
    ).fetchone()
    assert row["stato"] == "rosso"
    assert json.loads(row["citazioni"])[0]["pagina"] == 1


def test_salva_check_esito_upsert(db, ente_palermo):
    """Secondo salvataggio aggiorna lo stato, non duplica."""
    atto_id = inserisci_atto(db, _atto())
    salva_check_esito(db, atto_id, "check1", "giallo", data_check="2024-01-15T10:00:00")
    salva_check_esito(db, atto_id, "check1", "rosso", data_check="2024-01-16T10:00:00")
    rows = db.execute("SELECT stato FROM check_esiti WHERE atto_id=?", (atto_id,)).fetchall()
    assert len(rows) == 1
    assert rows[0]["stato"] == "rosso"


def test_salva_check_esito_senza_data(db, ente_palermo):
    atto_id = inserisci_atto(db, _atto())
    salva_check_esito(db, atto_id, "check2_termini", "verde")
    row = db.execute("SELECT data_check FROM check_esiti WHERE atto_id=?", (atto_id,)).fetchone()
    assert row["data_check"] is not None


# ---------------------------------------------------------------------------
# Red flags
# ---------------------------------------------------------------------------


def test_salva_e_leggi_red_flag(db, ente_palermo):
    ente_id, _ = ente_palermo
    flag_id = salva_red_flag(
        db,
        ente_id=ente_id,
        tipo_flag="frazionamento",
        severita="alta",
        descrizione="3 affidamenti diretti ravvicinati stesso fornitore",
        atti_cig=[{"cig": "A1", "url": "http://albo.pa.it/det001"}],
        periodo_da="2024-01-01",
        periodo_a="2024-03-31",
        data_rilevazione="2024-04-01T00:00:00",
    )
    assert flag_id > 0
    flags = red_flags_per_ente(db, "082053")
    assert len(flags) == 1
    assert flags[0]["tipo_flag"] == "frazionamento"
    assert flags[0]["severita"] == "alta"
    assert json.loads(flags[0]["atti_cig"])[0]["cig"] == "A1"


def test_red_flags_per_ente_vuoto(db, ente_palermo):
    flags = red_flags_per_ente(db, "082053")
    assert flags == []


def test_red_flags_per_ente_inesistente(db):
    flags = red_flags_per_ente(db, "000000")
    assert flags == []


def test_salva_red_flag_senza_data_rilevazione(db, ente_palermo):
    ente_id, _ = ente_palermo
    flag_id = salva_red_flag(db, ente_id, "concentrazione", "media", "fornitore ricorrente")
    assert flag_id > 0
    row = db.execute("SELECT data_rilevazione FROM red_flags WHERE id=?", (flag_id,)).fetchone()
    assert row["data_rilevazione"] is not None
