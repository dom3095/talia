"""Modulo 2 — Storage: schema SQLite e helper CRUD.

Schema:
    enti            — comuni e altri enti (chiave: codice ISTAT a 6 cifre)
    atti            — atti amministrativi raccolti (chiave: ente × url_fonte)
    entita_estratte — entità estratte dal testo (date, CIG, importi, …)
    check_esiti     — risultati dei check Modulo 1 applicati a un atto
    red_flags       — flag batch aggregati per ente (Modulo 2)

Compatibilità: SQLite in dev, PostgreSQL in produzione (sostituire '?' con '%s'
e usare psycopg2 / SQLAlchemy come adapter).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Dataclass dei metadati
# ---------------------------------------------------------------------------


@dataclass
class EnteMetadato:
    """Metadati di un ente (comune, città metropolitana, libero consorzio)."""

    denominazione: str
    codice_istat: str  # 6 cifre, es. "082053" per Palermo
    provincia: str | None = None
    popolazione: int | None = None
    sito_web: str | None = None
    modulo: str | None = None  # es. 'jcitygov', 'halley' — vedi registry.EntryRegistro
    url_base: str | None = None
    stato_scraper: str | None = None  # 'attivo' | 'escluso_default' | 'bloccato' | 'pending'


@dataclass
class AttoMetadato:
    """Metadati di un atto amministrativo raccolto dallo scraping."""

    ente_codice_istat: str
    tipo: str  # 'determina', 'delibera', 'bando', 'decreto', …
    url_fonte: str  # URL della pagina sorgente — obbligatorio per l'esplicabilità
    fonte_scraper: str  # 'icity', 'anac', 'gurs', …
    data_accesso: str  # ISO 8601 — quando lo abbiamo scaricato
    numero: str | None = None
    data_atto: str | None = None
    data_pub: str | None = None
    data_scadenza: str | None = None
    url_pdf: str | None = None
    hash_sha256: str | None = None
    cig: str | None = None
    oggetto: str | None = None
    importo_euro: float | None = None
    testo_estratto: str | None = None
    metadati: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_DDL = """\
CREATE TABLE IF NOT EXISTS enti (
    id            INTEGER PRIMARY KEY,
    denominazione TEXT    NOT NULL,
    codice_istat  TEXT    UNIQUE NOT NULL,
    provincia     TEXT,
    popolazione   INTEGER,
    sito_web      TEXT
);

CREATE TABLE IF NOT EXISTS atti (
    id             INTEGER PRIMARY KEY,
    ente_id        INTEGER NOT NULL REFERENCES enti(id),
    tipo           TEXT    NOT NULL,
    numero         TEXT,
    data_atto      TEXT,
    data_pub       TEXT,
    data_scadenza  TEXT,
    data_accesso   TEXT    NOT NULL,
    url_fonte      TEXT    NOT NULL,
    url_pdf        TEXT,
    hash_sha256    TEXT,
    cig            TEXT,
    oggetto        TEXT,
    importo_euro   REAL,
    testo_estratto TEXT,
    fonte_scraper  TEXT    NOT NULL,
    metadati       TEXT    NOT NULL DEFAULT '{}',
    UNIQUE (ente_id, url_fonte)
);

CREATE TABLE IF NOT EXISTS entita_estratte (
    id              INTEGER PRIMARY KEY,
    atto_id         INTEGER NOT NULL REFERENCES atti(id) ON DELETE CASCADE,
    tipo            TEXT    NOT NULL,
    valore          TEXT    NOT NULL,
    testo_originale TEXT    NOT NULL,
    offset_inizio   INTEGER NOT NULL,
    offset_fine     INTEGER NOT NULL,
    pagina          INTEGER
);

CREATE TABLE IF NOT EXISTS check_esiti (
    id          INTEGER PRIMARY KEY,
    atto_id     INTEGER NOT NULL REFERENCES atti(id) ON DELETE CASCADE,
    check_id    TEXT    NOT NULL,
    stato       TEXT    NOT NULL,
    motivazione TEXT,
    citazioni   TEXT    NOT NULL DEFAULT '[]',
    data_check  TEXT    NOT NULL,
    UNIQUE (atto_id, check_id)
);

CREATE TABLE IF NOT EXISTS red_flags (
    id               INTEGER PRIMARY KEY,
    ente_id          INTEGER NOT NULL REFERENCES enti(id),
    tipo_flag        TEXT    NOT NULL,
    severita         TEXT    NOT NULL,
    descrizione      TEXT    NOT NULL,
    atti_cig         TEXT    NOT NULL DEFAULT '[]',
    data_rilevazione TEXT    NOT NULL,
    periodo_da       TEXT,
    periodo_a        TEXT
);

CREATE TABLE IF NOT EXISTS scraper_runs (
    id           INTEGER PRIMARY KEY,
    scraper_id   TEXT    NOT NULL,
    avviato_a    TEXT    NOT NULL,
    completato_a TEXT,
    n_trovati    INTEGER,
    n_inseriti   INTEGER,
    n_duplicati  INTEGER,
    data_min     TEXT,
    data_max     TEXT,
    errore       TEXT
);

CREATE INDEX IF NOT EXISTS idx_atti_cig        ON atti (cig);
CREATE INDEX IF NOT EXISTS idx_atti_ente_data  ON atti (ente_id, data_atto);
CREATE INDEX IF NOT EXISTS idx_atti_scraper    ON atti (fonte_scraper);
CREATE UNIQUE INDEX IF NOT EXISTS idx_flags_ente_tipo_periodo
    ON red_flags (ente_id, tipo_flag, COALESCE(periodo_da,''), COALESCE(periodo_a,''));
CREATE INDEX IF NOT EXISTS idx_check_atto      ON check_esiti (atto_id, check_id);
CREATE INDEX IF NOT EXISTS idx_scraper_runs    ON scraper_runs (scraper_id, avviato_a DESC);
"""


# ---------------------------------------------------------------------------
# Connessione
# ---------------------------------------------------------------------------


def connetti(percorso: str | Path = ":memory:") -> sqlite3.Connection:
    """Apre (o crea) il database SQLite al percorso dato.

    ``':memory:'`` → DB in RAM, ideale per i test.
    """
    conn = sqlite3.connect(str(percorso))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def inizializza_db(conn: sqlite3.Connection) -> None:
    """Crea tabelle e indici se non esistono (idempotente)."""
    conn.executescript(_DDL)
    conn.commit()
    _estendi_enti(conn)


def _estendi_enti(conn: sqlite3.Connection) -> None:
    """Aggiunge a `enti` le colonne modulo/url_base/stato_scraper se mancanti.

    Migrazione lazy (stesso pattern di catena.py::_evolvi_schema): necessaria per
    i DB `talia.db` esistenti creati prima che queste colonne esistessero.
    """
    colonne = {row[1] for row in conn.execute("PRAGMA table_info(enti)").fetchall()}
    for col in ("modulo", "url_base", "stato_scraper"):
        if col not in colonne:
            conn.execute(f"ALTER TABLE enti ADD COLUMN {col} TEXT")
    conn.commit()


# ---------------------------------------------------------------------------
# Helper CRUD
# ---------------------------------------------------------------------------


def upsert_ente(conn: sqlite3.Connection, ente: EnteMetadato) -> int:
    """Inserisce o aggiorna un ente; ritorna il suo ``id``.

    ``modulo``/``url_base``/``stato_scraper`` usano ``COALESCE`` in update: se
    il chiamante non li passa (default ``None``, es. i runner scraper che
    upsertano solo denominazione/codice_istat) il valore esistente non viene
    azzerato — solo ``sincronizza_enti_da_registro()`` li valorizza esplicitamente.
    """
    conn.execute(
        """
        INSERT INTO enti (
            denominazione, codice_istat, provincia, popolazione, sito_web,
            modulo, url_base, stato_scraper
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (codice_istat) DO UPDATE SET
            denominazione = excluded.denominazione,
            provincia     = excluded.provincia,
            popolazione   = excluded.popolazione,
            sito_web      = excluded.sito_web,
            modulo        = COALESCE(excluded.modulo, enti.modulo),
            url_base      = COALESCE(excluded.url_base, enti.url_base),
            stato_scraper = COALESCE(excluded.stato_scraper, enti.stato_scraper)
        """,
        (
            ente.denominazione,
            ente.codice_istat,
            ente.provincia,
            ente.popolazione,
            ente.sito_web,
            ente.modulo,
            ente.url_base,
            ente.stato_scraper,
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM enti WHERE codice_istat = ?", (ente.codice_istat,)
    ).fetchone()
    return row["id"]


def inserisci_atto(conn: sqlite3.Connection, atto: AttoMetadato) -> int | None:
    """Inserisce un atto nuovo; ritorna l'``id`` se inserito, ``None`` se già presente.

    La chiave di unicità è ``(ente_id, url_fonte)``: un re-run non duplica.
    """
    row_ente = conn.execute(
        "SELECT id FROM enti WHERE codice_istat = ?", (atto.ente_codice_istat,)
    ).fetchone()
    if row_ente is None:
        raise ValueError(
            f"Ente con codice ISTAT {atto.ente_codice_istat!r} non trovato nel DB. "
            "Chiama prima upsert_ente()."
        )
    ente_id = row_ente["id"]

    try:
        cur = conn.execute(
            """
            INSERT INTO atti (
                ente_id, tipo, numero, data_atto, data_pub, data_scadenza,
                data_accesso, url_fonte, url_pdf, hash_sha256, cig, oggetto,
                importo_euro, testo_estratto, fonte_scraper, metadati
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ente_id,
                atto.tipo,
                atto.numero,
                atto.data_atto,
                atto.data_pub,
                atto.data_scadenza,
                atto.data_accesso,
                atto.url_fonte,
                atto.url_pdf,
                atto.hash_sha256,
                atto.cig,
                atto.oggetto,
                atto.importo_euro,
                atto.testo_estratto,
                atto.fonte_scraper,
                json.dumps(atto.metadati, ensure_ascii=False),
            ),
        )
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        conn.rollback()
        return None


def conta_atti(conn: sqlite3.Connection, ente_id: int | None = None) -> int:
    """Conta gli atti nel DB, opzionalmente filtrati per ``ente_id``."""
    if ente_id is None:
        return conn.execute("SELECT COUNT(*) FROM atti").fetchone()[0]
    return conn.execute("SELECT COUNT(*) FROM atti WHERE ente_id = ?", (ente_id,)).fetchone()[0]


def atti_per_ente(conn: sqlite3.Connection, codice_istat: str) -> list[sqlite3.Row]:
    """Ritorna gli atti di un ente ordinati per data (decrescente)."""
    return conn.execute(
        """
        SELECT a.*
        FROM   atti a
        JOIN   enti e ON e.id = a.ente_id
        WHERE  e.codice_istat = ?
        ORDER  BY a.data_atto DESC, a.data_accesso DESC
        """,
        (codice_istat,),
    ).fetchall()


def salva_check_esito(
    conn: sqlite3.Connection,
    atto_id: int,
    check_id: str,
    stato: str,
    motivazione: str | None = None,
    citazioni: list[dict] | None = None,
    data_check: str | None = None,
) -> None:
    """Inserisce o sostituisce l'esito di un check per un atto (upsert)."""
    if data_check is None:
        data_check = datetime.utcnow().isoformat()
    conn.execute(
        """
        INSERT INTO check_esiti (atto_id, check_id, stato, motivazione, citazioni, data_check)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (atto_id, check_id) DO UPDATE SET
            stato       = excluded.stato,
            motivazione = excluded.motivazione,
            citazioni   = excluded.citazioni,
            data_check  = excluded.data_check
        """,
        (
            atto_id,
            check_id,
            stato,
            motivazione,
            json.dumps(citazioni or [], ensure_ascii=False),
            data_check,
        ),
    )
    conn.commit()


def salva_red_flag(
    conn: sqlite3.Connection,
    ente_id: int,
    tipo_flag: str,
    severita: str,
    descrizione: str,
    atti_cig: list[dict] | None = None,
    periodo_da: str | None = None,
    periodo_a: str | None = None,
    data_rilevazione: str | None = None,
) -> int:
    """Inserisce un red flag aggregato per ente; ritorna l'``id``."""
    if data_rilevazione is None:
        data_rilevazione = datetime.utcnow().isoformat()
    cur = conn.execute(
        """
        INSERT OR REPLACE INTO red_flags (
            ente_id, tipo_flag, severita, descrizione,
            atti_cig, data_rilevazione, periodo_da, periodo_a
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ente_id,
            tipo_flag,
            severita,
            descrizione,
            json.dumps(atti_cig or [], ensure_ascii=False),
            data_rilevazione,
            periodo_da,
            periodo_a,
        ),
    )
    conn.commit()
    return cur.lastrowid


def inizia_run(conn: sqlite3.Connection, scraper_id: str) -> int:
    """Registra l'avvio di uno scraper; ritorna il run_id da passare a termina_run."""
    cur = conn.execute(
        "INSERT INTO scraper_runs (scraper_id, avviato_a) VALUES (?, ?)",
        (scraper_id, datetime.utcnow().isoformat()),
    )
    conn.commit()
    return cur.lastrowid


def termina_run(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    n_trovati: int,
    n_inseriti: int,
    n_duplicati: int,
    data_min: str | None = None,
    data_max: str | None = None,
    errore: str | None = None,
) -> None:
    """Chiude un run registrando statistiche e intervallo date."""
    conn.execute(
        """UPDATE scraper_runs
           SET completato_a=?, n_trovati=?, n_inseriti=?, n_duplicati=?,
               data_min=?, data_max=?, errore=?
           WHERE id=?""",
        (
            datetime.utcnow().isoformat(),
            n_trovati,
            n_inseriti,
            n_duplicati,
            data_min,
            data_max,
            errore,
            run_id,
        ),
    )
    conn.commit()


def ultimo_run_riuscito(conn: sqlite3.Connection, scraper_id: str) -> sqlite3.Row | None:
    """Ritorna il dict dell'ultimo run completato senza errori, o None."""
    return conn.execute(
        """SELECT * FROM scraper_runs
           WHERE scraper_id=? AND completato_a IS NOT NULL AND errore IS NULL
           ORDER BY avviato_a DESC LIMIT 1""",
        (scraper_id,),
    ).fetchone()


def red_flags_per_ente(conn: sqlite3.Connection, codice_istat: str) -> list[sqlite3.Row]:
    """Ritorna i red flag di un ente ordinati per data (decrescente)."""
    return conn.execute(
        """
        SELECT rf.*
        FROM   red_flags rf
        JOIN   enti e ON e.id = rf.ente_id
        WHERE  e.codice_istat = ?
        ORDER  BY rf.data_rilevazione DESC
        """,
        (codice_istat,),
    ).fetchall()


__all__ = [
    "EnteMetadato",
    "AttoMetadato",
    "connetti",
    "inizializza_db",
    "upsert_ente",
    "inserisci_atto",
    "conta_atti",
    "atti_per_ente",
    "salva_check_esito",
    "salva_red_flag",
    "red_flags_per_ente",
    "inizia_run",
    "termina_run",
    "ultimo_run_riuscito",
]
