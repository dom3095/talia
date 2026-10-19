# TAL-73 — Red flag di frazionamento: misurare i falsi positivi prima di pubblicare

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🔤 NLP + ⚖️ LEX
- **Priorità:** P1 (blocca la pubblicazione della dashboard: 12.892 flag su 13.964)
- **Stato:** Review — misura eseguita sul DB reale (2026-10-19); mancano l'etichettatura e la decisione sulla regola
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
- [x] Lanciare lo script su `talia.db` e riportare qui la tabella di `diagnosi.md` (Tentativo 2)
- [x] Correggere lo script: H4/H5 non misuravano nulla sui dati ANAC reali (Tentativo 2)
- [ ] Etichettare il campione. **Lo strato è uno solo** (`solo_anac`, 12.892 su 12.892): sono 20 flag, non 60
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

### 2026-10-19 — Tentativo 2 (misura sul DB reale)
**Approccio:** `python scripts/diagnosi_frazionamento.py` su `talia.db` (sola
lettura, ~2 min).
**Esito:** ⚠️ parziale — il primo giro dava numeri fuorvianti, corretti.
**Appreso:**

1. **Il primo giro era uno strumento rotto sui dati reali.** In SmartCIG
   `atti.oggetto` contiene solo `SERVIZI` / `FORNITURE` / `LAVORI` (3 valori
   distinti su 176.827 righe) e `metadati.tipo_appalto` è sempre vuoto. H5
   risultava "eterogeneo" per il **100%** (nessun testo da confrontare) e H4 a 0
   (cercava il tipo nel posto sbagliato): "0 superstiti" non significava nulla.
   I fixture dei test usavano oggetti descrittivi e non riproducevano la forma
   vera dei dati. Ora il tipo si legge anche da `oggetto`, H5 dichiara "non
   valutabile" dove mancano testi confrontabili, il report avverte quando il
   conteggio dei superstiti è solo un limite, e ci sono test con atti nella
   forma ANAC reale.
2. **Tutti i 12.892 flag sono `solo_anac`**, su 142 enti. Gli atti d'albo non
   producono alcun `frazionamento`: il campione è di un solo strato.
3. **H1 (accumulo tra run) non si conferma: 0 flag superati.** Il sospetto
   nato leggendo `salva_red_flag` non spiega il numero. Il bug dei flag mai
   cancellati resta teoricamente vero, ma non pesa qui.
4. **H2: 4.923 flag (38%) contenuti in un altro** dello stesso ente.
5. **H3: 0** — ogni atto SmartCIG ha un CIG proprio; banale, non informativo.
6. **H4 (lavori + beni/servizi): 12.794 (99%)**, ma da leggere con
   cautela: dice soprattutto che le finestre sono enormi.
7. **Il dato decisivo è la dimensione dei flag:** nessuno ha meno di **24 atti**,
   mediana **190**, 90° percentile 932, massimo **12.150**; **11.409 (88%) ne
   hanno almeno 100**. Gli importi sono micro-affidamenti: **100% sotto 5.000 €,
   media 1.449 €**. Un "frazionamento" di 190 affidamenti da ~1,4k€ non è un
   appalto spezzato, è il volume di attività ordinario di un ente in 90 giorni
   (primo flag del campione: Ragusa, 939 atti, 1,18 M€).
8. Per distinguere un vero frazionamento mancano i dati: **né operatore
   economico né CPV** sono persistiti per ANAC (lo dice già la Spec).

**Proposta, non decisione** (le domande aperte sono di Dom): escludere SmartCIG
dalla regola `frazionamento`, come TAL-71 ha escluso la fonte dalle strategie
fuzzy della catena; riservare la regola agli atti d'albo, dove c'è un oggetto
descrittivo, finché non si persistono aggiudicatario e CPV. Prima di decidere
vale guardare 5-10 flag del campione a mano.

## 🔗 Dipendenze

TAL-70 (dati ANAC), TAL-71 (fase red flags). Per H3 su atti d'albo e ANAC
della stessa gara, beneficia di TAL-64 (`atti_fonti`).

## 📝 Note

Lo stesso accumulo H1 potrebbe riguardare anche gli altri red flag con finestre
mobili (`concentrazione`, `tempi_anomali`): da verificare quando si corregge.
