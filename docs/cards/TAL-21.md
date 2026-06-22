# TAL-21 — Schema DB atti + storage

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🧭 TL
- **Priorità:** P1
- **Stato:** Done
- **Branch:** `feat/sprint3`

## 🎯 Obiettivo
Schema dati per atti, entità, esiti dei check. SQLite in dev, predisposto per Postgres free tier.

## 📚 Contesto
Storage [wiki/03](../wiki/03-stack.md). Alimenta Modulo 2 e Modulo 3.

## ✅ Task
- [x] Tabelle: `enti` (comuni), `atti`, `entita_estratte`, `check_esiti`, `red_flags`
- [x] Metadati atto: ente, tipo, date, URL fonte, data accesso, hash file
- [x] Codice ISTAT comune (per filtrare regione 19 e confronto tra pari)
- [x] DDL versionato in costante `_DDL` (IF NOT EXISTS — idempotente)
- [x] SQL grezzo con `sqlite3` stdlib; placeholder `?` documentati per migrazione Postgres
- [x] Scelta: SQL grezzo (no SQLAlchemy) — budget ≈ 0, dipendenze minime

## 🧪 Criteri di accettazione
- [x] Schema crea/migra su SQLite in-memory e su file
- [x] Vincoli di integrità (FK ente↔atto, CASCADE delete, UNIQUE url_fonte×ente)
- [x] Indici su CIG, ente×data, fonte_scraper, tipo_flag, check_id
- [x] 18 test CRUD passanti (`tests/test_db.py`)

## 🔗 Dipendenze
TAL-1.

## 📝 Note
Pensare fin da subito al confronto tra pari (taglia comune) → serve popolazione/ISTAT degli enti.
