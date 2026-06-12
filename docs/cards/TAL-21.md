# TAL-21 — Schema DB atti + storage

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🧭 TL
- **Priorità:** P1
- **Stato:** Backlog
- **Branch:** `feat/TAL-21-db-schema`

## 🎯 Obiettivo
Schema dati per atti, entità, esiti dei check. SQLite in dev, predisposto per Postgres free tier.

## 📚 Contesto
Storage [wiki/03](../wiki/03-stack.md). Alimenta Modulo 2 e Modulo 3.

## ✅ Task
- [ ] Tabelle: `enti` (comuni), `atti`, `entita_estratte`, `check_esiti`, `red_flags`
- [ ] Metadati atto: ente, tipo, date, URL fonte, data accesso, hash file
- [ ] Codice ISTAT comune (per filtrare regione 19 e confronto tra pari)
- [ ] Migrazioni / DDL versionato
- [ ] Astrazione che funzioni sia con SQLite sia con Postgres
- [ ] Decidere SQL grezzo vs SQLAlchemy (scelta aperta wiki/03)

## 🧪 Criteri di accettazione
- [ ] Schema crea/migra su SQLite e (almeno in teoria) Postgres
- [ ] Vincoli di integrità (FK ente↔atto, ecc.)
- [ ] Indici su CIG, ente, data per le query dei red flag batch
- [ ] Test CRUD base

## 🔗 Dipendenze
TAL-1.

## 📝 Note
Pensare fin da subito al confronto tra pari (taglia comune) → serve popolazione/ISTAT degli enti.
