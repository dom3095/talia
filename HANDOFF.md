# HANDOFF.md — Stato rapido Sprint 3

> Aggiornato: 2026-06-22

## Cosa è stato fatto (ultimo passo)

**B1 — TAL-21: Schema DB atti + storage** ✅

- Creato `src/talia/modulo2_scraping/db.py`:
  - DDL completo: tabelle `enti`, `atti`, `entita_estratte`, `check_esiti`, `red_flags`
  - Dataclass `EnteMetadato` e `AttoMetadato`
  - Helper CRUD: `connetti`, `inizializza_db`, `upsert_ente`, `inserisci_atto`,
    `conta_atti`, `atti_per_ente`, `salva_check_esito`, `salva_red_flag`, `red_flags_per_ente`
  - Idempotenza garantita (UNIQUE su `ente_id × url_fonte`)
  - Indici su CIG, ente×data, tipo_flag, check_id
- Creato `tests/test_db.py` — 18 test, tutti passanti
- Creata struttura `src/talia/modulo2_scraping/fonti/` e `tests/fonti/`
- Nuova wiki: `docs/wiki/12-schema-db.md`
- BOARD.md aggiornato: TAL-21 → Done, TAL-20 → In Progress

## Prossimo passo

**B2 — TAL-20: Spider pilota albo pretorio iCity**

Leggere `LOOP_STATE.md` sezione B2 per le istruzioni dettagliate.

File da creare:
- `src/talia/modulo2_scraping/fonti/icity.py` — spider con `_parse_lista`, `_parse_dettaglio`, `scarica_atti`, `salva_atti`
- `tests/fonti/fixtures/icity_lista.html` — HTML fixture realistica
- `tests/fonti/fixtures/icity_dettaglio.html` — HTML fixture dettaglio
- `tests/fonti/test_icity.py` — test offline (no rete, no PDF committati)

## Branch attivo

`feat/sprint3` — tutti i commit di Sprint 3 vanno qui.

## Stato LOOP_STATE.md

```
current_step: B2
```
