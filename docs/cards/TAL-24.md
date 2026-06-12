# TAL-24 — Ground truth: sentenze annullamento

- **Epica:** E2 — Scraping pilota
- **Ruolo:** ⚖️ LEX
- **Priorità:** P2
- **Stato:** Backlog
- **Branch:** `feat/TAL-24-ground-truth`

## 🎯 Obiettivo
Costruire un dataset "etichettato gratis" di atti con esito noto, per tarare gli indicatori e renderli difendibili.

## 📚 Contesto
[wiki/07](../wiki/07-fonti-dati.md): sentenze di annullamento (TAR/CGA) + atti dei comuni sciolti per infiltrazione.

## ✅ Task
- [ ] Raccogliere sentenze di annullamento da giustizia-amministrativa.it (TAR PA/CT, CGA)
- [ ] Collegare la sentenza all'atto annullato (dove reperibile)
- [ ] Raccogliere riferimenti agli atti dei comuni sciolti per infiltrazione mafiosa
- [ ] Etichettatura: "atto che ha preceduto un problema accertato"
- [ ] Conservare provenienza + data per ciascun esempio

## 🧪 Criteri di accettazione
- [ ] Insieme iniziale di esempi etichettati con fonte verificabile
- [ ] Utilizzabile per misurare i red flag (precision/recall indicativi)
- [ ] Nessun dato personale reale committato in chiaro

## 🔗 Dipendenze
TAL-21 (per persistere i collegamenti).

## 📝 Note
È la base statistica che rende gli indicatori "difendibili". Coinvolge competenza giuridica reale.
