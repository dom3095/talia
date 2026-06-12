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

## Link rapidi

- Visione completa: [`talia.md`](../../talia.md)
- Guida per Claude Code: [`CLAUDE.md`](../../CLAUDE.md)
- Board di sviluppo: [`docs/cards/BOARD.md`](../cards/BOARD.md)

## Stato del progetto

🟢 **Fase: prototipo Modulo 1 implementato** (branch `feat/TAL-1-modulo1-prototipo`, in review).
Pipeline end-to-end: PDF/testo → entità → checklist (check 1, 2, 5, 6) → report
markdown/JSON/HTML con citazioni e disclaimer. CLI: `talia analizza fascicolo/`.
Dettagli: [11 — Implementazione motore](11-implementazione-motore.md).
Prossimi passi: validazione su fascicoli reali (TAL-12) e check 3 con LLM (TAL-11).