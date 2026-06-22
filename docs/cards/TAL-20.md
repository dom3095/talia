# TAL-20 — Scraper pilota: un albo pretorio

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🕷️ SCR
- **Priorità:** P1
- **Stato:** Review
- **Branch:** `feat/sprint3`

## 🎯 Obiettivo
Spider che raccoglie atti da **un solo software di albo pretorio** (il più diffuso in Sicilia) o una sola provincia.

## 📚 Contesto
Tappa 2 roadmap. Strategia "parti piccolo": 4-5 scraper coprono gran parte dei 391 comuni ([wiki/07](../wiki/07-fonti-dati.md)).

## ✅ Task
- [x] Identificare il fornitore: **iCity/iPublic (Maggioli Spa)** — più diffuso tra i comuni siciliani
- [x] Spider stdlib (html.parser + urllib, zero deps): `_parse_lista`, `_parse_dettaglio`, `scarica_atti`, `salva_atti`
- [x] Rate limiting (parametro `delay`) + User-Agent identificativo
- [x] Persistenza su DB via `inserisci_atto` (TAL-21)
- [x] Idempotenza: `inserisci_atto` scarta duplicati per `(ente_id, url_fonte)`
- [x] PDF grezzi non committati (solo `url_pdf` nei metadati)

## 🧪 Criteri di accettazione
- [x] 31 test offline verdi (fixture HTML, `_fetch_fn` iniettabile)
- [x] Conserva URL + data accesso per ogni atto (esplicabilità)
- [x] Re-run non duplica (test `test_salva_atti_idempotente`)
- [x] Nessun PDF committato — solo URL

## 🔗 Dipendenze
TAL-21 (schema DB).

## 📝 Note
Predisporre per il cron su GitHub Actions (workflow predisposto in TAL-2).
