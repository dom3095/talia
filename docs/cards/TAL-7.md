# TAL-7 — Check 2: termini autotutela (12 mesi)

- **Epica:** E1 — Motore + Modulo 1
- **Ruolo:** 🔤 NLP
- **Priorità:** P1
- **Stato:** To Do
- **Branch:** `feat/TAL-7-check2-termini`

## 🎯 Obiettivo
Check 2: l'annullamento d'ufficio è entro il termine ragionevole (≤ 12 mesi dall'atto originario)?

## 📚 Contesto
[wiki/04](../wiki/04-checklist-modulo1.md) check 2. Termine ex art. 21-nonies per atti attributivi di vantaggi.

## ✅ Task
- [ ] Estrarre data dell'atto originario e data dell'annullamento (da TAL-4)
- [ ] Calcolare il delta temporale
- [ ] Soglia **12 mesi** come costante documentata (fonte normativa nel commento)
- [ ] Esito 🟢 (entro termine) / 🟡 (al limite) / 🔴 (oltre 12 mesi)
- [ ] Applicare solo se l'istituto è annullamento (non revoca)

## 🧪 Criteri di accettazione
- [ ] 🔴 quando delta > 12 mesi su un annullamento
- [ ] Non applicato (o nota) se l'atto è una revoca
- [ ] Gestione date mancanti/ambigue → 🟡 con spiegazione, mai crash
- [ ] Test: dentro termine, oltre termine, data mancante

## 🔗 Dipendenze
TAL-4, TAL-6.

## 📝 Note
Le date possono essere "data adozione" vs "data pubblicazione": documentare quale si usa e perché. ⚖️ LEX da consultare.
