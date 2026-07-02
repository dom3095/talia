# HANDOFF.md — Stato sessione

> Aggiornato: 2026-06-28

---

## Branch attivo

`feat/TAL-30-dashboard-mvp` — modifiche **non committate** (vedi sotto).

## DB attuale

```
7 enti | 3446 atti | 3 red flags
Agrigento:             278 atti  2026-06-03 → 2026-06-26
Caltanissetta:        1000 atti  2026-05-18 → 2026-06-25
Enna:                  400 atti  2022-01-19 → 2026-06-26  (bassa freq. ~3 atti/mese)
Palma di Montechiaro:   60 atti  2026-01-23 → 2026-06-05  ← backfill storico da fare
Ragusa:               1000 atti  2023-05-09 → 2026-04-15
Siracusa:              670 atti  2023-10-03 → 2026-06-26
Trapani:                38 atti  2026-06-11 → 2026-06-24  ← scraper ROTTO (BUG-4)
```

---

## Modifiche non committate

| File | Contenuto |
|------|-----------|
| `scripts/run_scrapers.py` | Palma aggiunta; `--no-stop`; `scraper_runs`; stop-on-known; coverage summary; `--anac-file` |
| `src/talia/modulo2_scraping/db.py` | Tabella `scraper_runs`; `inizia_run`, `termina_run`, `ultimo_run_riuscito` |
| `src/talia/modulo2_scraping/fonti/jcitygov.py` | Timeout 30s + 1 retry |
| `src/talia/engine/catena.py` | Engine catena di eventi (TAL-43) — nuovo file |
| `src/talia/modulo2_scraping/red_flags/catena_revoca.py` | Red flag revoca in catena (TAL-44) — nuovo file |
| `src/talia/modulo2_scraping/red_flags/runner.py` | Aggiunto `revoche_catena` |
| `src/talia/modulo3_dashboard/app.py` | Tab ⛓️ Procedimenti (TAL-45) |
| `tests/test_catena.py` | 29 test motore catena |
| `tests/red_flags/test_catena_revoca.py` | 6 test red flag revoca |
| `docs/wiki/02-architettura.md` | Pipeline due fasi |
| `docs/wiki/05-red-flags-batch.md` | 6 check PDF + caso studio Palma |
| `docs/cards/BOARD.md` | TAL-42..45 aggiunte in Review |
| `docs/cards/TAL-42..45.md` | Nuove card catena |

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

## Bug aperti (bloccanti per PR TAL-30)

### BUG-6: Dashboard — tab Panoramica vuota

**Rilevato:** 2026-06-28, test manuale con Playwright
**Sintomo:** tab "📊 Panoramica" si carica senza errori ma non mostra dati (tabella/chart assenti sotto il titolo "Comuni con segnalazioni"). Tab "🔍 Dettaglio comune" funziona (dati reali presenti). Tab "⛓️ Procedimenti" graceful degradation OK (catene non ancora costruite).
**Causa probabile:** query `carica_panoramica()` restituisce dati ma il componente Streamlit (dataframe o chart) non li renderizza — potrebbe essere colonna mancante, DataFrame vuoto per un filtro troppo stretto, o eccezione silenziosa.
**File:** `src/talia/modulo3_dashboard/app.py` — sezione tab Panoramica
**Fix necessario prima di chiudere la PR TAL-30.**

---

## Prossimi passi

### 0 — Fix Trapani (urgente, ~30 min)

```bash
python3 -c "
import urllib.request, http.cookiejar
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
opener.addheaders = [('User-Agent', 'Mozilla/5.0')]
r = opener.open('https://servizi-trapani.e-pal.it/AlboOnline/ricercaAlbo', timeout=15)
print(r.read(5000).decode('utf-8', errors='replace'))
" > /tmp/trapani_raw.html
```

Confrontare con `_RE_PANEL` in `trapani.py`, aggiornare la regex, aggiungere fixture di test.

### 1 — Commit (bloccante per tutto il resto)

```bash
git add -p
git commit -m "feat(E2): catena eventi, red flag revoca, tab dashboard (TAL-42/43/44/45)"
```

### 2 — Backfill storico Palma di Montechiaro

```bash
python scripts/run_scrapers.py --scrapers palma --max-pagine 50 --no-stop
```

### 3 — Validare la catena sul DB reale

`data/samples/1/` è un esempio costruito a mano — testarlo è circolare. La validazione vera è sul DB reale:

```bash
python -c "
from talia.modulo2_scraping.db import connetti
from talia.engine.catena import ricostruisci_catene

conn = connetti('talia.db')
ricostruisci_catene(conn)
rows = conn.execute('''
    SELECT e.denominazione, p.stato_finale, p.metodo_individuazione,
           COUNT(a.id) as n_atti
    FROM procedimenti p
    JOIN enti e ON p.ente_id = e.id
    JOIN atti a ON a.procedimento_id = p.id
    GROUP BY p.id ORDER BY e.denominazione, p.stato_finale
''').fetchall()
for r in rows: print(r)
conn.close()
"
```

Controllare:
1. Numeri plausibili per ente (poche decine di catene, non migliaia)
2. Catene con `metodo_individuazione = 'oggetto_simile'` → spot-check manuale (Jaccard è rumoroso)
3. Il fascicolo Palma (revoca Det. 35/2025) risulta collegato?

### 4 — TAL-14: check GDPR + numero atto incoerente

Card in Review. Casi concreti trovati su fascicolo Palma:
- Bozza graduatoria divulgata prima dell'ufficializzazione → `gdpr_breach_non_notificato`
- Revoca cita "N. 33/2025" ma l'atto in DB è "N. 35/2025" → `numero_atto_incoerente`

### 5 — Fase 2 pipeline: PDF on-demand

Download PDF solo per atti con `REVOCA`, `AUTOTUTELA`, `ANNULLAMENTO` nell'oggetto.
Alimenta TAL-14 e TAL-11. Da pianificare come nuova card E2.

### 6 — ANAC

WAF blocca urllib (TLS fingerprinting). Workaround attuale: `--anac-file <csv>`.
Alternativa: Playwright headless.

### 7 — Messina: bloccato, non azione immediata

FortiGate HTTP 403 + certificato scaduto 2023-06-27. `skip_ssl=True` non aggira il 403.
Richiede intervento IT del Comune. Vedi BUG-5 in `docs/bugs.md`.

---

## Note permanenti

- `data/samples/1/` — fascicoli reali locali, **mai committare**
- `talia.db` — **mai committare**
- Architettura E2: [`docs/handoff/epica_E2.md`](docs/handoff/epica_E2.md)
- Stato scraper: [`docs/wiki/13-scraper-status.md`](docs/wiki/13-scraper-status.md)
- Bug aperti: [`docs/bugs.md`](docs/bugs.md)
