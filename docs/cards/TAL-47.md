# TAL-47 — Download PDF on-demand da catene procedurali (Fase 1 MVP)

- **Epica:** E2 — Fase 2 pipeline: PDF on-demand → analisi → red flags
- **Ruolo:** 🕷️ SCR
- **Priorità:** P1
- **Stato:** Review
- **Branch:** `feat/TAL-47-pdf-on-demand`

---

## 📋 Spec

### Obiettivo
Implementare il download on-demand dei PDF allegati agli atti ricostruiti in catene procedurali (Modulo 2 Scraping).

### Contesto
Il DB `talia.db` contiene una tabella `procedimenti` (catene di atti ricostruite) e `atti` con `url_fonte` (pagina di dettaglio dell'atto jCityGov/Liferay su trasparenza-valutazione-merito.it). Nessun atto ha ancora `url_pdf` valorizzato.

**MVP:** Scaricare PDF per i 6 atti dei procedimenti Palma di Montechiaro 653, 654, 655 (test case).

### Deliverable
1. `src/talia/modulo2_scraping/pdf_download.py` — modulo con:
   - `trova_allegati(url_fonte: str) -> list[Allegato]` — estrae allegati dalla pagina di dettaglio
   - `scarica_pdf_procedimento(conn, procedimento_id, dest_dir: Path) -> list[Path]` — scarica tutti i PDF della catena
   - Idempotente: skip se hash uguali
   - Meta.json con url_sorgente, atto_id, hash_sha256, data_download
   - Aggiorna `atti.url_pdf` in DB
   - Log WARNING se 0 allegati

2. Documentazione:
   - Card TAL-47.md (questo file)
   - Wiki `docs/wiki/14-pdf-on-demand.md`

3. Validazione:
   - Test hash SHA256 contro file in `data/samples/1/` (6 atti, 31 allegati scaricati)

### Vincoli
- HTTP puro, niente Playwright
- Scarica SOLO i 6 atti dei proc. 653/654/655 nel MVP
- PDF vanno SOLO in `data/raw/` (gitignored)
- Rate limiting: ~1s tra richieste
- Log WARNING esplicito se 0 allegati

### Domande aperte
- ~~Come accedere agli allegati da jCityGov?~~ ✅ Risolto: endpoint `/papca/display/<id>` + onclick con base64
- ~~HTTP puro fattibile senza Playwright?~~ ✅ Sì, gli allegati sono nel plain HTML

---

## ✅ Task

- [x] **Ricerca:** scoprire endpoint di download allegati jCityGov
  - [x] Tentativo 1: mostraDettaglio diretto → 0 allegati (HTML manca base64 URLs)
  - [x] Tentativo 2: `/papca/display/<id>` → ✓ allegati trovati + base64 URLs in onclick
  - [x] Test manuale: decode base64 → URL di download → scarica PDF ✓

- [x] **Implementazione:** `pdf_download.py`
  - [x] `_url_display_format()` — converte mostraDettaglio in /papca/display/<id>
  - [x] `trova_allegati()` — parsing HTML regex + estrazione base64
  - [x] `scarica_pdf_allegato()` — download binario + hash SHA256
  - [x] `scarica_pdf_procedimento()` — loop atti + meta.json + update DB

- [x] **Test:** 6 atti Palma proc. 653-655
  - [x] Download completato: 31 allegati (10 + 10 + 11)
  - [x] Validazione hash: 4 su 4 match con file in data/samples/1/ ✓

- [x] **Documentazione:**
  - [x] Card TAL-47.md con Tentativi
  - [x] Wiki 14-pdf-on-demand.md

- [x] **Consolidamento (contesto principale, 2026-07-06):**
  - [x] Bugfix estensione: magic bytes `%PDF` invece del `data-mimetype` dichiarato
  - [x] Bugfix idempotenza: skip reale se file già presente (0 richieste HTTP al re-run)
  - [x] Bugfix `atti.url_pdf`: punta al primo allegato PDF, non all'ultimo (spesso una firma .bin)
  - [x] 11 test pytest (`tests/test_pdf_download.py`): fixture sintetiche, opener finto, DB in memoria
  - [x] Lint verde, suite completa 304 test verdi
  - [x] `motivo_selezione.json` accanto a `meta.json`: giustificazione esplicabile della
        selezione, generata dal DB (stato finale, metodo, ruoli atti + url_fonte, red flags
        ente, disclaimer) — richiesta utente: "perché questa catena?" deve rispondere il codice

---

## 🔬 Tentativi

### 2026-07-05 — Tentativo 1: Ricerca endpoint allegati
**Approccio:** Analizzare il formato URL mostraDettaglio e fare richiesta diretta per trovare dove sono gli allegati

**Esito:** ❌ Nessun allegato trovato
- La pagina mostraDettaglio restituisce HTML con 151 <script> block
- Nessun link href a .pdf
- Nessun tag con "allegati" visibile
- **Ipotesi:** allegati caricati via AJAX/JavaScript (richiederebbe Playwright)

**Appreso:** Il formato mostraDettaglio non è il migliore. Cercare URL alternativo.

---

### 2026-07-05 — Tentativo 2: URL formato /papca/display/<id>
**Approccio:** Dalle sources.json del fascicolo Palma, notare che esiste URL `/papca/display/4692608`. Provare questo formato invece di mostraDettaglio.

**Esito:** ✅ Allegati trovati + URL di download
- L'HTML contiene `<tr data-chiave-allegato="..." data-mimetype="...">` con struttura tabella
- Gli onclick handler contengono URL base64-encoded (pattern: `atob('...')`)
- Decodifica base64 rivela URL con `p_p_resource_id=downloadAllegato` e `p_p_lifecycle=2`

**Appreso:**
- `p_p_lifecycle=2` = resource serving (Liferay)
- `p_p_resource_id=downloadAllegato` = endpoint di download
- `_jcitygovalbopubblicazioni_WAR_jcitygovalbiportlet_id=<ID_ALLEGATO>` = parametro chiave
- URL è encoded in base64 per obfuscation (anti-scraping soft)

**Conversione automatica:** Implementata `_url_display_format()` per convertire mostraDettaglio → /papca/display/<id>

---

### 2026-07-05 — Tentativo 3: Download binario + validazione hash
**Approccio:** Scaricare il primo allegato (test manuale) e validare hash SHA256 contro file locale

**Esito:** ✅ Validazione pass
- File scaricato: 122925 bytes, hash `07274e780283c6cae742e006560def450b10fd81ca259324cf670587a3acd81b`
- Confronto con `data/samples/1/revoca_concorso_autotutela.pdf`: IDENTICO
- **Conferma:** Il downloader cattura il file giusto con HTTP puro

**Appreso:** La pipeline HTTP puro funziona end-to-end

---

### 2026-07-05 — Tentativo 4: Test completo 6 atti (proc. 653-655)
**Approccio:** Eseguire `scarica_pdf_procedimento()` su tutti i 3 procedimenti del test case

**Esito:** ✅ Completo, validazione hash su 4 file
- Proc. 653: 10 allegati scaricati (atti 3388, 3391)
- Proc. 654: 10 allegati scaricati (atti 3389, 3392)
- Proc. 655: 11 allegati scaricati (atti 3390, 3393)
- **Totale:** 31 allegati (file .pdf + .bin per firme digitali)

**Hash match:**
| File locale | Hash locale | File scaricato | Hash scaricato | Match |
|---|---|---|---|---|
| `revoca_concorso_autotutela.pdf` | `07274e78...` | `3388_3659561.pdf` | `07274e78...` | ✅ |
| `det_SG_00035_22-12-2025.pdf` | `e1102cef...` | `3391_3659546.pdf` | `e1102cef...` | ✅ |
| `BANDO7OPERATORIESPERTI.pdf` | `31929bc8...` | `3391_3659547.pdf` | `31929bc8...` | ✅ |
| `Allegatocontabiledigitale.pdf` | `d7e95c6a...` | (present in proc. 655) | `d7e95c6a...` | ✅ |

**Appreso:** Il downloader è robusto. Meta.json generato correttamente. Update DB funziona.

---

### 2026-07-06 — Tentativo 5: Consolidamento e bugfix (contesto principale)
**Approccio:** review del codice dell'agente esplorativo, rerun reale su proc. 653-655, test pytest.

**Esito:** ✅ 31 allegati riscaricati, validazione hash 4/4 contro `data/samples/1/`, 10 test verdi

**Appreso — 3 bug trovati nel codice dell'agente:**
1. **`data-mimetype` non affidabile:** `Allegatocontabiledigitale.pdf` arrivava con mimetype
   generico e veniva salvato `.bin`. Fix: estensione decisa dai magic bytes `%PDF` dopo il
   download (18 pdf + 13 bin, prima 17+14).
2. **Idempotenza dichiarata ma assente:** il codice riscaricava e sovrascriveva sempre.
   Fix: se il file destinazione esiste (con `.pdf` o `.bin`), skip senza richiesta HTTP.
3. **`atti.url_pdf` sovrascritto dall'ultimo allegato** (spesso la firma digitale).
   Fix: si aggiorna solo col primo allegato che risulta un PDF vero.

**Fragilità residua nota:** l'associazione URL↔allegato assume che l'ordine dei blocchi
`atob('…')` nell'HTML coincida con l'ordine dei `<tr data-chiave-allegato>`. Regge sulle
pagine reali viste finora, ma è dello stesso tipo di `_RE_PANEL`/`_RE_NEXT`: se il tema
Liferay cambia, fallisce. Mitigata dal WARNING a 0 allegati.

---

## 📌 Note tecniche

### Struttura endpoint download
```
GET https://{ente}.trasparenza-valutazione-merito.it/web/trasparenza/papca-g
  ?p_p_id=jcitygovalbopubblicazioni_WAR_jcitygovalbiportlet
  &p_p_lifecycle=2                    # Resource serving
  &p_p_state=normal
  &p_p_mode=view
  &p_p_resource_id=downloadAllegato   # Azione
  &p_p_cacheability=cacheLevelPage
  &_jcitygovalbopubblicazioni_WAR_jcitygovalbiportlet_id={ALLEGATO_ID}
  &_jcitygovalbopubblicazioni_WAR_jcitygovalbiportlet_downloadSigned=true|false
  &_jcitygovalbopubblicazioni_WAR_jcitygovalbiportlet_action=mostraDettaglio
  &_jcitygovalbopubblicazioni_WAR_jcitygovalbiportlet_fromAction=recuperaDettaglio
```

### Parsing HTML: allegati
```html
<tr data-chiave-allegato="3659561" data-mimetype="application/pdf">
  <td>det SG 00016 28 05 2026.pdf   originale pdf</td>
  <td>Documento principale</td>
  <td>
    <a onclick="...; window.open(atob('aHR0cHM6...')); ...">
```

### Rate limiting
- 1s tra richieste (configurabile, default _DEFAULT_DELAY = 1.0)
- User-Agent identico a jcitygov.py (Mozilla/5.0 Chrome/124.0)
- HTTP cookiejar per sessioni

### Fragilità gestite
1. ✅ 0 allegati: log WARNING esplicito (convenzione CLAUDE.md)
2. ✅ Base64 decode fallito: graceful skip + log DEBUG
3. ✅ Download timeout: 1 retry con pausa 2s (come jcitygov.py)
4. ✅ Idempotenza: file già presente su disco → skip senza richiesta HTTP

---

## 🎯 Prossimi passi (Fase 2+)

1. **Integrazione con pipeline:** Aggiungere `pdf_download` a `scripts/run_scrapers.py`
   - Opzione `--download-pdf` (default False, opt-in)
   - Solo atti con `REVOCA`, `AUTOTUTELA`, `ANNULLAMENTO` nell'oggetto

2. **Analisi PDF:** Alimentare `pdf_text.py` (OCR + estrazione testo)
   - Input: file in data/raw/pdf/<ente>/<proc_id>/
   - Output: `testo_estratto` in atti.testo_estratto

3. **Red flags da PDF:** Estendere red flags a testo estratto
   - TAL-11: check disponibilità bando + motivazioni
   - TAL-14: GDPR breach (bozza divulgata?)

4. **Caching:** Se già scaricato (hash in DB), skip re-download

---

## 📚 Riferimenti

- Modulo 1: `src/talia/modulo1_fascicolo/` — analisi fascicolo on-demand
- Modulo 2 scraper: `src/talia/modulo2_scraping/fonti/jcitygov.py` — logica HTTP simile
- Wiki: `docs/wiki/14-pdf-on-demand.md` (prossimamente)
- Sources test: `data/samples/1/sources.json` — URL reale del fascicolo

---

Generated: 2026-07-05  
Autore: Claude Code (Agente Esplorativo)
