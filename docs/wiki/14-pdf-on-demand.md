# 14 — Download PDF on-demand da catene procedurali

> **Fase 2 Pipeline:** catena ricostruita → **download PDF** → OCR/estrazione → analisi motore → red flags

---

## Flusso alto livello

```
┌─────────────────────────────────────────────────────────────────┐
│ Procedimento (catena di atti ricostruiti)                       │
│   - ID: 653 (revoca concorso Palma di Montechiaro)              │
│   - Atti: [3388, 3389, 3390, 3391, 3392, 3393]                 │
│   - url_fonte: papca-g?...&_jcitygovalbopubblicazioni_...id=468│
└─────────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────────┐
│ 1. Estrai allegati (HTTP puro, no Playwright)                   │
│                                                                  │
│   Converte:  mostraDettaglio → /papca/display/{id}             │
│   Fetcha:    GET /papca/display/4692614                         │
│   Parsa:     <tr data-chiave-allegato="..." data-mimetype="...">│
│   Decodifica: onclick="atob('aHR0cHM...')" → URL completo       │
│                                                                  │
│   Output: list[Allegato(chiave, mimetype, url_download)]       │
└─────────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. Scarica PDF (con rate limiting)                              │
│                                                                  │
│   GET {url_download}  # p_p_lifecycle=2, p_p_resource_id=...    │
│   → Content-Type: application/pdf                               │
│   → Salva: data/raw/pdf/{ente}/{procedimento_id}/{atto_id}_{id} │
│   → Hash: SHA256(contenuto)                                     │
│   → Meta.json: {atto_id, chiave_allegato, hash, data_download} │
│                                                                  │
│   Update DB: atti.url_pdf = {url_download}                      │
│             atti.hash_sha256 = {sha256}                         │
└─────────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. Estrai testo (prossimo: TAL-48)                              │
│                                                                  │
│   Input:  /data/raw/pdf/{ente}/{proc}/{atto_id}.pdf             │
│   OCR:    Tesseract (layout preservation)                       │
│   Output: testo_estratto → atti.testo_estratto                  │
└─────────────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. Analizza red flags (TAL-49+)                                 │
│                                                                  │
│   Input:  testo_estratto (bando, delibera, revoca, ...)         │
│   Check:  disponibilità bando, motivazioni, date anomale, ...   │
│   Output: red_flags table                                       │
└─────────────────────────────────────────────────────────────────┘
```

---

## API pubblica

### `pdf_download.trova_allegati(url_fonte: str) -> list[Allegato]`

Estrae metadati degli allegati dalla pagina di dettaglio di un atto.

**Args:**
- `url_fonte` — URL della pagina dettaglio (formato mostraDettaglio). Accetta anche `/papca/display/<id>` diretto.

**Returns:**
```python
[
  Allegato(
    chiave_allegato="3659561",       # ID univoco nel sistema
    mimetype="application/pdf",       # MIME type
    nome_file=None,                   # Il nome reale arriva dopo, dal Content-Disposition del download
    url_download="https://...p_p_resource_id=downloadAllegato&..._id=3659561..."
  ),
  ...
]
```

**Conversione automatica:**
Se `url_fonte` è nel formato mostraDettaglio, viene automaticamente convertito a `/papca/display/<id>`, che è più veloce e diretto.

**Log:**
- INFO: ✓ N allegati trovati
- WARNING: ✗ Nessun allegato trovato (convenzione CLAUDE.md: mai fallimento silenzioso a 0 risultati)

---

### `pdf_download.scarica_pdf_allegato(url_download: str, dest_base: Path) -> tuple[Path, str, str] | None`

Scarica un singolo allegato. `dest_base` è il percorso destinazione **senza estensione**:
l'estensione (`.pdf` / `.bin`) si decide dopo il download, dai magic bytes `%PDF` —
il `data-mimetype` dichiarato dal portale non è affidabile.

**Returns:**
- (path_salvato, filename_originale, hash_sha256)
- None se fallisce

**Idempotenza:** se il file destinazione esiste già (con `.pdf` o `.bin`), non riscarica
e non fa alcuna richiesta HTTP.

---

### `pdf_download.scarica_pdf_procedimento(conn: sqlite3.Connection, procedimento_id: int, dest_dir: Path | None = None) -> list[Path]`

Scarica **tutti** i PDF di un procedimento (catena di atti).

**Args:**
- `conn` — connessione SQLite al DB
- `procedimento_id` — ID del procedimento (chiave esterna da atti.procedimento_id)
- `dest_dir` — directory destinazione. Default: `data/raw/pdf/{ente}/{procedimento_id}/`

**Returns:**
- Lista di Path ai file scaricati

**Side effects:**
- Crea `dest_dir` se non esiste
- Salva meta.json con metadati di ogni allegato
- Aggiorna DB: `atti.url_pdf` e `atti.hash_sha256`
- Log WARNING se un atto ha 0 allegati

**Rate limiting:**
- Pausa ~1s tra richieste (configurabile con `delay` parameter)
- Timeout: 30s per richiesta, 1 retry con backoff 2s

---

## Struttura directory

```
data/raw/pdf/
├── palma_di_montechiaro/
│   ├── 653/
│   │   ├── 3388_3659561.pdf          # File scaricato
│   │   ├── 3388_3659562.bin          # Firma digitale (.p7m)
│   │   ├── 3388_3659563.bin
│   │   ├── 3391_3659546.pdf
│   │   ├── ...
│   │   ├── meta.json                 # Metadati allegati (url, hash, date)
│   │   └── motivo_selezione.json     # Perché la catena è stata scaricata (dal DB)
│   ├── 654/
│   └── 655/
└── (altri enti)
```

### meta.json
```json
[
  {
    "atto_id": 3388,
    "chiave_allegato": "3659561",
    "url_sorgente": "https://...p_p_resource_id=downloadAllegato&...&_id=3659561",
    "filename_originale": "det_SG_00016_28-05-2026.pdf",
    "filename_salvato": "3388_3659561.pdf",
    "hash_sha256": "07274e780283c6cae742e006560def450b10fd81ca259324cf670587a3acd81b",
    "mimetype": "application/pdf",
    "data_download": "2026-07-05T14:32:15.123456Z"
  },
  ...
]
```

### motivo_selezione.json

Ogni cartella di procedimento contiene la **giustificazione esplicabile** della selezione,
generata da `motivo_selezione(conn, procedimento_id)` con soli dati deterministici del DB:

- `criterio_selezione` — la regola che ha fatto scattare il download
- `stato_finale` + `metodo_individuazione` — cosa ha ricostruito l'engine catena e con
  quale confidenza
- `atti[]` — ruolo in catena (avvio/revoca/…), numero, data di pubblicazione, oggetto e
  `url_fonte` di ogni atto (esplicabilità: ogni segnalazione linka la fonte)
- `red_flags_ente[]` — le red flag batch registrate per l'ente
- `disclaimer` — "Segnalazioni da verificare, non accertamenti."

Principio: alla domanda "perché questi PDF sono stati scaricati?" risponde il **codice**,
non un giudizio umano o di un LLM.

---

## Endpoint jCityGov/Liferay

### 1. Lista atti (mostraLista)
```
GET /web/trasparenza/papca-g/-/papca?p_p_lifecycle=0
```
Ritorna lista HTML con righe `<tr data-id="{id}">...</tr>`.

### 2. Dettaglio atto (mostraDettaglio)
```
GET /web/trasparenza/papca-g?...&_jcitygovalbopubblicazioni_WAR_jcitygovalbiportlet_id={ID}&_jcitygovalbopubblicazioni_WAR_jcitygovalbiportlet_action=mostraDettaglio
```
Ritorna pagina HTML con dettagli atto (lento, carica a volte allegati via AJAX).

### 3. Display atto (formato veloce) ⭐
```
GET /web/trasparenza/papca-g/-/papca/display/{ID}
```
**PREFERITO:** Ritorna HTML con allegati direttamente visibili in `<tr data-chiave-allegato="..." data-mimetype="...">`.
Conversione automatica: mostraDettaglio → `/papca/display/<id>`.

### 4. Download allegato (resource serving)
```
GET /web/trasparenza/papca-g
  ?p_p_id=jcitygovalbopubblicazioni_WAR_jcitygovalbiportlet
  &p_p_lifecycle=2                                    # Resource serving
  &p_p_resource_id=downloadAllegato                   # Azione
  &_jcitygovalbopubblicazioni_WAR_jcitygovalbiportlet_id={ALLEGATO_ID}
  &_jcitygovalbopubblicazioni_WAR_jcitygovalbiportlet_downloadSigned=true|false
  &_jcitygovalbopubblicazioni_WAR_jcitygovalbiportlet_action=mostraDettaglio
```
Ritorna il file binario (PDF, P7M, ecc.).

---

## Sicurezza & obfuscation

### Base64 encoding dei link
L'URL di download è codificato in base64 negli onclick handler:
```html
<a onclick="...; window.open(atob('aHR0cHM6Ly9wYWxtYWRpbW9udGVjaWlhcm8uLi4=')); ...">
```

**Scopo:** Prevenire link scraping facile (anti-bot soft).

**Soluzione:** Decodifica base64 (Python stdlib `base64.b64decode`).

### User-Agent
Usa lo stesso User-Agent di jcitygov.py:
```
Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36
```

### Session management
Mantiene cookie di sessione tramite `CookieJar` (come jcitygov.py).

---

## Validazione test case (Palma di Montechiaro proc. 653-655)

| Procedimento | Atti | Allegati scaricati | Status |
|---|---|---|---|
| 653 | 3388, 3391 | 10 | ✅ |
| 654 | 3389, 3392 | 10 | ✅ |
| 655 | 3390, 3393 | 11 | ✅ |

**Hash match con data/samples/1/:**
- `revoca_concorso_autotutela.pdf`: ✅ Identico
- `det_SG_00035_22-12-2025.pdf`: ✅ Identico
- `BANDO7OPERATORIESPERTI.pdf`: ✅ Identico
- `Allegatocontabiledigitale.pdf`: ✅ Identico

---

## Note implementative

### Rate limiting
```python
delay: float = 1.0  # Pausa tra richieste
time.sleep(delay)   # Prima di fetcha allegati di un atto
time.sleep(delay)   # Prima di download ogni allegato
```

### Idempotenza
Se il file destinazione esiste già su disco (con estensione `.pdf` o `.bin`), il download
salta senza fare richieste HTTP. Un re-run su un procedimento già scaricato costa solo
il fetch delle pagine di dettaglio.

### Estensione file (magic bytes, non mimetype)
L'estensione si decide dal contenuto scaricato, non dal `data-mimetype` della pagina
(che a volte dichiara un tipo generico anche per PDF veri):
- contenuto che inizia con `%PDF` → `.pdf`
- tutto il resto (firme digitali .p7m, ecc.) → `.bin`

### Update DB
`atti.url_pdf` e `atti.hash_sha256` puntano al **primo allegato PDF vero** dell'atto
(il documento principale), non all'ultimo scaricato: gli allegati successivi sono
tipicamente firme digitali o copie firmate.

### Error handling
- ✅ 0 allegati → WARNING log (non silenzioso)
- ✅ Base64 decode fail → DEBUG log + skip
- ✅ Download timeout → 1 retry con backoff
- ✅ File write error → ERROR log + continue

---

## Prossime estensioni

1. **TAL-48** — OCR e estrazione testo
   - Input: PDF in data/raw/pdf/
   - Output: atti.testo_estratto

2. **TAL-49+** — Red flags da testo
   - Check disponibilità bando
   - Check completezza motivazioni
   - Check coerenza date/importi
   - Check riferimenti normativi

3. **Caching** — Deduplication per hash
   - Se allegato con lo stesso hash già scaricato → link simbolico
   - Risparmio storage per allegati duplicati in catene diverse

4. **Integrazione Modulo 3** — Dashboard
   - Tab "Documenti": lista allegati di una catena con link download
   - Filtrare per tipo (bando, revoca, allegati tecnici, ...)

---

Documentazione completata: 2026-07-05  
Modulo: `src/talia/modulo2_scraping/pdf_download.py`  
Card: `docs/cards/TAL-47.md`
