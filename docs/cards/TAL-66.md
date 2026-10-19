# TAL-66 — Run giornaliero automatico degli scraper (launchd) + riepilogo esiti

- **Epica:** E2 — Scraping pilota
- **Ruolo:** ⚙️ OPS
- **Priorità:** P0 (perdita di dati in corso)
- **Stato:** Review
- **Branch:** `feat/TAL-66-run-giornaliero-aggregati`

## 🎯 Obiettivo

Rendere continuo lo scraping, oggi lanciato a mano, e accorgersi
automaticamente quando qualcosa si rompe.

## 📚 Contesto — perché è P0 e non rimandabile

Stato misurato all'apertura della card (2026-08-18) su `talia.db` reale:

| Data run | Scraper | Atti inseriti |
|----------|---------|---------------|
| 2026-08-06 | 20 | 3.755 |
| 2026-08-05 | 289 | 17.131 |
| 2026-07-25 | 204 | 6.427 |
| 2026-07-20 | 204 | 6.071 |
| 2026-07-14 | 204 | 5.793 |

**L'ultimo run è del 2026-08-06: 12 giorni prima dell'apertura della card.**
La cadenza reale è "quando qualcuno se ne ricorda" (ogni 5-11 giorni).

Il problema non è l'estetica della cadenza: la maggior parte degli scraper
legge l'**Albo Pretorio**, che per legge espone solo gli atti *in
pubblicazione* — una finestra di 15-30 giorni (CLAUDE.md documenta il caso
per Trapani, Palermo, Catania, Nicosia; TAL-62 ha misurato che il 77-86%
degli atti già raccolti ha superato `data_scadenza`). Un atto pubblicato il
2026-08-07 con finestra di 15 giorni **non è più raccoglibile dall'albo dal
2026-08-22**. Ogni giorno di ritardo è perdita definitiva di copertura, non
recuperabile con un backfill.

Amministrazione Trasparente (TAL-62/TAL-64) mitigherebbe il problema per le
piattaforme dove è implementata, ma è ancora bloccata da due decisioni aperte
e non collegata al run: non sostituisce la continuità dello scraping.

## ❓ Domande aperte

- [x] **GitHub Actions o locale?** → locale. Il blocco Akamai sui runner
      GitHub (87% di fallimenti su portalepa, misurato il 2026-07-12) e il
      vincolo di budget zero escludono sia la CI sia una VM. Decisione già
      presa e documentata, questa card la applica invece di riaprirla.
- [x] **Con quale meccanismo?** → `launchd`, stesso schema di Pathosphere.
      `StartCalendarInterval` (non `StartInterval`): se il Mac è spento
      all'ora prevista, launchd recupera il run al risveglio invece di
      slittare in avanti in modo imprevedibile.

## 📋 Spec

1. **`scripts/run_daily.sh`** — wrapper del run:
   - **lock** (`mkdir` atomico + PID): un run completo dura ~4h40m su 260
     scraper (misurato il 2026-08-05, 18:37→23:17); due run sovrapposti si
     contenderebbero lo stesso SQLite.
   - **`caffeinate -i`**: il Mac non deve addormentarsi a metà run.
   - **backup del DB** prima di scrivere, via `sqlite3 .backup` (consistente
     in modalità WAL, a differenza di `cp`), con rotazione a 7 copie.
   - **rotazione dei log** a 30 file.
   - **notifica macOS** (`osascript`, best-effort) se il run ha problemi.
2. **`scripts/setup_launchd.sh`** — installa/rimuove/interroga l'agente
   `com.talia.scrapers` (`--ora`, `--minuto`, `--status`, `--uninstall`).
3. **`src/talia/modulo2_scraping/run_report.py`** + **`scripts/report_run.py`**
   — riepilogo dello stato dei run, con exit code non-zero se ci sono
   problemi. Tre condizioni tenute **distinte**, perché hanno cause diverse:
   - **fallito**: eccezione registrata in `scraper_runs.errore`;
   - **muto**: run completato senza errori ma con 0 atti trovati — la
     fragilità nota di CLAUDE.md ("fallimento silenzioso a 0 atti"), che
     nessun exit code intercetterebbe;
   - **fermo**: scraper attivo nel registro ma non eseguito da N giorni — la
     condizione che ha reso possibile questo stesso ritardo di 12 giorni.

## ✅ Task

- [x] `run_report.py` + 19 test
- [x] `scripts/report_run.py` (exit 0/1/2)
- [x] `scripts/run_daily.sh` (lock, caffeinate, backup, rotazione, notifica)
- [x] `scripts/setup_launchd.sh` (install/status/uninstall)
- [x] Fix collaterale: `scraper_runs.errore` conservava i **primi** 500
      caratteri del traceback, cioè quasi sempre senza la riga che nomina
      l'eccezione — il riepilogo mostrava `esito = fn(` invece di
      `ConnectionRefusedError: ...`. Ora l'eccezione è messa in testa prima
      di troncare (`_errore_db` in `run_scrapers.py`), e `sintesi_errore()`
      sa leggere anche il formato vecchio già in DB.
- [x] Agente installato e caricato (03:30 ora locale)
- [x] Run reale di recupero lanciato il 2026-08-18
- [x] `backups/` e `.run_daily.lock/` in `.gitignore`
- [x] Wiki: [`15-run-automatico.md`](../wiki/15-run-automatico.md)

## 🔬 Tentativi

### 2026-08-18 — Tentativo 1
**Approccio:** riuso dello schema launchd di Pathosphere
(`scripts/setup_launchd.sh`), adattato a TALIA.
**Esito:** ⚠️ parziale — lo schema va bene, due scelte del plist di
Pathosphere no.
**Appreso:** Pathosphere usa `StartInterval` **insieme** a `KeepAlive true`:
con un job che termina (non un demone) launchd lo rilancia immediatamente in
loop. Su un run da 4-5h che colpisce 260 server comunali sarebbe stato un
martellamento continuo. Qui: `StartCalendarInterval` + `KeepAlive false` +
`RunAtLoad false`, più `Nice 5`/`ProcessType Background` perché il run può
partire mentre qualcuno sta usando il Mac (recupero di un run saltato).

### 2026-08-18 — Tentativo 2 (buco trovato nella soluzione stessa)
**Approccio:** verifica di *quali* scraper girerebbero davvero nel run
notturno, invece di assumere che "il default" bastasse.
**Esito:** ❌ il default escludeva 3 comuni, tra cui un capoluogo.
**Appreso:** `agrigento`, `pachino` e `barrafranca` sono `escluso_default`
nel registro perché richiedono Playwright ed erano lenti *per un run
manuale* — una motivazione che nel contesto di un run notturno non vale più,
mentre la conseguenza (perdere per sempre gli atti di Agrigento quando escono
dalla finestra dell'albo) è esattamente il problema che questa card risolve.
Aggiunto `--extra-scrapers` a `run_scrapers.py` (aggiunge alla lista invece
di sostituirla come `--scrapers`) e i tre al run notturno. Costo reale
misurato: Pachino 9s, non i ~3 min stimati in CLAUDE.md. `anac` resta fuori
perché richiede `--anac-file`.

### 2026-08-18 — Tentativo 3
**Approccio:** primo `report_run.py` sul DB reale.
**Esito:** ⚠️ parziale — output corretto ma illeggibile.
**Appreso:** due difetti concreti trovati solo guardando l'output vero, non
i test: (1) quando *nessun* run gira da giorni la sezione "fermi" elenca
tutti e 265 gli scraper e nasconde le due sezioni azionabili (3 falliti, 2
muti) → cap a 15 voci per sezione; (2) le righe dei falliti mostravano una
riga di codice a caso invece dell'eccezione, per il troncamento in testa del
traceback → vedi Task sopra.
