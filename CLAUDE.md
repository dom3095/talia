# CLAUDE.md — Guida operativa per Claude Code

> Questo file orienta Claude Code (e ogni nuovo contributor) quando lavora su **TALIA**.
> Per la visione completa del progetto leggi sempre [`talia.md`](talia.md).

## Cos'è TALIA

**T**rasparenza **A**tti **L**ocali: **I**ndicatori e **A**nalisi.
Strumento civico open source che rileva **red flags** (anomalie da verificare, **mai** accuse)
negli atti delle Pubbliche Amministrazioni siciliane: gare, concorsi, delibere, revoche, annullamenti.

**Regola d'oro:** segnalare, non giudicare. Ogni output deve essere esplicabile e linkato all'atto sorgente.

## Principi non negoziabili (valgono per ogni riga di codice)

1. **Esplicabilità.** Nessun indicatore senza link alla fonte. Niente "score" nudi → rischio diffamazione.
2. **Determinismo prima degli LLM.** ~95% dei controlli = regex + SQL. LLM solo su documenti già flaggati e solo dove serve giudizio testuale (es. qualità motivazione).
3. **Budget ≈ 0.** Solo stack gratuito/open source. Nessuna dipendenza a pagamento senza discussione.
4. **Privacy.** Viste pubbliche aggregate/anonimizzate, specie nei piccoli comuni (soggetti identificabilissimi). Dettaglio nominativo solo per uso interno.
5. **Disclaimer ovunque.** "Segnalazioni da verificare, non accertamenti."

## Architettura (vedi `docs/wiki/02-architettura.md`)

Un **motore di analisi comune** alimenta tre moduli:

- **Modulo 1 — Analisi fascicolo on-demand** (PRIORITÀ 1): utente carica PDF → report checklist verde/giallo/rosso.
- **Modulo 2 — Scraping continuo**: raccolta atti da albi pretori / ANAC / GURS / UREGA.
- **Modulo 3 — Dashboard per comune**: aggregazioni, trend, confronti tra pari.

Pipeline motore: `OCR (Tesseract) → estrazione entità (regex + spaCy) → checklist deterministiche (SQL) → RAG normativo + LLM (solo casi filtrati)`.

## Stack (vedi `docs/wiki/03-stack.md`)

| Layer | Tecnologia |
|-------|-----------|
| Linguaggio | Python 3.14+ |
| Scraping | Scrapy / BeautifulSoup, cron su GitHub Actions |
| OCR | Tesseract (`pytesseract`) |
| NER / estrazione | regex + spaCy (`it_core_news_lg`) |
| Storage | SQLite (dev) → Postgres free tier (Supabase/Neon) |
| LLM | modelli open locali (Llama/Mistral/Qwen) o Colab; **mai** chiamate a pagamento di default |
| Dashboard | Streamlit / Datasette |
| Hosting | GitHub Pages / Streamlit Cloud / HF Spaces |

## Layout repo (atteso, da costruire)

```
talia/
├── talia.md                 # documento di visione (fonte di verità)
├── CLAUDE.md                # questo file
├── docs/
│   ├── wiki/                # wiki di progetto
│   └── cards/               # board: backlog + card di sviluppo
├── src/talia/
│   ├── engine/              # motore comune (ocr, extract, checklist, rag)
│   ├── modulo1_fascicolo/   # analisi on-demand
│   ├── modulo2_scraping/    # spider e pipeline
│   └── modulo3_dashboard/   # app Streamlit
├── data/
│   ├── raw/                 # PDF/atti grezzi (gitignored)
│   ├── samples/             # fascicoli di test (anonimizzati)
│   └── corpus_normativo/    # testi norme per RAG
├── tests/
└── pyproject.toml
```

## Convenzioni di sviluppo

- **Lingua codice:** identificatori e commenti in italiano OK (dominio giuridico italiano); messaggi/log chiari.
- **Branch:** `feat/<card-id>-slug`, `fix/<card-id>-slug`. Mai commit diretti su `main` senza richiesta.
- **Commit:** conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`). Riferire la card: `feat(M1): ... (TAL-12)`.
- **Test:** ogni regola deterministica ha test con esempio reale (atto anonimizzato) + caso negativo.
- **No segreti nel repo.** API key/credenziali via `.env` (gitignored).
- **Dati sensibili:** mai committare PDF con dati nominativi reali. Usare `data/samples/` solo anonimizzati.

## Definition of Done (DoD)

Una card è "Done" quando:
- [ ] Codice + test passano (`pytest`).
- [ ] Ogni red flag prodotto ha un riferimento testuale (offset/citazione) all'atto sorgente.
- [ ] Documentata nella wiki se introduce un concetto nuovo.
- [ ] Nessun dato personale reale committato.
- [ ] Disclaimer presente se l'output è user-facing.

## Per Claude Code: come muoversi

1. Leggi `talia.md` (visione) e la wiki prima di scrivere codice.
2. Prendi una card da `docs/cards/BOARD.md` (colonna *To Do*), spostala in *In Progress*.
3. Implementa col determinismo prima del LLM. Se servono dati reali, chiedi fascicoli campione.
4. Aggiorna la card e la wiki a fine lavoro.
5. In dubbio su normativa: segnala l'incertezza, non inventare riferimenti di legge.