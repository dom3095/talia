# TAL-9 — Check 6: coerenza firmatari

- **Epica:** E1 — Motore + Modulo 1
- **Ruolo:** 🔤 NLP
- **Priorità:** P1
- **Stato:** Review
- **Branch:** `feat/TAL-1-modulo1-prototipo` (sviluppo congiunto Sprint 1)

## 🎯 Obiettivo
Check 6: confronto firmatari indizione vs annullamento. Red flag se lo stesso dirigente si auto-annulla
a ridosso della graduatoria.

## 📚 Contesto
[wiki/04](../wiki/04-checklist-modulo1.md) check 6. Richiede due atti del fascicolo.

## ✅ Task
- [x] Confrontare firmatari dei due atti (da TAL-5)
- [x] Rilevare se il firmatario dell'annullamento è lo stesso dell'indizione
- [ ] Incrociare con la tempistica (vicinanza alla graduatoria) se disponibile
- [x] Esito 🟢 / 🟡 / 🔴 con spiegazione
- [x] ⚠️ Output interno: nomi = dato personale, anonimizzare nelle viste pubbliche

## 🧪 Criteri di accettazione
- [x] 🔴 quando stesso firmatario indizione+annullamento ravvicinato
- [x] Gestione matching nomi con varianti (maiuscole, titoli "Dott.")
- [x] Test: stesso firmatario, firmatari diversi, nome con varianti

## 🔗 Dipendenze
TAL-5.

## 📝 Note
Matching nomi è insidioso (omonimie, OCR sporco). Tenere conservativi i match → meglio 🟡 che falso 🔴.

## 📦 Consuntivo (12/06/2026)

Implementato in `engine/checklist/check6_firmatari.py`: confronto firmatari dei due atti
con `nome_normalizzato` (ordine, maiuscole, titoli). Sovrapposizione → 🟡 con entrambe le
citazioni (conservativo: nei piccoli comuni può essere fisiologico — mai 🔴 senza il dato
temporale). Non applicabile senza atto originario o senza firmatari estratti.
**Aperto:** incrocio con la tempistica della graduatoria (richiede estrazione dell'evento
"approvazione graduatoria") → eventuale card dedicata.
