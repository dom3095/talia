"""Motore di ricostruzione e individuazione della catena di eventi — TAL-43.

Un procedimento è una sequenza di atti amministrativi correlati:
avvio → modifiche/proroghe → conclusione (aggiudicazione) oppure revoca/annullamento.

Tre strategie di individuazione (deterministiche, senza LLM):
1. **CIG/CUP identico** — collegamento certo.
2. **Riferimenti incrociati** — un atto cita esplicitamente numero+data di un altro
   (es. "revoca della determina n.35 del 22/12/2025").
3. **Oggetto normalizzato simile** — Jaccard su trigrammi entro lo stesso ente+anno;
   produce catene marcate 'da_verificare', richiedono revisione umana.

Principio di funzionamento per M2 (scraping continuo):
Le catene vengono individuate a partire dai **metadati** già raccolti dagli spider
(oggetto, tipo, numero, cig, data_atto) — senza scaricare né leggere i PDF.
Il campo `testo_estratto` è un segnale bonus quando disponibile, non un prerequisito.
Il campo `oggetto` è il proxy primario: "REVOCA CONCORSO PUBBLICO..." classifica
l'atto come revoca anche senza testo completo.

Per fascicoli M1 (PDF già disponibili localmente) esiste `costruisci_catena_da_testi`,
che opera in-memory sul testo già estratto.
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime

# ---------------------------------------------------------------------------
# Classificazione ruolo dell'atto nella catena
# ---------------------------------------------------------------------------

# Ordinati per priorità: il più specifico prima.
_PATTERN_RUOLO: list[tuple[str, re.Pattern[str]]] = [
    ("revoca", re.compile(
        r"\b(revoc[aahi]\b|revoca\s+(?:il\s+)?(?:bando|concorso|gara|affidamento|contratto))",
        re.IGNORECASE,
    )),
    ("annullamento", re.compile(
        r"\b(annull(?:a|amento|ato|ati)\b|annulla\s+(?:il\s+)?(?:bando|concorso|gara|procedura))",
        re.IGNORECASE,
    )),
    ("aggiudicazione", re.compile(
        r"\b(aggiudic(?:a|azione|ato|ati)\b|aggiudicazione\s+definitiva|approvazione\s+graduatoria)",
        re.IGNORECASE,
    )),
    ("proroga", re.compile(
        r"\b(proroga\b|prorogato\b|proroga\s+termini|estensione\s+(?:dei\s+)?termini)",
        re.IGNORECASE,
    )),
    ("modifica", re.compile(
        r"\b(rettif(?:ica|icato)\b|rettifica\s+bando|modifica\s+bando|integrazione\s+(?:al\s+)?bando)",
        re.IGNORECASE,
    )),
    ("avvio", re.compile(
        r"\b(bando\b|indizione\b|avviso\s+pubblico|procedura\s+(?:aperta|negoziata|ristretta)"
        r"|concorso\s+pubblico|manifestazione\s+d['']interesse)",
        re.IGNORECASE,
    )),
]


def classifica_ruolo(testo: str = "", tipo_atto: str = "", oggetto: str = "") -> str:
    """Classifica il ruolo di un atto nella catena del procedimento.

    Proxy primari (sempre disponibili da scraping):
      - `oggetto` — titolo dell'atto dalla pagina web (es. "REVOCA CONCORSO PUBBLICO…")
      - `tipo_atto` — tipo DB (es. "bando", "determina")

    Proxy secondario (solo quando il PDF è stato scaricato):
      - `testo` — testo estratto; analizza le prime 2 000 caratteri

    Ritorna uno tra: avvio / modifica / proroga / aggiudicazione /
    revoca / annullamento / altro.
    """
    # oggetto ha la precedenza perché è un riassunto conciso e privo di boilerplate
    campione = (oggetto + " " + tipo_atto + " " + testo[:2000]).strip()
    for ruolo, pattern in _PATTERN_RUOLO:
        if pattern.search(campione):
            return ruolo
    return "altro"


# ---------------------------------------------------------------------------
# Estrazione riferimenti incrociati
# ---------------------------------------------------------------------------

_RE_RIFERIMENTO_ATTO = re.compile(
    r"(?:determina|delibera|decreto|ordinanza|nota)\s+"
    r"n[°.]?\s*(\d+)\s*"
    r"del\s+(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})",
    re.IGNORECASE,
)
_RE_CIG = re.compile(r"\bCIG\s*[:=]?\s*([A-Z0-9]{10})\b", re.IGNORECASE)
_RE_CUP = re.compile(r"\bCUP\s*[:=]?\s*([A-Z][A-Z0-9]{14})\b", re.IGNORECASE)
# Numero atto standalone (es. "Det. n. 35/2025")
_RE_NUM_ATTO = re.compile(
    r"\b(?:det|delib|ord|dec)[.\s]*n[°.]?\s*(\d+)[/\s]+(\d{4})\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RiferimentoAtto:
    """Riferimento incrociato a un altro atto trovato nel testo."""

    tipo: str      # 'numero_atto' | 'cig' | 'cup'
    valore: str
    contesto: str  # snippet intorno al match


def estrai_riferimenti(testo: str) -> list[RiferimentoAtto]:
    """Estrae riferimenti ad altri atti dal testo (regex, deterministico)."""
    risultati: list[RiferimentoAtto] = []
    for m in _RE_RIFERIMENTO_ATTO.finditer(testo):
        risultati.append(RiferimentoAtto(
            tipo="numero_atto",
            valore=f"n.{m.group(1)} del {m.group(2)}",
            contesto=testo[max(0, m.start() - 30):m.end() + 30].replace("\n", " "),
        ))
    for m in _RE_NUM_ATTO.finditer(testo):
        risultati.append(RiferimentoAtto(
            tipo="numero_atto",
            valore=f"n.{m.group(1)}/{m.group(2)}",
            contesto=testo[max(0, m.start() - 20):m.end() + 20].replace("\n", " "),
        ))
    for m in _RE_CIG.finditer(testo):
        risultati.append(RiferimentoAtto(
            tipo="cig",
            valore=m.group(1).upper(),
            contesto=testo[max(0, m.start() - 20):m.end() + 20].replace("\n", " "),
        ))
    for m in _RE_CUP.finditer(testo):
        risultati.append(RiferimentoAtto(
            tipo="cup",
            valore=m.group(1).upper(),
            contesto=testo[max(0, m.start() - 20):m.end() + 20].replace("\n", " "),
        ))
    return risultati


# ---------------------------------------------------------------------------
# Normalizzazione oggetto per collegamento per similarità
# ---------------------------------------------------------------------------

_RE_NON_ALFANUM = re.compile(r"[^\w\s]", re.UNICODE)
_STOPWORD_IT = frozenset(
    "di il la le gli i un una dei delle dello della per da con su tra fra non"
    " del al e è art n nr n°".split()
)
_SOGLIA_JACCARD = 0.35  # sotto questa soglia non colleghiamo


def _normalizza_oggetto(oggetto: str) -> str:
    s = unicodedata.normalize("NFC", oggetto.lower())
    s = _RE_NON_ALFANUM.sub(" ", s)
    tokens = [t for t in s.split() if t not in _STOPWORD_IT and len(t) > 2]
    return " ".join(tokens)


def _jaccard_trigrammi(a: str, b: str) -> float:
    def ngrams(s: str) -> set[str]:
        return {s[i : i + 3] for i in range(len(s) - 2)} if len(s) >= 3 else set()

    sa, sb = ngrams(a), ngrams(b)
    if not sa and not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


# ---------------------------------------------------------------------------
# Individuazione catene nel DB
# ---------------------------------------------------------------------------


def collega_per_cig(conn: sqlite3.Connection, cig: str) -> int | None:
    """Raggruppa tutti gli atti con lo stesso CIG in un procedimento.

    Crea il procedimento se non esiste; aggiorna stato e date se già presente.
    Ritorna il procedimento_id, o None se non ci sono atti con quel CIG.
    """
    atti = conn.execute(
        """
        SELECT a.id, a.ente_id, a.tipo, a.oggetto, a.data_atto, a.testo_estratto
        FROM   atti a
        WHERE  a.cig = ?
        ORDER  BY a.data_atto ASC NULLS LAST
        """,
        (cig,),
    ).fetchall()

    if not atti:
        return None

    ente_id = atti[0]["ente_id"]
    data_avvio = next((a["data_atto"] for a in atti if a["data_atto"]), None)
    data_chiusura = atti[-1]["data_atto"] if len(atti) > 1 else None
    oggetto = next((a["oggetto"] for a in atti if a["oggetto"]), "") or ""

    ruoli = [
        classifica_ruolo(a["testo_estratto"] or "", a["tipo"] or "", a["oggetto"] or "")
        for a in atti
    ]
    proc_id = _trova_o_crea_procedimento(
        conn,
        ente_id=ente_id,
        cig=cig,
        oggetto=oggetto,
        tipo=_inferisci_tipo(ruoli),
        data_avvio=data_avvio,
        data_chiusura=data_chiusura,
        stato_finale=_stato_da_ruoli(ruoli),
        metodo_individuazione="cig",
    )
    for atto, ruolo in zip(atti, ruoli, strict=False):
        _collega_atto(conn, atto_id=atto["id"], procedimento_id=proc_id, ruolo=ruolo)

    conn.commit()
    return proc_id


def collega_per_riferimenti_incrociati(
    conn: sqlite3.Connection, ente_id: int | None = None
) -> int:
    """Individua catene usando riferimenti incrociati espliciti.

    Cerca in `oggetto` (proxy primario, sempre disponibile da scraping) e in
    `testo_estratto` (bonus quando il PDF è stato scaricato):
    - CIG/CUP citati → collega all'atto del procedimento già noto
    - "determina n.X del GG/MM/AAAA" → trova l'atto originario per numero+data

    Ritorna il numero di nuovi collegamenti creati.
    """
    filtro = "AND a.ente_id = ?" if ente_id is not None else ""
    params: tuple = (ente_id,) if ente_id is not None else ()

    # Nessun filtro su testo_estratto: i riferimenti possono stare nell'oggetto
    atti = conn.execute(
        f"""
        SELECT a.id, a.ente_id, a.oggetto, a.testo_estratto, a.numero, a.data_atto,
               a.procedimento_id, a.tipo
        FROM   atti a
        WHERE  (a.oggetto IS NOT NULL OR a.testo_estratto IS NOT NULL)
        {filtro}
        """,
        params,
    ).fetchall()

    n_collegati = 0
    for atto in atti:
        # Proxy primario: oggetto; secondario: testo estratto
        testo_da_cercare = (atto["oggetto"] or "") + " " + (atto["testo_estratto"] or "")
        refs = estrai_riferimenti(testo_da_cercare)

        for ref in refs:
            if ref.tipo == "cig":
                proc_row = conn.execute(
                    "SELECT id FROM procedimenti WHERE cig = ? AND ente_id = ?",
                    (ref.valore, atto["ente_id"]),
                ).fetchone()
                if proc_row and atto["procedimento_id"] is None:
                    ruolo = classifica_ruolo(
                        atto["testo_estratto"] or "", atto["tipo"] or "", atto["oggetto"] or ""
                    )
                    _collega_atto(
                        conn,
                        atto_id=atto["id"],
                        procedimento_id=proc_row["id"],
                        ruolo=ruolo,
                    )
                    n_collegati += 1

            elif ref.tipo == "numero_atto":
                m_num = re.search(r"n\.(\d+)", ref.valore)
                if not m_num:
                    continue
                numero = m_num.group(1)
                atto_orig = conn.execute(
                    "SELECT id, procedimento_id FROM atti WHERE ente_id = ? AND numero = ? LIMIT 1",
                    (atto["ente_id"], numero),
                ).fetchone()
                if atto_orig and atto_orig["procedimento_id"] is not None:
                    if atto["procedimento_id"] is None:
                        ruolo = classifica_ruolo(
                            atto["testo_estratto"] or "", atto["tipo"] or "", atto["oggetto"] or ""
                        )
                        _collega_atto(
                            conn,
                            atto_id=atto["id"],
                            procedimento_id=atto_orig["procedimento_id"],
                            ruolo=ruolo,
                        )
                        n_collegati += 1

    conn.commit()
    return n_collegati


def collega_per_oggetto_simile(
    conn: sqlite3.Connection,
    ente_id: int,
    soglia: float = _SOGLIA_JACCARD,
) -> int:
    """Individua catene per similarità dell'oggetto (Jaccard su trigrammi).

    Opera solo su atti senza procedimento_id ancora assegnato.
    I procedimenti creati vengono marcati come 'da_verificare' perché
    il collegamento è probabilistico e richiede revisione umana.

    Ritorna il numero di nuovi procedimenti creati.
    """
    atti = conn.execute(
        """
        SELECT id, ente_id, oggetto, tipo, data_atto, testo_estratto
        FROM   atti
        WHERE  ente_id = ?
          AND  procedimento_id IS NULL
          AND  oggetto IS NOT NULL AND oggetto != ''
        ORDER  BY data_atto ASC NULLS LAST
        """,
        (ente_id,),
    ).fetchall()

    if not atti:
        return 0

    normalizzati = [(a, _normalizza_oggetto(a["oggetto"])) for a in atti]
    assegnazioni: dict[int, int] = {}  # atto_id → proc_id
    n_creati = 0

    for i, (atto_i, norm_i) in enumerate(normalizzati):
        if atto_i["id"] in assegnazioni:
            continue

        gruppo = [atto_i]
        for j, (atto_j, norm_j) in enumerate(normalizzati):
            if i == j or atto_j["id"] in assegnazioni:
                continue
            if _jaccard_trigrammi(norm_i, norm_j) >= soglia:
                gruppo.append(atto_j)

        if len(gruppo) < 2:
            continue

        ruoli = [
            classifica_ruolo(a["testo_estratto"] or "", a["tipo"] or "", a["oggetto"] or "")
            for a in gruppo
        ]
        dati_ordinati = sorted(gruppo, key=lambda a: a["data_atto"] or "")
        proc_id = _trova_o_crea_procedimento(
            conn,
            ente_id=ente_id,
            cig=None,
            oggetto=atto_i["oggetto"],
            tipo=_inferisci_tipo(ruoli),
            data_avvio=dati_ordinati[0]["data_atto"],
            data_chiusura=dati_ordinati[-1]["data_atto"],
            stato_finale=_stato_da_ruoli(ruoli),
            metodo_individuazione="oggetto_simile_da_verificare",
        )
        for atto, ruolo in zip(gruppo, ruoli, strict=False):
            assegnazioni[atto["id"]] = proc_id
            _collega_atto(conn, atto_id=atto["id"], procedimento_id=proc_id, ruolo=ruolo)
        n_creati += 1

    conn.commit()
    return n_creati


def ricostruisci_catene(conn: sqlite3.Connection, ente_id: int | None = None) -> dict:
    """Orchestratore: applica tutte le strategie di individuazione catene.

    Ordine di applicazione:
    1. CIG esplicito (alta confidenza)
    2. Riferimenti incrociati nel testo (alta confidenza)
    3. Oggetto simile per ente (bassa confidenza → marcato 'da_verificare')

    Args:
        conn: connessione con il DB già inizializzato.
        ente_id: se fornito, processa solo gli atti di quell'ente.

    Returns:
        dict con metriche per strategia.
    """
    _evolvi_schema(conn)

    filtro = "AND ente_id = ?" if ente_id is not None else ""
    params: tuple = (ente_id,) if ente_id is not None else ()

    # --- Strategia 1: CIG ---
    cigs = conn.execute(
        f"SELECT DISTINCT cig FROM atti WHERE cig IS NOT NULL AND cig != '' {filtro}",
        params,
    ).fetchall()
    n_proc_cig = sum(1 for row in cigs if collega_per_cig(conn, row["cig"]) is not None)

    # --- Strategia 2: riferimenti incrociati ---
    n_rif = collega_per_riferimenti_incrociati(conn, ente_id)

    # --- Strategia 3: oggetto simile (per ente) ---
    enti_ids: list[int]
    if ente_id is not None:
        enti_ids = [ente_id]
    else:
        enti_ids = [
            row["id"] for row in conn.execute("SELECT id FROM enti").fetchall()
        ]
    n_proc_fuzzy = sum(collega_per_oggetto_simile(conn, eid) for eid in enti_ids)

    n_atti_collegati = conn.execute(
        f"SELECT COUNT(*) FROM atti WHERE procedimento_id IS NOT NULL {filtro}",
        params,
    ).fetchone()[0]

    return {
        "n_procedimenti_da_cig": n_proc_cig,
        "n_atti_collegati_da_riferimenti": n_rif,
        "n_procedimenti_da_oggetto": n_proc_fuzzy,
        "n_atti_collegati_totale": n_atti_collegati,
    }


# ---------------------------------------------------------------------------
# Catena in-memory per fascicoli M1 (più PDF caricati insieme)
# ---------------------------------------------------------------------------


@dataclass
class EventoNellaCatena:
    """Un atto all'interno di una catena, arricchito con ruolo e riferimenti."""

    ruolo: str                              # avvio / modifica / revoca / …
    testo: str                              # testo estratto (o oggetto/titolo)
    data: str | None                        # ISO date string, se rilevabile
    riferimenti: list[RiferimentoAtto] = field(default_factory=list)
    percorso: str | None = None             # path del PDF sorgente
    metadati: dict = field(default_factory=dict)


@dataclass
class CatenaEventi:
    """Sequenza ordinata di atti di un procedimento.

    Disclaimer: segnalazioni da verificare, non accertamenti.
    """

    eventi: list[EventoNellaCatena]         # ordinati per data (avvio → chiusura)
    stato_finale: str                       # in_corso / revocato / annullato / aggiudicato
    cig: str | None = None
    metodo_individuazione: str = "fascicolo"  # 'cig' | 'riferimenti' | 'fascicolo'


def costruisci_catena_da_testi(
    testi: list[dict],
) -> CatenaEventi:
    """Costruisce una catena di eventi da un elenco di atti già estratti.

    Args:
        testi: lista di dict con chiavi 'testo' (str), 'tipo' (str, opz.),
               'data' (str ISO, opz.), 'percorso' (str, opz.), 'metadati' (dict, opz.).
               Tipicamente prodotti da `engine.pdf_text` applicato a più PDF.

    Returns:
        CatenaEventi con gli atti classificati e ordinati cronologicamente.

    Nota: quando i PDF vengono da un fascicolo M1 già raggruppato dall'utente,
    il collegamento è garantito dal fatto che l'utente li ha caricati insieme.
    """
    eventi: list[EventoNellaCatena] = []
    cig_globale: str | None = None

    for t in testi:
        testo = t.get("testo", "")
        tipo = t.get("tipo", "")
        refs = estrai_riferimenti(testo)

        # Primo CIG trovato diventa il CIG del procedimento
        if cig_globale is None:
            for ref in refs:
                if ref.tipo == "cig":
                    cig_globale = ref.valore
                    break

        eventi.append(EventoNellaCatena(
            ruolo=classifica_ruolo(testo, tipo),
            testo=testo[:500],  # snippet per il report
            data=t.get("data"),
            riferimenti=refs,
            percorso=t.get("percorso"),
            metadati=t.get("metadati", {}),
        ))

    # Ordinamento cronologico (None alla fine)
    eventi.sort(key=lambda e: e.data or "9999")
    ruoli = [e.ruolo for e in eventi]

    return CatenaEventi(
        eventi=eventi,
        stato_finale=_stato_da_ruoli(ruoli),
        cig=cig_globale,
        metodo_individuazione="fascicolo",
    )


# ---------------------------------------------------------------------------
# Schema DB (evoluzione lazy, idempotente) — TAL-42
# ---------------------------------------------------------------------------


def _evolvi_schema(conn: sqlite3.Connection) -> None:
    """Aggiunge tabella procedimenti e colonne su atti se non esistono."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS procedimenti (
            id                     INTEGER PRIMARY KEY,
            ente_id                INTEGER NOT NULL REFERENCES enti(id),
            tipo                   TEXT,
            cig                    TEXT,
            oggetto                TEXT,
            data_avvio             TEXT,
            data_chiusura          TEXT,
            stato_finale           TEXT,
            metodo_individuazione  TEXT,
            creato_a               TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_procedimenti_cig  ON procedimenti (cig)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_procedimenti_ente ON procedimenti (ente_id)"
    )

    colonne = {row[1] for row in conn.execute("PRAGMA table_info(atti)").fetchall()}
    if "procedimento_id" not in colonne:
        conn.execute(
            "ALTER TABLE atti ADD COLUMN procedimento_id INTEGER REFERENCES procedimenti(id)"
        )
    if "ruolo_in_catena" not in colonne:
        conn.execute("ALTER TABLE atti ADD COLUMN ruolo_in_catena TEXT")

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_atti_procedimento ON atti (procedimento_id)"
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Funzioni interne
# ---------------------------------------------------------------------------


def _trova_o_crea_procedimento(
    conn: sqlite3.Connection,
    *,
    ente_id: int,
    cig: str | None,
    oggetto: str,
    tipo: str,
    data_avvio: str | None,
    data_chiusura: str | None,
    stato_finale: str,
    metodo_individuazione: str = "cig",
) -> int:
    if cig:
        row = conn.execute(
            "SELECT id FROM procedimenti WHERE cig = ? AND ente_id = ?",
            (cig, ente_id),
        ).fetchone()
        if row:
            conn.execute(
                """UPDATE procedimenti
                   SET stato_finale = ?,
                       data_chiusura = ?,
                       oggetto = COALESCE(NULLIF(?, ''), oggetto)
                   WHERE id = ?""",
                (stato_finale, data_chiusura, oggetto, row["id"]),
            )
            return row["id"]

    cur = conn.execute(
        """
        INSERT INTO procedimenti
            (ente_id, tipo, cig, oggetto, data_avvio, data_chiusura,
             stato_finale, metodo_individuazione, creato_a)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ente_id, tipo, cig, oggetto,
            data_avvio, data_chiusura, stato_finale,
            metodo_individuazione,
            datetime.utcnow().isoformat(),
        ),
    )
    return cur.lastrowid


def _collega_atto(
    conn: sqlite3.Connection, *, atto_id: int, procedimento_id: int, ruolo: str
) -> None:
    conn.execute(
        "UPDATE atti SET procedimento_id = ?, ruolo_in_catena = ? WHERE id = ?",
        (procedimento_id, ruolo, atto_id),
    )


def _stato_da_ruoli(ruoli: list[str]) -> str:
    sr = set(ruoli)
    if "annullamento" in sr:
        return "annullato"
    if "revoca" in sr:
        return "revocato"
    if "aggiudicazione" in sr:
        return "aggiudicato"
    if "avvio" in sr:
        return "in_corso"
    return "sconosciuto"


def _inferisci_tipo(ruoli: list[str]) -> str:
    return "gara" if "avvio" in set(ruoli) else "generico"


__all__ = [
    "RiferimentoAtto",
    "EventoNellaCatena",
    "CatenaEventi",
    "classifica_ruolo",
    "estrai_riferimenti",
    "collega_per_cig",
    "collega_per_riferimenti_incrociati",
    "collega_per_oggetto_simile",
    "ricostruisci_catene",
    "costruisci_catena_da_testi",
]
