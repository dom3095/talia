"""Red flag: riapertura di procedimento dopo revoca/annullamento — TAL-48.

Rileva quando un ente pubblica un atto con oggetto simile dopo aver revocato/annullato
un procedimento precedente (pattern di bando "su misura" ripubblicato con criteri aggiustati).

Prerequisito: connessione SQLite con row_factory = sqlite3.Row (per accesso dict-like).

Disclaimer: segnalazione da verificare, non accertamento.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import date


@dataclass
class RiaperturaRivocaRilevata:
    """Procedimento revocato/annullato seguito da atto simile dello stesso ente."""

    procedimento_revocato_id: int
    ente_id: int
    oggetto_revocato: str | None
    data_revoca: str | None
    atto_riapertura_id: int
    oggetto_riapertura: str | None
    data_riapertura: str | None
    similarita_jaccard: float
    giorni_tra_revoca_e_riapertura: int | None
    metodo_individuazione_catena: str | None


# Stopword del dominio (escludere da confronto Jaccard)
_STOPWORD = {
    "e",
    "di",
    "da",
    "il",
    "la",
    "lo",
    "a",
    "an",
    "the",
    "in",
    "on",
    "at",
    "is",
    "are",
    "per",
    "su",
    "con",
    "del",
    "della",
    "dei",
    "delle",
    "anno",
    "mese",
    "giorno",
    "data",
    "n",
    "nr",
    "n.",
    "numero",
    "provincia",
    "comune",
    "regione",
    "sicilia",
    "ente",
    "amministrazione",
}


def _tokenize_oggetto(testo: str) -> set[str]:
    """Tokenizza un oggetto atto: minuscolo, rimuovi punteggiatura, stopword."""
    if not testo:
        return set()
    # Minuscolo, split su non-word, rimuovi stopword
    tokens = re.findall(r"\b\w+\b", testo.lower())
    return {t for t in tokens if t not in _STOPWORD and len(t) > 2}


def _jaccard_similarity(set1: set[str], set2: set[str]) -> float:
    """Calcola similarità Jaccard tra due insiemi di token."""
    if not set1 or not set2:
        return 0.0
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union if union > 0 else 0.0


def _ha_periodicita_ricorrente(
    conn: sqlite3.Connection,
    ente_id: int,
    oggetto: str,
    soglia_similarita: float = 0.5,
) -> bool:
    """Verifica se l'oggetto è parte di una routine amministrativa periodica.

    Ipotesi: se lo stesso ente ha ≥ 3 atti con oggetto simile distribuiti nel tempo,
    è una routine ricorrente (es. report trimestrali), non una riapertura.
    """
    tokens_query = _tokenize_oggetto(oggetto)
    if not tokens_query:
        return False

    try:
        atti_ente = conn.execute(
            """
            SELECT id, oggetto, data_atto FROM atti
            WHERE ente_id = ?
            ORDER BY data_atto ASC
            """,
            (ente_id,),
        ).fetchall()
    except Exception:
        return False

    # Contiamo quanti atti hanno similarità ≥ soglia
    match_count = 0
    for atto in atti_ente:
        tokens_atto = _tokenize_oggetto(atto["oggetto"] or "")
        if _jaccard_similarity(tokens_query, tokens_atto) >= soglia_similarita:
            match_count += 1
            if match_count >= 3:
                return True

    return False


def rileva_riapertura_dopo_revoca(
    conn: sqlite3.Connection,
    soglia_similarita: float = 0.5,
) -> list[RiaperturaRivocaRilevata]:
    """Trova procedimenti revocati/annullati seguiti da atto simile dello stesso ente.

    Args:
        conn: connessione SQLite
        soglia_similarita: soglia Jaccard (0.0-1.0, default 0.5)

    Returns:
        lista di RiaperturaRivocaRilevata (ordinate per proc_id)
    """
    if not 0.0 <= soglia_similarita <= 1.0:
        raise ValueError(f"soglia_similarita must be between 0.0 and 1.0, got {soglia_similarita}")

    try:
        catene_revocate = conn.execute(
            """
            SELECT p.id, p.ente_id, p.oggetto, p.data_chiusura, p.metodo_individuazione
            FROM procedimenti p
            WHERE p.stato_finale IN ('revocato', 'annullato')
              AND p.data_chiusura IS NOT NULL
            """
        ).fetchall()
    except Exception:
        # Tabella procedimenti non ancora creata
        return []

    risultati: list[RiaperturaRivocaRilevata] = []

    for proc_rev in catene_revocate:
        proc_id = proc_rev["id"]
        ente_id = proc_rev["ente_id"]
        oggetto_rev = proc_rev["oggetto"]
        data_chiusura_rev = proc_rev["data_chiusura"]
        metodo_individuazione = proc_rev["metodo_individuazione"]

        tokens_rev = _tokenize_oggetto(oggetto_rev or "")
        if not tokens_rev:
            continue

        # Guardia anti-periodicità: se l'oggetto è parte di routine ricorrente, skip
        if _ha_periodicita_ricorrente(conn, ente_id, oggetto_rev or "", soglia_similarita):
            continue

        try:
            # Cerca atti del MEDESIMO ente publicati DOPO la revoca
            atti_post_revoca = conn.execute(
                """
                SELECT id, oggetto, data_atto FROM atti
                WHERE ente_id = ?
                  AND data_atto > ?
                ORDER BY data_atto ASC
                """,
                (ente_id, data_chiusura_rev),
            ).fetchall()
        except Exception:
            continue

        for atto in atti_post_revoca:
            tokens_atto = _tokenize_oggetto(atto["oggetto"] or "")
            if not tokens_atto:
                continue

            similarita = _jaccard_similarity(tokens_rev, tokens_atto)
            if similarita < soglia_similarita:
                continue

            # Calcola giorni tra revoca e riapertura
            giorni_delta = None
            if data_chiusura_rev and atto["data_atto"]:
                try:
                    d0 = date.fromisoformat(data_chiusura_rev[:10])
                    d1 = date.fromisoformat(atto["data_atto"][:10])
                    giorni_delta = (d1 - d0).days
                except ValueError:
                    pass

            risultati.append(
                RiaperturaRivocaRilevata(
                    procedimento_revocato_id=proc_id,
                    ente_id=ente_id,
                    oggetto_revocato=oggetto_rev,
                    data_revoca=data_chiusura_rev,
                    atto_riapertura_id=atto["id"],
                    oggetto_riapertura=atto["oggetto"],
                    data_riapertura=atto["data_atto"],
                    similarita_jaccard=similarita,
                    giorni_tra_revoca_e_riapertura=giorni_delta,
                    metodo_individuazione_catena=metodo_individuazione,
                )
            )

    return risultati


__all__ = ["RiaperturaRivocaRilevata", "rileva_riapertura_dopo_revoca"]
