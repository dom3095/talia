# TAL-23 — Red flags batch deterministici

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🔤 NLP
- **Priorità:** P2
- **Stato:** Done
- **Branch:** `feat/sprint3`

## 🎯 Obiettivo
Implementare i red flag batch (regole deterministiche, **no LLM**) sui dati raccolti.

## 📚 Contesto
Catalogo completo in [wiki/05](../wiki/05-red-flags-batch.md).

## ✅ Task
- [x] Frazionamento artificioso: ≥3 affidamenti sotto soglia (140k) in 90 gg con totale > soglia
- [x] Concentrazione: quota affidamenti diretti vs bandi > 80% in un anno (≥10 atti)
- [x] Tempi anomali: bando con finestra pubblicazione < 15 gg (sotto soglia UE) / < 30 gg (sopra)
- [x] Runner: `esegui_tutti(conn)` salva tutti i flag nel DB e ritorna report
- [ ] Catene di proroghe; varianti gonfianti — rimandato (richiede campi non ancora presenti)
- [ ] Revoche ricorrenti + riaffidamento — rimandato (richiede join tra atti)
- [ ] Somma urgenza sistematica — rimandato
- [ ] Trasparenza D.lgs. 33/2013 — rimandato (richiede date di pubblicazione obbligatoria)

## 🧪 Criteri di accettazione
- [x] Ogni red flag elenca gli atti/CIG sorgente (esplicabilità)
- [x] Soglie documentate con fonte normativa nel codice
- [x] Test con dataset sintetico per ogni regola (positivo + negativo): 20 test offline
- [ ] Confronto tra pari (popolazione ± 30%) — rimandato (richiede join su `popolaz`)

## 🔗 Dipendenze
TAL-21 ✅, TAL-22 ✅.

## 📝 Note implementative
- Pacchetto `src/talia/modulo2_scraping/red_flags/` con 5 file
- `frazionamento.py`: algoritmo sliding window 90 giorni per ente
- `concentrazione.py`: query GROUP BY ente/anno con HAVING
- `tempi_anomali.py`: SELECT bandi + calcolo (data_scadenza - data_pub) in Python
- Bug fixato in concentrazione: `strftime('%Y')` ritorna TEXT → confronto con `str(anno)`
- Soglie regolabili via keyword args per i test
