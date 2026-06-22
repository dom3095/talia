"""Rilevamento di eccessiva concentrazione di affidamenti diretti (TAL-23).

Normativa di riferimento:
    D.lgs. 36/2023, art. 49 (principio di concorrenza) e art. 50 (affidamenti diretti).
    L. 190/2012 (anticorruzione) — evitare affidamenti ripetuti agli stessi soggetti.

Indicatore: un ente che in un anno ha almeno MIN_ATTI_ANNO atti registrati e
tra questi la quota di affidamenti diretti (tipo != 'bando') supera
SOGLIA_QUOTA_DIRETTI. La mancanza di ricorso a procedure competitive è
anomalia oggettivamente misurabile.

Nota: senza dati strutturati sul fornitore (disponibili solo via ANAC),
questo è un indicatore di processo, non di destinatario. La concentrazione
per fornitore richiederà il join con i dati ANAC (TAL-22).

Disclaimer: segnalazione da verificare, non accertamento.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Soglie
# ---------------------------------------------------------------------------

# Minimo di atti nell'anno per avere statistica significativa.
MIN_ATTI_ANNO = 10

# Quota massima di affidamenti diretti prima di scattare il flag (80%).
SOGLIA_QUOTA_DIRETTI = 0.80

# Anno di riferimento: se None, usa l'anno con più atti per ogni ente.
ANNO_DEFAULT = None


# ---------------------------------------------------------------------------
# Risultato
# ---------------------------------------------------------------------------


@dataclass
class ConcentrazioneRilevata:
    ente_id: int
    codice_istat: str
    anno: int
    n_totale: int
    n_diretti: int       # tipo != 'bando'
    n_bandi: int         # tipo == 'bando'
    quota_diretti: float  # n_diretti / n_totale
    atti_campione: list[dict] = field(default_factory=list)  # fino a 5 atti diretti


# ---------------------------------------------------------------------------
# Logica di rilevamento
# ---------------------------------------------------------------------------


def rileva_concentrazione(
    conn: sqlite3.Connection,
    *,
    min_atti_anno: int = MIN_ATTI_ANNO,
    soglia_quota: float = SOGLIA_QUOTA_DIRETTI,
    anno: int | None = ANNO_DEFAULT,
) -> list[ConcentrazioneRilevata]:
    """Analizza la quota di affidamenti diretti per ente per anno.

    Per ogni ente/anno con almeno ``min_atti_anno`` atti, segnala se la quota
    di affidamenti non a gara supera ``soglia_quota``.

    Returns:
        Lista di ``ConcentrazioneRilevata`` con dettaglio per ente/anno.
    """
    filtro_anno = "AND strftime('%Y', a.data_atto) = ?" if anno is not None else ""
    # strftime('%Y') restituisce TEXT in SQLite → convertiamo a str per il confronto
    params_base: list = [str(anno)] if anno is not None else []

    # Conteggio per ente/anno
    rows = conn.execute(
        f"""
        SELECT  a.ente_id,
                e.codice_istat,
                strftime('%Y', a.data_atto) AS anno,
                COUNT(*) AS n_totale,
                SUM(CASE WHEN lower(a.tipo) != 'bando' THEN 1 ELSE 0 END) AS n_diretti,
                SUM(CASE WHEN lower(a.tipo) = 'bando'  THEN 1 ELSE 0 END) AS n_bandi
        FROM    atti a
        JOIN    enti e ON e.id = a.ente_id
        WHERE   a.data_atto IS NOT NULL
          {filtro_anno}
        GROUP   BY a.ente_id, anno
        HAVING  n_totale >= ?
        ORDER   BY a.ente_id, anno
        """,
        params_base + [min_atti_anno],
    ).fetchall()

    risultati: list[ConcentrazioneRilevata] = []

    for row in rows:
        n_totale = row["n_totale"]
        n_diretti = row["n_diretti"]
        quota = n_diretti / n_totale if n_totale > 0 else 0.0

        if quota <= soglia_quota:
            continue

        # Campione di atti diretti per l'esplicabilità
        campione = conn.execute(
            """
            SELECT a.id, a.url_fonte, a.tipo, a.oggetto, a.importo_euro, a.data_atto
            FROM   atti a
            JOIN   enti e ON e.id = a.ente_id
            WHERE  a.ente_id = ?
              AND  strftime('%Y', a.data_atto) = ?
              AND  lower(a.tipo) != 'bando'
            ORDER  BY a.data_atto DESC
            LIMIT  5
            """,
            (row["ente_id"], row["anno"]),
        ).fetchall()

        risultati.append(
            ConcentrazioneRilevata(
                ente_id=row["ente_id"],
                codice_istat=row["codice_istat"],
                anno=int(row["anno"]),
                n_totale=n_totale,
                n_diretti=n_diretti,
                n_bandi=row["n_bandi"],
                quota_diretti=round(quota, 4),
                atti_campione=[
                    {
                        "id": r["id"],
                        "url_fonte": r["url_fonte"],
                        "tipo": r["tipo"],
                        "oggetto": r["oggetto"],
                        "importo_euro": r["importo_euro"],
                        "data_atto": r["data_atto"],
                    }
                    for r in campione
                ],
            )
        )

    return risultati
