"""Rilevamento di finestre di pubblicazione bandi anormalmente brevi (TAL-23).

Normativa di riferimento:
    D.lgs. 36/2023, art. 71 e Allegato II.1 — termini minimi di pubblicazione:
        - sopra soglia UE: 30 giorni (open) / 25 giorni (prenotifica)
        - sotto soglia nazionale: 15 giorni (prassi consolidata TAR Sicilia)

Red flag: bando con finestra di pubblicazione
    data_scadenza - data_pub < MIN_GIORNI_BANDO_SOTTO_SOGLIA (15 giorni)

Una finestra così breve riduce di fatto la concorrenza (solo operatori
già allertati possono partecipare) e può essere indice di accordo preventivo.

Disclaimer: segnalazione da verificare, non accertamento.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date


# ---------------------------------------------------------------------------
# Soglie
# ---------------------------------------------------------------------------

# Minimo di giorni di pubblicazione per bandi sotto soglia (prassi TAR).
MIN_GIORNI_BANDO_SOTTO_SOGLIA = 15

# Minimo per bandi sopra soglia UE (art. 71, D.lgs. 36/2023).
MIN_GIORNI_BANDO_SOPRA_SOGLIA = 30

# Soglia bando sopra/sotto (servizi/forniture, D.lgs. 36/2023).
SOGLIA_UE_FORNITURE = 215_000.0  # enti locali; adeguato periodicamente UE


# ---------------------------------------------------------------------------
# Risultato
# ---------------------------------------------------------------------------


@dataclass
class TempoAnomalioRilevato:
    ente_id: int
    codice_istat: str
    atto_id: int
    url_fonte: str
    oggetto: str | None
    data_pub: str
    data_scadenza: str
    giorni_pubblicazione: int
    soglia_applicata: int
    importo_euro: float | None


# ---------------------------------------------------------------------------
# Logica di rilevamento
# ---------------------------------------------------------------------------


def rileva_tempi_anomali(
    conn: sqlite3.Connection,
    *,
    min_giorni_sotto_soglia: int = MIN_GIORNI_BANDO_SOTTO_SOGLIA,
    min_giorni_sopra_soglia: int = MIN_GIORNI_BANDO_SOPRA_SOGLIA,
    soglia_ue: float = SOGLIA_UE_FORNITURE,
) -> list[TempoAnomalioRilevato]:
    """Analizza i bandi nel DB e segnala quelli con pubblicazione troppo breve.

    Considera solo atti con tipo == 'bando' e con sia data_pub che data_scadenza
    valorizzati. Applica soglie diverse in base all'importo.

    Returns:
        Lista di ``TempoAnomalioRilevato`` per ogni bando anomalo trovato.
    """
    rows = conn.execute(
        """
        SELECT  a.id, a.ente_id, e.codice_istat,
                a.url_fonte, a.oggetto,
                a.data_pub, a.data_scadenza, a.importo_euro
        FROM    atti a
        JOIN    enti e ON e.id = a.ente_id
        WHERE   lower(a.tipo) = 'bando'
          AND   a.data_pub IS NOT NULL
          AND   a.data_scadenza IS NOT NULL
        ORDER   BY a.ente_id, a.data_pub
        """,
    ).fetchall()

    risultati: list[TempoAnomalioRilevato] = []

    for row in rows:
        try:
            d_pub = date.fromisoformat(row["data_pub"])
            d_scad = date.fromisoformat(row["data_scadenza"])
        except ValueError:
            continue

        giorni = (d_scad - d_pub).days
        if giorni < 0:
            continue  # data incoerente: ignorare

        importo = row["importo_euro"]
        sopra_ue = importo is not None and importo >= soglia_ue
        soglia = min_giorni_sopra_soglia if sopra_ue else min_giorni_sotto_soglia

        if giorni >= soglia:
            continue  # OK: pubblicazione nei tempi

        risultati.append(
            TempoAnomalioRilevato(
                ente_id=row["ente_id"],
                codice_istat=row["codice_istat"],
                atto_id=row["id"],
                url_fonte=row["url_fonte"],
                oggetto=row["oggetto"],
                data_pub=row["data_pub"],
                data_scadenza=row["data_scadenza"],
                giorni_pubblicazione=giorni,
                soglia_applicata=soglia,
                importo_euro=importo,
            )
        )

    return risultati
