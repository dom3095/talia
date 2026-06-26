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
