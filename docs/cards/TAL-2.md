# TAL-2 — CI GitHub Actions (lint + test)

- **Epica:** E0 — Fondamenta repo
- **Ruolo:** ⚙️ OPS
- **Priorità:** P0
- **Stato:** To Do
- **Branch:** `feat/TAL-2-ci`

## 🎯 Obiettivo
Ogni push/PR esegue lint + test automaticamente. Gratis su GitHub Actions.

## 📚 Contesto
Budget zero → CI/cron su GitHub Actions ([wiki/03](../wiki/03-stack.md)).

## ✅ Task
- [ ] Workflow `.github/workflows/ci.yml`: setup Python, install, `ruff check`, `pytest`
- [ ] Cache dipendenze
- [ ] Installare Tesseract nel runner (per test OCR)
- [ ] Badge stato nel README

## 🧪 Criteri di accettazione
- [ ] Workflow verde su un PR di prova
- [ ] Fallisce correttamente se lint/test rompono
- [ ] Nessun segreto esposto nei log

## 🔗 Dipendenze
TAL-1.

## 📝 Note
Predisporre (commentato) un futuro workflow `cron` per lo scraping (TAL-20).
