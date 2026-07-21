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
    """Un chunk del corpus normativo, con provenienza per la citazione."""

    testo: str
    fonte: str  # percorso relativo al corpus, es. "nazionale/l-241-1990.md"


def _tokenizza(testo: str) -> list[str]:
    return [t for t in _RE_TOKEN.findall(testo.lower()) if t not in _STOPWORD and len(t) > 2]


def _chunk_file(path: Path, radice: Path) -> list[Passaggio]:
    """Divide un file markdown in chunk per paragrafo (accorpati fino a una dimensione massima)."""
    fonte = str(path.relative_to(radice))
    paragrafi = [p.strip() for p in path.read_text(encoding="utf-8").split("\n\n") if p.strip()]
    chunk: list[Passaggio] = []
    corrente = ""
    for paragrafo in paragrafi:
        if corrente and len(corrente) + len(paragrafo) > _DIMENSIONE_CHUNK_MAX:
            chunk.append(Passaggio(testo=corrente, fonte=fonte))
            corrente = paragrafo
        else:
            corrente = f"{corrente}\n\n{paragrafo}" if corrente else paragrafo
    if corrente:
        chunk.append(Passaggio(testo=corrente, fonte=fonte))
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
