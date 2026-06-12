# TAL-12 — Validazione su 10 fascicoli reali

- **Epica:** E1 — Motore + Modulo 1
- **Ruolo:** ⚖️ LEX
- **Priorità:** P1
- **Stato:** To Do
- **Branch:** `feat/TAL-12-validazione`

## 🎯 Obiettivo
Validare il prototipo Modulo 1 su **~10 fascicoli reali** (indizione + annullamento), misurando
falsi positivi/negativi e raffinando i check.

## 📚 Contesto
Chiusura della tappa 1 della [roadmap](../wiki/08-roadmap.md). È il test di realtà del prototipo.

## ✅ Task
- [ ] Raccogliere 10 fascicoli reali (anonimizzati per il repo, in `data/samples/`)
- [ ] Far girare il report su ciascuno
- [ ] Confronto esito TALIA vs valutazione di un esperto ⚖️ LEX
- [ ] Tabella falsi positivi / falsi negativi per check
- [ ] Lista di raffinamenti per le regole (issue/card di follow-up)
- [ ] Documentare i risultati nella wiki

## 🧪 Criteri di accettazione
- [ ] Report generato per tutti e 10 i fascicoli senza crash
- [ ] Tasso di falsi positivi accettabile sui check deterministici (concordato col team)
- [ ] Nessun dato personale reale committato (campioni anonimizzati)
- [ ] Findings documentati + card di follow-up create

## 🔗 Dipendenze
TAL-10 (report), almeno TAL-6/TAL-7 (check minimi).

## 📝 Note
Una red flag è un invito a verificare: l'obiettivo non è "0 falsi positivi" ma rumore gestibile e
spiegazioni sempre corrette. Coinvolgere un giurista reale per il ground truth.
