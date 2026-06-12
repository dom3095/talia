# 06 — Corpus normativo

[← Home](00-home.md)

**Approccio RAG, non fine-tuning.** Le norme cambiano: il corpus va aggiornato come *retrieval*, non
imparato a memoria dal modello. Ogni riferimento citato nel report deve puntare a un testo verificabile.

## Nazionale

- **D.lgs. 36/2023** — Codice contratti pubblici (+ correttivi)
- **L. 241/1990** — procedimento amministrativo (artt. 7, 21-*quinquies*, 21-*nonies*)
- **L. 190/2012** — anticorruzione; PTPCT
- **D.lgs. 33/2013** — trasparenza
- **GDPR + Codice privacy** — dati personali pubblicati per errore negli atti
- **D.lgs. 39/2013 e art. 6-bis L. 241** — conflitti d'interesse, inconferibilità

## Sicilia (statuto speciale)

- Leggi regionali di recepimento del Codice appalti (**verificare stato recepimento D.lgs. 36/2023**; storicamente L.R. 12/2011 e ss.)
- **L.R. 7/2019** — procedimento amministrativo regionale
- Disciplina **UREGA** — gare centralizzate sopra soglia
- Normativa **antimafia** — protocolli di legalità, white list, interdittive
- Giurisprudenza: **CGA** (Consiglio di Giustizia Amministrativa), **TAR Palermo**, **TAR Catania**

## ⚠️ Cautela per chi sviluppa

- Lo statuto speciale siciliano rende il quadro **diverso** da quello nazionale: verificare sempre il recepimento regionale prima di applicare una norma statale.
- Mai inventare o "ricordare" articoli: se incerto, segnalare l'incertezza nel report.
- Il corpus è dati, versionato e datato: ogni norma ha data di vigenza.

## Struttura suggerita del corpus (`data/corpus_normativo/`)

```
corpus_normativo/
├── nazionale/
│   ├── dlgs-36-2023.md
│   ├── l-241-1990.md
│   └── ...
├── sicilia/
│   ├── lr-7-2019.md
│   ├── urega/
│   └── ...
└── giurisprudenza/
    ├── cga/
    ├── tar-pa/
    └── tar-ct/
```

[→ 07 Fonti dati](07-fonti-dati.md)
