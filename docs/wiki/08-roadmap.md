# 08 — Roadmap

[← Home](00-home.md)

## Le tappe

### 1. Prototipo Modulo 1 ← **siamo qui**
Script che prende 2-3 PDF (indizione + annullamento) e produce il report con la checklist
[§04](04-checklist-modulo1.md). Validare su **~10 fascicoli reali**.

### 2. Scraper pilota
Un solo software di albo pretorio (il più diffuso) o una sola provincia. Pipeline end-to-end:
fetch → estrazione → DB.

### 3. Dashboard Streamlit
Sui dati pilota. Aggregazioni base + drill-down alla fonte.

### 4. Scale-up
Ai 391 comuni; arricchire gli indicatori con il **ground truth** giurisprudenziale ([07](07-fonti-dati.md)).

### 5. Crescita
Open source su GitHub, community civic tech (OpenPolis, onData), tesi universitarie, crediti cloud per
progetti civici, collaborazioni con testate locali.

## Mappa tappe → epiche della board

| Tappa | Epica | Card |
|-------|-------|------|
| 1 | E1 — Motore + Modulo 1 | TAL-1 … TAL-12 |
| 2 | E2 — Scraping pilota | TAL-20 … TAL-25 |
| 3 | E3 — Dashboard | TAL-30 … TAL-33 |
| 4–5 | E4 — Scale-up & community | TAL-40+ |

Dettaglio: [`docs/cards/BOARD.md`](../cards/BOARD.md).

[→ 09 Avvertenze legali](09-avvertenze-legali.md)
