"""RAG lessicale (BM25) sul corpus normativo — TAL-11.

Il corpus (`data/corpus_normativo/`) è piccolo (poche decine di file curati):
un retrieval lessicale è sufficiente a recuperare articoli di legge e massime
pertinenti, senza introdurre dipendenze pesanti (embedding/vector store) —
coerente col principio "budget ≈ 0" del progetto. Implementazione BM25 in puro
stdlib, nessuna nuova dipendenza.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

_CORPUS_DIR = Path(__file__).resolve().parents[3] / "data" / "corpus_normativo"

_RE_TOKEN = re.compile(r"[a-zàèéìòù]+", re.IGNORECASE)

# Stopword italiane minime: sufficienti a non appiattire il punteggio BM25 su
# articoli/preposizioni ricorrentissimi nel corpus giuridico.
_STOPWORD = frozenset(
    {
        "il",
        "lo",
        "la",
        "i",
        "gli",
        "le",
        "un",
        "uno",
        "una",
        "di",
        "a",
        "da",
        "in",
        "con",
        "su",
        "per",
        "tra",
        "fra",
        "e",
        "o",
        "ed",
        "od",
        "che",
        "non",
        "si",
        "del",
        "dello",
        "della",
        "dei",
        "degli",
        "delle",
        "al",
        "allo",
        "alla",
        "ai",
        "agli",
        "alle",
        "dal",
        "dallo",
        "dalla",
        "dai",
        "dagli",
        "dalle",
        "nel",
        "nello",
        "nella",
        "nei",
        "negli",
        "nelle",
        "sul",
        "sullo",
        "sulla",
        "sui",
        "sugli",
        "sulle",
        "è",
        "sono",
        "cui",
        "quale",
        "quali",
        "questo",
        "questa",
        "questi",
        "queste",
        "come",
        "anche",
    }
)

# Chunk oltre questa dimensione (caratteri) vengono chiusi e accodati.
_DIMENSIONE_CHUNK_MAX = 1200


@dataclass(frozen=True)
class Passaggio:
    """Un chunk del corpus normativo, con provenienza puntuale per la citazione.

    `offset_inizio`/`offset_fine` sono posizioni di carattere nel file sorgente
    (non nel testo concatenato di più file): permettono di citare il passaggio
    con lo stesso stile «testo» (offset A–B) usato per gli atti — un bare
    filename da solo non è un riferimento verificabile (principio di
    esplicabilità, CLAUDE.md).
    """

    testo: str
    fonte: str  # percorso relativo al corpus, es. "nazionale/l-241-1990.md"
    offset_inizio: int = 0
    offset_fine: int = 0


def _tokenizza(testo: str) -> list[str]:
    return [t for t in _RE_TOKEN.findall(testo.lower()) if t not in _STOPWORD and len(t) > 2]


def _dividi_paragrafo_lungo(testo: str, offset_base: int) -> list[tuple[str, int]]:
    """Spezza un paragrafo che eccede la dimensione massima in frammenti a lunghezza fissa.

    Necessario perché il corpus reale (`data/corpus_normativo/`, scaricato da
    Normattiva/EUR-Lex) è spesso un unico blocco di ~100k caratteri senza righe
    vuote: senza questo fallback l'intero file diventerebbe un solo passaggio,
    vanificando sia il ranking BM25 (sempre a livello di file intero) sia la
    precisione della citazione (un offset che copre tutto il documento non è
    più puntuale di un bare filename). Il taglio avviene al primo spazio dopo
    la soglia, per non spezzare le parole a metà.
    """
    pezzi: list[tuple[str, int]] = []
    inizio = 0
    n = len(testo)
    while inizio < n:
        fine = min(inizio + _DIMENSIONE_CHUNK_MAX, n)
        if fine < n:
            spazio = testo.find(" ", fine)
            if spazio != -1 and spazio - fine < 200:
                fine = spazio
        grezzo = testo[inizio:fine]
        ripulito = grezzo.strip()
        if ripulito:
            pezzi.append((ripulito, offset_base + inizio + grezzo.find(ripulito)))
        inizio = fine
    return pezzi


def _dividi_paragrafi(testo: str) -> list[tuple[str, int]]:
    """Paragrafi (separati da riga vuota) con il loro offset di inizio nel testo originale.

    Split su un separatore a lunghezza fissa ("\\n\\n"): l'offset si ricostruisce
    accumulando `len(parte) + 2` ad ogni iterazione, indipendentemente dal
    contenuto — non richiede ricercare il paragrafo nel testo originale. Un
    paragrafo che eccede da solo la dimensione massima di chunk viene spezzato
    ulteriormente (`_dividi_paragrafo_lungo`).
    """
    risultato: list[tuple[str, int]] = []
    offset = 0
    for parte in testo.split("\n\n"):
        ripulito = parte.strip()
        if ripulito:
            base = offset + parte.find(ripulito)
            if len(ripulito) > _DIMENSIONE_CHUNK_MAX:
                risultato.extend(_dividi_paragrafo_lungo(ripulito, base))
            else:
                risultato.append((ripulito, base))
        offset += len(parte) + 2
    return risultato


def _chunk_file(path: Path, radice: Path) -> list[Passaggio]:
    """Divide un file markdown in chunk per paragrafo (accorpati fino a una dimensione massima)."""
    fonte = str(path.relative_to(radice))
    paragrafi = _dividi_paragrafi(path.read_text(encoding="utf-8"))
    chunk: list[Passaggio] = []
    corrente = ""
    inizio_corrente = 0
    fine_corrente = 0
    for paragrafo, offset in paragrafi:
        if corrente and len(corrente) + len(paragrafo) > _DIMENSIONE_CHUNK_MAX:
            chunk.append(
                Passaggio(
                    testo=corrente,
                    fonte=fonte,
                    offset_inizio=inizio_corrente,
                    offset_fine=fine_corrente,
                )
            )
            corrente = paragrafo
            inizio_corrente = offset
        else:
            if not corrente:
                inizio_corrente = offset
            corrente = f"{corrente}\n\n{paragrafo}" if corrente else paragrafo
        fine_corrente = offset + len(paragrafo)
    if corrente:
        chunk.append(
            Passaggio(
                testo=corrente,
                fonte=fonte,
                offset_inizio=inizio_corrente,
                offset_fine=fine_corrente,
            )
        )
    return chunk


class IndiceCorpus:
    """Indice BM25 in-memory sul corpus normativo. Costruito una volta, riusabile."""

    def __init__(self, cartella: Path = _CORPUS_DIR):
        self._passaggi: list[Passaggio] = []
        for md in sorted(cartella.rglob("*.md")):
            self._passaggi.extend(_chunk_file(md, cartella))
        self._tokens = [_tokenizza(p.testo) for p in self._passaggi]
        self._df: dict[str, int] = {}
        for tok in self._tokens:
            for t in set(tok):
                self._df[t] = self._df.get(t, 0) + 1
        self._n = len(self._passaggi)
        self._avgdl = (sum(len(t) for t in self._tokens) / self._n) if self._n else 0.0

    def __len__(self) -> int:
        return self._n

    def _idf(self, termine: str) -> float:
        df = self._df.get(termine, 0)
        return math.log(1 + (self._n - df + 0.5) / (df + 0.5))

    def cerca(self, query: str, k: int = 5, *, k1: float = 1.5, b: float = 0.75) -> list[Passaggio]:
        """Top-k passaggi più pertinenti alla query, per punteggio BM25 decrescente.

        Passaggi con punteggio 0 (nessun termine della query in comune) sono
        esclusi anche se rientrerebbero nelle prime k posizioni.
        """
        query_tok = _tokenizza(query)
        punteggi = [0.0] * self._n
        for i, doc_tok in enumerate(self._tokens):
            if not doc_tok or not query_tok:
                continue
            freq: dict[str, int] = {}
            for t in doc_tok:
                freq[t] = freq.get(t, 0) + 1
            dl = len(doc_tok)
            score = 0.0
            for t in query_tok:
                f = freq.get(t, 0)
                if f == 0:
                    continue
                score += self._idf(t) * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / self._avgdl))
            punteggi[i] = score
        ordinati = sorted(range(self._n), key=lambda i: punteggi[i], reverse=True)
        return [self._passaggi[i] for i in ordinati[:k] if punteggi[i] > 0]


__all__ = ["Passaggio", "IndiceCorpus"]
