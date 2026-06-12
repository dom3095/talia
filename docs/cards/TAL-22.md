# TAL-22 — Pipeline ANAC/BDNCP (regione 19)

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🕷️ SCR
- **Priorità:** P2
- **Stato:** Backlog
- **Branch:** `feat/TAL-22-anac`

## 🎯 Obiettivo
Importare dati appalti da ANAC/BDNCP filtrati per Sicilia (codice ISTAT regione 19): CIG, aggiudicazioni, varianti.

## 📚 Contesto
[wiki/07](../wiki/07-fonti-dati.md). Dati strutturati → ottimi per i red flag batch deterministici.

## ✅ Task
- [ ] Individuare gli open data ANAC/BDNCP utili (dataset/API)
- [ ] Filtro regione 19
- [ ] Mapping su schema DB (TAL-21): CIG, importi, aggiudicatari, RUP, varianti
- [ ] Job ripetibile/incrementale

## 🧪 Criteri di accettazione
- [ ] Carica un batch di CIG siciliani nel DB
- [ ] Collega, dove possibile, CIG ↔ atti scrapati (TAL-20)
- [ ] Re-run incrementale senza duplicati

## 🔗 Dipendenze
TAL-21.

## 📝 Note
ANAC è la fonte più strutturata → abilita concentrazione, frazionamento, varianti ([wiki/05](../wiki/05-red-flags-batch.md)).
