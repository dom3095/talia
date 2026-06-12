# TAL-8 — Check 5: comunicazione avvio procedimento (art. 7)

- **Epica:** E1 — Motore + Modulo 1
- **Ruolo:** 🔤 NLP
- **Priorità:** P1
- **Stato:** Review
- **Branch:** `feat/TAL-1-modulo1-prototipo` (sviluppo congiunto Sprint 1)

## 🎯 Obiettivo
Check 5: l'atto menziona la comunicazione di avvio del procedimento (art. 7 L. 241/90) ai partecipanti?

## 📚 Contesto
[wiki/04](../wiki/04-checklist-modulo1.md) check 5.

## ✅ Task
- [ ] Cercare menzione di art. 7 / "comunicazione di avvio del procedimento" / "preavviso"
- [x] Distinguere menzione effettiva da assenza
- [x] Esito 🟢 (menzionata) / 🟡 (ambigua) / 🔴 (assente)
- [x] Citazione testuale a supporto

## 🧪 Criteri di accettazione
- [x] 🔴 quando nessuna menzione nei confronti dei partecipanti
- [x] 🟢 con citazione quando presente
- [x] Test: presente, assente, formula ambigua

## 🔗 Dipendenze
TAL-3, TAL-5.

## 📝 Note
L'assenza di menzione non prova l'omissione dell'adempimento → linguaggio prudente, è una red flag da verificare.

## 📦 Consuntivo (12/06/2026)

Implementato in `engine/checklist/check5_avvio.py`: cerca "comunicazione di avvio",
"avvio del procedimento" o "art. 7" con "241" entro 60 caratteri. 🟢 con citazione se
presente, 🔴 se assente (linguaggio prudente: assenza di menzione ≠ omissione provata).
**Deviazione:** "preavviso" non incluso (il preavviso di rigetto è art. 10-bis, istituto
diverso); l'esito 🟡 "formula ambigua" non ha ancora un caso d'innesco definito → da
raffinare con ⚖️ LEX.
