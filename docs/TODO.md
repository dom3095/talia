# ✅ TODO TALIA

Vista rapida. La fonte di verità è la board: [`docs/cards/BOARD.md`](cards/BOARD.md).

## 🔥 Adesso — Sprint 1 (prototipo Modulo 1 end-to-end)

Obiettivo: da un fascicolo in `data/samples/` (indizione + annullamento) → report checklist con citazioni e disclaimer.

- [ ] **TAL-1** Setup progetto Python + tooling · ⚙️ OPS · P0
- [ ] **TAL-2** CI GitHub Actions (lint + test) · ⚙️ OPS · P0
- [ ] **TAL-3** Estrazione testo PDF (nativo + OCR) · 🔤 NLP · P0
- [ ] **TAL-4** Estrazione entità: date, importi, CIG · 🔤 NLP · P0
- [ ] **TAL-6** Check 1: base giuridica revoca/annullamento · 🔤 NLP · P1
- [ ] **TAL-7** Check 2: termini autotutela (12 mesi) · 🔤 NLP · P1
- [ ] **TAL-10** Report Modulo 1 (verde/giallo/rosso) · 📊 FE · P1
- [ ] **TAL-12** Validazione su 10 fascicoli reali · ⚖️ LEX · P1

## ⏭️ Subito dopo

- [ ] **TAL-5** Firmatari + norme citate
- [ ] **TAL-8** Check 5: comunicazione avvio (art. 7)
- [ ] **TAL-9** Check 6: coerenza firmatari
- [ ] **TAL-11** Check 3: qualità motivazione (LLM, solo flaggati)

## 📦 Backlog per tappa

- **Scraping (E2):** TAL-20 spider pilota · TAL-21 schema DB · TAL-22 ANAC · TAL-23 red flags batch · TAL-24 ground truth
- **Dashboard (E3):** TAL-30 Streamlit MVP
- **Community (E4):** TAL-40 README + contributing

## 🧩 Decisioni aperte (da chiudere in card)

- [ ] Vector store RAG: FAISS vs Chroma (TAL-11)
- [ ] Modello LLM locale: Llama vs Mistral vs Qwen (TAL-11)
- [ ] DB access: SQL grezzo vs SQLAlchemy (TAL-21)
- [ ] Formato report: HTML statico vs Streamlit vs JSON+template (TAL-10)
- [ ] Licenza open source: MIT vs AGPL (TAL-40)

## 🧱 Pre-requisiti non tecnici

- [ ] Procurare **fascicoli campione reali** (anonimizzati) per `data/samples/`
- [ ] Coinvolgere un **esperto giuridico** (⚖️ LEX) per validare checklist e ground truth
- [ ] Verificare stato **recepimento siciliano del D.lgs. 36/2023** ([wiki/06](wiki/06-corpus-normativo.md))
