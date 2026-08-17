# TAL-64 — Deduplicazione atti: schema normalizzato `atti` / `atti_fonti`

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🕷️ SCR
- **Priorità:** P1 (blocca la messa in produzione di TAL-62 — Amministrazione Trasparente)
- **Stato:** To Do (spec confermata con Dom, non ancora implementata)
- **Branch:** `feat/TAL-60-streamlit-modulo1` (o nuovo branch dedicato in apertura lavori)

## 🎯 Obiettivo

Risolvere le due domande bloccanti lasciate aperte da [TAL-62](TAL-62.md): un atto
pubblicato sia sull'Albo Pretorio sia su Amministrazione Trasparente (stesso
documento reale, fonti diverse) non deve generare due righe indipendenti in
`atti` — oggi lo fa su Halley (0% dedup) e lo evita solo per caso su jCityGov
(stesso URL, ma con perdita silenziosa dell'informazione "ritenzione lunga" per
insert-or-ignore).

## 📚 Contesto

Segnalato da Dom mentre si discuteva la strategia di dedup: CIG, data di
pubblicazione e RUP sono proprietà del documento reale, non del portale da cui
l'abbiamo scaricato — tenerle duplicate su più righe è fragile (rischio di
valori discordanti tra le due copie). Verificato che il RUP oggi **non è
persistito da nessuna parte** (`engine/attori.py` lo estrae ma resta dato
transiente, usato solo dal check 6 di Modulo 1) — fuori scope qui, ma lo schema
nuovo gli dà una casa naturale in futuro (`atti.metadati` o colonna dedicata).

Verificato anche: Amministrazione Trasparente **non è ancora collegata al run
automatico** ([TAL-62](TAL-62.md)), quindi in `talia.db` oggi non esiste ancora
nessun atto realmente duplicato — la migrazione dei ~85k `atti` esistenti è un
1:1 puro (ogni riga → un `atto` + una `fonte`), senza merge da gestire.

Probabile causa della segnalazione "le catene hanno dei problemi" (Dom,
2026-08-16, non ancora approfondita): `catena.py` raggruppa per CIG assumendo
un atto = una riga; un atto raccolto da due fonti con lo stesso CIG produrrebbe
oggi due eventi nella stessa catena invece di uno. Da confermare quando si
approfondisce quella segnalazione — non certezza, solo ipotesi plausibile.

## ✅ Task

- [x] Ingest sperimentale ~1000 atti reali in tabella di staging (Tentativo 1)
- [x] Prova matching CIG/tipo+numero su jCityGov (Tentativo 1)
- [x] Indagare perché Halley AT non ha CIG/numero al livello di lista (Tentativo 2) — non è un bug: la pagina lista non li espone affatto, solo il PDF potrebbe averli
- [x] Notebook ripetibile per jCityGov (`notebooks/tal64_dedup_jcitygov.ipynb`) — trovato che il CIG da solo dà falsi positivi (40% dei CIG copre più atti), rivista la chiave in `(ente_id, cig, numero)`, ambigua solo nel 6,2% dei casi
- [x] Verificare se le gare Halley sono altrove (Tentativo 3) — no, sono già nell'Albo Pretorio; il gap AT reale sono i concorsi
- [x] Fattibilità download+estrazione PDF per Halley (Tentativo 4) — fattibile, riusa `engine.pdf_text.estrai_testo()`, numero estraibile su 3/5 PDF di prova, CIG assente per natura (concorsi)
- [ ] Rivedere la chiave di fallback `(tipo, numero, data_atto)` della spec
      rimuovendo `data_atto` (mai popolato su nessuna delle due piattaforme) —
      usare `(ente_id, cig, numero)` con fallback `(ente_id, tipo, numero)`,
      escludendo sempre `numero="0"` (sentinella)
- [ ] Decidere/implementare TAL-62 #2 (persistenza testo) almeno per i
      concorsi Halley, riusando `estrai_testo()` — validare il pattern
      numero su un campione più ampio di 5 PDF prima di fidarsene
- [x] Indagare il bug collaterale del CIG `"ORIGINARIO"` — risolto in
      [TAL-65](TAL-65.md): CIG padre/derivato scambiati o persi in 3 punti
      del codice (`utils.py`, `entita.py`, `catena.py`), non solo un
      placeholder isolato; 3585+235 atti corretti sul DB reale
- [ ] Gestire esplicitamente l'ambiguità residua della chiave jCityGov
      (6,2% dei casi) in `inserisci_atto()` — non deduplicare se la chiave
      non è univoca, inserire comunque come atto nuovo
- [ ] Solo dopo le decisioni sopra: implementare lo schema definitivo
      (`atti`/`atti_fonti`) e la migrazione

## 📋 Spec

**Schema:**

```sql
-- proprietà del documento reale, indipendenti da dove l'abbiamo trovato
CREATE TABLE atti (
    id             INTEGER PRIMARY KEY,
    ente_id        INTEGER NOT NULL REFERENCES enti(id),
    tipo           TEXT    NOT NULL,
    numero         TEXT,
    data_atto      TEXT,
    cig            TEXT,
    oggetto        TEXT,
    importo_euro   REAL,
    testo_estratto TEXT,
    metadati       TEXT    NOT NULL DEFAULT '{}'
);

-- una riga per ogni copia/pubblicazione trovata su un portale
CREATE TABLE atti_fonti (
    id             INTEGER PRIMARY KEY,
    atto_id        INTEGER NOT NULL REFERENCES atti(id),
    fonte_scraper  TEXT    NOT NULL,
    url_fonte      TEXT    NOT NULL,
    url_pdf        TEXT,
    data_pub       TEXT,
    data_scadenza  TEXT,
    data_accesso   TEXT    NOT NULL,
    hash_sha256    TEXT,
    UNIQUE (atto_id, url_fonte)
);
```

**Identità dell'atto (per il find-or-create in `inserisci_atto()`):**
- Se `cig` presente su entrambi i lati → match **esatto o niente** (confermato
  da Dom: un CIG identifica una gara in modo univoco, nessun matching parziale/fuzzy).
- Se `cig` assente (concorsi, delibere senza gara) → fallback su
  `(ente_id, tipo, numero, data_atto)` tutti uguali.
- Nessun matching su `oggetto` per il dedup stesso (resta riservato alle
  strategie più deboli/esplicite di `catena.py` per collegare atti *diversi*
  correlati — mescolarlo qui rischierebbe di fondere atti realmente distinti).
- **Aggiornamento post [TAL-65](TAL-65.md)**: esiste ora anche `cig_padre`
  (CIG dell'eventuale accordo quadro). **Non va usato per l'identità
  dell'atto** — un CIG padre è condiviso da molte adesioni distinte, è
  esattamente il tipo di falso positivo trovato nel notebook (Prova 2).
  Chiave di identità sempre e solo sul `cig` proprio/derivato.

**Migrazione dati esistenti:** 85.435 righe di `atti` → split 1:1 in `atti` +
`atti_fonti`, nessun merge necessario (vedi Contesto). Backup del DB prima,
stesso schema già seguito per TAL-61/TAL-63.

**File impattati:**
- `src/talia/modulo2_scraping/db.py`: schema, `inserisci_atto()` → find-or-create
  atto + insert fonte.
- `src/talia/engine/catena.py`: query di raggruppamento per CIG operano ora su
  `atti` deduplicato (dovrebbe risolvere/ridurre il problema catene segnalato
  da Dom — da verificare quando si affronta quella segnalazione).
- `src/talia/modulo3_dashboard/`: ogni lettura diretta di `atti.url_fonte` /
  `atti.fonte_scraper` va aggiornata per leggere da `atti_fonti` (e scegliere,
  quando ce n'è più di una, la fonte con `data_scadenza` più lontana per il
  link mostrato all'utente — chiude anche il problema originale dei link
  scaduti che aveva aperto tutto il filone TAL-62).
- `red_flags.atti_cig`: oggi salva una copia JSON denormalizzata dell'URL
  (causa del bug di sincronizzazione trovato in TAL-63) — da cambiare per
  salvare `atto_id` e risolvere l'URL a runtime.
- Tutti gli scraper in `src/talia/modulo2_scraping/fonti/`: nessuna modifica
  di logica prevista (continuano a chiamare `inserisci_atto()` con gli stessi
  parametri), ma va verificato scraper per scraper in fase di test.

## ❓ Domande aperte

- [x] `data_pub`: per-fonte, non canonica (confermato da Dom — Albo e AT sono
      due eventi di pubblicazione reali distinti anche per lo stesso atto).
- [x] Matching CIG: esatto o niente, nessun fuzzy (confermato da Dom).
- [ ] Nessun'altra domanda aperta bloccante.

## 🔬 Tentativi

### 2026-08-16 — Tentativo 1: ingest sperimentale + prova di identità su dati reali

**Approccio:** su richiesta di Dom, prima di implementare lo schema definitivo:
ingest di ~1000 atti reali di Amministrazione Trasparente in una tabella di
staging separata (`atti_trasparenza_staging`, creata da
`scripts/tal64_staging_trasparenza.py`, **non** nella DDL principale di
`db.py` — non tocca `atti`), poi prova della logica di matching identità
(CIG esatto, poi `tipo+numero` quando univoco) contro `atti` reale.
Backup preso prima (`talia.db.bak-pre-staging-tal64-20260816`).

**Comuni**: 7 jCityGov (Ragusa, Modica, Acireale, Scicli, Giarre, Sant'Agata
li Battiati, Gravina di Catania) + 1 Halley (Aci Bonaccorsi, l'unico
verificato in TAL-62). **1053 atti raccolti** (928 jCityGov + 125 Halley).

**Esito:** ⚠️ parziale — matching funziona ma con limiti reali scoperti sui dati:

1. **Le categorie di default non generalizzano.** `CATEGORIE_TRASPARENZA_DEFAULT`
   (`"Bandi di concorso"`, `"Bandi di gara e contratti"` esatti) hanno dato 0
   atti su 6 tenant su 8 testati inizialmente. Su jCityGov, la riforma
   ANAC 2023 ha frammentato "Bandi di gara e contratti" in sotto-categorie
   con date (es. `"Bandi di gara e contratti - Contratti con bandi e avvisi
   pubblicati dopo il 1 gennaio 2024 - Pubblicazione"`) — servito un match a
   substring (`"bandi" in nome.lower()`) invece del nome esatto. **Su Halley,
   nessuno dei 7 tenant testati oltre Aci Bonaccorsi espone una categoria con
   "bandi" nel nome** — tassonomia D.lgs. 33/2013 molto meno standardizzata
   lì. Non approfondito oltre (fuori scope per un ingest sperimentale).

2. **`data_atto` è 0/1053** — mai valorizzato per nessun atto di Amministrazione
   Trasparente, su nessuna delle due piattaforme. La chiave di fallback
   `(tipo, numero, data_atto)` della spec originale è quindi inutilizzabile
   così com'è: va rivista, probabilmente `(tipo, numero)` da solo quando
   univoco per ente (già usato in questo esperimento), coerente con il
   pattern `COALESCE(data_atto, data_pub)` già in uso altrove nel codebase.

3. **`numero = "0"` come sentinella** in 135/1053 righe (~13%) — placeholder,
   non un vero numero di protocollo. Escluso esplicitamente dal matching
   `(tipo, numero)` per evitare falsi positivi (due bandi diversi con
   `numero="0"` non vanno confusi come lo stesso atto).

4. **jCityGov**: CIG esatto → 250/928 match; `(tipo, numero)` univoco quando
   CIG assente → altri 229/928. **Tutti** i match trovati risultano avere
   *lo stesso identico* `url_fonte` tra staging e `atti` (stesso backend
   "igrid" condiviso, coerente con quanto già noto da TAL-62) — quindi
   questo esperimento **conferma che CIG/numero+tipo sono segnali di
   identità corretti (0 falsi positivi osservati)**, ma non ha ancora
   testato il caso interessante (stesso atto, URL diverso) perché su
   jCityGov quel caso non esiste. 574/928 senza alcun match: presumibilmente
   atti visibili solo in Amministrazione Trasparente (storico più profondo,
   o categorie tipo "Bandi di concorso" non coperte dal run Albo Pretorio
   di default) — comportamento atteso, non un problema.

5. **Halley: 0/125 match, sia per CIG sia per numero — perché il parser
   `_parse_pagina_trasparenza()` non estrae né `cig` né `numero`** per
   nessuna delle 125 righe (0/125 su entrambi i campi). Non è detto che manchi
   sovrapposizione reale con l'Albo Pretorio — è un **buco della fase di
   estrazione**, non ancora capito se recuperabile dall'HTML della pagina o
   assente strutturalmente per questa piattaforma. Impatto: **su Halley la
   strategia di identità attuale non ha alcun segnale**, va capito prima di
   implementare la deduplicazione reale.

**Appreso:** prima di procedere con lo schema definitivo, due cose da
chiudere: (a) rivedere la chiave di fallback rimuovendo `data_atto` (mai
popolato), (b) capire se `numero`/`cig` sono recuperabili dal parser Halley
AT o se serve un'altra strategia di identità per quella piattaforma (es.
match per `oggetto` esatto — non fuzzy — quando numero/cig mancano su
entrambi i lati, da valutare, non ancora deciso).

Tabella di staging lasciata nel DB reale (`talia.db`, 1053 righe) per
proseguire l'analisi senza dover riscaricare dal vivo.

### 2026-08-16 — Tentativo 2: perché Halley AT non ha CIG/numero

**Approccio:** ispezionare l'HTML grezzo delle righe di Amministrazione
Trasparente su Aci Bonaccorsi ("Bandi di concorso") e Melilli ("Informazioni
sui contratti pubblici... art.1 comma 32 L.190/12", l'unica categoria vicina
a "gara" trovata tra i comuni Halley testati) per capire se `numero`/`cig`
sono recuperabili e il parser semplicemente non li estrae, oppure se non
sono strutturalmente presenti nella pagina.

**Esito:** ✅ (capito il perché — non è un bug del parser)
**Appreso:**
- Ogni riga di Amministrazione Trasparente su Halley ha **una sola cella
  utile**: descrizione/titolo del documento + "Inserita il"/"Modificata il".
  Nessun campo "Numero", nessun CIG in chiaro — struttura completamente
  diversa dalle righe dell'Albo Pretorio (`_RE_FIELD`/`<strong>...</strong>`,
  che invece espone `Numero atto` esplicitamente). `_parse_pagina_trasparenza()`
  estrae correttamente tutto ciò che è presente nell'HTML — **non c'è nulla
  in più da estrarre a livello di lista**.
- Il link di ogni riga (`documento/<id>`) è un **download diretto del PDF**
  (`Content-Type: application/pdf`, verificato con l'header HTTP, coerente
  con quanto già trovato in TAL-63 Tentativo 3), non una pagina di dettaglio
  HTML — quindi CIG/numero non sono recuperabili nemmeno con un secondo
  fetch, solo scaricando e leggendo il testo del PDF stesso.
- Su Melilli, la categoria più vicina a "gara" (`art.1 comma 32 L.190/12`)
  contiene solo **dataset XML annuali riassuntivi** (link a
  `dataset/appalti-2022.xml` su un dominio diverso), non singole righe per
  procedura — nessun CIG per-atto nemmeno lì.

**Implicazione:** per Halley, l'unica via per un'identità affidabile
(CIG/numero) è scaricare ed estrarre il testo del PDF — la stessa decisione
già aperta e non presa in [TAL-62](TAL-62.md) (#2, download/persistenza del
testo). Finché quella decisione resta aperta, la strategia di identità per
Halley non può appoggiarsi a CIG/numero: le opzioni realistiche restano
`oggetto` esatto (non fuzzy) + `data_pub`, oppure accettare l'assenza di
deduplicazione automatica su questa piattaforma e demandarla a revisione
umana quando la sovrapposizione diventa visibile (es. red flag doppio).
Nessuna decisa ancora — da discutere con Dom.

### 2026-08-16 — Notebook `notebooks/tal64_dedup_jcitygov.ipynb`

Su richiesta di Dom, portato l'esperimento CIG/numero da script una-tantum a
notebook eseguibile e ripetibile (`notebooks/tal64_dedup_jcitygov.ipynb`,
staging jCityGov portato a 1048 righe). **Correzione importante rispetto al
Tentativo 1**: il primo controllo da riga di comando concludeva "0 falsi
positivi" per il CIG, ma controllava solo se un match *esisteva*
(`fetchone()`), non se fosse quello giusto quando ce n'erano altri. Rifatto
con precisione:

- **Il CIG da solo produce falsi positivi**: 5720/14362 CIG (40%) coprono
  più di un atto reale nell'Albo Pretorio — una gara genera più atti nel
  tempo (determina a contrarre, aggiudicazione, liquidazione...), tutti con
  lo stesso CIG. Esempio concreto nel notebook: un CIG con 85 atti diversi.
- **`(ente_id, cig, numero)` è molto meglio ma non perfetto**: ambiguo nel
  6,2% dei casi (1523/24438 gruppi) — un'implementazione reale deve gestire
  esplicitamente l'ambiguità residua, non ignorarla.
- **Il caso vero da deduplicare (stesso atto, `url_fonte` diverso) esiste
  ma è raro su jCityGov**: solo 159/1048 (15%) atti di staging hanno sia CIG
  sia numero; di questi, 149 trovano match univoco, **148 con lo stesso
  identico URL** (dedup già gratuita via `UNIQUE`) e **1 solo con URL
  diverso**. Confermato che il problema esiste davvero, non solo in teoria,
  ma è meno frequente di quanto ipotizzato.
- **Trovato anche un bug di qualità dati collaterale**: il campo `cig` a
  volte contiene la stringa letterale `"ORIGINARIO"` (91 atti su un solo
  comune) invece di un CIG vero o `NULL` — placeholder finito nell'estrazione,
  non ancora indagato dove entra (probabilmente `estrai_cig()` matcha del
  testo tipo "CIG ORIGINARIO: ..." riferito a un'altra gara). Da seguire
  separatamente, non blocca questa card.

### 2026-08-16 — Tentativo 3: le gare Halley sono davvero altrove?

**Approccio:** su suggerimento di Dom, verificare se le gare d'appalto per i
comuni Halley si trovano in una terza sezione, non Albo Pretorio né
Amministrazione Trasparente. Controllato (a) quanto CIG è già presente
nell'Albo Pretorio Halley reale (`fonte_scraper='halley'`, tutti i comuni),
(b) il menu del sito istituzionale di Aci Bonaccorsi e Melilli per link a
"gara"/"appalti"/"bandi" fuori dalle due app già note.

**Esito:** ⚠️ parziale — intuizione parzialmente confermata, ma non nel senso
di una terza fonte mancante:
- **Le gare CON CIG sono già nell'Albo Pretorio**: 3626/28160 atti Halley
  hanno CIG (per lo più "determine di direzione" — liquidazioni, affidamenti
  — con CIG incorporato nel testo dell'oggetto, estratto da `estrai_cig()`).
  Per Aci Bonaccorsi specificamente, però, l'Albo Pretorio non ha **nessun**
  atto di tipo "bando di concorso" (0 righe) — è proprio quella categoria,
  non le gare, ad essere assente dalla finestra breve dell'Albo.
- **Nessuna terza sezione trovata**: il sito istituzionale di Aci Bonaccorsi
  ha un link "Appalti pubblici" (`/servizi/default.aspx?category=6`) che
  sembrava promettente, ma è una pagina vuota del catalogo servizi generico
  ("0 servizi trovati") — il menu del sito rimanda solo a "Amministrazione
  Trasparente" e "Albo Pretorio", le due app già note. Melilli non ha
  nemmeno un link con "gara"/"appalti"/"bandi" nel testo del menu.

**Appreso:** il quadro si corregge così — per **gare d'appalto** (con CIG),
la deduplicazione tra Albo Pretorio e Amministrazione Trasparente probabilmente
conta poco su Halley: Albo Pretorio le cattura già abbastanza bene (13% delle
righe ha CIG). Il gap reale che Amministrazione Trasparente colma su Halley
sono i **concorsi** (bandi di concorso, spariti dall'Albo dopo 15-30gg) — che
però, coerentemente, non hanno mai CIG per loro natura. Non risolve il
problema dell'identità per i concorsi (resta aperto: nessun numero/CIG da
nessuna parte), ma restringe la domanda: la strategia di dedup per Halley
serve soprattutto per i concorsi, non per le gare.

### 2026-08-16 — Tentativo 4: fattibilità download+estrazione PDF per Halley

**Approccio:** su richiesta di Dom ("ok la soluzione che proponi, purché sia
fattibile, buona e non si perda tempo"), prova rapida di fattibilità prima di
implementare: scaricati 5 PDF reali di Amministrazione Trasparente da Aci
Bonaccorsi, passati a `engine.pdf_text.estrai_testo()` (già esistente, usato
da Modulo 1 — nessuna nuova dipendenza), cercato CIG (`estrai_cig()`, già
esistente) e un numero atto via un semplice pattern `"Determinazione n.
NNNN"`.

**Esito:** ✅ fattibile, con due avvertenze reali
**Appreso:**
- **`numero` è estraibile**: 3/5 PDF (le "DETERMINA", non gli allegati/schemi
  di contratto) hanno dato un numero pulito (es. "Determinazione n. 1217").
  Nessuna OCR necessaria, estrazione nativa, veloce.
- **`CIG` non trovato in nessuno dei 5** — atteso e corretto, non un
  fallimento: questi PDF sono concorsi/selezioni di personale, che non hanno
  CIG per natura (coerente con Tentativo 3).
- **Layout del testo spesso disordinato**: alcuni PDF hanno intestazioni con
  caratteri sparsi fuori ordine di lettura (probabile timbro/filigrana come
  oggetto di testo separato, es. `"D) | A | C | m.i. | ( | s. | COMUNE DI
  ACI BONACCORSI..."`), eppure il numero atto nel corpo resta comunque
  estraibile — `estrai_testo()` regge, ma un pattern di estrazione numero
  robusto per la produzione va testato su un campione più ampio prima di
  fidarsene, non solo su 5 PDF di un comune.

**Implicazione:** conferma che vale la pena decidere la persistenza del testo
(TAL-62 #2) almeno per Halley Amministrazione Trasparente — riusa
interamente infrastruttura esistente, nessun nuovo costo tecnico. Non ancora
implementato in produzione: serve (a) decidere se scaricare tutti gli atti
o solo un sottoinsieme, (b) validare il pattern numero su un campione più
ampio, (c) capire dove persistere il testo estratto (`testo_estratto` esiste
già nello schema `atti`, mai popolato finora).
