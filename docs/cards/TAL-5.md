# TAL-5 — Estrazione firmatari + norme citate

- **Epica:** E1 — Motore + Modulo 1
- **Ruolo:** 🔤 NLP
- **Priorità:** P1
- **Stato:** Review
- **Branch:** `feat/TAL-1-modulo1-prototipo` (sviluppo congiunto Sprint 1)

## 🎯 Obiettivo
Estrarre firmatari (nome + ruolo) e norme citate (legge/articolo), con posizione.

## 📚 Contesto
Serve a check 1 (norme) e check 6 (firmatari) → [wiki/04](../wiki/04-checklist-modulo1.md).

## ✅ Task
- [x] **Norme citate**: regex per `L. 241/1990`, `art. 21-quinquies`, `D.lgs. 36/2023`, `art. 7`, ecc.
- [x] Normalizzare in riferimento canonico (legge + articolo)
- [ ] **Firmatari**: spaCy NER (`it_core_news_lg`) + euristiche su "Il Dirigente", "Il RUP", firme finali
- [ ] Associare nome ↔ ruolo dove possibile
- [x] ⚠️ Marcare i firmatari come **dato personale** (gestione privacy a valle)

## 🧪 Criteri di accettazione
- [x] Riconosce le norme chiave dei campioni (L.241 artt. 7/21-quinquies/21-nonies; D.lgs. 36/2023)
- [x] Estrae almeno il dirigente firmatario nei campioni
- [x] Test reali + negativi

## 🔗 Dipendenze
TAL-3, TAL-4.

## 📝 Note
I nomi sono dati personali: non finiscono mai in viste pubbliche non anonimizzate ([wiki/09](../wiki/09-avvertenze-legali.md)).
Modello spaCy italiano da scaricare in setup/CI.

## 📦 Consuntivo (12/06/2026)

Implementato in `src/talia/engine/firmatari.py`: norme citate (articoli con suffissi
latini, leggi/decreti `n/anno`, dedup dei match contenuti) e firmatari via titoli
onorifici + formule di sottoscrizione (`F.to`, `firmato`). `nome_normalizzato()` per il
matching insensibile a ordine/maiuscole/titoli (usato dal check 6).
**Deviazione:** niente spaCy per ora — euristica deterministica pura (precisione >
recall); l'associazione nome↔ruolo è rinviata. I nomi restano dato personale: mai in
viste pubbliche non anonimizzate.
