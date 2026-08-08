# TAL-30 — Dashboard Streamlit MVP

- **Epica:** E3 — Dashboard
- **Ruolo:** 📊 FE
- **Priorità:** P2
- **Stato:** Done
- **Branch:** `feat/TAL-30-dashboard-mvp`

## 🎯 Obiettivo
Dashboard Streamlit sui dati pilota: indici per comune, trend, drill-down fino all'atto sorgente.

## 📚 Contesto
Modulo 3 ([wiki/02](../wiki/02-architettura.md)). Legge solo dal DB, non analizza. Vista user-facing → [wiki/09](../wiki/09-avvertenze-legali.md).

## ✅ Task
- [x] App Streamlit che legge dal DB (TAL-21)
- [ ] Vista per comune: red flag aggregate, indici, trend
- [ ] Confronto tra pari (comuni di taglia simile)
- [x] Drill-down: da indicatore → atti/CIG → fonte
- [x] **Anonimizzazione** viste pubbliche (piccoli comuni)
- [x] Disclaimer ben visibile
- [x] Evidenziare anche comuni **virtuosi** (principio di simmetria)

## 🧪 Criteri di accettazione
- [ ] Dashboard mostra i dati pilota con drill-down funzionante
- [ ] Ogni indicatore risale alla fonte
- [ ] Nessun dato personale esposto nei piccoli comuni
- [x] Disclaimer presente

## 🔗 Dipendenze
TAL-21, TAL-23.

## 📝 Note
Simmetria: la dashboard non è una gogna. Mostra il buono quanto il sospetto.

**2026-08-06:** aggiunte 2 tab su richiesta esplicita di Dom: **📈 Statistiche**
(atti ingeriti per giorno, KPI 7/30gg, aggregati per provincia/tipo/piattaforma
scraper) e **🗺️ Mappa copertura** (confini comunali da
`data/comuni_sicilia_confini.geojson`, colorati per stato scraper letto da
`enti.stato_scraper`; popolazione coperta calcolata incrociando
`data/comuni_sicilia.csv`). Unica eccezione al principio "legge solo dal DB":
i confini geografici e l'elenco completo dei comuni (compresi quelli mai
censiti, assenti da `enti`) non possono venire dal DB per definizione — vedi
commento in cima alla sezione mappa in `app.py`. Nessuna dipendenza nuova:
`pydeck` è già incluso in Streamlit. 10 nuovi test.
