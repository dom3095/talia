# TAL-22 — Pipeline ANAC/BDNCP (regione 19)

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🕷️ SCR
- **Priorità:** P2
- **Stato:** Done
- **Branch:** `feat/sprint3`

## 🎯 Obiettivo
Importare dati appalti da ANAC/BDNCP filtrati per Sicilia: CIG, stazioni appaltanti, oggetto, importo.

## 📚 Contesto
[wiki/07](../wiki/07-fonti-dati.md). Dati strutturati → ottimi per i red flag batch deterministici.

## ✅ Task
- [x] Individuare dataset open ANAC: SmartCIG CSV (sezione_regionale = "Sicilia")
- [x] Filtro regione Sicilia
- [x] Mapping su schema DB (TAL-21): CIG, importo, oggetto, tipo_appalto, CF ente
- [x] Job ripetibile/incrementale (idempotente su ente_id × url_fonte)
- [x] `crea_enti_mancanti=True` (default): inserisce enti da CF se non nel DB
- [x] Test offline con CSV sintetico (10 righe, 8 siciliane + 2 fuori)

## 🧪 Criteri di accettazione
- [x] Carica atti siciliani nel DB filtrandoli dal CSV ANAC
- [x] Re-run incrementale senza duplicati: `duplicati == n, inseriti == 0`
- [x] Enti non in DB vengono inseriti automaticamente (con CF come pseudo-ISTAT) o saltati
- [x] Test offline: 22 test passano

## 🔗 Dipendenze
TAL-21.

## 📝 Decisioni tecniche
- **url_fonte sintetico**: `https://dati.anticorruzione.it/opendata/cig/<cig>` — ogni CIG è univoco e cliccabile sul portale ANAC.
- **Pseudocodice per enti nuovi**: se un ente ANAC non è ancora nel DB, viene inserito usando il CF come pseudo-ISTAT. Andrà poi normalizzato con i veri ISTAT quando si popola la tabella `enti`.
- **`_fetch_fn` iniettabile**: tutti i test girano offline, la rete entra solo in `scarica_e_carica()`.
