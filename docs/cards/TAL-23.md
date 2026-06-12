# TAL-23 — Red flags batch deterministici

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🔤 NLP
- **Priorità:** P2
- **Stato:** Backlog
- **Branch:** `feat/TAL-23-red-flags-batch`

## 🎯 Obiettivo
Implementare i red flag batch (regole deterministiche, **no LLM**) sui dati raccolti.

## 📚 Contesto
Catalogo completo in [wiki/05](../wiki/05-red-flags-batch.md).

## ✅ Task
- [ ] Frazionamento artificioso (affidamenti diretti ripetuti sotto soglia, stesso oggetto/fornitore)
- [ ] Concentrazione (stesso fornitore/RUP; offerente unico)
- [ ] Tempi anomali (finestre pubblicazione brevi)
- [ ] Catene di proroghe; varianti gonfianti
- [ ] Revoche ricorrenti + riaffidamento
- [ ] Somma urgenza sistematica
- [ ] Fondi a scadenza (PNRR/PO-FESR) con affidamenti diretti concentrati
- [ ] Trasparenza: mancata/tardiva pubblicazione (D.lgs. 33/2013)
- [ ] Ogni regola: soglie come costanti documentate + elenco atti/CIG che la generano

## 🧪 Criteri di accettazione
- [ ] Ogni red flag elenca gli atti/CIG sorgente (esplicabilità)
- [ ] Soglie documentate con fonte
- [ ] Confronto tra pari dove ha senso (comuni di taglia simile)
- [ ] Test con dataset sintetico per ogni regola (positivo + negativo)

## 🔗 Dipendenze
TAL-21, TAL-22.

## 📝 Note
Tarare le soglie col ground truth (TAL-24). Falsi positivi attesi: è un invito a verificare, non un verdetto.
