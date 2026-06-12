# TAL-20 — Scraper pilota: un albo pretorio

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🕷️ SCR
- **Priorità:** P1
- **Stato:** Backlog
- **Branch:** `feat/TAL-20-scraper-pilota`

## 🎯 Obiettivo
Spider che raccoglie atti da **un solo software di albo pretorio** (il più diffuso in Sicilia) o una sola provincia.

## 📚 Contesto
Tappa 2 roadmap. Strategia "parti piccolo": 4-5 scraper coprono gran parte dei 391 comuni ([wiki/07](../wiki/07-fonti-dati.md)).

## ✅ Task
- [ ] Identificare il fornitore software di albo pretorio più diffuso
- [ ] Spider Scrapy: lista atti → download PDF → metadati (ente, data, tipo, URL, data accesso)
- [ ] Rispetto `robots.txt` + rate limiting
- [ ] Persistenza su DB (TAL-21)
- [ ] Idempotenza: non riscaricare atti già presenti
- [ ] PDF grezzi in `data/raw/` (gitignored)

## 🧪 Criteri di accettazione
- [ ] Raccoglie correttamente un batch di atti da almeno un comune pilota
- [ ] Conserva URL + data accesso per ogni atto (esplicabilità)
- [ ] Re-run non duplica
- [ ] Nessun PDF con dati nominativi committato

## 🔗 Dipendenze
TAL-21 (schema DB).

## 📝 Note
Predisporre per il cron su GitHub Actions (workflow predisposto in TAL-2).
