# 15 — Run automatico degli scraper

> Card di riferimento: [TAL-66](../cards/TAL-66.md).

## Perché in locale e non in CI

Gli scraper girano sulla **macchina locale**, non su GitHub Actions. Non è una
scelta di comodità:

- il WAF Akamai che protegge la piattaforma *portalepa* blocca gli IP/ASN dei
  runner GitHub (Azure) — 87% di fallimenti misurato il 2026-07-12, non
  risolvibile lato codice;
- una VM (Oracle Always Free, AWS, Azure) violerebbe il vincolo di budget ≈ 0
  o aggiungerebbe infrastruttura da mantenere.

Conseguenza operativa: **se il Mac è spento, lo scraping non gira.** launchd
recupera il run al risveglio, ma un Mac spento per due settimane produce lo
stesso buco di dati che questa automazione serve a evitare.

## Perché la continuità è critica

Quasi tutti gli scraper leggono l'**Albo Pretorio**, che per legge espone solo
gli atti *in pubblicazione*: una finestra di 15-30 giorni. Un atto che esce
dalla finestra non è più raccoglibile da lì — **nessun backfill lo recupera**.
Un ritardo di due settimane non è "dati in ritardo": è copertura persa per
sempre.

(La sezione *Amministrazione Trasparente*, ritenzione pluriennale, è la via
d'uscita strutturale — vedi [TAL-62](../cards/TAL-62.md) — ma non è ancora
collegata al run automatico.)

## Come si installa

```bash
./scripts/setup_launchd.sh                    # ogni giorno alle 03:30
./scripts/setup_launchd.sh --ora 5 --minuto 0 # altro orario
./scripts/setup_launchd.sh --status           # stato + ultimi log
./scripts/setup_launchd.sh --uninstall        # rimuove l'agente
```

Crea `~/Library/LaunchAgents/com.talia.scrapers.plist`, che lancia
`scripts/run_daily.sh`.

Scelte del plist, e perché:

| Chiave | Valore | Motivo |
|--------|--------|--------|
| `StartCalendarInterval` | 03:30 | se il Mac è spento a quell'ora, launchd recupera il run al risveglio; con `StartInterval` il conteggio riparte da zero ad ogni avvio |
| `KeepAlive` | `false` | il run **termina** (4-5h): con `KeepAlive true` launchd lo rilancerebbe in loop, martellando 260 server comunali |
| `RunAtLoad` | `false` | installare l'agente non deve far partire un run di 5h a sorpresa |
| `Nice` / `ProcessType` | 5 / `Background` | un run recuperato può partire mentre qualcuno sta usando il Mac |

## Cosa fa `run_daily.sh`

1. **Lock** (`mkdir` atomico + PID, con riconoscimento del lock orfano): un
   run dura ~4h40m su 260 scraper — due run sovrapposti si contenderebbero lo
   stesso SQLite.
2. **Backup del DB** in `backups/talia.db.YYYYMMDD` via `sqlite3 .backup`
   (consistente in WAL, a differenza di `cp`), rotazione a 7 copie.
3. **`caffeinate -i python scripts/run_scrapers.py "$@"`** — gli argomenti
   passati allo script arrivano al runner, più
   `--extra-scrapers agrigento pachino barrafranca`.

   Quei tre sono `escluso_default` nel registro perché richiedono Playwright
   ed erano lenti per un run manuale. In un run notturno il costo è
   irrilevante (misurato: Pachino 9s, non i ~3 min temuti), mentre escluderli
   significherebbe perdere **per sempre** gli atti di un capoluogo quando
   escono dalla finestra di pubblicazione — lo stesso problema che il run
   automatico esiste per risolvere. Modificabile con
   `TALIA_EXTRA_SCRAPERS="..."` (o `""` se Playwright non è installato).
   `anac` resta fuori: richiede `--anac-file`.
4. **`scripts/report_run.py`** — riepilogo in `logs/ultimo_report.md`.
5. **Rotazione** log (30 file) e backup (7 copie).
6. **Notifica macOS** se qualcosa è andato storto.

Exit code: `0` tutto ok · `1` problemi rilevati · `2` lock occupato.

Esecuzione manuale, identica a quella schedulata:

```bash
./scripts/run_daily.sh                          # run completo
./scripts/run_daily.sh --scrapers siracusa --max-pagine 2
launchctl kickstart -k gui/$(id -u)/com.talia.scrapers   # via launchd
```

## Il riepilogo: tre stati distinti

`scripts/report_run.py` (e la tab 📅 Aggregati della dashboard) distinguono
tre condizioni che hanno cause diverse e vanno lette diversamente:

| Stato | Significato | Causa tipica |
|-------|-------------|--------------|
| ❌ **fallito** | eccezione in `scraper_runs.errore` | rete, host giù, cert scaduto |
| 🔇 **muto** | run completato, **0 atti trovati**, nessun errore | HTML del portale cambiato, regex che non aggancia più nulla — nessun exit code se ne accorgerebbe |
| 🕒 **fermo** | attivo nel registro, non eseguito da N giorni | il Mac era spento, l'agente non è installato, il lock è rimasto appeso |

Lo stato *muto* è la fragilità nota già elencata in `CLAUDE.md` ("fallimento
silenzioso a 0 atti"): uno scraper rotto continua a "riuscire" per settimane.

Il report segnala inoltre in modo esplicito quando l'ultimo run è più vecchio
di 15 giorni, con il motivo (finestra di pubblicazione dell'albo superata).

## Dove guardare quando qualcosa non torna

```bash
./scripts/setup_launchd.sh --status     # l'agente è caricato? ultimo exit code?
cat logs/ultimo_report.md               # cosa è fallito nell'ultimo run
ls -1t logs/run_daily_*.log | head -3   # log completi, più recenti in cima
python scripts/report_run.py            # riepilogo on-demand, senza rilanciare nulla
```

In dashboard: tab **📅 Aggregati** → sezione *Stato degli scraper*, e il
grafico *Documenti ingeriti per giorno* (i giorni a zero sono espliciti: un
buco nel grafico è un run mancato).
