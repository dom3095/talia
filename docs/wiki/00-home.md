# Wiki TALIA — Home

> *Taliàri* (sic.): guardare, osservare. **Talia!** = "Guarda!"

Benvenuto nella wiki di **TALIA** — Trasparenza Atti Locali: Indicatori e Analisi.
Strumento civico open source per l'analisi di atti delle PA siciliane. Rileva **red flags**
(anomalie da verificare) **senza emettere giudizi**.

## Indice

| Pagina | Contenuto |
|--------|-----------|
| [01 — Visione e principi](01-visione-e-principi.md) | Perché esiste TALIA, le regole non negoziabili |
| [02 — Architettura](02-architettura.md) | Motore comune + tre moduli, pipeline di analisi |
| [03 — Stack tecnico](03-stack.md) | Tecnologie, vincolo budget zero, scelte |
| [04 — Checklist Modulo 1](04-checklist-modulo1.md) | Caso revoca/annullamento: i 7 check |
| [05 — Red flags batch](05-red-flags-batch.md) | Regole deterministiche per lo scraping |
| [06 — Corpus normativo](06-corpus-normativo.md) | Norme nazionali + Sicilia, approccio RAG |
| [07 — Fonti dati](07-fonti-dati.md) | Albi pretori, ANAC, GURS, UREGA, ground truth |
| [08 — Roadmap](08-roadmap.md) | Tappe dal prototipo allo scale-up |
| [09 — Avvertenze legali](09-avvertenze-legali.md) | Posizionamento, diffamazione, privacy |
| [10 — Glossario](10-glossario.md) | Sigle e termini (CIG, UREGA, CGA, autotutela…) |
| [11 — Implementazione motore](11-implementazione-motore.md) | Layout del codice, decisioni di design, pipeline Modulo 1 |
| [12 — Schema DB](12-schema-db.md) | Tabelle SQLite: atti, enti, red_flags, procedimenti, scraper_runs |
| [13 — Stato scraper per capoluogo](13-scraper-status.md) | Test 2026-06-28: status, problemi, piattaforme di tutti i 9 capoluoghi siciliani |

## Link rapidi

- Visione completa: [`talia.md`](../../talia.md)
- Guida per Claude Code: [`CLAUDE.md`](../../CLAUDE.md)
- Board di sviluppo: [`docs/cards/BOARD.md`](../cards/BOARD.md)

## Stato del progetto

🟢 **Fase: Modulo 1 + Modulo 2 (con catene procedimenti v2) + Dashboard implementati** (branch `main`, 290 test verdi).

| Modulo | Stato | Dettagli |
|--------|-------|----------|
| **Motore / Modulo 1** | ✅ Implementato | OCR → entità → check 1,2,5,6,7 → report HTML/JSON/CLI |
| **Modulo 2 — Scraping** | ✅ Implementato (⚠️ Trapani rotto) | Spider ANAC/Siracusa/Agrigento/jCityGov(CL,EN,RG,PA di M); Trapani: 0 atti (regex da fixare); vedi [13](13-scraper-status.md) |
| **Modulo 2 — Catene procedimenti** | ✅ v2 (TAL-42/43/46) | Strategie CIG / riferimenti / contenimento oggetto / fuzzy con guard-rail + LLM opt-in |
| **Modulo 3 — Dashboard** | ✅ MVP (TAL-30/45) | App Streamlit: panoramica comuni, drill-down fonte, tab procedimenti, anonimizzazione piccoli comuni |

Prossimi passi: validazione su fascicoli reali (TAL-12), check 3 con LLM (TAL-11).

Dettagli implementazione: [11 — Implementazione motore](11-implementazione-motore.md).