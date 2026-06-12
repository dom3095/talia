# 11 — Implementazione del motore e del Modulo 1

[← Home](00-home.md)

Stato dell'implementazione (Sprint 1, branch `feat/TAL-1-modulo1-prototipo`).
Riferimento all'architettura concettuale: [02 — Architettura](02-architettura.md).

## Layout del codice

```
src/talia/
├── engine/                      # motore comune (puro, non sa nulla dei moduli)
│   ├── models.py                # TestoAtto, PaginaTesto, Entita, Citazione, Stato
│   ├── pdf_text.py              # TAL-3: estrazione testo (nativo + OCR), da_pagine/da_testo
│   ├── entita.py                # TAL-4: date, importi, CIG, CUP (regex documentate)
│   ├── firmatari.py             # TAL-5: norme citate + firmatari (euristica)
│   ├── fascicolo.py             # AttoAnalizzato, ContestoFascicolo, RuoloAtto
│   └── checklist/
│       ├── base.py              # EsitoCheck, classe Check, registry, esegui_checklist
│       ├── check1_base_giuridica.py   # TAL-6
│       ├── check2_termini.py          # TAL-7
│       ├── check5_avvio.py            # TAL-8
│       └── check6_firmatari.py        # TAL-9
└── modulo1_fascicolo/
    ├── analisi.py               # orchestrazione: testi → ruoli → contesto → report
    ├── report.py                # TAL-10: Report + rese markdown/JSON/HTML
    └── cli.py                   # `talia analizza ...`
```

## Decisioni di design

1. **Esplicabilità come tipo.** Ogni `Entita` e ogni `Citazione` porta offset di
   carattere + pagina; `TestoAtto` mantiene il mapping testo→pagina
   (`PaginaTesto`). Un esito di check senza citazione è ammesso solo quando
   segnala un'**assenza** (es. check 5 rosso).
2. **Dipendenze pesanti opzionali.** Il core (entità, checklist, report) gira con
   la sola standard library. `pdfplumber`/`pytesseract` sono extra `[pdf]` a
   import lazy con messaggio d'errore esplicativo; spaCy (extra `[nlp]`) non è
   ancora usato — l'estrazione attuale è regex/euristica pura.
3. **Registry dei check.** Ogni check si auto-registra all'import
   (`checklist/__init__.py`); `esegui_checklist` li esegue tutti e include anche
   i NON_APPLICABILI nel report, per trasparenza su cosa è stato valutato.
4. **Check conservativi.** In dubbio l'esito è 🟡 con spiegazione, mai crash né
   🔴 azzardato (es. stesso firmatario → 🟡, non 🔴, perché fisiologico nei
   piccoli comuni).
5. **Report senza framework.** HTML statico generato in puro Python con escaping;
   JSON per integrazioni; markdown per la CLI. Streamlit resta al Modulo 3.

## Pipeline del Modulo 1

```
.pdf/.txt → estrai_testo / da_pagine     (TestoAtto, pagine+offset)
          → estrai_entita                (date, importi, CIG/CUP, norme, firmatari)
          → classifica_ruolo             (originario vs autotutela, euristica)
          → costruisci_contesto          (ContestoFascicolo)
          → esegui_checklist             (esiti 🟢🟡🔴⚪ con citazioni)
          → Report                       (markdown / JSON / HTML + disclaimer)
```

Uso: `talia analizza data/samples/fascicolo_coerente/ --formato html --out report.html`.

## Assunzioni da validare con ⚖️ LEX

- **Check 1**: liste di parole spia per motivazione da revoca vs annullamento
  (`check1_base_giuridica.py`).
- **Check 2**: scelta delle date (più antica dell'originario vs più recente
  dell'autotutela come proxy di adozione); soglia 365 giorni + tolleranza 30.
- **Check 5**: quali formule contano come menzione dell'art. 7; quando dare 🟡.

## Campioni di test

`data/samples/` contiene due fascicoli **sintetici e anonimizzati** (dati di
fantasia, dichiarato nell'intestazione):

- `fascicolo_coerente/` — annullamento ex 21-nonies entro 12 mesi, motivazione
  di illegittimità, art. 7 menzionato, firmatari diversi → tutto 🟢.
- `fascicolo_critico/` — 21-nonies ma motivazione da revoca (🔴), oltre 12 mesi
  (🔴), nessun art. 7 (🔴), stesso firmatario (🟡).

Manca ancora un PDF scansionato per il test OCR reale (vedi TAL-3).

## Lezioni dal primo fascicolo reale (TAL-12, 1/10)

Il primo fascicolo reale (revoca di selezione interna, provincia AG — PDF **non**
committati, fonti in `data/samples/1/sources.json`) ha fatto emergere e correggere
tre bug:

1. **Boilerplate dei bandi.** "L'amministrazione si riserva di revocare…" faceva
   classificare il bando come autotutela → classificazione a punteggio pesato
   (`punteggi_ruolo`): segnali forti ("in autotutela", 21-quinquies/nonies) vs
   deboli (sostantivo "revoca"; l'infinito "revocare" è escluso).
2. **Ordine dei file.** Con più candidati autotutela vinceva il primo in ordine
   alfabetico → ora vince il punteggio massimo.
3. **Secondo nome omesso.** "Pietro Amorosia" vs "Pietro Nicola Amorosia" non
   matchavano nel check 6 (falso 🟢) → matching per sottoinsieme (≥2 token comuni,
   un insieme contenuto nell'altro). Il solo cognome condiviso resta non-match.

Inoltre: trattino reso opzionale in "21(-)quinquies/nonies" (gli atti reali lo
omettono spesso). Annotato per follow-up: le date dei CCNL citati ("16.11.2022")
possono inquinare la stima delle date del check 2.

## Attori e procedimenti (TAL-13)

`engine/attori.py` estrae **attori** (ruolo istituzionale → nome, anche da firme
digitali "NOME COGNOME / Provider") e **riferimenti ad atti** (tipo, numero/anno,
data) per ricostruire la catena del procedimento — base del futuro check 7.
Lo script interno `scripts/estrai_attori.py` produce il report per fascicolo
(⚠️ nomi reali: mai committare l'output) con un livello **NER spaCy opzionale**
per scoprire pattern non coperti dalle regex.

Esito sul fascicolo reale 1: il deterministico ricostruisce attori e catena
completa; il NER `it_core_news_sm` è troppo rumoroso sul lessico giuridico e
resta strumento di discovery, fuori dal motore (riprovare con `it_core_news_lg`).

[→ 03 Stack](03-stack.md)
