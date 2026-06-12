# TAL-3 — Estrazione testo da PDF (nativo + OCR)

- **Epica:** E1 — Motore + Modulo 1
- **Ruolo:** 🔤 NLP
- **Priorità:** P0
- **Stato:** To Do
- **Branch:** `feat/TAL-3-pdf-text`

## 🎯 Obiettivo
Funzione `estrai_testo(pdf) -> TestoAtto` che gestisce sia PDF nativi sia scansioni (OCR).

## 📚 Contesto
Primo stadio del motore ([wiki/02](../wiki/02-architettura.md)). Molti atti sono scansioni → Tesseract.

## ✅ Task
- [ ] Rilevare se il PDF ha testo nativo o è immagine
- [ ] Estrazione nativa (pdfplumber/pypdf) con offset di carattere/posizione
- [ ] Fallback OCR Tesseract (`ita`) per le scansioni
- [ ] Conservare mapping testo→pagina per l'esplicabilità (citazioni)
- [ ] Modello dati `TestoAtto` (testo, pagine, fonte, metadati)

## 🧪 Criteri di accettazione
- [ ] Estrae testo corretto da un PDF nativo campione
- [ ] Estrae testo da una scansione campione via OCR
- [ ] Ogni porzione di testo è risalibile alla pagina (serve per citazioni)
- [ ] Test su `data/samples/` (anonimizzati)

## 🔗 Dipendenze
TAL-1.

## 📝 Note
Tesseract con `lang=ita`. Valutare pre-processing immagine (deskew/threshold) se OCR scarso.
Serve almeno 1 PDF nativo + 1 scansione in `data/samples/`.
