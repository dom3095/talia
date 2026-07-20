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

import json
import logging
import math
import re
import sqlite3
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Classificazione ruolo dell'atto nella catena
# ---------------------------------------------------------------------------

# Ordinati per priorità: il più specifico prima.
_PATTERN_RUOLO: list[tuple[str, re.Pattern[str]]] = [
    (
        "revoca",
        re.compile(
            r"\b(revoc[aahi]\b|revoca\s+(?:il\s+)?(?:bando|concorso|gara|affidamento|contratto))",
            re.IGNORECASE,
        ),
    ),
    (
        "annullamento",
        re.compile(
            r"\b(annull(?:a|amento|ato|ati)\b|annulla\s+(?:il\s+)?(?:bando|concorso|gara|procedura))",
            re.IGNORECASE,
        ),
    ),
    (
        "aggiudicazione",
        re.compile(
            r"\b(aggiudic(?:a|azione|ato|ati)\b|aggiudicazione\s+definitiva|approvazione\s+graduatoria"
            r"|affidament[oi]\b|affidamento\s+(?:diretto|mediante|dei?\s+servizi|dell[ao]\s+incarico|ai\s+sensi))",
            re.IGNORECASE,
        ),
    ),
    (
        "liquidazione",
        re.compile(
            r"\b(liquidazione\b|liquidazione\s+(?:fattur|sal\b|certificat|spesa|all[ao]\b)"
            r"|pagamento\s+fattura)",
            re.IGNORECASE,
        ),
    ),
    (
        "proroga",
        re.compile(
            r"\b(proroga\b|prorogato\b|proroga\s+termini|estensione\s+(?:dei\s+)?termini)",
            re.IGNORECASE,
        ),
    ),
    (
        "modifica",
        re.compile(
            r"\b(rettif(?:ica|icato)\b|rettifica\s+bando|modifica\s+bando|integrazione\s+(?:al\s+)?bando)",
            re.IGNORECASE,
        ),
    ),
    (
        "avvio",
        re.compile(
            r"\b(bando\b|indizione\b|avviso\s+pubblico|procedura\s+(?:aperta|negoziata|ristretta)"
            r"|concorso\s+pubblico|manifestazione\s+d['']interesse"
            r"|avviso\s+di\s+selezione|selezione\s+interna|approvazione\s+avviso)",
            re.IGNORECASE,
        ),
    ),
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

# Forme estese PRIMA delle abbreviazioni: l'alternation regex è ordinata, e
# "det" da solo matcherebbe il prefisso di "determinazione" senza poi consumare
# il resto della parola (caso reale: oggetto Palma "DETERMINAZIONE N. 33/2025").
_RE_RIFERIMENTO_ATTO = re.compile(
    r"(?:determinazione|determina|deliberazione|delibera|decreto|ordinanza|nota)\s+"
    r"n[°.]?\s*(\d+)\s*"
    r"del\s+(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})",
    re.IGNORECASE,
)
_RE_CIG = re.compile(r"\bCIG\s*[:=]?\s*([A-Z0-9]{10})\b", re.IGNORECASE)
_RE_CUP = re.compile(r"\bCUP\s*[:=]?\s*([A-Z][A-Z0-9]{14})\b", re.IGNORECASE)
# Numero atto standalone (es. "Det. n. 35/2025", "Determinazione n. 33/2025")
_RE_NUM_ATTO = re.compile(
    r"\b(?:determinazione|determina|deliberazione|delibera|ordinanza|decreto"
    r"|det|delib|ord|dec)[.\s]*n[°.]?\s*(\d+)[/\s]+(\d{4})\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RiferimentoAtto:
    """Riferimento incrociato a un altro atto trovato nel testo."""

    tipo: str  # 'numero_atto' | 'cig' | 'cup'
    valore: str
    contesto: str  # snippet intorno al match


def estrai_riferimenti(testo: str) -> list[RiferimentoAtto]:
    """Estrae riferimenti ad altri atti dal testo (regex, deterministico)."""
    risultati: list[RiferimentoAtto] = []
    for m in _RE_RIFERIMENTO_ATTO.finditer(testo):
        risultati.append(
            RiferimentoAtto(
                tipo="numero_atto",
                valore=f"n.{m.group(1)} del {m.group(2)}",
                contesto=testo[max(0, m.start() - 30) : m.end() + 30].replace("\n", " "),
            )
        )
    for m in _RE_NUM_ATTO.finditer(testo):
        risultati.append(
            RiferimentoAtto(
                tipo="numero_atto",
                valore=f"n.{m.group(1)}/{m.group(2)}",
                contesto=testo[max(0, m.start() - 20) : m.end() + 20].replace("\n", " "),
            )
        )
    for m in _RE_CIG.finditer(testo):
        risultati.append(
            RiferimentoAtto(
                tipo="cig",
                valore=m.group(1).upper(),
                contesto=testo[max(0, m.start() - 20) : m.end() + 20].replace("\n", " "),
            )
        )
    for m in _RE_CUP.finditer(testo):
        risultati.append(
            RiferimentoAtto(
                tipo="cup",
                valore=m.group(1).upper(),
                contesto=testo[max(0, m.start() - 20) : m.end() + 20].replace("\n", " "),
            )
        )
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
_SOGLIA_GEMELLI = 0.75  # sopra: oggetti quasi identici → controllare gli slot
_N_TOKEN_CODA = 6  # coda discriminante dei titoli PA (l'oggetto specifico sta in fondo)


def _gemelli_contraddittori(tok_a: list[str], tok_b: list[str]) -> bool:
    """True se due oggetti quasi identici sono atti GEMELLI, non lo stesso procedimento.

    Caso reale (Palma): tre avvisi di selezione con identico boilerplate CCNL ma
    aree/posti diversi ("N. 7 … OPERATORI→ESPERTI" vs "N. 3 … ISTRUTTORI→FUNZIONARI").
    Due segnali di contraddizione:
    - multiset dei token numerici diverso (7 posti vs 3 posti);
    - coda di _N_TOKEN_CODA token diversa come sequenza (l'oggetto specifico).

    Da chiamare SOLO sopra _SOGLIA_GEMELLI: nelle catene legittime (bando→sua
    aggiudicazione) numeri e code variano fisiologicamente a similarità medie.
    """
    num_a = sorted(t for t in tok_a if t.isdigit())
    num_b = sorted(t for t in tok_b if t.isdigit())
    if num_a and num_b and num_a != num_b:
        return True
    if len(tok_a) >= _N_TOKEN_CODA and len(tok_b) >= _N_TOKEN_CODA:
        if tok_a[-_N_TOKEN_CODA:] != tok_b[-_N_TOKEN_CODA:]:
            return True
    return False


def _token_oggetto(oggetto: str) -> list[str]:
    s = unicodedata.normalize("NFC", oggetto.lower())
    s = _RE_NON_ALFANUM.sub(" ", s)
    return [t for t in s.split() if t not in _STOPWORD_IT and len(t) > 2]


def _normalizza_oggetto(oggetto: str) -> str:
    return " ".join(_token_oggetto(oggetto))


def _jaccard_trigrammi(a: str, b: str) -> float:
    def ngrams(s: str) -> set[str]:
        return {s[i : i + 3] for i in range(len(s) - 2)} if len(s) >= 3 else set()

    sa, sb = ngrams(a), ngrams(b)
    if not sa and not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


_MIN_TOKEN_CONTENIMENTO = 5  # sotto: mai collegare (oggetti troppo corti/generici)
_COPERTURA_CONTENIMENTO = 0.5  # il suffisso deve coprire almeno metà dell'originario


def _oggetto_contenuto(
    contenitore: str,
    contenuto: str,
    min_token: int = _MIN_TOKEN_CONTENIMENTO,
    copertura: float = _COPERTURA_CONTENIMENTO,
) -> int:
    """Lunghezza del più lungo suffisso di `contenuto` presente contiguo in `contenitore`.

    Gli atti derivati (revoca/proroga/rettifica) citano il titolo dell'atto
    originario per esteso, ma spesso con un prefisso proprio ("REVOCA IN
    AUTOTUTELA DELL'AVVISO … APPROVATO CON DETERMINAZIONE N. X, [titolo]").
    Il suffisso ancorato alla FINE dell'originario cattura la parte discriminante
    (l'oggetto specifico sta in coda nei titoli PA) e scarta i gemelli che
    condividono solo il boilerplate iniziale.

    Ritorna 0 se il match non raggiunge `min_token` o la frazione `copertura`
    dei token dell'originario; altrimenti la lunghezza del suffisso trovato.
    """
    tok_grande = _token_oggetto(contenitore)
    tok_piccolo = _token_oggetto(contenuto)
    n = len(tok_piccolo)
    soglia = max(min_token, math.ceil(copertura * n))
    if n < min_token or len(tok_grande) < soglia:
        return 0

    for k in range(n, soglia - 1, -1):
        suffisso = tok_piccolo[-k:]
        for i in range(len(tok_grande) - k + 1):
            if tok_grande[i : i + k] == suffisso:
                return k
    return 0


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
        SELECT a.id, a.ente_id, a.tipo, a.oggetto,
               COALESCE(a.data_atto, a.data_pub) AS data_atto, a.testo_estratto
        FROM   atti a
        WHERE  a.cig = ?
        ORDER  BY data_atto ASC NULLS LAST
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


def collega_per_riferimenti_incrociati(conn: sqlite3.Connection, ente_id: int | None = None) -> int:
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
        SELECT a.id, a.ente_id, a.oggetto, a.testo_estratto, a.numero,
               COALESCE(a.data_atto, a.data_pub) AS data_atto,
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
                    """SELECT id, procedimento_id FROM atti
                       WHERE ente_id = ?
                         AND (numero = ?
                              OR numero_settoriale = ?
                              OR numero_settoriale LIKE ? || '/%')
                       LIMIT 1""",
                    (atto["ente_id"], numero, numero, numero),
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


_RUOLI_DERIVATI = frozenset({"revoca", "annullamento", "modifica", "proroga"})


def collega_per_contenimento(
    conn: sqlite3.Connection,
    ente_id: int | None = None,
    min_token: int = _MIN_TOKEN_CONTENIMENTO,
) -> int:
    """Strategia 2.5: collega atti derivati all'originario citato per titolo.

    Un atto derivato (revoca/annullamento/modifica/proroga) incorpora quasi
    sempre il titolo dell'atto originario nel proprio oggetto. Il collegamento
    per contenimento è più robusto dei riferimenti numerici (caso reale Palma:
    revoca che cita il numero sbagliato ma il titolo giusto).

    Match unico → collegamento ad alta confidenza (`contenimento_oggetto`).
    Match multipli a parità di lunghezza → nessun collegamento, WARNING
    (es. revoca cumulativa di più bandi: serve revisione umana).

    Ritorna il numero di atti derivati collegati.
    """
    filtro = "AND ente_id = ?" if ente_id is not None else ""
    params: tuple = (ente_id,) if ente_id is not None else ()
    atti = conn.execute(
        f"""
        SELECT id, ente_id, tipo, oggetto,
               COALESCE(data_atto, data_pub) AS data_atto, testo_estratto, procedimento_id
        FROM   atti
        WHERE  oggetto IS NOT NULL AND oggetto != ''
        {filtro}
        ORDER  BY ente_id, data_atto ASC NULLS LAST
        """,
        params,
    ).fetchall()

    per_ente: dict[int, list] = {}
    for a in atti:
        per_ente.setdefault(a["ente_id"], []).append(a)

    n_collegati = 0
    # procedimento_id assegnati durante QUESTO run (le righe fetchate sono stale)
    assegnati: dict[int, int] = {
        a["id"]: a["procedimento_id"] for a in atti if a["procedimento_id"] is not None
    }

    for eid, gruppo in per_ente.items():
        ruoli = {
            a["id"]: classifica_ruolo(a["testo_estratto"] or "", a["tipo"] or "", a["oggetto"])
            for a in gruppo
        }
        derivati = [a for a in gruppo if ruoli[a["id"]] in _RUOLI_DERIVATI]
        candidati = [a for a in gruppo if ruoli[a["id"]] not in _RUOLI_DERIVATI]

        for der in derivati:
            if der["id"] in assegnati:
                continue
            match = [
                cand
                for cand in candidati
                if _oggetto_contenuto(der["oggetto"], cand["oggetto"], min_token) > 0
            ]
            if not match:
                continue

            ruolo_der = ruoli[der["id"]]
            if len(match) > 1:
                # Ambiguo (es. revoca cumulativa di più bandi) — salvo il caso in
                # cui tutti gli originari appartengano già allo stesso procedimento.
                proc_noti = {assegnati.get(c["id"]) for c in match}
                if len(proc_noti) == 1 and None not in proc_noti:
                    proc_id = proc_noti.pop()
                    _collega_atto(conn, atto_id=der["id"], procedimento_id=proc_id, ruolo=ruolo_der)
                    assegnati[der["id"]] = proc_id
                    _aggiorna_stato_procedimento(conn, proc_id)
                    n_collegati += 1
                else:
                    _log.warning(
                        "Contenimento ambiguo per atto %s (%d possibili originari) — skip",
                        der["id"],
                        len(match),
                    )
                continue

            orig = match[0]
            ruolo_orig = ruoli[orig["id"]]

            proc_id = assegnati.get(orig["id"])
            if proc_id is None:
                proc_id = _trova_o_crea_procedimento(
                    conn,
                    ente_id=eid,
                    cig=None,
                    oggetto=orig["oggetto"],
                    tipo=_inferisci_tipo([ruolo_orig, ruolo_der]),
                    data_avvio=orig["data_atto"],
                    data_chiusura=der["data_atto"],
                    stato_finale=_stato_da_ruoli([ruolo_orig, ruolo_der]),
                    metodo_individuazione="contenimento_oggetto",
                )
                _collega_atto(conn, atto_id=orig["id"], procedimento_id=proc_id, ruolo=ruolo_orig)
                assegnati[orig["id"]] = proc_id
            _collega_atto(conn, atto_id=der["id"], procedimento_id=proc_id, ruolo=ruolo_der)
            assegnati[der["id"]] = proc_id
            _aggiorna_stato_procedimento(conn, proc_id)
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
        SELECT id, ente_id, oggetto, tipo,
               COALESCE(data_atto, data_pub) AS data_atto, testo_estratto
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

    normalizzati = [(a, _token_oggetto(a["oggetto"])) for a in atti]
    assegnazioni: dict[int, int] = {}  # atto_id → proc_id
    n_creati = 0

    for i, (atto_i, tok_i) in enumerate(normalizzati):
        if atto_i["id"] in assegnazioni:
            continue

        norm_i = " ".join(tok_i)
        gruppo = [atto_i]
        for j, (atto_j, tok_j) in enumerate(normalizzati):
            if i == j or atto_j["id"] in assegnazioni:
                continue
            jac = _jaccard_trigrammi(norm_i, " ".join(tok_j))
            if jac < soglia:
                continue
            # Guard-rail: oggetti quasi identici con slot incompatibili sono
            # atti gemelli (stesso boilerplate, procedimenti diversi) — no merge.
            if jac >= _SOGLIA_GEMELLI and _gemelli_contraddittori(tok_i, tok_j):
                continue
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


# ---------------------------------------------------------------------------
# Strategia 4: classificazione LLM locale (Ollama) — opt-in
# ---------------------------------------------------------------------------

_RUOLI_VALIDI = frozenset(
    {
        "avvio",
        "aggiudicazione",
        "liquidazione",
        "revoca",
        "annullamento",
        "modifica",
        "proroga",
        "altro",
    }
)

_PROMPT_CLASSIFICA = (
    "Classifica il seguente titolo di atto amministrativo italiano in UNA sola parola tra:\n"
    "avvio / aggiudicazione / liquidazione / revoca / annullamento / modifica / proroga / altro\n\n"
    "Definizioni rapide:\n"
    "- avvio: bando, gara, concorso, avviso pubblico\n"
    "- aggiudicazione: affidamento, assegnazione contratto\n"
    "- liquidazione: pagamento fattura, liquidazione spesa/SAL\n"
    "- revoca: revoca di atto precedente\n"
    "- annullamento: annullamento in autotutela\n"
    "- modifica: rettifica, integrazione, variante\n"
    "- proroga: proroga termini\n"
    "- altro: non classificabile con le categorie precedenti\n\n"
    "Titolo: {oggetto}\n"
    "Risposta (una parola):"
)


def classifica_ruolo_llm(
    oggetto: str,
    modello: str = "llama3.2",
    base_url: str = "http://localhost:11434",
    timeout: int = 15,
) -> str:
    """Classifica il ruolo di un atto via LLM locale Ollama.

    Restituisce 'altro' se Ollama non risponde o la risposta non è nel vocabolario.
    """
    payload = json.dumps(
        {
            "model": modello,
            "prompt": _PROMPT_CLASSIFICA.format(oggetto=oggetto[:300]),
            "stream": False,
            "options": {"temperature": 0},
        }
    ).encode()
    try:
        req = urllib.request.Request(
            f"{base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        testo = (data.get("response") or "").strip().lower()
        prima_parola = testo.split()[0] if testo else "altro"
        return prima_parola if prima_parola in _RUOLI_VALIDI else "altro"
    except Exception as exc:
        _log.debug("LLM classify fallback per %r: %s", oggetto[:60], exc)
        return "altro"


def aggiorna_sconosciuti_con_llm(
    conn: sqlite3.Connection,
    modello: str = "llama3.2",
    base_url: str = "http://localhost:11434",
    ente_id: int | None = None,
    limite: int = 200,
) -> int:
    """Riclassifica atti 'altro' in procedimenti 'sconosciuto' usando LLM locale.

    Eseguita dopo le strategie deterministiche: tocca solo i procedimenti che
    le regex non hanno saputo classificare.
    Aggiorna ruolo_in_catena e ricalcola stato_finale; marca metodo con suffisso '_llm'.
    Restituisce il numero di procedimenti il cui stato_finale è cambiato.
    """
    try:
        urllib.request.urlopen(f"{base_url}/api/tags", timeout=3)
    except Exception:
        _log.warning("Ollama non raggiungibile su %s — skip classificazione LLM", base_url)
        return 0

    filtro_ente = "AND p.ente_id = ?" if ente_id is not None else ""
    params: tuple = (ente_id,) if ente_id is not None else ()

    procedimenti = conn.execute(
        f"""
        SELECT p.id, p.metodo_individuazione
        FROM   procedimenti p
        WHERE  p.stato_finale = 'sconosciuto'
               {filtro_ente}
        LIMIT  ?
        """,
        (*params, limite),
    ).fetchall()

    n_aggiornati = 0
    for proc in procedimenti:
        atti = conn.execute(
            """
            SELECT id, oggetto FROM atti
            WHERE  procedimento_id = ?
              AND  ruolo_in_catena = 'altro'
              AND  oggetto IS NOT NULL AND oggetto != ''
            """,
            (proc["id"],),
        ).fetchall()

        modificato = False
        for atto in atti:
            ruolo = classifica_ruolo_llm(atto["oggetto"], modello, base_url)
            if ruolo != "altro":
                conn.execute(
                    "UPDATE atti SET ruolo_in_catena = ? WHERE id = ?",
                    (ruolo, atto["id"]),
                )
                modificato = True

        if modificato:
            ruoli = [
                r[0]
                for r in conn.execute(
                    "SELECT ruolo_in_catena FROM atti WHERE procedimento_id = ?",
                    (proc["id"],),
                ).fetchall()
            ]
            nuovo_stato = _stato_da_ruoli(ruoli)
            metodo_orig = proc["metodo_individuazione"] or "sconosciuto"
            conn.execute(
                "UPDATE procedimenti SET stato_finale = ?, metodo_individuazione = ? WHERE id = ?",
                (nuovo_stato, metodo_orig + "_llm", proc["id"]),
            )
            if nuovo_stato != "sconosciuto":
                n_aggiornati += 1

    conn.commit()
    return n_aggiornati


def reset_procedimenti_da_verificare(conn: sqlite3.Connection, ente_id: int | None = None) -> int:
    """Cancella i procedimenti fuzzy ('…da_verificare') e scollega i loro atti.

    I procedimenti individuati da CIG/riferimenti/contenimento restano intatti.
    Da usare prima di un rerun con strategie migliorate (TAL-46).
    Ritorna il numero di procedimenti cancellati.
    """
    filtro = "AND ente_id = ?" if ente_id is not None else ""
    params: tuple = (ente_id,) if ente_id is not None else ()
    ids = [
        row["id"]
        for row in conn.execute(
            f"""SELECT id FROM procedimenti
                WHERE metodo_individuazione LIKE '%da_verificare%' {filtro}""",
            params,
        ).fetchall()
    ]
    if not ids:
        return 0
    segnaposto = ",".join("?" * len(ids))
    conn.execute(
        f"""UPDATE atti SET procedimento_id = NULL, ruolo_in_catena = NULL
            WHERE procedimento_id IN ({segnaposto})""",
        ids,
    )
    conn.execute(f"DELETE FROM procedimenti WHERE id IN ({segnaposto})", ids)
    conn.commit()
    return len(ids)


def ricostruisci_catene(
    conn: sqlite3.Connection,
    ente_id: int | None = None,
    modello_llm: str | None = None,
    llm_base_url: str = "http://localhost:11434",
    llm_limite: int = 200,
    reset_da_verificare: bool = False,
) -> dict:
    """Orchestratore: applica tutte le strategie di individuazione catene.

    Ordine di applicazione:
    1. CIG esplicito (alta confidenza)
    2. Riferimenti incrociati nel testo (alta confidenza)
    2.5 Contenimento oggetto: il derivato incorpora il titolo dell'originario (alta confidenza)
    3. Oggetto simile per ente (bassa confidenza → marcato 'da_verificare')
    4. LLM locale (Ollama) sui procedimenti ancora 'sconosciuto' — opt-in via modello_llm

    Args:
        conn: connessione con il DB già inizializzato.
        ente_id: se fornito, processa solo gli atti di quell'ente.
        modello_llm: nome modello Ollama (es. 'llama3.2'). None = skip strategia 4.
        llm_base_url: URL base Ollama (default http://localhost:11434).
        llm_limite: numero massimo di procedimenti da passare all'LLM per run.
        reset_da_verificare: se True, cancella prima i procedimenti fuzzy
            esistenti e li ricalcola con le strategie correnti (migrazione TAL-46).

    Returns:
        dict con metriche per strategia.
    """
    _evolvi_schema(conn)

    n_reset = reset_procedimenti_da_verificare(conn, ente_id) if reset_da_verificare else 0

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

    # --- Strategia 2.5: contenimento oggetto ---
    n_cont = collega_per_contenimento(conn, ente_id)

    # --- Strategia 3: oggetto simile (per ente) ---
    enti_ids: list[int]
    if ente_id is not None:
        enti_ids = [ente_id]
    else:
        enti_ids = [row["id"] for row in conn.execute("SELECT id FROM enti").fetchall()]
    n_proc_fuzzy = sum(collega_per_oggetto_simile(conn, eid) for eid in enti_ids)

    # --- Strategia 4: LLM locale (opt-in) ---
    n_proc_llm = 0
    if modello_llm:
        n_proc_llm = aggiorna_sconosciuti_con_llm(
            conn,
            modello=modello_llm,
            base_url=llm_base_url,
            ente_id=ente_id,
            limite=llm_limite,
        )

    n_atti_collegati = conn.execute(
        f"SELECT COUNT(*) FROM atti WHERE procedimento_id IS NOT NULL {filtro}",
        params,
    ).fetchone()[0]

    return {
        "n_procedimenti_reset": n_reset,
        "n_procedimenti_da_cig": n_proc_cig,
        "n_atti_collegati_da_riferimenti": n_rif,
        "n_atti_collegati_da_contenimento": n_cont,
        "n_procedimenti_da_oggetto": n_proc_fuzzy,
        "n_procedimenti_aggiornati_llm": n_proc_llm,
        "n_atti_collegati_totale": n_atti_collegati,
    }


# ---------------------------------------------------------------------------
# Catena in-memory per fascicoli M1 (più PDF caricati insieme)
# ---------------------------------------------------------------------------


@dataclass
class EventoNellaCatena:
    """Un atto all'interno di una catena, arricchito con ruolo e riferimenti."""

    ruolo: str  # avvio / modifica / revoca / …
    testo: str  # testo estratto (o oggetto/titolo)
    data: str | None  # ISO date string, se rilevabile
    riferimenti: list[RiferimentoAtto] = field(default_factory=list)
    percorso: str | None = None  # path del PDF sorgente
    metadati: dict = field(default_factory=dict)


@dataclass
class CatenaEventi:
    """Sequenza ordinata di atti di un procedimento.

    Disclaimer: segnalazioni da verificare, non accertamenti.
    """

    eventi: list[EventoNellaCatena]  # ordinati per data (avvio → chiusura)
    stato_finale: str  # in_corso / revocato / annullato / aggiudicato
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

        eventi.append(
            EventoNellaCatena(
                ruolo=classifica_ruolo(testo, tipo),
                testo=testo[:500],  # snippet per il report
                data=t.get("data"),
                riferimenti=refs,
                percorso=t.get("percorso"),
                metadati=t.get("metadati", {}),
            )
        )

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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_procedimenti_cig  ON procedimenti (cig)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_procedimenti_ente ON procedimenti (ente_id)")

    colonne = {row[1] for row in conn.execute("PRAGMA table_info(atti)").fetchall()}
    if "procedimento_id" not in colonne:
        conn.execute(
            "ALTER TABLE atti ADD COLUMN procedimento_id INTEGER REFERENCES procedimenti(id)"
        )
    if "ruolo_in_catena" not in colonne:
        conn.execute("ALTER TABLE atti ADD COLUMN ruolo_in_catena TEXT")
    if "numero_settoriale" not in colonne:
        # Numero di registro settoriale (es. "35/2025"): è quello citato nei
        # riferimenti incrociati, mentre `numero` è il registro generale.
        conn.execute("ALTER TABLE atti ADD COLUMN numero_settoriale TEXT")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_atti_procedimento ON atti (procedimento_id)")
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
            ente_id,
            tipo,
            cig,
            oggetto,
            data_avvio,
            data_chiusura,
            stato_finale,
            metodo_individuazione,
            datetime.utcnow().isoformat(),
        ),
    )
    return cur.lastrowid


def _aggiorna_stato_procedimento(conn: sqlite3.Connection, proc_id: int) -> None:
    """Ricalcola stato_finale e data_chiusura dai ruoli/date degli atti membri."""
    righe = conn.execute(
        "SELECT ruolo_in_catena, COALESCE(data_atto, data_pub) AS data_atto "
        "FROM atti WHERE procedimento_id = ?",
        (proc_id,),
    ).fetchall()
    ruoli = [r["ruolo_in_catena"] for r in righe if r["ruolo_in_catena"]]
    date = sorted(r["data_atto"] for r in righe if r["data_atto"])
    conn.execute(
        "UPDATE procedimenti SET stato_finale = ?, data_chiusura = ? WHERE id = ?",
        (_stato_da_ruoli(ruoli), date[-1] if len(date) > 1 else None, proc_id),
    )


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
    if "liquidazione" in sr:
        return "concluso"
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
    "classifica_ruolo_llm",
    "estrai_riferimenti",
    "collega_per_cig",
    "collega_per_riferimenti_incrociati",
    "collega_per_contenimento",
    "collega_per_oggetto_simile",
    "aggiorna_sconosciuti_con_llm",
    "reset_procedimenti_da_verificare",
    "ricostruisci_catene",
    "costruisci_catena_da_testi",
]
