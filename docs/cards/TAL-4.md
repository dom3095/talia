# TAL-4 — Estrazione entità: date, importi, CIG

- **Epica:** E1 — Motore + Modulo 1
- **Ruolo:** 🔤 NLP
- **Priorità:** P0
- **Stato:** Review
- **Branch:** `feat/TAL-1-modulo1-prototipo` (sviluppo congiunto Sprint 1)

## 🎯 Obiettivo
Estrarre dal testo le entità deterministiche di base, ognuna con offset/posizione nel documento.

## 📚 Contesto
Secondo stadio del motore ([wiki/02](../wiki/02-architettura.md)). Regex per pattern rigidi.

## ✅ Task
- [x] **Date** (formati italiani: `12/06/2026`, `12 giugno 2026`, ecc.) → normalizzate ISO
- [x] **Importi** (`€ 1.234,56`, `euro ...`) → Decimal normalizzato
- [x] **CIG** (10 caratteri alfanumerici) con validazione formato
- [x] **CUP** (15 caratteri) opzionale
- [x] Ogni entità porta: valore normalizzato, testo originale, offset, pagina
- [x] Modello `Entita` + `EntitaEstratte`

## 🧪 Criteri di accettazione
- [x] Estrae date/importi/CIG corretti dai campioni
- [x] Casi negativi: non confonde numeri di protocollo con CIG, ecc.
- [x] Ogni entità risalibile alla posizione nel testo
- [x] Test con esempi reali + negativi

## 🔗 Dipendenze
TAL-3.

## 📝 Note
CIG: formato ANAC. Documentare le regex con commento + fonte. Numeri "magici" → costanti.

## 📦 Consuntivo (12/06/2026)

Implementato in `src/talia/engine/entita.py`: date numeriche e testuali italiane → `date`
ISO (scarto date di calendario invalide), importi `€`/`euro` → `Decimal`, CIG (10 alfanum.)
e CUP (15, iniziale alfabetica) **solo se etichettati** (evita falsi positivi su protocolli).
Ogni entità porta valore normalizzato, testo originale, offset e pagina (`Entita`,
`EntitaEstratte` in `models.py`). Regex documentate con motivazione; soglie come costanti.
Test positivi e negativi in `tests/test_entita.py`.
