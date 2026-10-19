# TAL-73 — Red flag di frazionamento: misurare i falsi positivi prima di pubblicare

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🔤 NLP + ⚖️ LEX
- **Priorità:** P1 (blocca la pubblicazione della dashboard: 12.892 flag su 13.964)
- **Stato:** Review — strumento di misura pronto; mancano la misura sul DB reale e l'etichettatura
- **Branch:** `feat/TAL-73-diagnosi-frazionamento`

## 🎯 Obiettivo

Sapere quanti dei red flag `frazionamento` sono rumore, e **perché**, prima che
compaiano in una vista pubblica — e decidere la correzione della regola sui
numeri invece che su un'impressione.

## 📋 Spec

### Il problema

Dopo il caricamento SmartCIG (TAL-70) i red flag sono passati da 665 a 13.964,
di cui **12.892 `frazionamento`** (HANDOFF, sessione TAL-71). SmartCIG contiene
per definizione affidamenti sotto soglia: la regola attuale
(`red_flags/frazionamento.py` — ≥3 atti sotto 140k€ in 90 giorni, totale
oltre 140k€, **per ente**) lì trova un terreno dove quasi tutto somiglia a un
segnale. Pubblicarli così vorrebbe dire violare il principio n. 1 di
`CLAUDE.md` con migliaia di segnalazioni non difendibili.

### Ipotesi di falso positivo strutturale (dalla lettura della regola)

Misurabili senza leggere gli atti, una per una correzione candidata:

| # | Ipotesi | Correzione candidata |
|---|---|---|
| H1 | **Flag superati**: la finestra si allunga a ogni run (`periodo_a` cambia), l'unique su `(ente, tipo, periodo_da, periodo_a)` non sostituisce il vecchio e i flag non vengono mai ripuliti | ricalcolo completo: cancellare i `frazionamento` prima di riscriverli |
| H2 | **Flag contenuti**: una finestra per ogni atto-ancora → decine di flag sullo stesso gruppo | una sola finestra massimale per gruppo |
| H3 | **Stesso CIG contato più volte**: contratto ANAC + determina d'albo + liquidazione della stessa gara sommati come affidamenti distinti | sommare per CIG distinto |
| H4 | **Tipi di appalto mescolati**: lavori (soglia 150k€) con forniture/servizi (140k€) | raggruppare per `tipo_appalto` e soglia corretta |
| H5 | **Oggetti eterogenei**: cancelleria + strade + mensa non sono un appalto spezzato | richiedere ≥3 atti con oggetto simile |

Fuori dalla misura automatica, da valutare con ⚖️ LEX: il frazionamento
rilevante è sullo **stesso operatore economico** o sulla stessa categoria
merceologica (CPV) — dati che oggi non persistiamo (né aggiudicatario né CPV
nei `metadati` ANAC).

### Interfaccia

```bash
python scripts/diagnosi_frazionamento.py [--db talia.db] [--per-strato 20] [--seme 72]
# → reports/tal73/diagnosi.md  (conteggi per ipotesi, % e superstiti)
# → reports/tal73/campione.csv (flag da etichettare: esito, note)
```

Sola lettura (`mode=ro`). `reports/` è in `.gitignore`: contiene oggetti e URL
di atti reali.

### Casi limite

- Le ipotesi si sovrappongono: le percentuali non si sommano, conta il
  numero di **superstiti** (flag che resistono a tutte).
- H5 usa una similarità di token deliberatamente bassa (Jaccard ≥ 0,35):
  serve a *escludere* i casi palesemente eterogenei, non a confermare quelli
  omogenei.
- Atti senza `tipo_appalto` (tutti quelli d'albo) non contano per H4.

## ❓ Domande aperte

- [ ] Quale tasso di falsi positivi è accettabile per pubblicare? (stesso
      criterio "rumore gestibile" di TAL-12, da fissare con Dom)
- [ ] La correzione della regola (H1-H5) si decide **dopo** aver visto i
      numeri: non implementare prima.

## 📚 Contesto

- [TAL-23](TAL-23.md) — la regola originale
- [TAL-70](TAL-70.md), [TAL-71](TAL-71.md) — il caricamento ANAC e l'esplosione dei flag
- [`docs/wiki/05-red-flags-batch.md`](../wiki/05-red-flags-batch.md)

## ✅ Task

- [x] Diagnosi strutturale (H1-H5) e campione stratificato per fonte
      (`red_flags/diagnosi_frazionamento.py` + `scripts/diagnosi_frazionamento.py`)
- [x] Test su flag prodotti dalla regola vera, uno scenario per ipotesi
- [ ] Lanciare lo script su `talia.db` e riportare qui la tabella di `diagnosi.md`
- [ ] Etichettare il campione (60 flag: 20 per strato) e stimare il tasso di FP
- [ ] Decidere le correzioni della regola e aprire la card di implementazione

## 🧪 Criteri di accettazione

- [ ] Tasso di falsi positivi stimato per strato (ANAC / Albo / misto), con
      il campione etichettato allegato alla card (non nel repo)
- [ ] Ogni correzione della regola giustificata da un numero di questa card
- [x] Test passano (`pytest`)

## 🔬 Tentativi

### 2026-10-19 — Tentativo 1 (strumento di misura)
**Approccio:** invece di correggere la regola a occhio, uno script che misura
ciascuna ipotesi sul DB reale e prepara un campione da etichettare. Sessione da
cloud senza accesso a `talia.db`: lo script è verificato su flag sintetici
prodotti dalla regola vera, non ancora sui dati.
**Esito:** ✅ strumento; ⏳ misura
**Appreso:** leggendo la regola per scrivere la diagnosi è emersa H1, che non
era tra i sospetti: `salva_red_flag` fa `INSERT OR REPLACE` su
`(ente, tipo, periodo_da, periodo_a)` e nessuno cancella i flag del giro
precedente, quindi ogni allungamento di finestra lascia indietro un flag
vecchio. Parte dei 12.892 potrebbe essere accumulo tra run, non segnali
distinti — la diagnosi lo conta.

## 🔗 Dipendenze

TAL-70 (dati ANAC), TAL-71 (fase red flags). Per H3 su atti d'albo e ANAC
della stessa gara, beneficia di TAL-64 (`atti_fonti`).

## 📝 Note

Lo stesso accumulo H1 potrebbe riguardare anche gli altri red flag con finestre
mobili (`concentrazione`, `tempi_anomali`): da verificare quando si corregge.
