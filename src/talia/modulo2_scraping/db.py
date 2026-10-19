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
    cig_padre: str | None = None  # CIG dell'accordo quadro, se l'atto ne cita uno (TAL-65)
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
    cig_padre      TEXT,
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
    _estendi_atti(conn)
    _crea_atti_fonti(conn)


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


def _estendi_atti(conn: sqlite3.Connection) -> None:
    """Aggiunge a `atti` la colonna `cig_padre` se mancante (TAL-65).

    Migrazione lazy per i DB `talia.db` esistenti creati prima che il CIG
    dell'accordo quadro (distinto dal CIG proprio dell'atto) fosse tracciato.
    """
    colonne = {row[1] for row in conn.execute("PRAGMA table_info(atti)").fetchall()}
    if "cig_padre" not in colonne:
        conn.execute("ALTER TABLE atti ADD COLUMN cig_padre TEXT")
    # L'indice va creato qui (non nella _DDL statica): su un DB esistente la
    # colonna non c'era finché la ALTER TABLE sopra non gira in questa stessa
    # chiamata, quindi un CREATE INDEX in _DDL (eseguito prima di _estendi_atti)
    # fallirebbe con "no such column" sui DB creati prima di questa migrazione.
    conn.execute("CREATE INDEX IF NOT EXISTS idx_atti_cig_padre ON atti (cig_padre)")
    conn.commit()


_DDL_ATTI_FONTI = """\
CREATE TABLE IF NOT EXISTS atti_fonti (
    id             INTEGER PRIMARY KEY,
    atto_id        INTEGER NOT NULL REFERENCES atti(id) ON DELETE CASCADE,
    fonte_scraper  TEXT    NOT NULL,
    url_fonte      TEXT    NOT NULL,
    url_pdf        TEXT,
    data_pub       TEXT,
    data_scadenza  TEXT,
    data_accesso   TEXT    NOT NULL,
    hash_sha256    TEXT,
    UNIQUE (atto_id, fonte_scraper, url_fonte)
);
CREATE INDEX IF NOT EXISTS idx_atti_fonti_atto  ON atti_fonti (atto_id);
CREATE INDEX IF NOT EXISTS idx_atti_ente_cig_num ON atti (ente_id, cig, numero);
CREATE INDEX IF NOT EXISTS idx_atti_ente_tipo_num ON atti (ente_id, tipo, numero);
"""


def _crea_atti_fonti(conn: sqlite3.Connection) -> None:
    """Crea `atti_fonti` e la popola 1:1 dagli atti che non hanno ancora una fonte (TAL-64).

    `atti_fonti` registra **ogni** pubblicazione in cui un atto è stato trovato
    (Albo Pretorio, Amministrazione Trasparente, …): la stessa determina può
    stare su due portali, con URL, date di pubblicazione e scadenza diverse.

    Le colonne per-fonte restano anche in `atti` e descrivono la **prima** fonte
    da cui l'atto è stato acquisito: decine di query (catene, red flag,
    dashboard, `COALESCE(data_atto, data_pub)`) le leggono da lì, e spostarle
    tutte in un colpo solo su un DB di 300k+ atti, senza poterlo verificare,
    sarebbe stato il rischio maggiore di questa card. `atti_fonti` è quindi
    additiva: niente di ciò che oggi legge `atti` cambia comportamento.

    Il backfill è idempotente e riguarda solo gli atti senza alcuna fonte: al
    primo avvio copia l'intero DB (una riga per atto, nessun merge — oggi non
    esistono duplicati reali, vedi la card), poi diventa un no-op.
    """
    conn.executescript(_DDL_ATTI_FONTI)
    conn.execute(
        """
        INSERT INTO atti_fonti (
            atto_id, fonte_scraper, url_fonte, url_pdf,
            data_pub, data_scadenza, data_accesso, hash_sha256
        )
        SELECT a.id, a.fonte_scraper, a.url_fonte, a.url_pdf,
               a.data_pub, a.data_scadenza, a.data_accesso, a.hash_sha256
        FROM atti a
        WHERE NOT EXISTS (SELECT 1 FROM atti_fonti f WHERE f.atto_id = a.id)
        """
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Helper CRUD
# ---------------------------------------------------------------------------


def upsert_ente(conn: sqlite3.Connection, ente: EnteMetadato) -> int:
    """Inserisce o aggiorna un ente; ritorna il suo ``id``.

    Tutti i campi opzionali (``provincia``/``popolazione``/``sito_web``/
    ``modulo``/``url_base``/``stato_scraper``) usano ``COALESCE`` in update:
    se il chiamante non li passa (default ``None``, es. i runner scraper che
    upsertano solo denominazione/codice_istat) il valore esistente non viene
    azzerato. Solo ``denominazione``/``codice_istat`` sono obbligatori e
    quindi sempre sovrascritti direttamente. Bug corretto in code review
    (2026-07-11): ``provincia`` era sovrascritta incondizionatamente, così
    ``sincronizza_enti_da_registro()`` (che gira ad ogni run indipendentemente
    da ``--scrapers``, con provincia vuota per la quasi totalità delle righe
    del registro) azzerava silenziosamente la provincia impostata dai singoli
    scraper monocomune per i comuni non inclusi nel run corrente.
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
            provincia     = COALESCE(excluded.provincia, enti.provincia),
            popolazione   = COALESCE(excluded.popolazione, enti.popolazione),
            sito_web      = COALESCE(excluded.sito_web, enti.sito_web),
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


def azzera_info_scraper(conn: sqlite3.Connection, codice_istat: str) -> None:
    """Azzera esplicitamente modulo/url_base/stato_scraper per un ente.

    ``upsert_ente()`` protegge questi 3 campi con ``COALESCE`` apposta perché
    non vengano azzerati per errore da un upsert "vecchio stile" — ma questo
    significa che nessun percorso di codice può più farlo per errore, nemmeno
    quando serve davvero (es. un comune rimosso dal registro, o uno scraper
    disattivato in modo permanente). Questa funzione è l'unica via esplicita
    per farlo. Non è chiamata automaticamente da ``sincronizza_enti_da_registro``
    (non fa riconciliazione: non rileva da sola i comuni tolti dal CSV).
    """
    conn.execute(
        "UPDATE enti SET modulo = NULL, url_base = NULL, stato_scraper = NULL "
        "WHERE codice_istat = ?",
        (codice_istat,),
    )
    conn.commit()


def _numero_valido(numero: str | None) -> bool:
    """`"0"` è una sentinella dei portali (13% delle righe AT in TAL-64), non un numero."""
    return bool(numero) and numero.strip() not in ("", "0")


def _anno(atto: AttoMetadato) -> str | None:
    data = atto.data_atto or atto.data_pub
    return data[:4] if data and data[:4].isdigit() else None


def trova_stesso_atto(conn: sqlite3.Connection, ente_id: int, atto: AttoMetadato) -> int | None:
    """Cerca un atto già in DB che sia **lo stesso documento** pubblicato altrove (TAL-64).

    Ritorna l'``id`` solo se il candidato è **unico**; con zero o più candidati
    ritorna ``None`` e l'atto viene inserito come nuovo. Fondere due atti
    diversi è un errore peggiore che tenerne due copie: una copia in più si
    vede, una fusione sbagliata sparisce.

    Regole (spec della card, confermate con Dom):

    * **Solo tra fonti diverse.** Un candidato già visto dalla stessa
      ``fonte_scraper`` non è mai lo stesso atto: dentro un portale, URL
      diverso = atto diverso, come oggi. Il caso da deduplicare è Albo
      Pretorio vs Amministrazione Trasparente.
    * Con CIG: chiave ``(ente_id, cig, numero)``, CIG **esatto** — il CIG da
      solo non basta (il 40% dei CIG copre più atti: determina a contrarre,
      aggiudicazione, liquidazione…). Mai ``cig_padre``: è condiviso da tutte
      le adesioni a un accordo quadro.
    * Senza CIG: ``(ente_id, tipo, numero)``. ``data_atto`` è fuori dalla chiave
      (mai valorizzato in Amministrazione Trasparente); per non fondere la
      determina n. 12 del 2019 con quella del 2026 si richiede però lo stesso
      anno quando è noto da entrambe le parti.
    * ``numero`` assente o ``"0"`` (sentinella): nessuna deduplicazione.
    """
    if not _numero_valido(atto.numero):
        return None
    if atto.cig:
        condizione, parametri = "a.cig = ?", [atto.cig]
    else:
        condizione, parametri = "a.cig IS NULL AND a.tipo = ?", [atto.tipo]
    righe = conn.execute(
        f"""
        SELECT a.id, COALESCE(a.data_atto, a.data_pub) AS data
        FROM atti a
        WHERE a.ente_id = ? AND a.numero = ? AND {condizione}
          AND NOT EXISTS (
              SELECT 1 FROM atti_fonti f
              WHERE f.atto_id = a.id AND f.fonte_scraper = ?
          )
        LIMIT 3
        """,
        [ente_id, atto.numero, *parametri, atto.fonte_scraper],
    ).fetchall()
    anno = _anno(atto)
    candidati = [
        r["id"]
        for r in righe
        if anno is None or not r["data"] or r["data"][:4] == anno or not r["data"][:4].isdigit()
    ]
    return candidati[0] if len(candidati) == 1 else None


def _aggiungi_fonte(conn: sqlite3.Connection, atto_id: int, atto: AttoMetadato) -> bool:
    """Registra una pubblicazione dell'atto; ``False`` se era già registrata."""
    cur = conn.execute(
        """
        INSERT OR IGNORE INTO atti_fonti (
            atto_id, fonte_scraper, url_fonte, url_pdf,
            data_pub, data_scadenza, data_accesso, hash_sha256
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            atto_id,
            atto.fonte_scraper,
            atto.url_fonte,
            atto.url_pdf,
            atto.data_pub,
            atto.data_scadenza,
            atto.data_accesso,
            atto.hash_sha256,
        ),
    )
    return cur.rowcount > 0


def inserisci_atto(conn: sqlite3.Connection, atto: AttoMetadato) -> int | None:
    """Inserisce un atto nuovo; ritorna l'``id`` se inserito, ``None`` se già presente.

    La chiave di unicità è ``(ente_id, url_fonte)``: un re-run non duplica.

    Dal TAL-64 "già presente" ha due casi in più, entrambi registrati in
    `atti_fonti` invece di essere scartati:

    * stesso URL ma **fonte diversa** (su jCityGov Albo Pretorio e
      Amministrazione Trasparente condividono il backend e quindi l'URL): prima
      l'insert falliva sull'UNIQUE e l'informazione "è anche in AT, con
      ritenzione di anni" andava persa in silenzio;
    * URL diverso ma **stesso documento** secondo `trova_stesso_atto`.

    In entrambi i casi il ritorno resta ``None``: l'atto non è nuovo, e i
    conteggi "inseriti" degli scraper non cambiano significato.
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

    esistente = conn.execute(
        "SELECT id FROM atti WHERE ente_id = ? AND url_fonte = ?", (ente_id, atto.url_fonte)
    ).fetchone()
    if esistente is not None:
        if _aggiungi_fonte(conn, esistente["id"], atto):
            conn.commit()
        return None

    stesso = trova_stesso_atto(conn, ente_id, atto)
    if stesso is not None:
        _aggiungi_fonte(conn, stesso, atto)
        conn.commit()
        return None

    try:
        cur = conn.execute(
            """
            INSERT INTO atti (
                ente_id, tipo, numero, data_atto, data_pub, data_scadenza,
                data_accesso, url_fonte, url_pdf, hash_sha256, cig, cig_padre,
                oggetto, importo_euro, testo_estratto, fonte_scraper, metadati
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                atto.cig_padre,
                atto.oggetto,
                atto.importo_euro,
                atto.testo_estratto,
                atto.fonte_scraper,
                json.dumps(atto.metadati, ensure_ascii=False),
            ),
        )
        _aggiungi_fonte(conn, cur.lastrowid, atto)
        conn.commit()
        return cur.lastrowid
    except sqlite3.IntegrityError:
        conn.rollback()
        return None


def fonti_atto(conn: sqlite3.Connection, atto_id: int) -> list[sqlite3.Row]:
    """Tutte le pubblicazioni note di un atto, la più duratura per prima (TAL-64).

    L'ordine serve al link da mostrare all'utente: l'Albo Pretorio espone un
    atto per 15-30 giorni, Amministrazione Trasparente per anni — linkare la
    fonte con la scadenza più lontana (o senza scadenza) evita i link morti che
    avevano aperto il filone TAL-62.
    """
    return conn.execute(
        """
        SELECT * FROM atti_fonti
        WHERE atto_id = ?
        ORDER BY data_scadenza IS NOT NULL, data_scadenza DESC, id
        """,
        (atto_id,),
    ).fetchall()


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
    "fonti_atto",
    "trova_stesso_atto",
]
