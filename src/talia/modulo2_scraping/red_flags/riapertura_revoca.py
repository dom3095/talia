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


# Ruoli in catena che rappresentano la chiusura critica di un procedimento
_RUOLI_CHIUSURA = ("revoca", "annullamento")


# Dominio del red flag (TAL-48): "pattern di bando 'su misura' ripubblicato con
# criteri aggiustati" — non contenziosi, delibere di giunta, pianificazione
# urbanistica, ordinanze, convenzioni tra enti, ecc.
#
# Un primo tentativo su singole parole chiave ("servizio", "procedura", "lavori"
# come token isolati) si è rivelato troppo permissivo: parole isolate come
# "servizio" compaiono anche in "autovetture DI SERVIZIO" (censimento veicoli),
# "servizi demografici" (nome di un ufficio), "servizio idrico integrato"
# (adesione societaria) — nessuno di questi è un bando. Verificato sui 23 flag
# residui reali dopo il primo giro di filtro: 7/23 (30%) restavano falsi
# positivi proprio per questo. Sostituito con frasi (non singole parole):
# "determina a contrarre", "affidamento diretto/dei/del/della/delle",
# "procedura di gara/aperta/negoziata/ristretta" — che richiedono il contesto
# giuridico specifico dell'atto di gara, non la sola presenza di una parola
# genericamente burocratica.
_RE_DOMINIO_GARA = re.compile(
    r"\b(?:"
    r"gar[ae]"
    r"|appalt\w*"
    r"|bando\w*"
    r"|concors\w*"
    r"|capitolat\w*"
    r"|aggiudicazion\w*"
    r"|determina(?:zione)?\s+a\s+contra(?:rre|ttare)"
    r"|affidament\w*\s+(?:diretto|dei|del|della|delle)"
    r"|procedura\s+(?:di\s+gara|aperta|negoziata|ristretta)"
    r")\b",
    re.IGNORECASE,
)


def _tokenize_oggetto(testo: str) -> set[str]:
    """Tokenizza un oggetto atto: minuscolo, rimuovi punteggiatura, stopword."""
    if not testo:
        return set()
    # Minuscolo, split su non-word, rimuovi stopword
    tokens = re.findall(r"\b\w+\b", testo.lower())
    return {t for t in tokens if t not in _STOPWORD and len(t) > 2}


def _e_dominio_gara_appalti(oggetto: str) -> bool:
    """Verifica se l'oggetto riguarda gare/appalti/concorsi (dominio del red flag).

    Senza questo filtro il red flag si applicava a qualunque procedimento
    revocato/annullato — contenziosi, delibere di giunta, pianificazione
    urbanistica — non solo ai bandi per cui è stato progettato (TAL-59: 532/555
    procedimenti annullati/revocati nel DB reale non avevano nessun atto di tipo
    gara/concorso/bando).
    """
    if not oggetto:
        return False
    return bool(_RE_DOMINIO_GARA.search(oggetto))


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
            SELECT id, oggetto, COALESCE(data_atto, data_pub) AS data_evento FROM atti
            WHERE ente_id = ?
            ORDER BY data_evento ASC
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

    segnaposto = ",".join("?" * len(_RUOLI_CHIUSURA))
    try:
        catene_revocate = conn.execute(
            f"""
            SELECT p.id, p.ente_id, p.oggetto, p.metodo_individuazione,
                   MAX(COALESCE(a.data_atto, a.data_pub)) AS data_chiusura_eff
            FROM procedimenti p
            JOIN atti a ON a.procedimento_id = p.id
            WHERE p.stato_finale IN ('revocato', 'annullato')
              AND a.ruolo_in_catena IN ({segnaposto})
            GROUP BY p.id
            HAVING data_chiusura_eff IS NOT NULL
            """,
            _RUOLI_CHIUSURA,
        ).fetchall()
    except Exception:
        # Tabella procedimenti non ancora creata
        return []

    risultati: list[RiaperturaRivocaRilevata] = []

    for proc_rev in catene_revocate:
        proc_id = proc_rev["id"]
        ente_id = proc_rev["ente_id"]
        oggetto_rev = proc_rev["oggetto"]
        data_chiusura_rev = proc_rev["data_chiusura_eff"]
        metodo_individuazione = proc_rev["metodo_individuazione"]

        tokens_rev = _tokenize_oggetto(oggetto_rev or "")
        if not tokens_rev:
            continue

        # Guardia di dominio: solo procedimenti di gara/appalto/concorso (TAL-59)
        if not _e_dominio_gara_appalti(oggetto_rev or ""):
            continue

        # Guardia anti-periodicità: se l'oggetto è parte di routine ricorrente, skip
        if _ha_periodicita_ricorrente(conn, ente_id, oggetto_rev or "", soglia_similarita):
            continue

        try:
            # Cerca atti del MEDESIMO ente publicati DOPO la revoca. COALESCE:
            # data_atto è quasi sempre NULL su jCityGov (piattaforma dominante
            # nel DB), data_pub è la data affidabile in quel caso.
            atti_post_revoca = conn.execute(
                """
                SELECT id, oggetto, COALESCE(data_atto, data_pub) AS data_evento FROM atti
                WHERE ente_id = ?
                  AND COALESCE(data_atto, data_pub) > ?
                ORDER BY data_evento ASC
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
            if data_chiusura_rev and atto["data_evento"]:
                try:
                    d0 = date.fromisoformat(data_chiusura_rev[:10])
                    d1 = date.fromisoformat(atto["data_evento"][:10])
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
                    data_riapertura=atto["data_evento"],
                    similarita_jaccard=similarita,
                    giorni_tra_revoca_e_riapertura=giorni_delta,
                    metodo_individuazione_catena=metodo_individuazione,
                )
            )

    return risultati


__all__ = ["RiaperturaRivocaRilevata", "rileva_riapertura_dopo_revoca"]
