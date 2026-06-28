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

## 🐛 Problemi noti / debito tecnico

1. **CSV ~400 MB per anno**: ogni download è pesante; in produzione serve o un HTTP Range request per scaricare solo righe nuove, o un mirror locale, o sfruttare i file delta se ANAC li pubblica.

2. **Ritardo strutturale 12-18 mesi**: il dataset SmartCIG dell'anno N arriva con ~1-2 anni di ritardo (es. 2024 disponibile solo a metà 2026). Il default `anno - 2` lo aggira, ma significa che i dati sono sempre "vecchi". Non c'è modo di avere dati recenti da questa fonte; per il near-real-time bisogna usare le API SIMOG/BDNCP (diverse, richiedono accreditamento).

3. **Schema CSV instabile tra anni**: le colonne cambiano nome tra versioni del dataset (es. `denominazione_sa` vs `denominazione_amministrazione`). `_ALIAS_COLONNE` copre i casi noti ma va riallineato ogni volta che ANAC rilascia un nuovo anno — non c'è garanzia di retrocompatibilità.

4. **CF come pseudo-ISTAT**: gli enti inseriti da ANAC usano il Codice Fiscale come `codice_istat`, che non è il vero codice ISTAT ISTAT del comune. Rende difficile il join con IPA, ISTAT e altri dataset. Va normalizzato con una lookup CF→ISTAT prima di andare in produzione.

5. **Multi-anno non automatico**: `scarica_e_carica()` scarica solo un anno. Per avere uno storico completo (es. 2019-2024) bisogna iterare manualmente; non c'è ancora un job che copre più anni in sequenza.

6. **WAF fragile**: il workaround UA browser-like funziona oggi ma è fragile — ANAC può rafforzare il WAF in qualsiasi momento. Se inizia a bloccare, valutare il download via curl con cookie di sessione o usare un proxy.

7. **URL sintetico potenzialmente rotto**: `dati.anticorruzione.it/opendata/cig/<cig>` è costruito a mano, non estratto dalla risposta. Se ANAC cambia la struttura degli URL i link nel DB diventano stale.

8. **Affidamenti diretti sotto soglia assenti**: molte procedure sotto i €5.000 (o quelle senza obbligo CIG) non finiscono nel dataset SmartCIG. Copertura strutturalmente parziale per i micro-affidamenti, che sono spesso i più interessanti per i red flag.
