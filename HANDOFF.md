# HANDOFF.md — Stato rapido Sprint 3

> Aggiornato: 2026-06-22

## Cosa è stato fatto (ultimo passo)

**B3 — TAL-22: Pipeline ANAC open data (regione 19)** ✅

- Creato `src/talia/modulo2_scraping/fonti/anac.py`:
  - `_leggi_csv(contenuto)` — genera righe normalizzate da CSV ANAC (delimiter `;`)
  - `_filtra_sicilia(righe)` — filtra per `sezione_regionale == 'Sicilia'`
  - `_normalizza_colonne(riga)` — gestisce alias colonne tra versioni CSV diverse
  - `_mappa_atto(riga, codice_istat)` → `AttoMetadato` con `tipo='contratto_anac'`
  - `_upsert_ente_anac(conn, riga)` — inserisce ente da CF se non nel DB
  - `carica_csv_anac(contenuto, conn, *, crea_enti_mancanti=True)` — API principale
  - `scarica_e_carica(conn, *, url, _fetch_fn)` — download + caricamento
  - `url_fonte` sintetico: `https://dati.anticorruzione.it/opendata/cig/<cig>`
  - Idempotente: UNIQUE su `(ente_id, url_fonte)` → re-run sicuro

- Creato `tests/fonti/fixtures/anac_sample.csv` — 10 righe (8 siciliane + 2 fuori Sicilia)
- Creato `tests/fonti/test_anac.py` — 22 test offline, tutti verdi
- 144 test totali sul progetto, tutti verdi

## Cosa era stato fatto prima

**B2 — TAL-20: Spider iCity** ✅ — `icity.py` + 31 test

**B1 — TAL-21: Schema DB** ✅ — `db.py` + 18 test

## Prossimo passo

**B4 — TAL-23: Red flags batch deterministici**

Leggere `LOOP_STATE.md` sezione B4 per le istruzioni dettagliate.

File da creare:
- `src/talia/modulo2_scraping/red_flags/__init__.py`
- `src/talia/modulo2_scraping/red_flags/frazionamento.py`
- `src/talia/modulo2_scraping/red_flags/concentrazione.py`
- `src/talia/modulo2_scraping/red_flags/tempi_anomali.py`
- `src/talia/modulo2_scraping/red_flags/runner.py`
- `tests/red_flags/` (test per ogni regola)

## Branch attivo

`feat/sprint3` — tutti i commit di Sprint 3 vanno qui.

## Stato LOOP_STATE.md

```
current_step: B4
```
