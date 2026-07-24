# 03 — Stack tecnico

[← Home](00-home.md)

## Vincolo guida: budget ≈ 0

Tutto gratuito/open source. Nessuna dipendenza a pagamento di default. L'LLM gira locale o su Colab.

## Tabella stack

| Componente | Scelta | Costo |
|------------|--------|-------|
| Linguaggio | Python 3.12+ | 0 |
| Scraping | Scrapy / BeautifulSoup, cron su GitHub Actions | 0 |
| Storage | SQLite (dev) → Postgres free tier (Supabase/Neon) | 0 |
| OCR | Tesseract (`pytesseract`) — molti atti sono scansioni | 0 |
| NER / estrazione | regex + spaCy (`it_core_news_lg`) | 0 |
| LLM | filtro a imbuto: regole prima, LLM **solo** su documenti già flaggati e solo per il check "motivazione"; **qwen3:4b via Ollama** (TAL-11 ✅), locale | ~0 |
| RAG | retrieval **BM25 in puro stdlib** su `data/corpus_normativo/` (TAL-11 ✅) — nessun embedding/vector store: corpus piccolo (~16 file curati), un retrieval lessicale è sufficiente | 0 |
| Dashboard | Streamlit >= 1.35 (TAL-30 ✅) | 0 |
| Hosting | GitHub Pages / Streamlit Cloud / HF Spaces | 0 |
| CI/cron | GitHub Actions | 0 |

## Il filtro a imbuto (perché conta)

```
TUTTI gli atti
   │  regex + SQL (deterministico, gratis, veloce)
   ▼
atti FLAGGATI (pochi)
   │  LLM solo qui, solo per giudizio testuale (es. qualità motivazione)
   ▼
red flag esplicabili + linkati alla fonte
```

L'LLM costa (calcolo/tempo/energia) ed è meno verificabile. Va usato come ultima risorsa, su un sottoinsieme
già ristretto.

## Scelte aperte (da decidere nelle card)

- ORM/accesso DB: SQL grezzo vs SQLAlchemy.

## Scelte chiuse

- Formato report Modulo 1: **HTML statico + JSON + CLI** (TAL-10 ✅).
- Dashboard Modulo 3: **Streamlit** (TAL-30 ✅). Avvio: `TALIA_DB=talia.db streamlit run src/talia/modulo3_dashboard/app.py`.
- Vector store per il RAG: **nessuno** — retrieval BM25 in puro stdlib, niente FAISS/Chroma
  (TAL-11 ✅): il corpus normativo è piccolo e curato, l'overhead di embedding/vector store
  non è giustificato. Da rivalutare solo se il corpus crescesse molto (es. giurisprudenza
  massiva non curata).
- Modello LLM locale di riferimento: **qwen3:4b via Ollama** (TAL-11 ✅) — già disponibile in
  locale, gratuito. Nota: è un modello "thinking" (ragiona ad alta voce prima della risposta
  finale) — prevedere timeout generosi (~300s) e un parsing dell'output tollerante a testo
  extra prima/dopo il JSON di risposta.

[→ 04 Checklist Modulo 1](04-checklist-modulo1.md)