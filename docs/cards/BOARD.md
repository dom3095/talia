# 🗂️ Board di sviluppo TALIA

Kanban del team. Sposta le card tra le colonne aggiornando la tabella. Dettaglio di ogni card nei file
`TAL-*.md` di questa cartella.

**Stato attuale:** repo appena inizializzata, zero codice. Focus tappa 1 (prototipo Modulo 1).

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
| [TAL-20](TAL-20.md) | Scraper pilota: un albo pretorio | E2 | 🕷️ SCR | P1 |
| [TAL-21](TAL-21.md) | Schema DB atti + storage | E2 | 🧭 TL | P1 |
| [TAL-22](TAL-22.md) | Pipeline ANAC/BDNCP (regione 19) | E2 | 🕷️ SCR | P2 |
| [TAL-23](TAL-23.md) | Red flags batch deterministici | E2 | 🔤 NLP | P2 |
| [TAL-24](TAL-24.md) | Ground truth: sentenze annullamento | E2 | ⚖️ LEX | P2 |
| [TAL-30](TAL-30.md) | Dashboard Streamlit MVP | E3 | 📊 FE | P2 |
| [TAL-40](TAL-40.md) | README pubblico + contributing | E4 | 🧭 TL | P3 |

### 📝 To Do (pronte da prendere)
| ID | Titolo | Epica | Ruolo | Pri |
|----|--------|-------|-------|-----|
| [TAL-1](TAL-1.md) | Setup progetto Python + tooling | E0 | ⚙️ OPS | P0 |
| [TAL-2](TAL-2.md) | CI GitHub Actions (lint + test) | E0 | ⚙️ OPS | P0 |
| [TAL-3](TAL-3.md) | Estrazione testo da PDF (nativo + OCR) | E1 | 🔤 NLP | P0 |
| [TAL-4](TAL-4.md) | Estrazione entità: date, importi, CIG | E1 | 🔤 NLP | P0 |
| [TAL-5](TAL-5.md) | Estrazione firmatari + norme citate | E1 | 🔤 NLP | P1 |
| [TAL-6](TAL-6.md) | Check 1: base giuridica revoca/annullamento | E1 | 🔤 NLP | P1 |
| [TAL-7](TAL-7.md) | Check 2: termini autotutela (12 mesi) | E1 | 🔤 NLP | P1 |
| [TAL-8](TAL-8.md) | Check 5: comunicazione avvio (art. 7) | E1 | 🔤 NLP | P1 |
| [TAL-9](TAL-9.md) | Check 6: coerenza firmatari | E1 | 🔤 NLP | P1 |
| [TAL-10](TAL-10.md) | Report Modulo 1 (verde/giallo/rosso) | E1 | 📊 FE | P1 |
| [TAL-11](TAL-11.md) | Check 3: qualità motivazione (LLM) | E1 | 🔤 NLP | P2 |
| [TAL-12](TAL-12.md) | Validazione su 10 fascicoli reali | E1 | ⚖️ LEX | P1 |

### 🔧 In Progress
| ID | Titolo | Ruolo | Note |
|----|--------|-------|------|
| — | _(vuoto)_ | | |

### 👀 Review
| ID | Titolo | Ruolo | Note |
|----|--------|-------|------|
| — | _(vuoto)_ | | |

### ✅ Done
| ID | Titolo | Note |
|----|--------|------|
| TAL-0 | Wiki + CLAUDE.md + board iniziale | doc di partenza |

## Legenda priorità

- **P0** — blocca tutto il resto (fondamenta).
- **P1** — necessaria per il prototipo Modulo 1 (tappa 1).
- **P2** — importante, non blocca la tappa 1.
- **P3** — nice-to-have / crescita.

## Sprint 1 proposto (obiettivo: prototipo Modulo 1 end-to-end)

> Da `data/samples/` (indizione + annullamento) → report checklist con citazioni e disclaimer.

TAL-1 → TAL-2 → TAL-3 → TAL-4 → TAL-6 → TAL-7 → TAL-10 → TAL-12.
Check più complessi (TAL-5, TAL-8, TAL-9, TAL-11) a seguire.
