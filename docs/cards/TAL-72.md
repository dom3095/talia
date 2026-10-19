# TAL-72 — Il run notturno supera le 24h e fa saltare i giorni successivi

- **Epica:** E2 — Scraping pilota
- **Ruolo:** ⚙️ OPS + 🕷️ SCR
- **Priorità:** P0
- **Stato:** Review (codice + test; manca la misura sul run reale)
- **Branch:** `feat/TAL-72-tetto-tempo-scraper`

## 🎯 Obiettivo

Il run notturno deve finire entro poche ore in modo prevedibile, così che il
trigger delle 03:30 del giorno dopo trovi il lock libero: nessun host lento può
tenere in ostaggio l'intero run, e un fallimento di massa con causa unica (DNS,
rete) è riconoscibile a colpo d'occhio invece di essere sepolto in 232 righe di
errore.

## 📋 Spec

### Il problema, misurato

Dati da `scraper_runs` su `talia.db` reale (2026-09-02).

**1. Durata oltre le 24h → giorni saltati.** Il run del 01/09 ha scrapato
01:45→16:28 UTC (14,7h) più ~2h di red flags. Peggio prima:

| run avviato | scraping finito | esito |
|---|---|---|
| 2026-08-22 03:03 | 2026-08-24 20:22 | **23 e 24 agosto saltati** |
| 2026-08-27 02:17 | 2026-08-28 11:00 | **28 agosto saltato** |

Il lock di `run_daily.sh` ha funzionato come progettato (niente due run
concorrenti sullo stesso SQLite). Il difetto non è il lock: è che un run duri
più del suo intervallo. Ogni giorno saltato è copertura persa in modo
definitivo — l'Albo Pretorio espone 15-30 giorni.

**2. ~10 scraper su 266 fanno il 98% del tempo.** Somma delle durate dei 266 run
del 01/09: **53.011s**. I peggiori:

| scraper | durata | atti trovati |
|---|---|---|
| `adrano` | 11.566s (3h12m) | 32 |
| `baucina` | 7.293s | 0 (TimeoutError) |
| `catania` | 6.782s | 0 (TimeoutError) |
| `condro` | 4.976s | 0 (handshake SSL) |
| `acibonaccorsi` | 4.901s | 30 |
| `cammarata` | 4.654s | 33 |
| `barcellonapg` | 3.682s | 0 (TimeoutError) |

Quattro dei sette hanno speso ore per **restituire zero atti**: il tempo è finito
in retry e timeout di socket, non in lavoro utile. I timeout per singola
richiesta esistono già negli scraper; quello che manca è un tetto sul **totale**
di uno scraper, che è la somma di tutte le sue richieste e dei suoi retry.

**3. Il 31/08 è stato perso quasi per intero senza allarme.** 232 scraper su 266
in errore, di cui **225 con lo stesso `URLError [Errno 8] nodename nor servname
provided`** — guasto DNS locale, non 225 portali rotti simultaneamente. 115 atti
inseriti in tutta la giornata. Il report ha elencato le solite prime N righe,
indistinguibili da una giornata normale con qualche rottura.

### Comportamento richiesto

**A. Tetto di tempo per scraper.** `run_scrapers.py` interrompe uno scraper che
supera un budget (default configurabile, `--timeout-scraper`, in secondi) e
registra il run come fallito con una causa esplicita, senza abortire il run
complessivo. Gli atti già inseriti da quello scraper restano (`salva_atti`
committa man mano); non si perde lavoro fatto, si smette di aspettare.

**B. Riconoscimento del fallimento di massa nel report.** Quando una singola
causa spiega una quota dominante degli errori di un run, `run_report.py` la
segnala come tale ("225 dei 232 errori hanno la stessa causa: risoluzione DNS
fallita — probabile guasto di rete locale, non dei portali") invece di elencare
le prime 15 righe.

### Casi limite

- Se lo scraper è in un backfill legittimo (`--no-stop`, `--max-pagine` alto) il
  tetto va disattivabile: un backfill storico *deve* poter durare ore.
- Se il tetto scatta su uno scraper che stava inserendo atti a ritmo normale, è
  un segnale che il tetto è troppo basso, non che lo scraper è rotto: il report
  deve distinguere "interrotto per timeout" da "fallito con eccezione".
- Un solo scraper interrotto non deve far uscire `run_daily.sh` con exit non-zero
  se il resto è andato: il canale di notifica perde valore se suona ogni notte.

## ❓ Domande aperte

- [x] Valore di default del tetto — deciso in implementazione sulla base delle
      durate misurate (vedi Tentativi), non a priori.

## 📚 Contesto

- [`docs/wiki/15-run-automatico.md`](../wiki/15-run-automatico.md)
- [TAL-66](TAL-66.md) — il run automatico e il report che ha reso visibile questo
- [TAL-68](TAL-68.md) — stesso ragionamento (misurare il costo a regime) un
  livello più in basso: Caccamo costava 40 min dentro un run da 260
- [TAL-71](TAL-71.md) — il collo di bottiglia precedente (fase red flags, 11h)

## ✅ Task

- [x] Tetto di tempo per scraper in `run_scrapers.py` + flag CLI (`--timeout-scraper`)
- [x] Registrazione distinta dell'interruzione per timeout in `scraper_runs`
- [x] Riconoscimento della causa dominante in `run_report.py`
- [x] Test: scraper che supera il tetto, scraper sotto il tetto, backfill esente
- [ ] Misurare il run completo dopo il fix e riportare la durata reale qui
      *(richiede il Mac: vedi "Verifica sul DB reale" sotto)*

## 🧪 Criteri di accettazione

- [ ] Un run completo su `talia.db` reale finisce in una durata che lascia
      libero il trigger del giorno dopo (misurata, non stimata)
- [ ] Nessuno scraper sano viene interrotto dal tetto (verificato sui dati)
- [ ] Il report distingue una giornata con guasto di rete da una con rotture vere
- [x] Test passano (`pytest`): 733 verdi, ruff pulito
- [ ] DoD rispettata (vedi CLAUDE.md)

## 🔬 Tentativi

### 2026-09-02 — Tentativo 0 (diagnosi)
**Approccio:** invece di leggere i log del run (che non hanno timestamp per
fase), interrogare `scraper_runs` per durata per scraper e per distribuzione
delle cause di errore.
**Esito:** ✅
**Appreso:** la diagnosi "il run è lento" era troppo grossolana per agire — la
distribuzione dice che è concentrata su ~10 host, quindi la risposta è un tetto,
non un'ottimizzazione diffusa. Stessa lezione di TAL-71: contare prima di
ottimizzare. E che i tre giorni saltati non erano visibili da nessuna parte se
non incrociando le date dei run: nessun allarme li ha segnalati.

### 2026-10-19 — Tentativo 1 (implementazione)
**Approccio:** `SIGALRM` via `signal.setitimer` attorno a ogni scraper
(`modulo2_scraping/tetto_tempo.py`), eccezione `TettoTempoSuperato` derivata da
`BaseException`. Scartati: thread (non si può interrompere una `recv` da un
altro thread, e la connessione SQLite è condivisa) e un sottoprocesso per
scraper (refactor dell'orchestratore e una connessione per processo, per un
problema che il segnale risolve in poche righe).
**Esito:** ✅ sui test: interrompe `sleep`, `recv` bloccata su socket e loop di
retry con `except Exception`; timer e gestore sempre ripristinati.
**Appreso:**
- `BaseException` non è un dettaglio: con `Exception` il primo
  `except Exception: continue` di un retry avrebbe inghiottito l'interruzione e
  lo scraper avrebbe continuato a girare — il comportamento da eliminare.
- Gli inseriti prima dello stop si contano dagli id (`id > MAX(id)` di
  partenza): il run è sequenziale su una connessione, quindi è esatto, mentre
  `data_accesso` non ha un formato uniforme tra scraper.
- La causa dominante va calcolata sulla **riga dell'eccezione**, non sul
  traceback: un timeout in lettura TLS ha `ssl.py` tra i frame e sarebbe finito
  tra gli "errori SSL".
- Default **1200s**: i 259 scraper non patologici del 01/09 sommavano ~9.200s
  (~35s di media), i più lenti tra i sani (Agrigento Playwright, Caccamo dopo
  TAL-68) sotto i 3 minuti. Caso peggiore con 10 host appesi: ~6h di scraping.
  **Da confermare sui dati** con la query sotto prima di chiudere la card.

### Verifica sul DB reale (da fare sul Mac)

Quali scraper *sani* il tetto avrebbe interrotto nell'ultimo mese — cioè run
oltre 1200s che però inserivano atti:

```sql
SELECT scraper_id,
       COUNT(*)                                             AS run_oltre_tetto,
       ROUND(MAX((julianday(completato_a) - julianday(avviato_a)) * 86400)) AS max_s,
       SUM(n_inseriti)                                      AS inseriti
FROM scraper_runs
WHERE avviato_a >= date('now', '-30 days')
  AND completato_a IS NOT NULL
  AND (julianday(completato_a) - julianday(avviato_a)) * 86400 > 1200
GROUP BY scraper_id
ORDER BY inseriti DESC;
```

Se compaiono scraper con molti inseriti e durate appena sopra il tetto, alzare
il default o passare `--timeout-scraper` da `run_daily.sh`. Dopo il primo run
notturno col fix: durata complessiva da `logs/run_daily_*.log` e sezione
⏱️ di `logs/ultimo_report.md`.

## 🔗 Dipendenze

TAL-66 (run automatico, report), TAL-71 (fase red flags)

## 📝 Note

Il 01/09 la fase red flags ha impiegato ~2h contro i 30 min misurati in TAL-71:
il DB nel frattempo è cresciuto a 338.628 atti. Da tenere d'occhio, non è
l'oggetto di questa card.
