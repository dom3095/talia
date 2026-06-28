# 08 — Roadmap

[← Home](00-home.md)

## Le tappe

### 1. Prototipo Modulo 1 ✅
Script che prende 2-3 PDF (indizione + annullamento) e produce il report con la checklist
[§04](04-checklist-modulo1.md). In validazione su fascicoli reali (TAL-12 in corso: 1/10).

### 2. Scraper pilota ✅
Spider iCity, ANAC open data Sicilia, Siracusa, Trapani, Agrigento. Pipeline end-to-end:
fetch → estrazione → DB. Red flags batch: frazionamento, concentrazione, tempi anomali.

### 3. Dashboard Streamlit ✅ MVP — **siamo qui**
App Streamlit su `src/talia/modulo3_dashboard/app.py`. Panoramica per comune, drill-down
fino alla fonte, anonimizzazione piccoli comuni, comuni virtuosi. Prossimi step: confronto
tra pari (comuni di taglia simile), trend temporali.

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
