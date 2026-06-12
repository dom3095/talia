# TAL-2 — CI GitHub Actions (lint + test)

- **Epica:** E0 — Fondamenta repo
- **Ruolo:** ⚙️ OPS
- **Priorità:** P0
- **Stato:** Review
- **Branch:** `feat/TAL-1-modulo1-prototipo` (sviluppo congiunto Sprint 1)

## 🎯 Obiettivo
Ogni push/PR esegue lint + test automaticamente. Gratis su GitHub Actions.

## 📚 Contesto
Budget zero → CI/cron su GitHub Actions ([wiki/03](../wiki/03-stack.md)).

## ✅ Task
- [x] Workflow `.github/workflows/ci.yml`: setup Python, install, `ruff check`, `pytest`
- [x] Cache dipendenze
- [x] Installare Tesseract nel runner (per test OCR)
- [x] Badge stato nel README

## 🧪 Criteri di accettazione
- [ ] Workflow verde su un PR di prova *(da verificare al primo PR)*
- [ ] Fallisce correttamente se lint/test rompono *(da verificare al primo PR)*
- [x] Nessun segreto esposto nei log

## 🔗 Dipendenze
TAL-1.

## 📝 Note
Predisporre (commentato) un futuro workflow `cron` per lo scraping (TAL-20).

## 📦 Consuntivo (12/06/2026)

Workflow `.github/workflows/ci.yml`: matrice Python 3.11/3.12, cache pip, Tesseract (`ita`)
installato nel runner, `ruff check` + `pytest`. Badge nel README. Workflow cron per lo
scraping predisposto come commento (TAL-20). Da verificare il primo run verde sul PR.
