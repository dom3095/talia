# HANDOFF.md — Stato sessione

> Aggiornato: 2026-07-03

---

## Branch attivo

`fix/BUG-4-trapani-filtro-data` — fix BUG-4 committato, da mergiare su `main`.
Il branch `feat/TAL-30-dashboard-mvp` (catch-all TAL-30/42…46) è stato
**mergiato e cancellato il 2026-07-03** (merge `51014cd`, 290 test verdi).
Da ora: **un branch per card** (`feat/TAL-XX-slug`), come da convenzione CLAUDE.md.
Il vecchio branch locale `fix/BUG-4-trapani-regex` è superato (conteneva solo un
commit docs, nessun fix): può essere cancellato.

## DB attuale

Aggiornato 2026-07-03 (notte), dopo fix Trapani + run completo:

```
7 enti | 4463 atti | 5 red flags
Agrigento:             278 atti  2026-06-03 → 2026-06-26
Caltanissetta:        1000 atti  2026-05-18 → 2026-06-25
Enna:                  400 atti  2022-01-19 → 2025-04-02  (bassa freq. ~3 atti/mese)
Palma di Montechiaro:  748 atti  2018-05-11 → 2026-06-05  ✅ backfill completo (già dal 26/06)
Ragusa:               1000 atti  2023-05-09 → 2026-04-15
Siracusa:              670 atti  2023-10-03 → 2026-06-26
Trapani:               367 atti  2026-04-10 → 2026-07-02  ✅ BUG-4 risolto, +329 atti
```

---

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
