# TALIA — Trasparenza Atti Locali: Indicatori e Analisi

[![CI](https://github.com/dom3095/talia/actions/workflows/ci.yml/badge.svg)](https://github.com/dom3095/talia/actions/workflows/ci.yml)
[![Licenza: AGPL v3](https://img.shields.io/badge/licenza-AGPL--3.0-blue.svg)](LICENSE)

> *Taliàri* (sic.): guardare, osservare. **Talia!** = «Guarda!»

TALIA è uno strumento civico open source che legge gli atti pubblicati dalle
Pubbliche Amministrazioni siciliane (gare, concorsi, delibere, revoche,
annullamenti) e segnala le **anomalie da verificare**: un concorso revocato e
rilanciato poco dopo con lo stesso oggetto, una revoca senza motivazione né
comunicazione di avvio, un bando pubblicato per meno giorni di quelli previsti.

> ⚠️ **Segnalazioni da verificare, non accertamenti.** Un red flag è un invito
> a guardare meglio un atto, mai l'affermazione che un illecito sia avvenuto.
> Ogni segnalazione indica l'atto sorgente e il passaggio che l'ha generata.
> Vedi [avvertenze legali](docs/wiki/09-avvertenze-legali.md).

## Cosa fa oggi

| Modulo | Cosa fa | Stato |
|---|---|---|
| **1 — Analisi fascicolo** | Dai i PDF di un procedimento (es. bando + revoca): esce un report verde/giallo/rosso, con la citazione testuale e la norma accanto a ogni check | prototipo funzionante, in validazione su fascicoli reali |
| **2 — Raccolta continua** | Legge ogni notte gli albi pretori di **258 comuni siciliani (81% della popolazione)** e i contratti SmartCIG di ANAC, ricostruisce le catene di atti dello stesso procedimento e calcola i red flag | in produzione su una macchina locale |
| **3 — Dashboard** | Panoramica per comune e provincia, andamento nel tempo, catene di procedimenti, stato della raccolta | uso interno, non pubblicata |

Principi che valgono per ogni riga di codice:

1. **Esplicabilità.** Nessun indicatore senza link alla fonte; niente punteggi "nudi".
2. **Determinismo prima degli LLM.** Quasi tutto è regex + SQL; un modello
   linguistico, **locale**, interviene solo su documenti già segnalati, dove
   serve un giudizio sul testo (es. qualità della motivazione).
3. **Budget zero.** Solo software libero e servizi gratuiti.
4. **Privacy.** Le viste pubbliche sono aggregate; il dettaglio nominativo resta
   per uso interno, soprattutto nei piccoli comuni.

## Provarlo in 5 minuti (Modulo 1)

Richiede Python 3.12+.

```bash
git clone https://github.com/dom3095/talia.git && cd talia
python -m venv .venv && source .venv/bin/activate
pip install -e '.[pdf]'          # estrazione testo da PDF (+ OCR con Tesseract)

# analizza un fascicolo di esempio (anonimizzato, incluso nel repo)
talia analizza data/samples/fascicolo_coerente/

# report HTML su file, o JSON per integrazioni
talia analizza bando.pdf revoca.pdf --formato html --out report.html
```

Per l'OCR delle scansioni serve Tesseract con l'italiano: `brew install
tesseract tesseract-lang` (macOS) o `sudo apt-get install tesseract-ocr
tesseract-ocr-ita` (Debian/Ubuntu).

I check del Modulo 1 (dettaglio in [wiki/04](docs/wiki/04-checklist-modulo1.md)):
base giuridica dell'autotutela, termine dei 12 mesi, qualità della motivazione
(LLM locale, opzionale), comunicazione di avvio del procedimento, coerenza dei
firmatari, divulgazione di dati personali senza notifica al Garante (GDPR).

## Raccolta e dashboard (Moduli 2 e 3)

```bash
pip install -e '.[all]'

# un comune, due pagine, su un DB di prova
python scripts/run_scrapers.py --scrapers ragusa --max-pagine 2 --db /tmp/prova.db

# dashboard locale
TALIA_DB=/tmp/prova.db streamlit run src/talia/modulo3_dashboard/app.py
```

Il run completo gira ogni notte con `scripts/run_daily.sh`
([wiki/15](docs/wiki/15-run-automatico.md)). Gira in locale e non in CI perché
alcuni portali bloccano gli IP dei datacenter. Gli scraper si presentano con un
User-Agent identificabile e rallentano tra una richiesta e l'altra: **se il
gestore di un portale chiede di fermarsi, ci si ferma.**

## Contribuire

Il progetto cerca soprattutto:

- **giuristi** (diritto amministrativo, contratti pubblici) per validare i check
  e dire quando una segnalazione è sbagliata;
- **sviluppatori Python** per scraper di nuove piattaforme e nuove regole;
- **giornalisti e attivisti** che conoscono i casi reali da cui imparare.

Leggi [CONTRIBUTING.md](CONTRIBUTING.md). Il lavoro è organizzato in card sulla
[board](docs/cards/BOARD.md); la visione completa è in [`talia.md`](talia.md),
la documentazione tecnica nella [wiki](docs/wiki/00-home.md).

## Licenza

[AGPL-3.0-or-later](LICENSE): chi offre TALIA come servizio deve pubblicare
anche le proprie modifiche, perché il progetto resti un bene comune.
