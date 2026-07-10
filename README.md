# TALIA — Trasparenza Atti Locali: Indicatori e Analisi

[![CI](https://github.com/dom3095/talia/actions/workflows/ci.yml/badge.svg)](https://github.com/dom3095/talia/actions/workflows/ci.yml)

> *Taliàri* (sic.): guardare, osservare. **Talia!** = «Guarda!»

> 🔍 **Tracking Anomalies in Local Institutional Acts**

Strumento civico open source che rileva **red flags** (anomalie da verificare,
**mai** accuse) negli atti delle Pubbliche Amministrazioni siciliane: gare,
concorsi, delibere, revoche, annullamenti.

**Regola d'oro:** segnalare, non giudicare. Ogni segnalazione è esplicabile e
collegata al passaggio testuale dell'atto sorgente.

Per la visione completa vedi [`talia.md`](talia.md); per la guida operativa
[`CLAUDE.md`](CLAUDE.md) e la [wiki](docs/wiki/00-home.md).

## Stato

Prototipo del **Modulo 1 — Analisi fascicolo on-demand** (Sprint 1): dato un
fascicolo (es. indizione + annullamento) produce un report con checklist
verde/giallo/rosso, citazioni e disclaimer. Pipeline:

```
estrazione testo (nativo/OCR) → entità (regex) → checklist deterministica → report
```

Check implementati: **1** base giuridica, **2** termini autotutela (12 mesi),
**5** comunicazione avvio (art. 7), **6** coerenza firmatari. Check 3 (qualità
motivazione, LLM) previsto in TAL-11.

## Installazione

Richiede Python 3.11+.

```bash
# core (regole deterministiche, report): nessuna dipendenza esterna
pip install -e .

# con estrazione PDF + OCR (richiede Tesseract di sistema, lingua 'ita')
pip install -e '.[pdf]'

# tutto, inclusi strumenti di sviluppo
pip install -e '.[all]'
```

Su macOS: `brew install tesseract tesseract-lang`. Su Debian/Ubuntu:
`sudo apt-get install tesseract-ocr tesseract-ocr-ita`.

## Uso

```bash
# analizza una cartella con i file del fascicolo (.pdf e/o .txt)
talia analizza data/samples/fascicolo_coerente/

# file espliciti, output HTML su file
talia analizza indizione.txt annullamento.txt --formato html --out report.html

# JSON per integrazioni
talia analizza caso.pdf --formato json
```

Da Python:

```python
from talia.modulo1_fascicolo.analisi import analizza_pdf
report = analizza_pdf(["indizione.pdf", "annullamento.pdf"])
print(report.to_markdown())
```

## Sviluppo

```bash
pip install -e '.[dev]'
ruff check .
pytest
```

## Avvertenze

Le segnalazioni di TALIA sono **anomalie da verificare, non accertamenti**. Mai
punteggi senza link alla fonte. Le viste pubbliche vanno anonimizzate, specie nei
piccoli comuni. Vedi [`docs/wiki/09-avvertenze-legali.md`](docs/wiki/09-avvertenze-legali.md).

## Licenza

[AGPL-3.0-or-later](LICENSE): chi offre TALIA come servizio deve ripubblicare le
modifiche — il progetto resta un bene comune.
