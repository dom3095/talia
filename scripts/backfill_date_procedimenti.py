"""Migrazione one-off (TAL-48, 2026-07-20/21).

`engine/catena.py` calcolava `data_avvio`/`data_chiusura` dei procedimenti solo da
`atti.data_atto`, NULL per l'80% degli atti nel DB (jCityGov, catania, urbi, hspromila,
ribera al 100%; halley al 12%). Il fix (COALESCE con `data_pub`) vale per i procedimenti
creati da quel commit in poi: quelli già esistenti in `talia.db` hanno ancora i valori
(spesso NULL) calcolati dal codice pre-fix.

Nessuna richiesta HTTP: ricalcola solo da dati già presenti in DB, con la stessa
semantica per metodo di individuazione usata alla creazione (vedi engine/catena.py):
- ``cig`` / ``oggetto_simile_da_verificare``: data_avvio = atto più vecchio della catena
- ``contenimento_oggetto``: data_avvio = data dell'atto originario (ruolo non derivato)

data_chiusura è ricalcolata con `_aggiorna_stato_procedimento`, la stessa funzione usata
dal codice normale — nessuna logica duplicata per quel campo.

Idempotente: rieseguibile senza effetti collaterali (se i valori sono già corretti non
cambia nulla).
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from talia.engine.catena import _RUOLI_DERIVATI, _aggiorna_stato_procedimento  # noqa: E402


def ricalcola_data_avvio(conn: sqlite3.Connection, proc_id: int, metodo: str | None) -> str | None:
    """Ricalcola data_avvio con la stessa semantica della strategia che ha creato
    il procedimento (collega_per_cig / collega_per_contenimento / collega_per_oggetto_simile
    in engine/catena.py)."""
    atti = conn.execute(
        """
        SELECT ruolo_in_catena, COALESCE(data_atto, data_pub) AS data
        FROM   atti
        WHERE  procedimento_id = ? AND COALESCE(data_atto, data_pub) IS NOT NULL
        ORDER  BY data ASC
        """,
        (proc_id,),
    ).fetchall()
    if not atti:
        return None

    if metodo == "contenimento_oggetto":
        originario = next(
            (a["data"] for a in atti if a["ruolo_in_catena"] not in _RUOLI_DERIVATI), None
        )
        return originario or atti[0]["data"]

    # cig, oggetto_simile_da_verificare, riferimento, o altro: il più vecchio della catena
    return atti[0]["data"]


def esegui_backfill(conn: sqlite3.Connection) -> dict:
    """Ricalcola data_avvio/data_chiusura per tutti i procedimenti esistenti.

    Ritorna un dict con i contatori (per verifica/log), non stampa nulla: la CLI
    stampa il riepilogo.
    """
    procedimenti = conn.execute(
        "SELECT id, metodo_individuazione, data_avvio FROM procedimenti"
    ).fetchall()

    n_avvio_cambiati = 0
    n_chiusura_cambiati = 0

    for p in procedimenti:
        nuovo_avvio = ricalcola_data_avvio(conn, p["id"], p["metodo_individuazione"])
        if nuovo_avvio != p["data_avvio"]:
            conn.execute(
                "UPDATE procedimenti SET data_avvio = ? WHERE id = ?", (nuovo_avvio, p["id"])
            )
            n_avvio_cambiati += 1

        vecchia_chiusura = conn.execute(
            "SELECT data_chiusura FROM procedimenti WHERE id = ?", (p["id"],)
        ).fetchone()["data_chiusura"]
        _aggiorna_stato_procedimento(conn, p["id"])
        nuova_chiusura = conn.execute(
            "SELECT data_chiusura FROM procedimenti WHERE id = ?", (p["id"],)
        ).fetchone()["data_chiusura"]
        if nuova_chiusura != vecchia_chiusura:
            n_chiusura_cambiati += 1

    conn.commit()
    return {
        "procedimenti_totali": len(procedimenti),
        "data_avvio_aggiornati": n_avvio_cambiati,
        "data_chiusura_aggiornati": n_chiusura_cambiati,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="talia.db", help="percorso DB (default: talia.db)")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"DB non trovato: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    prima = conn.execute(
        "SELECT COUNT(*), "
        "SUM(CASE WHEN data_avvio IS NULL THEN 1 ELSE 0 END), "
        "SUM(CASE WHEN data_chiusura IS NULL THEN 1 ELSE 0 END) "
        "FROM procedimenti"
    ).fetchone()
    print(
        f"Prima: {prima[0]} procedimenti | {prima[1]} senza data_avvio | "
        f"{prima[2]} senza data_chiusura"
    )

    risultato = esegui_backfill(conn)

    dopo = conn.execute(
        "SELECT SUM(CASE WHEN data_avvio IS NULL THEN 1 ELSE 0 END), "
        "SUM(CASE WHEN data_chiusura IS NULL THEN 1 ELSE 0 END) "
        "FROM procedimenti"
    ).fetchone()
    print(
        f"Dopo:  {prima[0]} procedimenti | {dopo[0]} senza data_avvio | "
        f"{dopo[1]} senza data_chiusura"
    )
    print(
        f"Aggiornati: {risultato['data_avvio_aggiornati']} data_avvio, "
        f"{risultato['data_chiusura_aggiornati']} data_chiusura"
    )

    conn.close()


if __name__ == "__main__":
    main()
