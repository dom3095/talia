# TAL-7 — Check 2: termini autotutela (12 mesi)

- **Epica:** E1 — Motore + Modulo 1
- **Ruolo:** 🔤 NLP
- **Priorità:** P1
- **Stato:** Review
- **Branch:** `feat/TAL-1-modulo1-prototipo` (sviluppo congiunto Sprint 1)

## 🎯 Obiettivo
Check 2: l'annullamento d'ufficio è entro il termine ragionevole (≤ 12 mesi dall'atto originario)?

## 📚 Contesto
[wiki/04](../wiki/04-checklist-modulo1.md) check 2. Termine ex art. 21-nonies per atti attributivi di vantaggi.

## ✅ Task
- [x] Estrarre data dell'atto originario e data dell'annullamento (da TAL-4)
- [x] Calcolare il delta temporale
- [x] Soglia **12 mesi** come costante documentata (fonte normativa nel commento)
- [x] Esito 🟢 (entro termine) / 🟡 (al limite) / 🔴 (oltre 12 mesi)
- [x] Applicare solo se l'istituto è annullamento (non revoca)

## 🧪 Criteri di accettazione
- [x] 🔴 quando delta > 12 mesi su un annullamento
- [x] Non applicato (o nota) se l'atto è una revoca
- [x] Gestione date mancanti/ambigue → 🟡 con spiegazione, mai crash
- [x] Test: dentro termine, oltre termine, data mancante

## 🔗 Dipendenze
TAL-4, TAL-6.

## 📝 Note
Le date possono essere "data adozione" vs "data pubblicazione": documentare quale si usa e perché. ⚖️ LEX da consultare.

## 📦 Consuntivo (12/06/2026)

Implementato in `engine/checklist/check2_termini.py`. Applicabile solo se l'atto cita
21-nonies. Soglia `SOGLIA_GIORNI = 365` (+ tolleranza 30 gg → 🟡 "al limite") documentata
con fonte. Date mancanti/incongruenti → 🟡 con spiegazione, mai crash.
**Assunzione documentata nel modulo (da validare con ⚖️ LEX):** data atto originario =
data più antica dell'atto originario (o, senza di esso, la più antica citata
nell'autotutela); data annullamento = data più recente dell'atto di autotutela.
