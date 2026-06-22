# HANDOFF.md — Stato rapido Sprint 3

> Aggiornato: 2026-06-22

## Cosa è stato fatto (ultimo passo)

**B2 — TAL-20: Spider pilota albo pretorio iCity** ✅

- Creato `src/talia/modulo2_scraping/fonti/icity.py`:
  - `_parse_lista(html, base_url)` — estrae righe dalla tabella lista iCity
  - `_parse_dettaglio(html, url, codice_istat)` → `AttoMetadato`
  - `_data_iso()`, `_estrai_cig()`, `_estrai_importo()` — utilità parsing
  - `scarica_atti(base_url, codice_istat, *, limit, delay, _fetch_fn)` — genera atti con `_fetch_fn` iniettabile per i test
  - `salva_atti(atti, conn)` → `dict[str, int]` (inseriti/duplicati)
  - Rate limiting via parametro `delay`; User-Agent identificativo
- Creato `tests/fonti/fixtures/icity_lista.html` e `icity_dettaglio.html` — HTML realistici
- Creato `tests/fonti/test_icity.py` — 31 test offline, tutti verdi
- 122 test totali sul progetto, tutti verdi

## Cosa era stato fatto prima (B1)

**B1 — TAL-21: Schema DB atti + storage** ✅
- `src/talia/modulo2_scraping/db.py` — DDL, `AttoMetadato`/`EnteMetadato`, helper CRUD
- `tests/test_db.py` — 18 test
- `docs/wiki/12-schema-db.md` — documentazione schema

## Prossimo passo

**B3 — TAL-22: Pipeline ANAC open data (regione 19)**

Leggere `LOOP_STATE.md` sezione B3 per le istruzioni dettagliate.

File da creare:
- `src/talia/modulo2_scraping/fonti/anac.py` — fetcher ANAC CSV/JSON, filtro cod_nuts=ITG1
- `tests/fonti/fixtures/anac_sample.csv` — campione CSV sintetico
- `tests/fonti/test_anac.py` — test offline con CSV fixture

## Branch attivo

`feat/sprint3` — tutti i commit di Sprint 3 vanno qui.

## Stato LOOP_STATE.md

```
current_step: B3
```
