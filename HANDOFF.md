# HANDOFF.md — Stato sessione

> Aggiornato: 2026-07-10 (TAL-50 Palermo/Trapani, in corso)

---

## Branch attivo (priorità)

`feat/E3-province-palermo-trapani` — **Estensione E3: censimento Palermo/Trapani (TAL-50)**.
Sessione del 2026-07-10: partita da E3, completato censimento web sistematico (77 comuni 
mancanti PA/TP → 100% con albo online), aggiunta TIER 0 al registry (8 comuni: 2 jCityGov, 
6 portalepa, 1 URBI), validazione HTTP 200 su 3 comuni campione. Tutto committato e pushato. 
Working tree pulito (escludendo `data/samples/1/` locale e `scripts/sweep_palermo_trapani.py` 
temporaneo).

## Branch secondario (upstream)

`feat/E3-censimento-comuni-sicilia` — **PR #8 aperta, pronta per il merge (TAL-49)**.
Sessione del 2026-07-07 (TAL-49): partita come sessione autonoma (censimento + rollout
jCityGov), proseguita interattiva nel pomeriggio/sera con Dom (fix, nuove piattaforme,
sweep di dominio). Proseguita il 2026-07-08 con il completamento dei 12 comuni più
popolosi mancanti della provincia di Agrigento (4 gruppi da 3), e il 2026-07-09 con
altri 6 dei 13 comuni ancora scoperti della stessa provincia (i più piccoli, tutti su
piattaforme già supportate). Tutto committato e pushato, working tree pulito a parte
`data/samples/1/` (locale, mai committare) e `notebooks/`/
`data/comuni_sicilia_confini.geojson` (mappa di copertura, non ancora committati —
decisione pendente di Dom).

### Cosa contiene la PR #8 (da rivedere e mergiare)

Riassunto cumulativo:

- `data/comuni_sicilia.csv` — 391 comuni per popolazione (codici ISTAT ufficiali)
- **Palermo** (`palermo.py`): SISPI in HTTP puro — 8 test
- **Catania** (`catania.py`): wizard URBI in HTTP puro — 6 test
- **Fix 4 codici ISTAT errati** (Caltanissetta, Siracusa, Enna, Palma) — migrazione applicata a `talia.db`
- **jCityGov**: 60 comuni rollout iniziale + fix parser (12 tenant senza colonna "Anno e Numero
  Registro") + fallback automatico per tenant con "0 risultati" sul percorso standard
  (scopre risorsa "Albo pretorio" o "Storico atti" alternativa) → **66 comuni totali**
  (Milazzo, Aragona, Gaggi, Letojanni, Noto, Racalmuto sbloccati così)
- **`portalepa.py`** (nuovo modulo, generalizzato da `siracusa.py`): **18 comuni**, di cui 16
  trovati con sweep di dominio (`<slug>.soluzionipa.it`) — include **Caltagirone**, sbloccata
  qui nonostante sia bloccata su jCityGov (WAF/cert scaduto)
- **`halley.py`** (nuovo modulo, piattaforma Halley Informatica): **93 comuni**, di cui 85
  trovati con sweep di dominio + Menfi/Siculiana/Realmonte/Joppolo Giancaxio (Agrigento) —
  `skip_ssl` opzionale per catene certificato incomplete (Siculiana, Joppolo Giancaxio)
- **`urbi.py`** (nuovo modulo, generalizzato da `catania.py`): **8 comuni** provincia di
  Agrigento (Favara, Raffadali, Ravanusa, Campobello di Licata, Naro, Santa Margherita di
  Belice, San Biagio Platani, Villafranca Sicula)
- **`hspromila.py`** (nuovo modulo, variante Halley ASP.NET): **5 comuni** (Sambuca di Sicilia,
  Santo Stefano Quisquina, Santa Elisabetta, Montallegro, Lucca Sicula) — bug di dedup
  url_fonte scoperto e corretto in fase di test
- **`ribera.py`** (nuovo modulo dedicato, WordPress): 1 comune
- Wiki censimento aggiornata: `docs/wiki/14-censimento-albi.md`
- **384 test verdi, ruff pulito** (erano 322 a inizio PR)

**Copertura finale: 192 comuni attivi ≈ 3.644.530 abitanti, 72,9% della popolazione
siciliana** (era 55% a inizio PR).

### ⚠️ Decisioni per Dom (prima/durante il merge)

1. **Migrazione `talia.db`**: ✅ già applicata (backup `talia.db.bak-20260707`, gitignored).
2. **Default run**: ora include **192 scraper HTTP**. Molto più ampio di quando la PR è stata
   aperta (erano 64): valutare se va bene o se serve una whitelist più conservativa per i run
   automatici futuri (cron) — vedi anche [[pre-cron-checklist]] in memoria.
3. **La maggior parte dei comuni non è ancora mai stata eseguita su `talia.db`**: solo testati
   su DB isolati (`/tmp/test_*.db`). Il primo run reale su `talia.db` con tutti gli scraper
   andrà monitorato (volume, eventuali timeout SSL transitori già osservati su 1-2 comuni Halley).
4. Restano scoperti: **Partinico** (portalepa variante `_full`, mapping colonne da fare),
   **Messina** (bloccata, intervento IT del Comune necessario), 7 comuni piccolissimi della
   provincia di Agrigento (~19.500 abitanti totali, ciascuno su una piattaforma diversa non
   supportata: APKAPPA, Alph@soft, ComuneWeb, Municipium, custom — vedi dettagli e note
   tecniche in `docs/wiki/14-censimento-albi.md` e `docs/cards/TAL-49.md` Tentativo 17).
5. **`notebooks/copertura_scraper_sicilia.ipynb` + `data/comuni_sicilia_confini.geojson`**:
   creati su richiesta (mappa colorata di copertura), ancora non committati — decidere se
   includerli in questa PR o in una successiva.

## Sessione 2026-07-10 — TAL-50: Censimento Palermo + Trapani (E3 estensione)

### Cosa contiene il branch `feat/E3-province-palermo-trapani`

**Fase 1 (censimento) — Completato:**
- Ricerca web sistematica: 77 comuni mancanti PA/TP
- Risultato: **100% con albo online raggiungibile** (nessun gap)
- Distribuzione per piattaforma:
  - **TIER 0 (subito):** 12 comuni su piattaforme già supportate
    - jCityGov: Termini Imerese (26k), Campofelice Roccella (6.9k)
    - portalepa: Partinico (31k), Cefalù (14k), Castellammare (14.6k), Corleone (11k), Capaci (11k), Partanna (10.8k)
    - URBI: Caccamo (8.3k)
    - + 3 comuni già nel registry E3 (Gibellina, Vicari, Lercara Friddi, Campobello di Mazara)
  - **TIER 1 (facile):** 18 comuni su Halley/EGov/APKAPPA varianti
  - **TIER 2 (reverse-eng):** 14 comuni custom/local
  - **TIER 3 (fallback):** 1 comune (Gazzetta Amministrativa)
- CSV: `data/censimento_albi_pa_tp.csv` (77 righe ordinato per popolazione)
- Card TAL-50 con dettagli implementazione futura

**Fase 2 (registry update) — In Progress:**
- [x] Aggiunta 8 comuni TIER 0 a `scripts/run_scrapers.py` (2 jCityGov + 6 portalepa + 1 URBI)
- [x] Validazione: HTTP 200 su 3 comuni campione (Termini Imerese, Partinico, Caccamo) ✅
- [ ] Run test su DB isolato (opzionale, aggiunge confidence)
- [ ] Merge su E3 → PR unificata per review

**Fase 3 (TIER 1 + TIER 2 reverse-eng) — Completato:**
- [x] Analizzato TIER 1 (Halley/EGov/APKAPPA): pattern non completamente generalizzabile → rimandato a TAL-51
- [x] Reverse-engineering TIER 2 (5 comuni custom più grandi): TUTTI richiedono API JS/Playwright → NON fattibili HTTP puro, ROI basso
- [x] Mappa copertura TALIA aggiornata: notebook `copertura_scraper_sicilia.ipynb` + GeoJSON + PNG/HTML interactive

**Copertura finale TAL-50:**
- Pre-merge E3: 192 comuni (~73% popolazione)
- **Post-merge E3 + TAL-50 completo: 200 comuni (~81% popolazione) ← PRONTO ORA**
- Potenziale TIER 1 (se implementato): 218 comuni (~85%) — rimandato a TAL-51
- TIER 2 custom: NON prioritario (36.8k abitanti, alto effort)

### Modifiche non committate

Nessuna (working tree pulito).

## DB attuale

`talia.db`: **65 enti | 78.323 atti** (dopo backfill storico, vedi sotto). I 109 comuni
nuovi di oggi (portalepa/Halley + jCityGov sbloccati) **non sono ancora in `talia.db`**,
solo nel codice registrato in `scripts/run_scrapers.py`.

**Backfill storico completato** (2 lotti lanciati manualmente da Dom in parallelo alla
sessione, 27 comuni jCityGov totali, `--no-stop --max-pagine 500`): entrambi terminati
senza errori, verificato in `scraper_runs`. Alcuni comuni (Bagheria, Giarre, Gravina di
Catania, Salemi, Sant'Agata li Battiati, Caltanissetta) hanno toccato il tetto dei 10.000
atti: potrebbero avere ancora storico oltre il limite, da tenere a mente per un lotto 2.

Nota dati residua: Lentini ha una `data_pub` "0202-06-16" — refuso della fonte (albo),
non del parser. Valutare un guard "anno < 1990 → NULL" in `parse_data_iso` (non ancora fatto).

## 🤝 Istruzioni per la prossima sessione

1. **Se Dom ha già mergiato la PR #8**: verificare che `main` sia aggiornato, poi valutare
   se lanciare il primo run completo con tutti i 161 scraper su `talia.db` (grande, farlo
   a lotti o monitorare attentamente le prime esecuzioni).
2. **Se la PR #8 è ancora aperta**: continua a ricevere commit su questo branch (fix,
   nuove piattaforme) finché non viene mergiata — non aprire branch nuovi per lo stesso
   filone di lavoro (censimento/scraper).
3. Prossimi comuni da censire (non ancora fatti): Favara (URBI Cloud), Partinico (portalepa
   `_full`), e la lista media/piccola in `docs/wiki/14-censimento-albi.md` (~15 comuni,
   piattaforma da scoprire).
4. Vale la pena ripetere lo sweep di dominio (Halley/portalepa) periodicamente: nuovi
   comuni potrebbero attivare l'albo o cambiare piattaforma nel tempo.

### Regole di sempre

- MAI push su main, MAI merge: branch + PR, il merge lo fa Dom (PR #8 è sua da rivedere).
- Fix agli scraper: commit sul branch `feat/E3-censimento-comuni-sicilia` finché
  la PR #8 è aperta (sono la stessa unità di lavoro), poi branch nuovi.
- Ogni tentativo significativo va nella card `docs/cards/TAL-49.md`, sezione 🔬 Tentativi
  (12 tentativi loggati oggi).
- Prima di dichiarare una piattaforma "nuova", verificare contro gli scraper già esistenti
  nel repo (portalepa era etichettato erroneamente "SoluzioniPA" da un agente di ricognizione
  — era in realtà lo stesso codice di `siracusa.py`).
- Validare sempre la funzione di fingerprint di uno sweep contro un caso noto-positivo E
  noto-negativo prima di lanciarlo su scala (il primo sweep Halley falliva silenziosamente
  per un limite di lettura troppo basso sulla risposta HTTP).

## Modifiche non committate

Nessuna (working tree pulito a parte `data/samples/1/`, locale only).
La tabella sotto è lo storico di cosa conteneva l'ultima ondata di commit (2026-07-02/03):

| File | Contenuto |
|------|-----------|
| `scripts/run_scrapers.py` | Palma aggiunta; `--no-stop`; `scraper_runs`; stop-on-known; coverage summary; `--anac-file`; **`--llm-modello`, `--llm-limite`** |
| `src/talia/modulo2_scraping/db.py` | Tabella `scraper_runs`; `inizia_run`, `termina_run`, `ultimo_run_riuscito` |
| `src/talia/modulo2_scraping/fonti/jcitygov.py` | Timeout 30s + 1 retry |
| `src/talia/engine/catena.py` | Engine catena di eventi (TAL-43); pattern AFFIDAMENTO + LIQUIDAZIONE; stato "concluso"; Strategia 4 LLM (Ollama); **TAL-46: strategia 2.5 contenimento, guard-rail gemelli, regex estese, colonna `numero_settoriale`, `reset_procedimenti_da_verificare`** |
| `src/talia/modulo2_scraping/red_flags/catena_revoca.py` | Red flag revoca in catena (TAL-44) — nuovo file |
| `src/talia/modulo2_scraping/red_flags/runner.py` | Aggiunto `revoche_catena`; **parametri LLM passati a `ricostruisci_catene()`** |
| `src/talia/modulo3_dashboard/app.py` | Tab ⛓️ Procedimenti (TAL-45) |
| `tests/test_catena.py` | **41 test** (erano 29) — nuovi: AFFIDAMENTO, LIQUIDAZIONE, LLM fallback, **TAL-46: contenimento caso Palma, revoca cumulativa, guard-rail gemelli, reset** |
| `docs/cards/TAL-46.md` | **Nuova card (Spec-Driven): engine catena v2 — in Review** |
| `tests/red_flags/test_catena_revoca.py` | 6 test red flag revoca |
| `docs/wiki/02-architettura.md` | Pipeline due fasi |
| `docs/wiki/05-red-flags-batch.md` | 6 check PDF + caso studio Palma |
| `docs/cards/BOARD.md` | TAL-42..45 aggiunte in Review |
| `docs/cards/TAL-42..45.md` | Nuove card catena |
| `docs/cards/_TEMPLATE.md` | **Sezioni `## 📋 Spec`, `## ❓ Domande aperte`, `## 🔬 Tentativi`** |
| `docs/cards/TAL-11.md` | **Spec compilata (interfaccia + domande aperte)** |
| `CLAUDE.md` | **Loop di esecuzione; convenzioni Tentativi, Spec/Domande aperte; delega ad agente economico** |

---

## Test scraper 2026-06-28

9 agenti paralleli (uno per capoluogo siciliano). Dettaglio: [`docs/wiki/13-scraper-status.md`](docs/wiki/13-scraper-status.md).

| Comune | Esito | Note |
|--------|-------|------|
| Agrigento | ✅ 224 atti | Playwright installato, funziona |
| Caltanissetta | ✅ 40 atti | OK |
| Catania | ❌ non implementato | URBI/Maggioli (non HCL Domino); HTTP puro fattibile con enumerazione ID |
| Enna | ✅ 40 atti | Portale attivo, bassa frequenza |
| Messina | ⛔ bloccato | FortiGate HTTP 403 + cert scaduto 2023; non risolvibile lato codice (BUG-5) |
| Palermo | ❌ non implementato | SISPI JSP; Playwright obbligatorio; URL: `albopretorio.comune.palermo.it` |
| Ragusa | ✅ 40 atti | OK |
| Siracusa | ✅ 30 atti | OK; mancano test unitari |
| Trapani | ⚠️ 0 atti | `_RE_PANEL` non matcha più l'HTML → BUG-4 |

---

## Bug aperti

Nessuno bloccante. **BUG-6 chiuso il 2026-07-03: non era un bug** — falso positivo
del test Playwright del 28/06, che verificava la tabella con `inner_text()`;
`st.dataframe` renderizza in canvas (glide-data-grid), invisibile all'estrazione
testuale. Screenshot su DB reale conferma il rendering corretto. Dettagli e lezione
per i test UI in [`docs/bugs.md`](docs/bugs.md).

---

## Sessione 2026-07-02 — Cosa è cambiato

### Catena eventi: 81% dei procedimenti sconosciuto risolti

Prima di questa sessione, `ricostruisci_catene()` lasciava 574 procedimenti con `stato_finale = 'sconosciuto'` perché mancavano i pattern per le fasi normali di un procedimento amministrativo.

Aggiunti due pattern in `src/talia/engine/catena.py`:
- **AFFIDAMENTO** → ruolo `aggiudicazione` (es. "affidamento diretto ai sensi", "affidamento del servizio")
- **LIQUIDAZIONE** → ruolo `liquidazione` (es. "liquidazione fattura", "liquidazione sal") → nuovo stato finale **"concluso"**

Risultato: da 574 a ~109 sconosciuto (-81%).

### Strategia 4 — LLM locale (opt-in)

Per i restanti 109, aggiunta classificazione via Ollama HTTP API come Strategia 4 in `ricostruisci_catene()`.

- Opt-in: `--llm-modello llama3.2` (default: skip)
- Graceful degradation: se Ollama non risponde, warning nel log e skip silenzioso
- Tracciabilità: procedimenti classificati via LLM hanno `metodo_individuazione` con suffisso `_llm`
- Limite configurabile: `--llm-limite N` (default 200 per run)

### Processo di lavoro aggiornato

Aggiornati `CLAUDE.md` e `docs/cards/_TEMPLATE.md` con:
- **Loop di esecuzione** formale per card (Spec check → Esecuzione → Bugfix → Refactor → Lint → Doc)
- **`## 🔬 Tentativi`**: log strutturato degli approcci provati (persistente tra sessioni)
- **`## 📋 Spec` + `## ❓ Domande aperte`**: spec compilata prima di toccare codice; se ci sono domande aperte, bloccarsi
- **Delega esplorativa**: per task pesanti, delegare a haiku, consolidare, validare

---

## Prossimi passi

### 0 — Review e merge PR #8 (TAL-49)

Rivedere la PR, decidere su migrazione ISTAT e default run (vedi sopra), mergiare.

### 1 — Approfondimento Palermo e Catania

**Palermo** (`palermo.py`) e **Catania** (`catania.py`) sono già implementati e HTTP puro
(non richiedono Playwright come per Agrigento). Entrambi espongono solo atti in pubblicazione
(~15-30 gg), quindi il primo run su `talia.db` post-merge avrà dati recenti ma no storico.

Verificare da `talia.db` dopo merge:
- Palermo: `SELECT COUNT(*) FROM atti WHERE ente_codice_istat = '082053'`
- Catania: `SELECT COUNT(*) FROM atti WHERE ente_codice_istat = '087003'`

Se i numeri sono bassi (< 100 atti), consider fare un backfill manuale via
`--no-stop --max-pagine 500` su un DB separato per capire quanto storico è
recuperabile.

### 2 — Comuni restanti della provincia di Agrigento (7, molto piccoli)

Caltabellotta, Bivona, Cianciana, Castrofilippo, Burgio, Sant'Angelo Muxaro, Calamonaci:
ciascuno su una piattaforma diversa (APKAPPA, Alph@soft, ComuneWeb, custom, Municipium).
Vedi documentazione dettagliata in `docs/wiki/14-censimento-albi.md` e `docs/cards/TAL-49.md`
(Tentativo 17) per chi vuole riprenderli in futuro.


### 0 — ~~Fix Trapani~~ ✅ FATTO (2026-07-03, branch `fix/BUG-4-trapani-filtro-data`)

**La regex era innocente**: `_RE_PANEL` matchava ancora. La causa era il default
`dataPubblicazioneAl=oggi` — il server e-pal.it esclude gli atti la cui finestra di
pubblicazione termina dopo `al`, cioè proprio quelli in pubblicazione. Fix: `al = oggi+60gg`
(`_MARGINE_FUTURO_GIORNI`), WARNING su 0 atti, 4 test nuovi (23 totali su Trapani).
Run reale: +329 atti. **Nota strutturale**: l'albo espone solo atti in pubblicazione
(~15-30 gg), lo storico non è recuperabile → serve scraping continuo per non perdere atti.
Dettagli in `docs/bugs.md` (BUG-4). **Da fare: mergiare il branch su `main`.**

### 1 — ~~Commit~~ ✅ FATTO (2026-07-03)

Tutto committato, mergiato su `main` e pushato; branch cancellato. BUG-6 chiuso
(falso positivo del test UI — vedi `docs/bugs.md`).

### 2 — ~~Backfill storico Palma di Montechiaro~~ ✅ GIÀ FATTO (2026-06-26)

Il backfill era già stato eseguito il 2026-06-26 (688 inseriti, vedi `scraper_runs`):
la voce "60 atti / backfill da fare" nell'HANDOFF era stantia. Rerun di verifica del
2026-07-03: 748 trovati, 748 duplicati, 0 nuovi → l'albo espone 748 atti totali
(2018-05-11 → 2026-06-05), tutto lo storico disponibile è in DB.

### 3 — ~~Validare la catena sul DB reale~~ ✅ FATTO (2026-07-02, TAL-46)

Il fascicolo Palma (`data/samples/1`) È ricostruibile dal DB, ma il fuzzy v1 aveva
fuso 3 selezioni distinte in una mega-catena (proc. 674). Risolto con TAL-46:
strategia 2.5 (contenimento oggetto) + guard-rail gemelli. Migrazione applicata
a `talia.db`: reset di 523 procedimenti fuzzy + rerun → ora 646 da CIG, 10 da
contenimento (alta confidenza, incluse le 3 catene Palma: proc. 1170/1171/1172),
521 fuzzy da_verificare. Dettagli in `docs/cards/TAL-46.md` (sezione Tentativi).

### 4 — TAL-14: check GDPR + numero atto incoerente

Card in Review. Casi concreti trovati su fascicolo Palma:
- Bozza graduatoria divulgata prima dell'ufficializzazione → `gdpr_breach_non_notificato`
- Revoca cita "N. 33/2025" ma l'atto in DB è "N. 35/2025" → `numero_atto_incoerente`

### 5 — ~~Fase 2 pipeline: PDF on-demand (MVP)~~ ✅ AVVIATA (2026-07-06, TAL-47)

Downloader jCityGov funzionante e validato (vedi sezione sessione 2026-07-05/06).
Restano: selezione automatica catene, estrazione testo, check sui PDF, altre piattaforme.

### 6 — ANAC

WAF blocca urllib (TLS fingerprinting). Workaround attuale: `--anac-file <csv>`.
Alternativa: Playwright headless.

### 7 — Messina: bloccato, non azione immediata

FortiGate HTTP 403 + certificato scaduto 2023-06-27. `skip_ssl=True` non aggira il 403.
Richiede intervento IT del Comune. Vedi BUG-5 in `docs/bugs.md`.

## Sessione 2026-07-10 — TAL-48: red flag riapertura dopo revoca/annullamento (MVP)

**Fatto:**
- Nuovo modulo `src/talia/modulo2_scraping/red_flags/riapertura_revoca.py`:
  - `rileva_riapertura_dopo_revoca(conn, soglia_similarita=0.5)`: query procedimenti
    revocati/annullati, ricerca atti stesso ente con oggetto simile
  - Tokenizzazione normalizzata: stopword dominio, regex `\b\w+\b`, ≥3 char
  - Similarità Jaccard su token
  - Guardia anti-periodicità: ≥3 atti simili nel tempo → skip (routine admin)
- Integrazione runner: `_salva_riapertura_dopo_revoca()`, nuovo campo RapportoRunner
- Test: 12 nuovi (tokenizzazione, Jaccard, 4 casi reali: Palma 656, Ragusa 1079, Enna 924 periodico, edge case)
- **320 test verdi totali** (312 base + 8 suite nuove)
- 2 commit: feat TAL-48 MVP + doc update (BOARD, card)
- Spec: due domande aperte rimangono aperte per dom (conferma soglia, scopo PDF confronto)

**Branch:** `feat/TAL-48-riapertura-dopo-revoca` — non ancora pushato (locale)

**Prossimi passi:**
1. Push branch e apertura PR (opzionale, dipende da necessità dom)
2. Integrazione con pdf_download: scaricare PDF di entrambi i bandi (rivocato + riapertura)
3. Confronto testuale bando originale vs rilanciato (richiede estrazione testo dai PDF, card futura)
4. Test su fascicolo Palma reale con DB completo (dopo merge PR #8)
5. Calibrazione soglia Jaccard dopo run completo (domanda aperta 1)

---

## Note permanenti

- `data/samples/1/` — fascicoli reali locali, **mai committare**
- `talia.db` — **mai committare**
- Architettura E2: [`docs/handoff/epica_E2.md`](docs/handoff/epica_E2.md)
- Stato scraper: [`docs/wiki/13-scraper-status.md`](docs/wiki/13-scraper-status.md)
- Bug aperti: [`docs/bugs.md`](docs/bugs.md)
