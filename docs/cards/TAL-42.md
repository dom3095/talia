# TAL-42 — Schema DB: tabella `procedimenti` + colonne catena su `atti`

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🧭 TL + 🕷️ SCR
- **Priorità:** P2
- **Stato:** Done
- **Branch:** `feat/TAL-30-dashboard-mvp`

## 🎯 Obiettivo

Estendere lo schema SQLite per rappresentare la **catena di eventi** di un procedimento
amministrativo (bando → modifiche → revoca/aggiudicazione).

## 📚 Contesto

Un procedimento raggrupa atti correlati (stesso CIG, stessi riferimenti incrociati, stesso
oggetto). Il DB deve tracciare il gruppo e il ruolo di ciascun atto al suo interno.
Schema aggiunto via `_evolvi_schema()` (lazy, idempotente — non rompe il DB esistente).

## ✅ Task

- [x] Tabella `procedimenti` (id, ente_id, tipo, cig, oggetto, data_avvio, data_chiusura, stato_finale, metodo_individuazione, creato_a)
- [x] `ALTER TABLE atti ADD COLUMN procedimento_id` (FK verso procedimenti)
- [x] `ALTER TABLE atti ADD COLUMN ruolo_in_catena` (avvio/modifica/proroga/aggiudicazione/revoca/annullamento/altro)
- [x] Indici: `idx_procedimenti_cig`, `idx_procedimenti_ente`, `idx_atti_procedimento`
- [x] Evoluzione lazy in `engine/catena._evolvi_schema()` — idempotente, testata

## 🧪 Criteri di accettazione

- [x] Doppia esecuzione di `_evolvi_schema` non duplica tabelle/colonne
- [x] Foreign key `procedimento_id → procedimenti.id` rispettata
- [x] Compatibile con DB esistente (ALTER IF NOT EXISTS)

## 🔗 Dipendenze

TAL-21 ✅ (schema base atti + enti).

## 📝 Note implementative

- Schema creato in `src/talia/engine/catena._evolvi_schema()`, non in `db.py`, per tenere
  la logica di catena nel modulo engine (separazione responsabilità).
- SQLite non supporta `ALTER TABLE ADD COLUMN IF NOT EXISTS` → check via `PRAGMA table_info`.
