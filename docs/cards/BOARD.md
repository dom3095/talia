# 🗂️ Board di sviluppo TALIA

Kanban del team. Sposta le card tra le colonne aggiornando la tabella. Dettaglio di ogni card nei file
`TAL-*.md` di questa cartella.

batch + catene procedimenti v2 + download PDF on-demand + registro scraper unificato) e
Modulo 3 (Dashboard Streamlit, +tab Statistiche/Mappa copertura). In corso: validazione
fascicoli reali (TAL-12). Censimento Palermo/Trapani (TAL-50), registro unificato
scraper (#11), download PDF on-demand (TAL-47), riapertura dopo revoca (TAL-48) e
check-3 qualità motivazione LLM (TAL-11, PR #14) completati e mergiati in `main`.
Ripulita la colonna Review (2026-07-25): 11 card verificate e spostate in Done, 3
lasciate aperte con un gap specifico ancora documentato nella card (TAL-3 OCR, TAL-5
associazione nome↔ruolo, TAL-9 incrocio tempistica graduatoria). I gap di TAL-5/TAL-9
sono stati chiusi da TAL-53 (2026-08-07); resta aperto solo TAL-3 (OCR).
PR #17 (TAL-53…TAL-58: Modulo 1 nome↔ruolo/graduatoria + fix RAG/LLM, Modulo 2
Pachino/Barrafranca, Modulo 3 tab Statistiche/Mappa) mergiata in `main` il 2026-08-09.
PR #18 (TAL-59: falsi positivi in riapertura_dopo_revoca) mergiata il 2026-08-13 — colonna
Review era rimasta indietro (mostrava ancora TAL-59 come aperta), corretto il 2026-08-16.

## Ruoli del team (anche se sei una persona sola: indossa il cappello giusto)

| Ruolo | Sigla | Responsabilità |
|-------|-------|----------------|
| Tech Lead | 🧭 TL | architettura, scelte tecniche, code review |
| Data/NLP Engineer | 🔤 NLP | OCR, estrazione entità, regole, LLM |
| Scraping Engineer | 🕷️ SCR | spider, pipeline raccolta atti |
| Domain Expert (legale) | ⚖️ LEX | normativa, validazione checklist, ground truth |
| Frontend/Dashboard | 📊 FE | report Modulo 1, dashboard Modulo 3 |
| DevOps | ⚙️ OPS | CI, cron, deploy, segreti |

## Epiche

- **E0 — Fondamenta repo** (setup, CI, struttura)
- **E1 — Motore + Modulo 1** (prototipo prioritario)
- **E2 — Scraping pilota**
- **E3 — Dashboard**
- **E4 — Scale-up & community**

## Board

### 📥 Backlog
| ID | Titolo | Epica | Ruolo | Pri |
|----|--------|-------|-------|-----|
| [TAL-51](TAL-51.md) | Scraper comuni Palermo/Trapani (TIER 1 + custom) | E3 | 🕷️ SCR | P2 |
| [TAL-41](TAL-41.md) | Modulo 0: Registro Attori (gerarchia comuni + società in house) | E2 | 🕷️ SCR + 🔤 NLP | P2 |
| [TAL-24](TAL-24.md) | Ground truth: sentenze annullamento | E2 | ⚖️ LEX | P2 |
| [TAL-40](TAL-40.md) | README pubblico + contributing | E4 | 🧭 TL | P3 |
| [TAL-52](TAL-52.md) | Deduplicazione atti tra scraper ridondanti (stesso comune, 2 piattaforme) | E2 | 🕷️ SCR | P3 |

### 📝 To Do (pronte da prendere)
| ID | Titolo | Epica | Ruolo | Pri |
|----|--------|-------|-------|-----|
| [TAL-64](TAL-64.md) | Deduplicazione atti: schema normalizzato `atti`/`atti_fonti` | E2 | 🕷️ SCR | P1 |

### 🔧 In Progress
| ID | Titolo | Ruolo | Note |
|----|--------|-------|------|
| [TAL-62](TAL-62.md) | Scraper "Amministrazione Trasparente" (jCityGov + Halley) | 🕷️ SCR | branch `feat/TAL-60-streamlit-modulo1`; `scarica_atti_trasparenza()` implementata e verificata dal vivo su entrambe le piattaforme (Ragusa/jCityGov, Aci Bonaccorsi/Halley); riusa il motore "igrid" esistente su jCityGov, applicazione separata (Zend Framework) su Halley; **non ancora in produzione**: manca decisione su deduplicazione con l'Albo Pretorio e su download/persistenza del testo, nessun wiring in `run_scrapers.py` |
| [TAL-12](TAL-12.md) | Validazione su 10 fascicoli reali | ⚖️ LEX | 1/10: fascicolo reale AG analizzato, 3 bug corretti; candidati 2-3 pronti (PDF scaricati via TAL-48) |

### 👀 Review
| ID | Titolo | Ruolo | Note |
|----|--------|-------|------|
| [TAL-66](TAL-66.md) | Run giornaliero automatico degli scraper (launchd) + riepilogo esiti | ⚙️ OPS | P0; branch `feat/TAL-66-run-giornaliero-aggregati`; l'ultimo run era del 2026-08-06 (**12 giorni**) con albi che espongono solo 15-30gg → perdita definitiva in corso; `run_daily.sh` (lock, caffeinate, backup DB via `sqlite3 .backup`, rotazione, notifica macOS) + `setup_launchd.sh` (`StartCalendarInterval`, non `StartInterval`+`KeepAlive` come Pathosphere: rilancerebbe in loop) + `run_report.py` che distingue **fallito / muto (0 atti, nessun errore) / fermo**; fix collaterale: `scraper_runs.errore` troncava via la riga dell'eccezione; agente installato (03:30) e run di recupero lanciato |
| [TAL-67](TAL-67.md) | Dashboard: aggregati temporali per comune e provincia | 📊 FE | branch `feat/TAL-66-run-giornaliero-aggregati`; nuovo modulo `aggregati.py` (funzioni pure, nessuno Streamlit) + tab 📅 Aggregati: granularità giornaliera/settimanale/mensile/trimestrale/semestrale, filtro provincia/comune, **due assi tenuti distinti** (data atto via `COALESCE(data_atto,data_pub)` vs data ingestione), zeri espliciti nel grafico giornaliero, date corrotte escluse; verificato dal vivo con `AppTest` su `talia.db` reale |
| [TAL-3](TAL-3.md) | Estrazione testo da PDF (nativo + OCR) | 🔤 NLP | manca ancora un PDF scansionato campione in `data/samples/` per un test OCR automatizzato (OCR reale comunque validato ad-hoc su fascicoli TAL-12/48 con Tesseract installato) |

### ✅ Done
| ID | Titolo | Note |
|----|--------|------|
| [TAL-60](TAL-60.md) | UI Streamlit per Modulo 1 (tab "Analisi fascicolo") | PR #19 mergiata (2026-08-16); catena di box "allega file + descrizione" (un documento alla volta), la descrizione concorre a `classifica_ruolo` e compare nel report; nessuna persistenza dei file; bug reale trovato solo con `AppTest.from_file` (import relativi rotti in modalità `streamlit run`); drive-by: rimossa doppia esecuzione di tab Statistiche/Mappa |
| [TAL-65](TAL-65.md) | `estrai_cig()`: CIG padre/derivato scambiati o persi, colonna `cig_padre` | Trovato durante TAL-64 (Dom: "i CIG possono avere CIG padre e figli"); bug in 3 punti (`utils.py`, `entita.py`, `catena.py`), usato da 14/14 scraper — 578 atti con pattern padre/derivato, 127 falsi positivi (`cig='ORIGINARIO'`), 368 falsi negativi (`cig` NULL); tre regex distinte con lookahead invece di un'unica etichetta opzionale; nuova colonna `atti.cig_padre` + migrazione lazy; **backfill completo su talia.db reale**: 3820 atti corretti, 0 garbage residuo, 200 con `cig_padre` popolato; 12 nuovi test, 655 verdi (erano 643) |
| [TAL-63](TAL-63.md) | jCityGov: `url_fonte` mai stato un permalink funzionante | P0, esplicabilità; segnalato da Dom cliccando un link reale; formato `mostraDettaglio` dava sempre errore server-side (verificato con Playwright, freddo e con sessione, e curl puro), formato vero `/display/<id>` trovato cliccando davvero il bottone del portale; **backfill completo eseguito e verificato**: 85.394 atti + 2019 voci in 341 `red_flags.atti_cig` (copia denormalizzata dell'URL, scoperta durante il backfill di prova su Acate) corrette, 14/14 campione casuale funzionante dopo il fix; Halley controllata in parallelo, nessun bug analogo |
| [TAL-61](TAL-61.md) | `enti` senza provincia/popolazione: mai incrociati con l'anagrafica comuni | segnalato da Dom su tab Panoramica; `sincronizza_enti_da_registro()` ora incrocia `data/comuni_sicilia.csv`; backfill su `talia.db` reale: 0/307 senza provincia (era 192), 1/307 senza popolazione (era 307); 3 nuovi test |
| [TAL-59](TAL-59.md) | Falsi positivi in riapertura_dopo_revoca: tag "[annullato]" + dominio mancante | PR #18 mergiata (2026-08-13); 3 commit (fix dominio a frasi, verifica critica su campione casuale di 40 procedimenti mai ispezionati, guardia minori/tutela da code review); verificato dal vivo su `talia.db` reale: 82→23→10→8 flag; 614 test verdi (erano 598) |
| [TAL-53](TAL-53.md) | Check 6: associazione nome↔ruolo + incrocio tempistica graduatoria | PR #17 mergiata (2026-08-09); `graduatoria.py` + wiring in check6; 2 bug trovati da `/code-review` e corretti (Tentativo 3); 598 test verdi (erano 572) |
| [TAL-54](TAL-54.md) | Check 3: retrieval RAG cieco ai temi già individuati dai check deterministici | PR #17 mergiata (2026-08-09); scoperto girando check 3 con Ollama reale sul fascicolo 1 (GDPR mancava dal retrieval nonostante check-7 l'avesse già individuato); fix `_cerca_passaggi_rag()` + istruzione di grounding nel prompt + temperatura fissata a 0 |
| [TAL-55](TAL-55.md) | Scraper: fallimenti silenziosi in serviziolinealbo.py | PR #17 mergiata (2026-08-09); da `/code-review`; log WARNING su atto scartato/0 atti + test "pagina corrotta" |
| [TAL-56](TAL-56.md) | Scraper: consolidare _strip()/tabella tipi + retry hspromila | PR #17 mergiata (2026-08-09); da `/code-review`; `strip_html()`/`TIPI_ATTO_DEFAULT` condivisi in `utils.py` (fix drift avviso/avvisi), retry hspromila allargato |
| [TAL-57](TAL-57.md) | Modulo 1: pulizia minore (check3, RAG, graduatoria) | PR #17 mergiata (2026-08-09); da `/code-review`; fix troncamento motivazione, dedup offset citazioni, precompute BM25, costanti graduatoria unificate |
| [TAL-58](TAL-58.md) | Dashboard: query duplicate + pulizia minore | PR #17 mergiata (2026-08-09); da `/code-review`; query caricate una volta per tab, avviso privacy condiviso, verificato dal vivo con `AppTest` (0 eccezioni) |
| [TAL-5](TAL-5.md) | Estrazione firmatari + norme citate | senza spaCy (euristica deterministica); associazione nome↔ruolo chiusa da TAL-53, PR #17 mergiata (2026-08-09) |
| [TAL-9](TAL-9.md) | Check 6: coerenza firmatari | incrocio con la tempistica della graduatoria chiuso da TAL-53, PR #17 mergiata (2026-08-09) |
| — | Pachino/Barrafranca via Playwright (2026-08-06) | branch `feat/sweep-comuni-mancanti`; stessa piattaforma DevExpress di Agrigento, nuovo scraper generico `serviziolinealbo.py` (non fork di `agrigento.py`); +178 atti Pachino, +90 Barrafranca; entrambi `escluso_default` come Agrigento; Leonforte (Cloudflare) verificato ma non forzato di proposito; copertura 82,0%→83,0% (258 comuni, 85 mai censiti); 572 test verdi |
| — | Esplorazione manuale 10 comuni residui più popolosi (2026-08-06) | branch `feat/sweep-comuni-mancanti`; 2 attivati (Aci Catena +1.000 atti su jCityGov esistente ma dominio proprio; Nicosia +12 atti, nuovo scraper dedicato WordPress `nicosia.py`, backend reale URBI non ancora supportato dal frontend nuovo), 8 approfonditi e rimandati (piattaforme diverse: JSF, ASP.NET DevExpress, URBI, Cloudflare, non identificate); copertura 81,0%→82,0% (256 comuni, 87 mai censiti); 556 test verdi |
| — | Secondo sweep comuni residui (2026-08-06) | branch `feat/sweep-comuni-mancanti` (PR #16); 17 hit su 106 comuni mai censiti (9 Halley EG, 3 jCityGov, 3 portalepa, 1 HSPromila), 16 verificati con atti reali e attivati (+2.475 atti, +116.978 abitanti, copertura 79,0%→81,0%), 1 pending (Valguarnera Caropepe, 0 atti); bugfix critico: fingerprint jCityGov dava 106/106 falsi positivi (403 wildcard del vendor su qualsiasi sottodominio) — corretto richiedendo marker reale nel body; 545 test verdi |
| [TAL-11](TAL-11.md) | Check 3: qualità motivazione (LLM) | PR #14 mergiata (2026-08-05); RAG BM25 stdlib (`engine/rag.py`) + client Ollama (`engine/llm.py`) + `check3_motivazione.py`, non nel registry automatico (`valuta_llm=True`/`--llm`); qwen3:4b verificato end-to-end reale; 9 findings da code review corretti |
| — | Fix registro: certificati SSL incompleti + base_url errato | PR #15 mergiata (2026-08-05): `brolo`/`pozzallo`/`sortino` (skip_ssl) + `castellammare_golfo` (base_url) |
| — | Sweep di dominio comuni mai censiti (2026-07-26) | branch `feat/sweep-comuni-mancanti` (PR #16, riconciliata con main 2026-08-05); 153 comuni mai censiti individuati, 47 hit (jCityGov/Halley/HSPromila), 40 verificati con atti reali e attivati (+189.921 abitanti, copertura 74,0%→77,8%), 7 pending (fingerprint ok ma 0 atti); bugfix retry HSPromila + fix codice ISTAT Messina; 2026-08-06: run completa 234/244 scraper OK, bugfix retry anche su `halley.py`; Cefalù (+440 atti) e Partanna sbloccati (base_url errata, in realtà già su Halley EG — rimosso anche `partanna_tp`, duplicato di registro); Corleone scartato deliberatamente (WordPress con solo 12 documenti totali, non un registro atti reale); dashboard +tab Statistiche/Mappa copertura; 545 test verdi |
| [TAL-48](TAL-48.md) | Red flag: riapertura dopo revoca | MVP + integrazione pdf_download (branch `feat/TAL-48-pdf-riaperture`); bugfix critico (data_atto NULL su jCityGov → 0 rilevazioni reali, ora 78); 480 test verdi |
| [TAL-50](TAL-50.md) | Censimento Palermo + Trapani (E3 estensione) | PR #12 mergiata (2026-07-12): 9 comuni TIER 0 nel registro, riconciliato con refactor registro scraper (#11) |
| — | Refactor: registro unificato scraper + health-check (#11) | `data/registro_scraper.csv` + `registry.py` + `_FACTORY_PER_MODULO`; health-check settimanale CI; 39 comuni censiti recuperati (1 attivato — Altavilla Milicia) |
| TAL-0 | Wiki + CLAUDE.md + board iniziale | doc di partenza |
| [TAL-21](TAL-21.md) | Schema DB atti + storage | `db.py`: DDL + helper CRUD + dataclass AttoMetadato/EnteMetadato |
| [TAL-22](TAL-22.md) | Pipeline ANAC open data (regione 19) | `anac.py`: filtro Sicilia + idempotenza + 22 test offline |
| [TAL-23](TAL-23.md) | Red flags batch deterministici | `red_flags/`: frazionamento + concentrazione + tempi anomali + runner; 20 test |
| [TAL-30](TAL-30.md) | Dashboard Streamlit MVP | `modulo3_dashboard/app.py`: panoramica comuni, drill-down fonte, anonimizzazione; BUG-6 chiuso (falso positivo); 2026-08-06: +tab Statistiche (trend ingestione, aggregati) e Mappa copertura (pydeck + GeoJSON comuni); 17 test totali |
| [TAL-42](TAL-42.md) | Schema DB: tabella procedimenti + colonne catena | `engine/catena._evolvi_schema`; lazy, idempotente |
| [TAL-43](TAL-43.md) | Engine catena: individuazione e collegamento procedimenti | 3 strategie (CIG/riferimenti/oggetto simile) |
| [TAL-44](TAL-44.md) | Red flag: revoca/annullamento in catena | integrato in runner; 6 test |
| [TAL-45](TAL-45.md) | Dashboard M3: tab ⛓️ Procedimenti + timeline | graceful degradation se catene non costruite |
| [TAL-46](TAL-46.md) | Engine catena v2: contenimento oggetto + guard-rail gemelli | strategia 2.5; caso Palma: mega-catena → 3 catene; migrazione DB applicata |
| [TAL-49](TAL-49.md) | Censimento albi + rollout scraper comuni siciliani | mergiata (#8); 192 comuni (72,9% popolazione), 384 test |

## Legenda priorità

- **P0** — blocca tutto il resto (fondamenta).
- **P1** — necessaria per il prototipo Modulo 1 (tappa 1).
- **P2** — importante, non blocca la tappa 1.
- **P3** — nice-to-have / crescita.

## Sprint 1 proposto (obiettivo: prototipo Modulo 1 end-to-end)

> Da `data/samples/` (indizione + annullamento) → report checklist con citazioni e disclaimer.

TAL-1 → TAL-2 → TAL-3 → TAL-4 → TAL-6 → TAL-7 → TAL-10 → TAL-12.
Check più complessi (TAL-5, TAL-8, TAL-9, TAL-11) a seguire.
