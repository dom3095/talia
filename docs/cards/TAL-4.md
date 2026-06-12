# TAL-4 — Estrazione entità: date, importi, CIG

- **Epica:** E1 — Motore + Modulo 1
- **Ruolo:** 🔤 NLP
- **Priorità:** P0
- **Stato:** To Do
- **Branch:** `feat/TAL-4-entita-base`

## 🎯 Obiettivo
Estrarre dal testo le entità deterministiche di base, ognuna con offset/posizione nel documento.

## 📚 Contesto
Secondo stadio del motore ([wiki/02](../wiki/02-architettura.md)). Regex per pattern rigidi.

## ✅ Task
- [ ] **Date** (formati italiani: `12/06/2026`, `12 giugno 2026`, ecc.) → normalizzate ISO
- [ ] **Importi** (`€ 1.234,56`, `euro ...`) → Decimal normalizzato
- [ ] **CIG** (10 caratteri alfanumerici) con validazione formato
- [ ] **CUP** (15 caratteri) opzionale
- [ ] Ogni entità porta: valore normalizzato, testo originale, offset, pagina
- [ ] Modello `Entita` + `EntitaEstratte`

## 🧪 Criteri di accettazione
- [ ] Estrae date/importi/CIG corretti dai campioni
- [ ] Casi negativi: non confonde numeri di protocollo con CIG, ecc.
- [ ] Ogni entità risalibile alla posizione nel testo
- [ ] Test con esempi reali + negativi

## 🔗 Dipendenze
TAL-3.

## 📝 Note
CIG: formato ANAC. Documentare le regex con commento + fonte. Numeri "magici" → costanti.
