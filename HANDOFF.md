# HANDOFF.md — Stato sessione

> Aggiornato: 2026-07-11 (Refactor: Registro unificato scraper — code review multi-angolo eseguita, bug corretti, 39 comuni recuperati)

---

## Branch attivo (priorità)

`feat/config-scraper-registro` — **Refactor: Registro unificato scraper + health-check**,
parte da `main` con PR #8/#9/#10 già mergiate (censimento E3, TAL-48, TAL-50 Palermo/Trapani).
Piano: `.claude/plans/smooth-wibbling-teapot.md`.

**Tutte e 5 le PR del piano sono completate e committate su questo branch, in attesa di
review complessiva da Dom prima del merge** (nessun push, main resta protetto):

1. `6027328` — **PR1**: `data/registro_scraper.csv` (206 righe consolidate) + `registry.py`
   loader + validazione fail-fast + 15 test.
2. `94d0bb6` — **PR2**: parametrizzazione dei 6 moduli monocomune (palermo, catania, trapani,
   siracusa, ribera, agrigento) — `base_url` (+ `qs_base`/`ente_mittente` per catania)
   propagati a `scarica_atti()`/`prepara_ente()` e helper interni. Default = comportamento
   invariato. 7 test di parametrizzazione.
3. `72da866` — **PR3**: `scripts/run_scrapers.py` legge dal registro per tutti gli 11 moduli
   (5 famiglie parametriche + 6 monocomune) via `costruisci_scrapers(registro)` uniforme
   (`_FACTORY_PER_MODULO`). Rimosse le 5 liste hardcoded + `_HALLEY_SKIP_SSL` (ora
   `entry.skip_ssl`). **Verificato lossless**: `_SCRAPERS`/`_SCRAPERS_DEFAULT` prima/dopo
   sono insiemi identici (205 scraper, 203 di default). Rimossi i CSV di censimento
   ridondanti, wiki 14 aggiornata. 12 nuovi test.
4. `075a6f6` — **PR4**: schema DB `enti` esteso (`modulo`/`url_base`/`stato_scraper`) via
   migrazione lazy `_estendi_enti()` (compatibile con `talia.db` locali esistenti).
   `sincronizza_enti_da_registro()` in `registry.py`, chiamata in `main()`. `upsert_ente`
   usa `COALESCE` sulle 3 colonne nuove per non azzerarle sui run scraper "vecchio stile".
   Verificato su DB reale: 205 righe registro → 199 enti distinti (comuni con più endpoint
   scraper collassano sullo stesso `codice_istat`). 9 nuovi test.
5. `693bcbe` — **PR5**: `scripts/health_check_registro.py` (stdlib puro, HEAD+fallback GET,
   `ThreadPoolExecutor`, exit code non-zero solo su righe attivo/escluso_default fallite) +
   `.github/workflows/health-check.yml` (schedule lunedì 05:00 UTC + `workflow_dispatch`,
   notifica via issue GitHub persistente label `health-check`). Verificato su rete reale
   (7 comuni campione OK, Messina bloccata fallisce come atteso senza alzare l'exit code).
   20 nuovi test.

**Totale sessione: 458 test verdi (erano 411 a inizio sessione), ruff pulito su tutto il
codice nuovo/modificato** (gli 8 errori E501 residui in `tests/test_registry.py` sono
preesistenti da PR1, non introdotti in questa sessione).

### Code review multi-angolo (2026-07-11) — 8 findings, bug corretti

Eseguita `/code-review` (8 angolazioni parallele + verifica 1-voto) sull'intero diff
`main...HEAD`. 6 findings confermati, 2 plausibili (bassa severità, non corretti — vedi
sotto). Bug corretti in un commit successivo alle 5 PR:

1. **`trapani.py`**: `_parse_page()` ignorava `base_url` e costruiva `url_fonte` sempre
   dalla costante di modulo — bug di correttezza reale introdotto in PR2 (violava
   l'esplicabilità: un `base_url` custom avrebbe prodotto link alla fonte sbagliati).
   Fix: `base_url` propagato a `_parse_page`. 2 nuovi test.
2. **`db.py::upsert_ente`**: `provincia`/`popolazione`/`sito_web` non erano protette da
   `COALESCE` come `modulo`/`url_base`/`stato_scraper` — ogni run di `run_scrapers.py`
   (che sincronizza *tutto* il registro ad ogni invocazione) azzerava silenziosamente la
   provincia dei comuni non inclusi nel run corrente (205/206 righe hanno provincia vuota
   nel CSV). Fix: `COALESCE` esteso a tutti i campi opzionali. 2 nuovi test.
3. **`registry.py::_row_to_entry`**: `stato` non applicava il default `"attivo"` su una
   cella CSV presente-ma-vuota (solo su chiave mancante) — una riga malformata sarebbe
   silenziosamente sparita da tutto lo scraping senza errore di validazione. Fix: pattern
   `or` coerente con gli altri campi. 1 nuovo test.
4. **`registry.py::valida_registro`**: nessuna validazione che `qs_base`/`ente_mittente`
   fossero *presenti* per righe catania/urbi attive (solo che fossero assenti altrove) —
   gap che avrebbe prodotto un URL con `?None` a runtime. Fix: nuovo controllo + aggiunto
   `modulo="pending"` come pseudo-modulo valido (serviva per il recupero dei 39 comuni,
   vedi sotto). 4 nuovi test.

**Sistemati anche i 3 findings non bloccanti** (su richiesta esplicita di Dom):

5. **`run_scrapers.py`**: `_REGISTRO`/`_SCRAPERS` non si costruiscono più a import
   time — nuova funzione `_registro_e_scrapers()` (`functools.lru_cache`) chiamata
   lazy da `_parse_args()`/`main()`. Un CSV malformato fallisce solo all'uso reale
   della CLI, non ad ogni import del modulo (es. dai test). Import verificato
   ~istantaneo (niente parsing), prima chiamata reale ~3ms.
6. **ANAC centralizzato**: era special-casato come stringa letterale in 6 punti
   sparsi tra `registry.py` e `run_scrapers.py`. Ora un'unica costante nominata
   `registry.MODULI_SENZA_ENTE = frozenset({"anac"})`; in `run_scrapers.py` ANAC
   è dispatchato uniformemente via `_FACTORY_PER_MODULO` come ogni altro modulo
   (rimossi sia il seed hardcoded `{"anac": _run_anac}` sia lo skip esplicito nel
   loop) — **verificato lossless** (206 scraper prima e dopo).
7. **`db.py`**: aggiunta `azzera_info_scraper(conn, codice_istat)` — via esplicita
   per azzerare `modulo`/`url_base`/`stato_scraper` (impossibile tramite
   `upsert_ente` dopo il fix COALESCE del punto 2). Non chiamata automaticamente
   (nessuna riconciliazione automatica dei comuni tolti dal registro — scelta
   deliberata, fuori scope).

6 nuovi test per questi 3 fix (473 test totali verdi, erano 467).

### Recupero 39 comuni censiti

La review ha anche scoperto che la rimozione dei CSV di censimento (PR3) aveva perso i
dati (piattaforma/URL) di 39 comuni PA/TP censiti in TAL-50 senza scraper — il piano
originale prevedeva di migrarli come righe `stato=pending`, passo non eseguito. Recuperati
da `git show main:data/censimento_albi_pa_tp.csv` e riaggiunti al registro con
`modulo=pending`. Di questi, **Altavilla Milicia** (etichettata "HyperSIC" nel censimento)
usa in realtà lo stesso URL pattern già gestito da `hspromila.py` — verificato dal vivo
(102 atti reali) e attivato subito (`modulo=hspromila`, `stato=attivo`), zero nuovo codice.
Dettagli in `docs/wiki/14-censimento-albi.md`.

**Registro dopo il recupero: 245 righe (204 attive di default, 38 pending, 2 escluso_default,
1 bloccato).** 467 test totali verdi.

Working tree pulito (tutto committato). Nessun dato nominativo committato.

### Prossimo passo

Review complessiva da parte di Dom (richiesta esplicitamente: "facciamo review alla fine
di tutto" → eseguita `/code-review`, bug corretti). Dopo l'approvazione: push del branch +
apertura PR su GitHub, oppure squash/riorganizzazione dei commit se Dom preferisce una
history diversa — da concordare in fase di review, non ancora deciso.

## DB attuale

`talia.db` locale (gitignored), non toccato da questa sessione (refactor PR1-3 è solo
configurazione/codice, zero scraping reale eseguito). Le sezioni sotto (backfill,
copertura) sono storico di sessioni precedenti (PR #8/#9/#10, già mergiate in main)
e non sono state riverificate in questa sessione.

## 🤝 Istruzioni per la prossima sessione

1. Se questa sessione (refactor registro) è stata approvata e mergiata: valutare se
   lanciare un run completo con `_SCRAPERS_DEFAULT` (203 scraper) su `talia.db` — non
   ancora fatto dopo il refactor, anche se il set di scraper è identico a prima
   (verificato lossless, vedi sopra).
2. Continua la sequenza PR4 (schema DB `enti` esteso) → PR5 (health-check CI) del piano
   `Registro unificato scraper + health-check automatico`.
3. Vale la pena ripetere lo sweep di dominio (Halley/portalepa) periodicamente: nuovi
   comuni potrebbero attivare l'albo o cambiare piattaforma nel tempo.

### Regole di sempre

- MAI push su main, MAI merge: branch + PR, il merge lo conferma sempre Dom.
- Ogni tentativo significativo va nella card di riferimento, sezione 🔬 Tentativi.
- Prima di dichiarare una piattaforma "nuova", verificare contro gli scraper già esistenti
  nel repo (portalepa era etichettato erroneamente "SoluzioniPA" da un agente di ricognizione
  — era in realtà lo stesso codice di `siracusa.py`).
- Validare sempre la funzione di fingerprint di uno sweep contro un caso noto-positivo E
  noto-negativo prima di lanciarlo su scala (il primo sweep Halley falliva silenziosamente
  per un limite di lettura troppo basso sulla risposta HTTP).

## Storico modifiche (sessioni precedenti, già mergiate in main)

La tabella sotto è lo storico di cosa conteneva un'ondata di commit precedente (2026-07-02/03):

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

### 0 — ~~Review e merge PR #8 (TAL-49)~~ ✅ FATTO — mergiata (#8), insieme a #9 (TAL-48) e #10 (TAL-50)

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
