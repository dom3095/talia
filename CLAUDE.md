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

## Layout repo

```
talia/
├── talia.md                 # documento di visione (fonte di verità)
├── CLAUDE.md                # questo file
├── HANDOFF.md               # stato corrente: branch, DB, prossimi passi (aggiornato a ogni sessione)
├── docs/
│   ├── handoff/
│   │   └── epica_E2.md      # architettura e debiti tecnici dell'Epica E2 (documento stabile)
│   ├── wiki/                # wiki di progetto
│   └── cards/               # board: backlog + card di sviluppo (BOARD.md + TAL-*.md)
├── src/talia/
│   ├── engine/              # motore comune (ocr, extract, checklist, catena, rag)
│   ├── modulo1_fascicolo/   # analisi on-demand
│   ├── modulo2_scraping/    # spider, pipeline, red flags
│   └── modulo3_dashboard/   # app Streamlit
├── data/
│   ├── raw/                 # PDF/atti grezzi (gitignored)
│   ├── samples/             # fascicoli di test — creati a mano, mai committare PDF nominativi
│   └── corpus_normativo/    # testi norme per RAG
├── scripts/
│   └── run_scrapers.py      # orchestratore scraper
├── tests/
└── pyproject.toml
```

## Modulo 2 — Stato scraper per capoluogo

Aggiornato: 2026-06-28 (test con `--max-pagine 2`, DB temporaneo isolato).

| Comune | Scraper | Piattaforma | Stato | Note |
|--------|---------|------------|-------|------|
| Agrigento | `agrigento.py` | ASP.NET + DevExpress (Playwright) | ✅ OK | escluso dal default run; ~3 min/run completo per attese Playwright |
| Caltanissetta | `jcitygov.py` | jCityGov/Liferay | ✅ OK | nel default run |
| Catania | — | URBI/Maggioli (**non** HCL Domino) | ❌ mancante | HTTP puro fattibile con enumerazione ID; `DB_NAME=wt00041571`; URL: `servizionline.comune.catania.it` |
| Enna | `jcitygov.py` | jCityGov/Liferay | ✅ OK | bassa frequenza (~3 atti/mese) — la presunta staleness era errata |
| Messina | — | jCityGov/Liferay | ⛔ bloccato | FortiGate 403 + cert scaduto 2023-06-27; `skip_ssl=True` non basta; accesso probabilmente solo da intranet comunale |
| Palermo | — | SISPI JSP | ❌ mancante | Playwright obbligatorio (JS stateful); URL reale: `albopretorio.comune.palermo.it`; stessa logica di `agrigento.py` |
| Ragusa | `jcitygov.py` | jCityGov/Liferay | ✅ OK | nel default run |
| Siracusa | `siracusa.py` | portalepa PHP | ✅ OK | nel default run; mancano test unitari |
| Trapani | `trapani.py` | e-pal.it | ⚠️ ROTTO | 0 atti — `_RE_PANEL` non matcha più la struttura HTML corrente |

Altri comuni scraper attivi (non capoluogo): **Palma di Montechiaro** (jCityGov, backfill storico da completare).

### Fragilità comuni

- **Fallimento silenzioso a 0 atti**: nessuno scraper logga WARNING esplicito se il parsing ritorna zero righe. Sempre aggiungere un log quando `len(atti) == 0`.
- **Nessun retry su HTTPError**: `jcitygov.py` gestisce solo `TimeoutError`; errori 4xx/5xx propagano senza retry.
- **Regex fragili sull'HTML**: `_RE_PANEL` (Trapani) e `_RE_NEXT` (jCityGov) falliscono silenziosamente a struttura cambiata.
- **Nessun test unitario** per `siracusa.py` e `trapani.py` (da aggiungere con HTML fixture).

### Come testare uno scraper

```bash
# Test rapido (2 pagine, DB isolato, no red flags)
python scripts/run_scrapers.py --scrapers <nome> --max-pagine 2 --db /tmp/test_<nome>.db --no-red-flags

# Backfill storico (senza stop-on-known)
python scripts/run_scrapers.py --scrapers <nome> --max-pagine 50 --no-stop
```

### Come aggiungere uno scraper

1. Creare `src/talia/modulo2_scraping/fonti/<comune>.py` con `prepara_ente`, `scarica_atti`, `salva_atti`.
2. Aggiungere `_run_<comune>` in `scripts/run_scrapers.py` e registrarlo in `_SCRAPERS`.
3. Se è jCityGov: aggiungere entry in `_JCITYGOV_COMUNI` (nome, base_url, codice_istat, denominazione).
4. Se richiede Playwright: vedi `agrigento.py` come template.
5. Almeno 3 test con HTML fixture reale (anonimizzato): caso normale + 0 atti + pagina corrotta.

### Problema ANAC (WAF)

Download CSV SmartCIG ANAC bloccato da WAF (TLS fingerprinting). Workaround attivo: `--anac-file <file.csv>`. Alternativa in valutazione: Playwright headless.

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

### All'inizio di ogni sessione

1. Leggi **`HANDOFF.md`** (root del repo) — stato del branch, DB, prossimi passi concordati.
2. Se stai lavorando sull'architettura E2, leggi anche **`docs/handoff/epica_E2.md`**.
3. Per la visione d'insieme: `talia.md` e `docs/wiki/`.

### Durante il lavoro

4. Prendi una card da `docs/cards/BOARD.md` (colonna *To Do*), spostala in *In Progress*.
5. Implementa col determinismo prima del LLM. Se servono dati reali, chiedi fascicoli campione.
6. Aggiorna la card e la wiki a fine lavoro.
7. In dubbio su normativa: segnala l'incertezza, non inventare riferimenti di legge.

### A fine sessione

8. Aggiorna **`HANDOFF.md`** (root) con branch, DB snapshot e prossimi passi.
   Se si chiude un'epica, aggiorna o crea il relativo `docs/handoff/epica_E*.md`.