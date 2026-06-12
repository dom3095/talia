# TAL-10 — Report Modulo 1 (verde/giallo/rosso)

- **Epica:** E1 — Motore + Modulo 1
- **Ruolo:** 📊 FE
- **Priorità:** P1
- **Stato:** Review
- **Branch:** `feat/TAL-1-modulo1-prototipo` (sviluppo congiunto Sprint 1)

## 🎯 Obiettivo
Dato un fascicolo, produrre il **report strutturato** con tutti i check: stato, citazione, norma, disclaimer.

## 📚 Contesto
Output del Modulo 1 ([wiki/02](../wiki/02-architettura.md)). È la prima cosa user-facing → regole [wiki/09](../wiki/09-avvertenze-legali.md).

## ✅ Task
- [x] Modello `Report` che aggrega gli esiti dei check
- [x] Render: per ogni check → 🟢🟡🔴, citazione testuale, riferimento normativo, una riga di spiegazione
- [x] **Disclaimer** ben visibile ("segnalazioni da verificare, non accertamenti")
- [x] Link/ancora alla pagina+offset dell'atto sorgente per ogni flag
- [x] Formato: scegliere tra HTML statico / JSON+template / Streamlit (vedi scelte aperte wiki/03)
- [x] CLI: `talia analizza fascicolo/ --out report.html`

## 🧪 Criteri di accettazione
- [x] Report leggibile con tutti i check eseguiti
- [x] Ogni flag ha citazione + riferimento + link alla fonte
- [x] Disclaimer presente
- [x] Nessun dato personale reale in eventuale vista pubblica (anonimizzazione opzionale)
- [x] Test su un fascicolo campione end-to-end

## 🔗 Dipendenze
TAL-6, TAL-7, TAL-8, TAL-9 (i check; può partire con un subset).

## 📝 Note
Anche con un solo check pronto, vale costruire lo scheletro del report per il flusso end-to-end (sblocca TAL-12).

## 📦 Consuntivo (12/06/2026)

Implementato in `modulo1_fascicolo/`: `Report` (esiti + metadati atti + conteggio) con
rese **markdown**, **JSON** e **HTML statico** (puro Python, escaping, disclaimer in
evidenza); orchestrazione `analisi.py` (classificazione ruolo atti, contesto, checklist);
CLI `talia analizza <file|cartella> [--formato testo|md|json|html] [--out f]`.
**Decisione formato:** HTML statico + JSON (niente Streamlit per il Modulo 1: zero deps;
Streamlit resta per il Modulo 3). Ogni citazione espone pagina+offset; link cliccabile al
PDF sorgente rinviato a quando i report saranno pubblicati accanto agli atti.
