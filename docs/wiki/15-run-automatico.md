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

   Ogni scraper ha un **tetto di tempo** (default 20 minuti, `--timeout-scraper`,
   TAL-72): oltre, l'orchestratore lo interrompe e passa al successivo. Senza
   tetto il run del 22/08/2026 era finito il 24/08 e il lock aveva fatto saltare
   due notti — un singolo host appeso teneva in ostaggio tutti gli altri.
   Dettagli nella sezione *Il tetto di tempo per scraper* più sotto.
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

## Il tetto di tempo per scraper

Il run è sequenziale, quindi la sua durata è la somma delle durate degli
scraper — e quella somma era dominata da pochissimi. Misurato il 01/09/2026 su
`scraper_runs`: ~10 scraper su 266 facevano il 98% dei 53.011s, e quattro dei
sette peggiori spendevano ore in retry e timeout di socket per restituire
**zero** atti. I timeout per singola richiesta c'erano già; mancava un tetto
sulla loro somma.

- **Meccanismo:** `SIGALRM` (`src/talia/modulo2_scraping/tetto_tempo.py`).
  Interrompe anche una `recv` bloccata o la `sleep` di un backoff. L'eccezione
  deriva da `BaseException`, così i `except Exception` di retry dentro gli
  scraper non la intercettano.
- **Nessun lavoro perso:** `inserisci_atto` committa atto per atto; gli atti
  salvati prima dello stop restano e vengono contati in `scraper_runs.n_inseriti`.
- **Registrazione distinta:** `scraper_runs.errore` inizia con
  `TettoTempoSuperato` e riporta *dove* lo scraper era fermo (i tre frame più
  interni), che è l'informazione utile per capire perché.
- **Non è un fallimento del run:** non alza l'exit code di `run_scrapers.py` né
  quello di `report_run.py`, quindi non fa scattare la notifica. Un host lento
  interrotto ogni notte non deve far suonare l'allarme ogni notte.
- **Default 1200s**, scelto sulle durate misurate: gli scraper sani stanno
  sotto i 3 minuti (~35s di media). Nel caso peggiore, con una decina di host
  appesi, il run resta sulle ~6 ore invece delle 14,7 misurate.
- **Backfill esente:** con `--no-stop` il tetto è disattivato, salvo valore
  esplicito. `--timeout-scraper 0` lo disattiva sempre.

Se uno scraper viene interrotto **mentre stava ancora inserendo atti**, il
report lo marca: è il segnale che il tetto è troppo basso per quel comune, non
che lo scraper è rotto.

## Il ripasso dei falliti transitori (TAL-75)

A fine loop, gli scraper falliti per cause di rete **transitorie** (timeout,
handshake TLS in timeout, connessione chiusa o resettata, risposta troncata,
DNS) vengono ritentati **una volta**. Nella settimana 12-19/10/2026 Catania è
fallita 3 volte su 8 e Palermo e Trapani 2 su 8, sempre nelle stesse notti e
sempre per timeout, mentre di norma finiscono in 2 minuti: ore dopo, l'host
risponde quasi sempre.

- Non si ritentano certificati non validi né risposte HTTP 4xx/5xx: si
  ripresenterebbero identici (`run_report.e_transitorio()`).
- Budget complessivo `--budget-ripasso` (default 3600s, `0` = disattivato):
  in una notte di rete degradata decine di scraper possono andare in timeout,
  e ritentarli tutti col tetto da 20 minuti riporterebbe il run oltre le 24h.
- Il tentativo scrive una sua riga in `scraper_runs`; il report legge l'ultima,
  quindi un recupero risulta OK. Più righe per lo stesso scraper nello stesso
  giorno = recupero al ripasso.

## Il riepilogo: stati distinti

`scripts/report_run.py` (e la tab 📅 Aggregati della dashboard) distinguono
condizioni che hanno cause diverse e vanno lette diversamente:

| Stato | Significato | Causa tipica |
|-------|-------------|--------------|
| ❌ **fallito** | eccezione in `scraper_runs.errore` | rete, host giù, cert scaduto |
| 🔇 **muto** | run completato, **0 atti trovati**, nessun errore | HTML del portale cambiato, regex che non aggancia più nulla — nessun exit code se ne accorgerebbe |
| 🕒 **fermo** | attivo nel registro, non eseguito da N giorni | il Mac era spento, l'agente non è installato, il lock è rimasto appeso |
| ⏱️ **interrotto** | fermato dal tetto di tempo, non da un'eccezione (informativo) | host lento o semi-morto; se stava inserendo, tetto troppo basso |

Lo stato *muto* è la fragilità nota già elencata in `CLAUDE.md` ("fallimento
silenzioso a 0 atti"): uno scraper rotto continua a "riuscire" per settimane.
È così che è stato trovato Caccamo, fermo a 0 atti dal 2026-07-14 senza mai
un errore ([TAL-68](../cards/TAL-68.md)).

**Cosa *non* viene segnalato, di proposito:** gli scraper non previsti dal run
(`bloccato` nel registro come Corleone e Messina, o esclusi dal default come
ANAC che richiede `--anac-file`). Il loro ultimo run è vecchio e fallito *per
definizione*: contarli farebbe scattare la notifica ogni singola notte, e una
notifica che suona sempre è una notifica che si impara a ignorare. Compaiono
come nota informativa in fondo al report, senza incidere sull'exit code.

Gli extra del run notturno (`agrigento`, `pachino`, `barrafranca`) vanno
passati **anche** a `report_run.py` (`--extra-scrapers`, già fatto da
`run_daily.sh`): altrimenti risulterebbero "non previsti" e i loro fallimenti
non verrebbero mai segnalati.

Il report segnala inoltre in modo esplicito quando l'ultimo run è più vecchio
di 15 giorni, con il motivo (finestra di pubblicazione dell'albo superata).

### Fallimento di massa con causa unica

Il 31/08/2026 232 scraper su 266 sono falliti, 225 con lo stesso
`[Errno 8] nodename nor servname provided`: un guasto DNS della macchina, non
225 portali rotti. Il report di allora elencava 15 righe a caso, indistinguibile
da una giornata con qualche rottura vera.

Ora, se una sola causa spiega almeno il **60% dei falliti** (e almeno 10
scraper), il report lo dice in testa, specifica se la causa è quasi certamente
locale (DNS, rete non raggiungibile) e nella sezione *Falliti per altre cause*
elenca solo le rotture che restano da guardare una a una. Le cause sono
raggruppate per famiglia (DNS, rete, SSL/TLS, timeout, connessione rifiutata)
sulla riga dell'eccezione, così lo stesso guasto non appare come due cause
diverse tra macOS e Linux. La giornata resta un problema (exit code non-zero).

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
