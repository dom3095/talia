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

Aggiornato: 2026-07-07.

| Comune | Scraper | Piattaforma | Stato | Note |
|--------|---------|------------|-------|------|
| Agrigento | `agrigento.py` | ASP.NET + DevExpress (Playwright) | ✅ OK | escluso dal default run; ~3 min/run completo per attese Playwright |
| Caltanissetta | `jcitygov.py` | jCityGov/Liferay | ✅ OK | nel default run |
| Catania | `catania.py` | URBI/Maggioli (**non** HCL Domino) | ✅ OK | HTTP puro: wizard stepper riprodotto via POST (StwEvent 910001/9100030); metadati completi nella lista; scarta atti di altri enti mittenti; espone solo atti in pubblicazione → scraping continuo; server a volte instabile |
| Enna | `jcitygov.py` | jCityGov/Liferay | ✅ OK | bassa frequenza (~3 atti/mese) — la presunta staleness era errata |
| Messina | — | jCityGov/Liferay | ⛔ bloccato | FortiGate 403 + cert scaduto 2023-06-27; `skip_ssl=True` non basta; accesso probabilmente solo da intranet comunale |
| Palermo | `palermo.py` | SISPI JSP | ✅ OK | HTTP puro (la nota "Playwright obbligatorio" era errata): sessione + scoperta categorie dal menu + POST paginazione; espone solo atti in pubblicazione → scraping continuo |
| Ragusa | `jcitygov.py` | jCityGov/Liferay | ✅ OK | nel default run |
| Siracusa | `siracusa.py` | portalepa PHP | ✅ OK | nel default run |
| Trapani | `trapani.py` | e-pal.it | ✅ OK | BUG-4 risolto 2026-07-03: era il filtro data server-side, non la regex (`al` ora = oggi+60gg). L'albo espone solo atti in pubblicazione (~15-30 gg): serve scraping continuo |

Altri comuni scraper attivi (non capoluogo): **Palma di Montechiaro** (jCityGov, backfill storico ✅ completato 2026-06-26: 748 atti, 2018→2026 — tutto lo storico esposto dall'albo) e, dal 2026-07-07 (TAL-49), **65 comuni jCityGov** trovati con sweep del pattern `<slug>.trasparenza-valutazione-merito.it` e verificati con atti reali (elenco in `scripts/run_scrapers.py::_JCITYGOV_COMUNI`, censimento completo in `docs/wiki/14-censimento-albi.md`). 5 di questi (Milazzo, Aragona, Gaggi, Letojanni, Noto) richiedono il percorso alternativo `papca-ap/igrid/<id>` invece dello standard `papca-g`: `jcitygov.py` lo scopre e usa automaticamente quando il percorso standard ritorna 0 risultati.

⚠️ **Codici ISTAT**: il 2026-07-07 sono stati corretti 4 codici errati (Caltanissetta era Butera, Siracusa era Solarino, Enna e Palma off-by-one). `talia.db` esistente ha gli enti con i codici vecchi: serve migrazione prima del prossimo run (SQL nella card TAL-49).

### Fragilità comuni

- **Fallimento silenzioso a 0 atti**: quasi nessuno scraper logga WARNING esplicito se il parsing ritorna zero righe (Trapani ✅ fatto). Sempre aggiungere un log quando `len(atti) == 0`.
- **Nessun retry su HTTPError**: `jcitygov.py` gestisce solo `TimeoutError`; errori 4xx/5xx propagano senza retry.
- **Regex fragili sull'HTML**: `_RE_PANEL` (Trapani) e `_RE_NEXT` (jCityGov) falliscono silenziosamente a struttura cambiata.
- **Filtri data server-side controintuitivi**: e-pal.it esclude gli atti la cui pubblicazione termina dopo `dataPubblicazioneAl` — con `al=oggi` si perdono i più recenti (era BUG-4). Non fidarsi dei default "dal/al=oggi".

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
- **Branch:** `feat/<card-id>-slug`, `fix/<card-id>-slug`.
- **`main` è protetto per convenzione: MAI commit o push diretti, MAI merge locale.**
  Ogni modifica arriva via branch + Pull Request; il merge lo fa (o lo conferma
  esplicitamente) l'utente. Vale anche per fix piccoli, doc e "emergenze CI":
  se `main` è rotto, la correzione passa comunque da una PR.
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

### Loop di esecuzione (per ogni card)

Seguire questo ordine. Non saltare fasi, non fonderle.

**0. Spec check** — Prima di toccare codice, leggere `## 📋 Spec` e `## ❓ Domande aperte` della card.
   Se ci sono domande aperte non barrate: fermarsi e chiedere. Solo quando sono tutte risolte si procede.

**1. Esecuzione** — Implementare secondo la spec. Determinismo prima del LLM.
   Se servono dati reali, chiedere fascicoli campione.

**2. Bugfix** — Correggere i problemi emersi in fase di esecuzione/test.

**3. Refactor** — Solo se il codice lo richiede. Motivare esplicitamente cosa e perché.
   Non introdurre astrazioni per uso futuro ipotetico.

**4. Lint** — `ruff check . && ruff format .`

**5. Doc update** — Aggiornare nell'ordine:
   - Card: spostare in *Review*, aggiornare `## ✅ Task` e `## 🔬 Tentativi`
   - Wiki: se introduce un concetto nuovo
   - Tabella scraper in `CLAUDE.md` se tocca uno scraper
   - `BOARD.md`

### A fine sessione

Aggiornare **`HANDOFF.md`** con branch, DB snapshot e prossimi passi.
Se si chiude un'epica, aggiornare o creare `docs/handoff/epica_E*.md`.

### Convenzione `## 🔬 Tentativi`

Ogni volta che un approccio produce un risultato significativo (positivo, negativo, parziale),
aggiungere una voce nella card:

```markdown
### YYYY-MM-DD — Tentativo N
**Approccio:** cosa si è provato
**Esito:** ✅ / ❌ / ⚠️ parziale
**Appreso:** perché ha funzionato o fallito, cosa cambiare
```

Scopo: permettere di riprendere un'attività in sessioni future senza ri-esplorare strade già percorse.

### Convenzione `## 📋 Spec` e `## ❓ Domande aperte`

La Spec si compila quando si sposta una card in *To Do* (non in anticipo sul backlog).
Se `## ❓ Domande aperte` ha checkbox ancora aperti: bloccarsi e chiedere prima di procedere.
Se è vuota o tutta barrata: procedere autonomamente.

### Delegare il lavoro esplorativo

Quando un task richiede molte chiamate (analisi dati, debug iterativo, esplorazione codebase estesa):

1. **Delega** l'esplorazione a un sotto-agente con modello economico (`haiku`): fagli raccogliere dati, formulare ipotesi, identificare pattern.
2. **Consolida** le sue considerazioni nel contesto principale.
3. **Valida** sperimentando direttamente (eseguendo codice, leggendo file critici).

Non delegare: decisioni architetturali, scrittura di codice finale, aggiornamenti a file di configurazione sensibili.

### In dubbio

- Su normativa: segnalare l'incertezza, non inventare riferimenti di legge.
- Su architettura: proporre, non decidere unilateralmente.