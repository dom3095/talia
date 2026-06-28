# 02 — Architettura

[← Home](00-home.md)

## Schema generale: tre moduli, un motore

```
            ┌─────────────────────────────────────────────┐
            │           MOTORE DI ANALISI COMUNE           │
            │  OCR (Tesseract) → estrazione testo PDF      │
            │  Estrazione entità: date, importi, CIG,      │
            │  firmatari, norme citate (regex + spaCy)     │
            │  Checklist deterministiche (regole/SQL)      │
            │  RAG normativo + LLM (solo casi filtrati)    │
            └───────┬──────────────┬──────────────┬────────┘
                    │              │              │
        ┌───────────▼───┐  ┌───────▼───────┐  ┌──▼───────────────┐
        │ MODULO 1      │  │ MODULO 2      │  │ MODULO 3         │
        │ Analisi       │  │ Scraping      │  │ Dashboard        │
        │ fascicolo     │  │ continuo      │  │ aggregata        │
        │ on-demand     │  │ (batch)       │  │ per comune       │
        └───────────────┘  └───────────────┘  └──────────────────┘
```

## Il motore comune (`src/talia/engine/`)

Pipeline a stadi, ognuno isolabile e testabile:

1. **OCR / estrazione testo** — molti atti sono scansioni → Tesseract. Per i PDF nativi, estrazione diretta.
2. **Estrazione entità** — date, importi, CIG, firmatari, norme citate. Regex per i pattern rigidi, spaCy per le entità sfumate.
3. **Checklist deterministiche** — regole espresse come SQL/funzioni pure. Producono check verde/giallo/rosso.
4. **RAG normativo + LLM** — **solo** sui documenti già flaggati e solo dove serve giudizio testuale (qualità della motivazione). Il corpus normativo è retrieval, non fine-tuning (le norme cambiano).

> **Principio chiave:** il 95% dei controlli è regex + SQL. L'LLM è l'eccezione, non la regola.

## Modulo 1 — Analisi fascicolo on-demand (PRIORITÀ 1)

L'utente carica un fascicolo (es. delibera di indizione concorso + atto di annullamento) e ottiene un
**report strutturato**: check verde/giallo/rosso, passaggio testuale citato, norma/giurisprudenza di
riferimento, disclaimer. → vedi [04 Checklist](04-checklist-modulo1.md).

## Modulo 2 — Pipeline di scraping

Raccolta **continua** degli atti pubblicati (albi pretori, ANAC, GURS, UREGA) per alimentare storico e
statistiche. Parte da **un solo software di albo pretorio** o una sola provincia.
→ vedi [05 Red flags batch](05-red-flags-batch.md) e [07 Fonti dati](07-fonti-dati.md).

### Pipeline scraping in due fasi

Il download dei PDF avviene **solo su atti già segnalati**, non su tutto il corpus:

```
FASE 1 — metadati (sempre)
  scraping albo pretorio
    → tipo, numero, oggetto, date, url_fonte
    → red flag batch su metadati (regex + SQL)
    → atti sospetti → coda `da_analizzare`

FASE 2 — PDF on-demand (solo flag positivi)
  download allegati da url_fonte
    → OCR se scansione (Tesseract)
    → estrazione entità (regex + spaCy)
    → checklist deterministiche contenuto
    → LLM solo su casi filtrati (qualità motivazione, GDPR, ecc.)
```

**Perché non scaricare tutto?** Su un comune medio ~5-10 revoche/annullamenti/anno su 500+ atti totali.
Scaricare solo i flaggati riduce il traffico al 2% e rende il sistema scalabile a centinaia di comuni.

**Segnali che attivano la Fase 2** (keyword nell'oggetto):
`REVOCA`, `ANNULLAMENTO`, `SOSPENSIONE`, `AUTOTUTELA`, `DECADENZA`, `IRREGOLARITÀ`

## Modulo 3 — Dashboard per comune

Aggregazioni dei risultati: indici, trend, confronti tra pari (comuni di taglia simile), drill-down fino
al documento sorgente. **MVP implementato (TAL-30).**

### Funzionalità MVP (`src/talia/modulo3_dashboard/app.py`)

- **Panoramica comuni** — tabella con conteggio red flags per tipo (frazionamento, concentrazione, tempi)
  e severità (alta/media/bassa), ordinata per numero di segnalazioni.
- **Drill-down** — per ogni red flag: descrizione, periodo, elenco atti/CIG con link diretto a `url_fonte`.
- **Comuni virtuosi** — sezione dedicata ai comuni senza segnalazioni (principio di simmetria).
- **Anonimizzazione** — per comuni < 5.000 abitanti il drill-down nominativo è disabilitato; vengono
  mostrate solo le aggregazioni (tutela privacy in contesti dove i soggetti sono identificabilissimi).
- **Disclaimer permanente** in cima alla pagina: *"Segnalazioni da verificare, non accertamenti."*

### Avvio

```bash
TALIA_DB=talia.db streamlit run src/talia/modulo3_dashboard/app.py
```

## Confini tra i moduli

- Il **motore** non sa nulla dei moduli: espone funzioni pure (testo → entità → check).
- Il **Modulo 1** è sincrono, single-document, user-facing.
- Il **Modulo 2** è batch/asincrono, popola il DB.
- Il **Modulo 3** legge solo dal DB, non analizza.

[→ 03 Stack](03-stack.md)