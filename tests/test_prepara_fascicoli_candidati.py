"""Test selezione candidati per data/samples/ (script prepara_fascicoli_candidati)."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

from talia.modulo2_scraping.db import (
    AttoMetadato,
    EnteMetadato,
    connetti,
    inizializza_db,
    inserisci_atto,
    salva_red_flag,
    upsert_ente,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from prepara_fascicoli_candidati import seleziona_candidati  # noqa: E402


@pytest.fixture()
def db():
    conn = connetti(":memory:")
    inizializza_db(conn)
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE procedimenti (
            id INTEGER PRIMARY KEY, ente_id INTEGER, stato_finale TEXT,
            metodo_individuazione TEXT, creato_a TEXT
        );
        ALTER TABLE atti ADD COLUMN procedimento_id INTEGER;
        """
    )
    return conn


def _atto_jcitygov(codice_istat: str, url: str) -> AttoMetadato:
    return AttoMetadato(
        ente_codice_istat=codice_istat,
        tipo="determina",
        url_fonte=url,
        fonte_scraper="jcitygov",
        data_accesso="2026-07-20T00:00:00",
        data_pub="2026-01-01",
    )


def test_riapertura_esclude_la_propria_catena_dai_critici(db):
    """Una catena revocata già coperta da una riapertura non deve comparire
    ANCHE come 'critica' semplice: sarebbe lo stesso fascicolo due volte."""
    ente_id = upsert_ente(db, EnteMetadato(denominazione="Comune A", codice_istat="000001"))
    db.execute(
        """INSERT INTO procedimenti (id, ente_id, stato_finale, metodo_individuazione, creato_a)
           VALUES (100, ?, 'revocato', 'cig', '2026-01-01')""",
        (ente_id,),
    )
    inserisci_atto(db, _atto_jcitygov("000001", "http://albo/a"))
    db.execute("UPDATE atti SET procedimento_id = 100 WHERE url_fonte = 'http://albo/a'")
    salva_red_flag(
        db,
        ente_id=ente_id,
        tipo_flag="riapertura_dopo_revoca",
        severita="media",
        descrizione="test",
        atti_cig=[{"id_catena_revocata": 100, "atto_riapertura_id": 1, "similarita": 0.9}],
    )
    db.commit()

    candidati = seleziona_candidati(db, limite=10)
    tipi_e_id = [(c["tipo"], c["id"]) for c in candidati]
    assert ("riapertura", 1) in tipi_e_id or any(t == "riapertura" for t, _ in tipi_e_id)
    # 100 non deve comparire come "critica": è già coperto dalla riapertura
    assert ("critica", 100) not in tipi_e_id


def test_critica_senza_riapertura_resta_selezionabile(db):
    ente_id = upsert_ente(db, EnteMetadato(denominazione="Comune B", codice_istat="000002"))
    db.execute(
        """INSERT INTO procedimenti (id, ente_id, stato_finale, metodo_individuazione, creato_a)
           VALUES (200, ?, 'annullato', 'cig', '2026-01-01')""",
        (ente_id,),
    )
    inserisci_atto(db, _atto_jcitygov("000002", "http://albo/b"))
    db.execute("UPDATE atti SET procedimento_id = 200 WHERE url_fonte = 'http://albo/b'")
    db.commit()

    candidati = seleziona_candidati(db, limite=10)
    assert {"tipo": "critica", "id": 200, "ente_id": ente_id} in candidati


def test_seleziona_candidati_rispetta_il_limite(db):
    for i in range(5):
        ente_id = upsert_ente(
            db, EnteMetadato(denominazione=f"Comune {i}", codice_istat=str(i).zfill(6))
        )
        db.execute(
            """INSERT INTO procedimenti (id, ente_id, stato_finale, metodo_individuazione, creato_a)
               VALUES (?, ?, 'revocato', 'cig', '2026-01-01')""",
            (300 + i, ente_id),
        )
        inserisci_atto(db, _atto_jcitygov(str(i).zfill(6), f"http://albo/c{i}"))
        db.execute(
            "UPDATE atti SET procedimento_id = ? WHERE url_fonte = ?", (300 + i, f"http://albo/c{i}")
        )
    db.commit()

    assert len(seleziona_candidati(db, limite=3)) == 3
