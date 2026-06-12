# TAL-9 — Check 6: coerenza firmatari

- **Epica:** E1 — Motore + Modulo 1
- **Ruolo:** 🔤 NLP
- **Priorità:** P1
- **Stato:** To Do
- **Branch:** `feat/TAL-9-check6-firmatari`

## 🎯 Obiettivo
Check 6: confronto firmatari indizione vs annullamento. Red flag se lo stesso dirigente si auto-annulla
a ridosso della graduatoria.

## 📚 Contesto
[wiki/04](../wiki/04-checklist-modulo1.md) check 6. Richiede due atti del fascicolo.

## ✅ Task
- [ ] Confrontare firmatari dei due atti (da TAL-5)
- [ ] Rilevare se il firmatario dell'annullamento è lo stesso dell'indizione
- [ ] Incrociare con la tempistica (vicinanza alla graduatoria) se disponibile
- [ ] Esito 🟢 / 🟡 / 🔴 con spiegazione
- [ ] ⚠️ Output interno: nomi = dato personale, anonimizzare nelle viste pubbliche

## 🧪 Criteri di accettazione
- [ ] 🔴 quando stesso firmatario indizione+annullamento ravvicinato
- [ ] Gestione matching nomi con varianti (maiuscole, titoli "Dott.")
- [ ] Test: stesso firmatario, firmatari diversi, nome con varianti

## 🔗 Dipendenze
TAL-5.

## 📝 Note
Matching nomi è insidioso (omonimie, OCR sporco). Tenere conservativi i match → meglio 🟡 che falso 🔴.
