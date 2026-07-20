"""Rilevamento di frazionamento artificioso degli affidamenti (TAL-23).

Normativa di riferimento:
    D.lgs. 36/2023, art. 50 — soglie per affidamento diretto:
        - servizi/forniture: fino a 140.000 EUR
        - lavori: fino a 150.000 EUR

Red flag: un ente che nell'arco di FINESTRA_GIORNI ha almeno N_ATTI_SOGLIA
affidamenti con importo ciascuno < SOGLIA_FORNITURE EUR, ma la cui somma supera
SOGLIA_FORNITURE EUR. Indicatore di potenziale suddivisione artificiale
dell'appalto per evitare l'obbligo di gara.

Disclaimer: segnalazione da verificare, non accertamento di illecito.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# Soglie (documentate con il riferimento normativo)
# ---------------------------------------------------------------------------

# Art. 50, co. 1, lett. b), D.lgs. 36/2023 (come aggiornato dal correttivo).
SOGLIA_FORNITURE = 140_000.0

# Finestra temporale: 3 mesi (90 giorni) — criterio consolidato in giurisprudenza.
FINESTRA_GIORNI = 90

# Minimo di atti nella finestra per scattare il flag.
N_ATTI_SOGLIA = 3


# ---------------------------------------------------------------------------
# Risultato
# ---------------------------------------------------------------------------


@dataclass
class FrazionamentoRilevato:
    ente_id: int
    codice_istat: str
    n_atti: int
    totale_euro: float
    periodo_da: str  # ISO date
    periodo_a: str  # ISO date
    atti: list[dict] = field(default_factory=list)  # {id, url_fonte, importo, data_atto}


# ---------------------------------------------------------------------------
# Logica di rilevamento
# ---------------------------------------------------------------------------


def rileva_frazionamento(
    conn: sqlite3.Connection,
    *,
    soglia: float = SOGLIA_FORNITURE,
    finestra_giorni: int = FINESTRA_GIORNI,
    n_atti_soglia: int = N_ATTI_SOGLIA,
) -> list[FrazionamentoRilevato]:
    """Analizza il DB e restituisce i casi di potenziale frazionamento.

    Per ogni ente recupera gli atti con importo < soglia, poi cerca finestre
    temporali di ``finestra_giorni`` giorni con almeno ``n_atti_soglia`` atti
    il cui totale supera ``soglia``.

    Returns:
        Lista di ``FrazionamentoRilevato``, una per ogni ente/finestra segnalata.
    """
    # COALESCE: data_atto manca sempre o quasi su alcune piattaforme (jCityGov,
    # catania, urbi, hspromila, ribera — espongono solo la finestra di
    # pubblicazione nella pagina-lista, non la data dell'atto). Senza fallback
    # su data_pub questi enti restano invisibili al check.
    rows = conn.execute(
        """
        SELECT a.id, a.ente_id, e.codice_istat,
               a.importo_euro, COALESCE(a.data_atto, a.data_pub) AS data_atto,
               a.url_fonte, a.cig
        FROM   atti a
        JOIN   enti e ON e.id = a.ente_id
        WHERE  a.importo_euro > 0
          AND  a.importo_euro < ?
          AND  COALESCE(a.data_atto, a.data_pub) IS NOT NULL
        ORDER  BY a.ente_id, data_atto
        """,
        (soglia,),
    ).fetchall()

    # Raggruppa per ente
    per_ente: dict[int, list[sqlite3.Row]] = {}
    for row in rows:
        per_ente.setdefault(row["ente_id"], []).append(row)

    risultati: list[FrazionamentoRilevato] = []

    for ente_id, atti in per_ente.items():
        # Scansione sliding window: per ogni atto come "ancora", cerca quanti
        # atti cadono nella finestra successiva (finestra_giorni giorni).
        # Usa l'istat dell'ente (tutti i rows lo hanno uguale per lo stesso ente_id).
        codice_istat = atti[0]["codice_istat"]
        finestre_già_segnalate: set[str] = set()

        for i, ancora in enumerate(atti):
            data_ancora = date.fromisoformat(ancora["data_atto"])
            data_fine = data_ancora + timedelta(days=finestra_giorni)

            atti_finestra = [a for a in atti[i:] if date.fromisoformat(a["data_atto"]) <= data_fine]

            if len(atti_finestra) < n_atti_soglia:
                continue

            totale = sum(a["importo_euro"] for a in atti_finestra)
            if totale <= soglia:
                continue

            # Chiave di dedup: coppia (periodo_da, ente_id)
            chiave = f"{ente_id}:{ancora['data_atto']}"
            if chiave in finestre_già_segnalate:
                continue
            finestre_già_segnalate.add(chiave)

            periodo_a = max(a["data_atto"] for a in atti_finestra)
            risultati.append(
                FrazionamentoRilevato(
                    ente_id=ente_id,
                    codice_istat=codice_istat,
                    n_atti=len(atti_finestra),
                    totale_euro=totale,
                    periodo_da=ancora["data_atto"],
                    periodo_a=periodo_a,
                    atti=[
                        {
                            "id": a["id"],
                            "url_fonte": a["url_fonte"],
                            "importo_euro": a["importo_euro"],
                            "data_atto": a["data_atto"],
                            "cig": a["cig"],
                        }
                        for a in atti_finestra
                    ],
                )
            )

    return risultati
