# TAL-3 — Estrazione testo da PDF (nativo + OCR)

- **Epica:** E1 — Motore + Modulo 1
- **Ruolo:** 🔤 NLP
- **Priorità:** P0
- **Stato:** Review
- **Branch:** `feat/TAL-1-modulo1-prototipo` (sviluppo congiunto Sprint 1)

## 🎯 Obiettivo
Funzione `estrai_testo(pdf) -> TestoAtto` che gestisce sia PDF nativi sia scansioni (OCR).

## 📚 Contesto
Primo stadio del motore ([wiki/02](../wiki/02-architettura.md)). Molti atti sono scansioni → Tesseract.

## ✅ Task
- [x] Rilevare se il PDF ha testo nativo o è immagine
- [x] Estrazione nativa (pdfplumber/pypdf) con offset di carattere/posizione
- [x] Fallback OCR Tesseract (`ita`) per le scansioni
- [x] Conservare mapping testo→pagina per l'esplicabilità (citazioni)
- [x] Modello dati `TestoAtto` (testo, pagine, fonte, metadati)

## 🧪 Criteri di accettazione
- [x] Estrae testo corretto da un PDF nativo campione
- [ ] Estrae testo da una scansione campione via OCR
- [x] Ogni porzione di testo è risalibile alla pagina (serve per citazioni)
- [x] Test su `data/samples/` (anonimizzati)

## 🔗 Dipendenze
TAL-1.

## 📝 Note
Tesseract con `lang=ita`. Valutare pre-processing immagine (deskew/threshold) se OCR scarso.
Serve almeno 1 PDF nativo + 1 scansione in `data/samples/`.

## 📦 Consuntivo (12/06/2026)

Implementato in `src/talia/engine/pdf_text.py`: `estrai_testo(pdf) -> TestoAtto` con
rilevamento pagina nativa vs scansione (soglia caratteri) e fallback OCR Tesseract `ita`
per pagina; fonte NATIVO/OCR/MISTO. Mapping testo→pagina via offset (`PaginaTesto`),
`TestoAtto.pagina_per_offset` ed `estratto()` per le citazioni. Costruttori `da_pagine`/
`da_testo` senza dipendenze esterne per test e campioni `.txt`.
**Aperto:** manca un PDF scansionato campione in `data/samples/` per il test OCR reale
(oggi i test usano `.txt`); import lazy di pdfplumber/pytesseract con errore esplicativo.
