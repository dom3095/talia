# TAL-1 — Setup progetto Python + tooling

- **Epica:** E0 — Fondamenta repo
- **Ruolo:** ⚙️ OPS
- **Priorità:** P0
- **Stato:** Review
- **Branch:** `feat/TAL-1-modulo1-prototipo` (sviluppo congiunto Sprint 1)

## 🎯 Obiettivo
Scheletro Python installabile, con tooling di qualità configurato.

## 📚 Contesto
Layout atteso in [`CLAUDE.md`](../../CLAUDE.md). Stack in [wiki/03](../wiki/03-stack.md).

## ✅ Task
- [x] `pyproject.toml` (build backend, deps base: spacy, pytesseract, pdfplumber/pypdf, scrapy, streamlit)
- [x] Struttura `src/talia/{engine,modulo1_fascicolo,modulo2_scraping,modulo3_dashboard}/`
- [x] `tests/` con un test smoke
- [x] `ruff` + `black` (o `ruff format`) configurati
- [x] `.gitignore` (`.env`, `data/raw/`, `__pycache__`, venv, `*.db`)
- [x] `.env.example`
- [x] `data/{raw,samples,corpus_normativo}/` con `.gitkeep`
- [x] README minimo con istruzioni install

## 🧪 Criteri di accettazione
- [x] `pip install -e .` funziona
- [x] `pytest` verde (smoke test)
- [x] `ruff check` pulito
- [x] Nessun segreto/PDF reale committato

## 🔗 Dipendenze
Nessuna.

## 📝 Note
Python 3.11+. Decidere se SQLAlchemy o SQL grezzo (vedi scelte aperte wiki/03) → può slittare a TAL-21.

## 📦 Consuntivo (12/06/2026)

Implementato: `pyproject.toml` (setuptools, ruff, pytest), struttura `src/talia/*`,
`tests/` (45 test), `.env.example`, `data/{raw,samples,corpus_normativo}/`, README con badge CI.
**Deviazione:** le dipendenze pesanti (pdfplumber/pytesseract/spaCy) sono **extra opzionali**
(`[pdf]`, `[nlp]`) e non deps base: il core deterministico gira con la sola standard library
(budget zero, test rapidi). Scrapy/Streamlit rinviate alle card E2/E3 che le useranno.
SQLAlchemy vs SQL grezzo slitta a TAL-21 come previsto.
