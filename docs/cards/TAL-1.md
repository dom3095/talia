# TAL-1 — Setup progetto Python + tooling

- **Epica:** E0 — Fondamenta repo
- **Ruolo:** ⚙️ OPS
- **Priorità:** P0
- **Stato:** To Do
- **Branch:** `feat/TAL-1-setup`

## 🎯 Obiettivo
Scheletro Python installabile, con tooling di qualità configurato.

## 📚 Contesto
Layout atteso in [`CLAUDE.md`](../../CLAUDE.md). Stack in [wiki/03](../wiki/03-stack.md).

## ✅ Task
- [ ] `pyproject.toml` (build backend, deps base: spacy, pytesseract, pdfplumber/pypdf, scrapy, streamlit)
- [ ] Struttura `src/talia/{engine,modulo1_fascicolo,modulo2_scraping,modulo3_dashboard}/`
- [ ] `tests/` con un test smoke
- [ ] `ruff` + `black` (o `ruff format`) configurati
- [ ] `.gitignore` (`.env`, `data/raw/`, `__pycache__`, venv, `*.db`)
- [ ] `.env.example`
- [ ] `data/{raw,samples,corpus_normativo}/` con `.gitkeep`
- [ ] README minimo con istruzioni install

## 🧪 Criteri di accettazione
- [ ] `pip install -e .` funziona
- [ ] `pytest` verde (smoke test)
- [ ] `ruff check` pulito
- [ ] Nessun segreto/PDF reale committato

## 🔗 Dipendenze
Nessuna.

## 📝 Note
Python 3.11+. Decidere se SQLAlchemy o SQL grezzo (vedi scelte aperte wiki/03) → può slittare a TAL-21.
