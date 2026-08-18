"""TAL-64 — Ingest sperimentale di Amministrazione Trasparente in tabella di staging.

Non tocca `atti`: scrive in una tabella a parte (`atti_trasparenza_staging`),
creata da questo script, non dalla DDL principale di `db.py`. Serve a
raccogliere un campione reale (~1000 atti, jCityGov + Halley) su cui provare
la logica di deduplicazione contro `atti` prima di decidere lo schema
definitivo di TAL-64.

Uso:
    python scripts/tal64_staging_trasparenza.py [--db talia.db] [--target 1000]
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import time

from talia.modulo2_scraping.db import AttoMetadato, connetti
from talia.modulo2_scraping.fonti import halley, jcitygov

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_DDL_STAGING = """\
CREATE TABLE IF NOT EXISTS atti_trasparenza_staging (
    id             INTEGER PRIMARY KEY,
    ente_id        INTEGER NOT NULL REFERENCES enti(id),
    codice_istat   TEXT    NOT NULL,
    tipo           TEXT    NOT NULL,
    numero         TEXT,
    data_atto      TEXT,
    data_pub       TEXT,
    data_scadenza  TEXT,
    data_accesso   TEXT    NOT NULL,
    url_fonte      TEXT    NOT NULL,
    url_pdf        TEXT,
    cig            TEXT,
    oggetto        TEXT,
    importo_euro   REAL,
    fonte_scraper  TEXT    NOT NULL,
    metadati       TEXT    NOT NULL DEFAULT '{}',
    UNIQUE (ente_id, url_fonte)
);
"""

# Comuni scelti tra quelli con più atti già in `atti` per la stessa piattaforma
# (dedup significativa solo se esiste già storico Albo Pretorio da confrontare).
# Vittoria esclusa: piattaforma Halley diversa ("Stanza del cittadino"), nota
# non compatibile con lo scraper halley.py attuale.
#
# I nomi categoria di default ("Bandi di concorso"/"Bandi di gara e contratti")
# non sono uniformi tra tenant: verificato con una probe live prima di questo
# script (substring "bandi", case-insensitive) che generalizza su jCityGov
# (7/8 comuni testati hanno almeno una categoria "Bandi..."), ma su Halley
# **nessuno dei 7 comuni testati oltre Aci Bonaccorsi** (quello già verificato
# in TAL-62) espone una categoria con "bandi" nel nome — la tassonomia D.lgs.
# 33/2013 lì è molto meno standardizzata. Non approfondito oltre: fuori scope
# per un ingest sperimentale, segnalato nella card TAL-64 per chi riprende il
# lavoro sulle piattaforme Halley restanti.
_COMUNI_JCITYGOV = [
    ("088009", "https://ragusa.trasparenza-valutazione-merito.it"),
    ("088006", "https://modica.trasparenza-valutazione-merito.it"),
    ("087004", "https://acireale.trasparenza-valutazione-merito.it"),
    ("088011", "https://scicli.trasparenza-valutazione-merito.it"),
    ("087017", "https://giarre.trasparenza-valutazione-merito.it"),
    ("087045", "https://santagatalibattiati.trasparenza-valutazione-merito.it"),
    ("087019", "https://gravinadicatania.trasparenza-valutazione-merito.it"),
]
_COMUNI_HALLEY = [
    ("087001", "https://servizi.comune.acibonaccorsi.ct.it"),
]

_DELAY_TRA_COMUNI_SEC = 2.0


def crea_tabella_staging(conn: sqlite3.Connection) -> None:
    conn.executescript(_DDL_STAGING)
    conn.commit()


def _ente_id(conn: sqlite3.Connection, codice_istat: str) -> int | None:
    row = conn.execute("SELECT id FROM enti WHERE codice_istat = ?", (codice_istat,)).fetchone()
    return row["id"] if row else None


def _inserisci_staging(
    conn: sqlite3.Connection, ente_id: int, codice_istat: str, atto: AttoMetadato
) -> bool:
    try:
        conn.execute(
            """
            INSERT INTO atti_trasparenza_staging (
                ente_id, codice_istat, tipo, numero, data_atto, data_pub,
                data_scadenza, data_accesso, url_fonte, url_pdf, cig, oggetto,
                importo_euro, fonte_scraper, metadati
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ente_id,
                codice_istat,
                atto.tipo,
                atto.numero,
                atto.data_atto,
                atto.data_pub,
                atto.data_scadenza,
                atto.data_accesso,
                atto.url_fonte,
                atto.url_pdf,
                atto.cig,
                atto.oggetto,
                atto.importo_euro,
                atto.fonte_scraper,
                json.dumps(atto.metadati, ensure_ascii=False),
            ),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        conn.rollback()
        return False


def _ingest_comune(
    conn: sqlite3.Connection, codice_istat: str, base_url: str, modulo: str, rimanenti: int
) -> int:
    ente_id = _ente_id(conn, codice_istat)
    if ente_id is None:
        logger.warning(f"Ente {codice_istat} non trovato in `enti`, salto ({base_url})")
        return 0

    if modulo == "jcitygov":
        scopri, scarica = jcitygov.scopri_categorie_trasparenza, jcitygov.scarica_atti_trasparenza
    elif modulo == "halley":
        scopri, scarica = halley.scopri_categorie_trasparenza, halley.scarica_atti_trasparenza
    else:
        raise ValueError(f"Modulo non gestito: {modulo}")

    categorie = [c for c in scopri(base_url) if "bandi" in c.lower()]
    if not categorie:
        logger.warning(f"{modulo} trasparenza {base_url}: nessuna categoria 'bandi*' trovata")
        return 0
    generatore = scarica(base_url, codice_istat, categorie=categorie)

    inseriti = 0
    try:
        for atto in generatore:
            if inseriti >= rimanenti:
                break
            if _inserisci_staging(conn, ente_id, codice_istat, atto):
                inseriti += 1
    except Exception as exc:  # noqa: BLE001 — script di raccolta dati, un tenant che fallisce non deve bloccare gli altri
        logger.warning(f"Errore su {base_url} ({modulo}): {exc}")

    logger.info(f"{base_url} ({modulo}): {inseriti} atti inseriti in staging")
    return inseriti


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="talia.db")
    parser.add_argument("--target", type=int, default=1000)
    args = parser.parse_args()

    conn = connetti(args.db)
    crea_tabella_staging(conn)

    totale = 0
    comuni = [(c, u, "jcitygov") for c, u in _COMUNI_JCITYGOV] + [
        (c, u, "halley") for c, u in _COMUNI_HALLEY
    ]
    per_comune = max(1, args.target // len(comuni))

    for codice_istat, base_url, modulo in comuni:
        if totale >= args.target:
            break
        rimanenti = min(per_comune, args.target - totale)
        totale += _ingest_comune(conn, codice_istat, base_url, modulo, rimanenti)
        time.sleep(_DELAY_TRA_COMUNI_SEC)

    logger.info(f"Totale inserito in staging: {totale} (target {args.target})")
    n_staging = conn.execute("SELECT COUNT(*) FROM atti_trasparenza_staging").fetchone()[0]
    logger.info(f"Righe totali ora in atti_trasparenza_staging: {n_staging}")
    conn.close()


if __name__ == "__main__":
    main()
