# 🗂️ Board di sviluppo TALIA

Kanban del team. Sposta le card tra le colonne aggiornando la tabella. Dettaglio di ogni card nei file
`TAL-*.md` di questa cartella.

batch + catene procedimenti v2 + download PDF on-demand + registro scraper unificato) e
Modulo 3 (Dashboard Streamlit). In corso: Fase 2 pipeline (TAL-47 in Review), validazione
fascicoli reali (TAL-12), censimento Palermo/Trapani (TAL-50: merge con `main` in corso,
pronta per PR finale).

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
| [TAL-11](TAL-11.md) | Check 3: qualità motivazione (LLM) | E1 | 🔤 NLP | P2 |

### 🔧 In Progress
| ID | Titolo | Ruolo | Note |
|----|--------|-------|------|
| [TAL-48](TAL-48.md) | Red flag: riapertura dopo revoca | 🔤 NLP | branch `feat/TAL-48-riapertura-dopo-revoca`; MVP implementato (12 test); prossimo: integrazione pdf_download |
| [TAL-12](TAL-12.md) | Validazione su 10 fascicoli reali | ⚖️ LEX | 1/10: fascicolo reale AG analizzato, 3 bug corretti |

### 👀 Review
| ID | Titolo | Ruolo | Note |
|----|--------|-------|------|
| [TAL-50](TAL-50.md) | Censimento Palermo + Trapani (E3 estensione) | 🕷️ SCR | **PR #12 aperta**, in attesa di review Dom — branch `feat/E3-province-palermo-trapani`, Fase 1-3 completate (9 comuni TIER 0 nel registro), riconciliato con `main` dopo refactor registro scraper (PR #11) |
| [TAL-20](TAL-20.md) | Spider pilota albo pretorio iCity | 🕷️ SCR | `icity.py` + 31 test; branch `feat/sprint3` |
| [TAL-1](TAL-1.md) | Setup progetto Python + tooling | ⚙️ OPS | branch `feat/TAL-1-modulo1-prototipo` |
| [TAL-2](TAL-2.md) | CI GitHub Actions (lint + test) | ⚙️ OPS | verde da confermare al primo PR |
| [TAL-3](TAL-3.md) | Estrazione testo da PDF (nativo + OCR) | 🔤 NLP | manca scansione campione per test OCR reale |
| [TAL-4](TAL-4.md) | Estrazione entità: date, importi, CIG | 🔤 NLP | |
| [TAL-5](TAL-5.md) | Estrazione firmatari + norme citate | 🔤 NLP | senza spaCy (euristica deterministica) |
| [TAL-6](TAL-6.md) | Check 1: base giuridica revoca/annullamento | 🔤 NLP | parole spia da validare con ⚖️ LEX |
| [TAL-7](TAL-7.md) | Check 2: termini autotutela (12 mesi) | 🔤 NLP | assunzione sulle date da validare con ⚖️ LEX |
| [TAL-8](TAL-8.md) | Check 5: comunicazione avvio (art. 7) | 🔤 NLP | |
| [TAL-9](TAL-9.md) | Check 6: coerenza firmatari | 🔤 NLP | senza incrocio tempistica graduatoria |
| [TAL-10](TAL-10.md) | Report Modulo 1 (verde/giallo/rosso) | 📊 FE | formato scelto: HTML statico + JSON + CLI |
| [TAL-13](TAL-13.md) | Attori nominati + procedimenti (regex + NER) | 🔤 NLP | NER sm rumoroso: resta discovery, non in motore |
| [TAL-14](TAL-14.md) | Check 7: data breach GDPR non notificato | ⚖️ LEX + 🔤 NLP | check-8 DPO conflict rimandato a TAL-25 |
| [TAL-47](TAL-47.md) | Download PDF on-demand da catene (Fase 2, MVP jCityGov) | 🕷️ SCR | branch `feat/TAL-47-pdf-on-demand`; validato hash 4/4 su fascicolo Palma; 10 test |

### ✅ Done
| ID | Titolo | Note |
|----|--------|------|
| — | Refactor: registro unificato scraper + health-check (#11) | `data/registro_scraper.csv` + `registry.py` + `_FACTORY_PER_MODULO`; health-check settimanale CI; 39 comuni censiti recuperati (1 attivato — Altavilla Milicia) |
| TAL-0 | Wiki + CLAUDE.md + board iniziale | doc di partenza |
| [TAL-21](TAL-21.md) | Schema DB atti + storage | `db.py`: DDL + helper CRUD + dataclass AttoMetadato/EnteMetadato |
| [TAL-22](TAL-22.md) | Pipeline ANAC open data (regione 19) | `anac.py`: filtro Sicilia + idempotenza + 22 test offline |
| [TAL-23](TAL-23.md) | Red flags batch deterministici | `red_flags/`: frazionamento + concentrazione + tempi anomali + runner; 20 test |
| [TAL-30](TAL-30.md) | Dashboard Streamlit MVP | `modulo3_dashboard/app.py`: panoramica comuni, drill-down fonte, anonimizzazione; 7 test; BUG-6 chiuso (falso positivo) |
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
