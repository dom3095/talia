# TAL-10 — Report Modulo 1 (verde/giallo/rosso)

- **Epica:** E1 — Motore + Modulo 1
- **Ruolo:** 📊 FE
- **Priorità:** P1
- **Stato:** To Do
- **Branch:** `feat/TAL-10-report`

## 🎯 Obiettivo
Dato un fascicolo, produrre il **report strutturato** con tutti i check: stato, citazione, norma, disclaimer.

## 📚 Contesto
Output del Modulo 1 ([wiki/02](../wiki/02-architettura.md)). È la prima cosa user-facing → regole [wiki/09](../wiki/09-avvertenze-legali.md).

## ✅ Task
- [ ] Modello `Report` che aggrega gli esiti dei check
- [ ] Render: per ogni check → 🟢🟡🔴, citazione testuale, riferimento normativo, una riga di spiegazione
- [ ] **Disclaimer** ben visibile ("segnalazioni da verificare, non accertamenti")
- [ ] Link/ancora alla pagina+offset dell'atto sorgente per ogni flag
- [ ] Formato: scegliere tra HTML statico / JSON+template / Streamlit (vedi scelte aperte wiki/03)
- [ ] CLI: `talia analizza fascicolo/ --out report.html`

## 🧪 Criteri di accettazione
- [ ] Report leggibile con tutti i check eseguiti
- [ ] Ogni flag ha citazione + riferimento + link alla fonte
- [ ] Disclaimer presente
- [ ] Nessun dato personale reale in eventuale vista pubblica (anonimizzazione opzionale)
- [ ] Test su un fascicolo campione end-to-end

## 🔗 Dipendenze
TAL-6, TAL-7, TAL-8, TAL-9 (i check; può partire con un subset).

## 📝 Note
Anche con un solo check pronto, vale costruire lo scheletro del report per il flusso end-to-end (sblocca TAL-12).
