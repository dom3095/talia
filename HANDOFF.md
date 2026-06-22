# HANDOFF.md — Stato rapido Sprint 3

> Aggiornato: 2026-06-22

## Cosa è stato fatto (ultimo passo)

**B4 — TAL-23: Red flags batch deterministici** ✅

Creato pacchetto `src/talia/modulo2_scraping/red_flags/`:

| File | Contenuto |
|------|-----------|
| `frazionamento.py` | sliding window 90 gg: ≥3 atti < 140k EUR con totale > soglia |
| `concentrazione.py` | quota affidamenti diretti > 80% in anno (≥10 atti) |
| `tempi_anomali.py` | bandi con finestra < 15 gg (sotto soglia UE) / < 30 gg (sopra) |
| `runner.py` | `esegui_tutti(conn)` → salva su DB, ritorna `RapportoRunner` |

- 20 test in `tests/red_flags/` — tutti verdi
- Suite completa: **164 test passano**
- Bug fixato: `strftime('%Y')` restituisce TEXT in SQLite; confronto con `str(anno)`

## Cosa era stato fatto prima

**B3 — TAL-22: Pipeline ANAC open data** ✅ — `anac.py` + 22 test

**B2 — TAL-20: Spider iCity** ✅ — `icity.py` + 31 test

**B1 — TAL-21: Schema DB** ✅ — `db.py` + 18 test

## Prossimo passo

**B5 — TAL-30: Dashboard Streamlit MVP**

Leggere `LOOP_STATE.md` sezione B5 per le istruzioni dettagliate.

File da creare:
- `src/talia/modulo3_dashboard/app.py` — app Streamlit
- `src/talia/modulo3_dashboard/query.py` — helper query DB
- `tests/test_dashboard_query.py` — test query (senza Streamlit)

Criteri:
- Vista per comune: red flags aggregate + link fonte
- Drill-down: flag → atti → URL
- Disclaimer ben visibile
- Anonimizzazione comuni ≤ 5000 abitanti
- Test delle query (no dipendenza da Streamlit nel test runner)

## Branch attivo

`feat/sprint3` — tutti i commit di Sprint 3 vanno qui.

## Stato LOOP_STATE.md

```
current_step: B5
```
