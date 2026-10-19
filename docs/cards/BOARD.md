# 🗂️ Board di sviluppo TALIA

Kanban del team. Sposta le card tra le colonne aggiornando la tabella. Dettaglio di ogni card nei file
`TAL-*.md` di questa cartella.

> Aggiornata: 2026-10-19. Obiettivo corrente: **MVP** ("portare a terra"), criteri in
> [wiki/16](../wiki/16-definizione-mvp.md). `main` contiene fino alla PR #24; le PR
> #25-#32 sono in Review (dettaglio e ordine di merge in `HANDOFF.md`).

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
| [TAL-52](TAL-52.md) | Deduplicazione atti tra scraper ridondanti (stesso comune, 2 piattaforme) | E2 | 🕷️ SCR | P3 |

### 📝 To Do (pronte da prendere)
| ID | Titolo | Epica | Ruolo | Pri |
|----|--------|-------|-------|-----|
| [TAL-76](TAL-76.md) | `concentrazione_diretti` segnala tutti gli enti: riprogettare la regola (disattivata in #26) | E2 | 🔤 NLP + ⚖️ LEX | P2 |


### 🔧 In Progress
| ID | Titolo | Ruolo | Note |
|----|--------|-------|------|
| [TAL-12](TAL-12.md) | Validazione su 10 fascicoli reali | ⚖️ LEX | **collo di bottiglia dell'MVP**: 1/10 validato; fascicoli 2-9 pronti con report automatico, serve la lettura di un giurista |


### 👀 Review
| ID | Titolo | Ruolo | Note |
|----|--------|-------|------|
| [TAL-75](TAL-75.md) | Fallimenti cronici residui: certificati Halley + ripasso dei transitori | 🕷️ SCR + ⚙️ OPS | **PR #25**; 13 Halley `skip_ssl` (13/13 dal vivo); ripasso a fine run dei falliti per timeout/reset entro `--budget-ripasso` (3600s) |
| [TAL-77](TAL-77.md) | Testo degli atti jCityGov nuovi, estratto ogni notte | 🕷️ SCR + 🔤 NLP | **PR #27** (stacked su #25); `--testo-atti 400`; solo testo nativo, solo tipi utili alle regole, PDF non conservato, CIG dal testo solo se univoco; 35/40 dal vivo, ~2,5 s/atto |
| [TAL-62](TAL-62.md) | Amministrazione Trasparente (jCityGov nel run, Halley no) | 🕷️ SCR | **PR #28** (stacked su #27); categorie per prefisso (menu gerarchici), stop per categoria; Acate +230 atti mai visti, Ragusa 0 |
| [TAL-73](TAL-73.md) | Frazionamento: SmartCIG escluso, ricalcolo completo | 🔤 NLP + ⚖️ LEX | diagnosi in #23 (mergiata), correzione **PR #26** insieme alla disattivazione di TAL-76; sul DB reale 12.892 → 0 flag (nessun atto d'albo ha `importo_euro`) |
| [TAL-69](TAL-69.md) | Scraper "stagnanti" nel report | 🕷️ SCR + ⚙️ OPS | **PR #29**; soglia `max(14, 3 × intervallo tipico)`, informativa; 15 stagnanti sul DB reale, gemelli TAL-52 annotati |
| [TAL-78](TAL-78.md) | Backup del DB fuori dal disco (iCloud Drive) | ⚙️ OPS | **PR #30**; settimanale, zstd 1,1 GB → 60 MB, 4 copie |
| [TAL-3](TAL-3.md) | Estrazione testo da PDF (nativo + OCR) | 🔤 NLP | **PR #31**: chiuso l'ultimo criterio (test OCR su scansione sintetica) |
| [TAL-40](TAL-40.md) | README pubblico + contributing | 🧭 TL | **PR #32**; README, CONTRIBUTING, codice di condotta, 3 issue template |


### ✅ Done
| ID | Titolo | Note |
|----|--------|------|
| [TAL-74](TAL-74.md) | PortalePA: 24 comuni bloccati dal filtro sull'User-Agent | PR #24 mergiata (2026-10-19); da verificare al primo run notturno |
| [TAL-64](TAL-64.md) | `atti_fonti` + dedup tra fonti (fase 1 additiva) | PR #22 mergiata; fase 1 confermata come assetto stabile (2026-10-19) |
| [TAL-72](TAL-72.md) | Tetto di tempo per scraper + causa dominante nel report | PR #21 mergiata; durata del primo run con tetto da misurare |
| [TAL-66](TAL-66.md) | Run giornaliero automatico (launchd) + riepilogo esiti | PR #20 mergiata |
| [TAL-67](TAL-67.md) | Dashboard: aggregati temporali per comune e provincia | PR #20 mergiata |
| [TAL-68](TAL-68.md) | `caccamo` (URBI) e `sangiuseppejato` (SSL) rotti in silenzio | PR #20 mergiata |
| [TAL-70](TAL-70.md) | Bonifica scraper: mai diagnosticati, Corleone, ANAC, stagnanti | PR #20 mergiata |
| [TAL-71](TAL-71.md) | La fase red flags del run notturno girava 11 ore | PR #20 mergiata |
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
