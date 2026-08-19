# TAL-70 — Bonifica scraper: mai diagnosticati, Corleone, ANAC, stagnanti

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🕷️ SCR
- **Priorità:** P1
- **Stato:** Review
- **Branch:** `feat/TAL-66-run-giornaliero-aggregati`

## 🎯 Obiettivo

Richiesta di Dom: *"sistema anac con playwright, fai lo scraper nuovo per
corleone. Sistema anche i mai diagnosticati, stagnanti e muti"*.

## 📊 Esito in sintesi

| Gruppo | Esito |
|--------|-------|
| Muti | **nessuno da sistemare** — la categoria è vuota da TAL-68 |
| Mai diagnosticati (8) | **2 attivati** (+110 atti), 4 albi realmente vuoti, 2 errore lato server |
| Corleone | **attivato, 499 atti** — senza scrivere uno scraper nuovo |
| ANAC | **risolto senza Playwright**: era muto perché l'URL configurato era un manifest, non il dataset |
| Stagnanti | gli scraper funzionano: sono gli albi ad essere fermi. Indagine sospesa |

## 1. Mai diagnosticati — 5 hspromila

**Causa (2 su 5): una seconda skin dello stesso portale.** Stessa lezione di
Caccamo/TAL-68: il portale rispondeva **200 con la tabella piena**, ma
`_RE_ROW` cercava solo `<tr class="">` mentre questi tenant usano righe
`itemstyle`/`alternatingitemstyle` con **6 colonne invece di 10**.

- `_parse_legacy()` accanto a `_parse_moderna()`, con la moderna prioritaria:
  nessun cambiamento per i 36 tenant già attivi (verificato dal vivo — Tusa
  73, Niscemi 101, invariati).
- **Paginazione**: la skin legacy pagina a 10 e le pagine successive esistono
  solo via `__doPostBack`. Implementata rigiocando lo stato del form
  (`__VIEWSTATE`) con opener a **cookie jar condiviso** — senza il cookie di
  sessione WebForms risponde 200 con zero righe invece di un errore.
- **Floresta 40 atti, Cianciana 70** (erano 0). Attivati.

**Gli altri 3 non sono un bug nostro**, e ora il registro lo dice invece di
lasciarli ambigui: `oliveri`, `monterossoalmo`, `novaradisicilia` rispondono
*"La tua ricerca non ha prodotto risultati"* — albo realmente vuoto.

## 2. Mai diagnosticati — 3 halley

Diagnosi letta nel **corpo** della risposta, non nello status:

- `acquavivaplatani`, `sanmichelediganzaria` → **"Errore 5052"** del portale
  Halley sulla ricerca albo. Errore lato server: serve intervento del gestore,
  non è un problema di parsing.
- `valguarneracaropepe` → *"Nessuna pubblicazione estratta"*, anche sullo
  storico. Albo vuoto.

## 3. Corleone — nessuno scraper nuovo

Era `bloccato` con la nota *"sito WordPress con CPT `documento_pubblico`"*.
**La diagnosi era sbagliata**: l'API REST di WordPress non espone alcun
`documento_pubblico`, e la pagina albo contiene 36 riferimenti a `urbi`,
`DB_NAME=wt00032263` e `StwEvent` — è un **URBI self-hosted**.

`urbi.py` esistente, con `base_url`/`qs_base`/`ente_mittente` corretti:
**499 atti**. Zero righe di codice nuovo. Registro aggiornato da
`bloccato`/`portalepa` a `attivo`/`urbi`.

## 4. ANAC — risolto, ma non con Playwright

**Correzione di una mia conclusione sbagliata.** In un primo giro avevo
concluso che il CSV fosse stato dismesso e che restasse solo RDF Turtle da
1,8 GB per file. Era falso, e l'ha fatto emergere una domanda di Dom: *"su
quale URL sei andato?"*. Ero andato **solo** sull'URL configurato nel codice —
il manifest — e da lì avevo dedotto l'inventario delle risorse, invece di
provare l'URL dei CSV per analogia col nome dei TTL.

I CSV esistono: `smartcig_csv_{anno}_{mese}.zip`, **~40 MB zippati a mese**,
12 mesi per anno, **anche per il 2025** (che il codice dava per non ancora
pubblicato). Verificato: 2023, 2024 e 2025 completi.

Quello che invece resta vero della prima analisi:

1. **Il download non è bloccato.** L'URL configurato risponde `200`… con
   **1288 byte**: non è il dataset, è un **manifest** che elenca le risorse.
   Lo scraper lo scaricava e ci cercava dentro i contratti — *ecco perché
   ANAC risultava muto*, non per il WAF.
2. **Il manifest elenca solo risorse TTL.** È da qui che avevo dedotto —
   sbagliando — che il CSV fosse sparito: l'inventario non lo cita, ma il file
   c'è, allo stesso path.
3. **Playwright non aiuta.** Le pagine del portale sono respinte da un WAF F5
   ("Request Rejected") **anche con Chromium reale**; gli endpoint SPARQL
   idem. I file di dati invece si scaricano benissimo in HTTP semplice: il
   browser non serve dove funziona, e non passa dove non funziona.
4. Il TTL è effettivamente enorme (1,8 GB/file), ma è **irrilevante**: i CSV
   pesano un quarantesimo e sono già nel formato che il parser si aspetta.

### Fix applicati

- `_url_smartcig(anno, mese)` punta ai file mensili (zip di default: 47 MB
  contro 189 MB su 2024-11); `_url_manifest()` resta, ma con un commento che
  dice a chiare lettere che **non** è il dataset.
- `scarica_e_carica()` scorre i 12 mesi; un mese mancante (404) non ferma gli
  altri, perché ANAC pubblica progressivamente.
- **Due bug del tracciato scoperti solo caricando i dati veri**, che avrebbero
  lasciato ANAC a zero anche con l'URL giusto:
  - le colonne sono `denominazione_amministrazione_appaltante` /
    `cf_amministrazione_appaltante` / `oggetto_lotto` / `importo_lotto`:
    aggiunti gli alias;
  - il filtro era `sezione_regionale == "Sicilia"`, ma quel campo vale
    `"SEZIONE REGIONALE SICILIA"` e per alcuni enti siciliani perfino
    `"SEZIONE REGIONALE CENTRALE"` (la Casa di reclusione di San Cataldo).
    **Filtrando lì si perdevano righe in silenzio**: ora si filtra su
    `regione`.
- **Aggancio dell'ente via `istat_comune`** (`"019082054"` → `082054`,
  Partinico) invece del solo LIKE sulla denominazione, che su nomi come
  "COMUNE DI SAN GIOVANNI" può agganciare il comune sbagliato.

### Un quarto bug, trovato solo guardando i totali

Caricata l'annata 2025 (176.827 atti), la somma degli importi dava **98 mila
miliardi di euro**: assurda a colpo d'occhio. Causa: `_parse_importo` era
scritto per il formato italiano (`4.500,00`) e trattava il punto come
separatore di migliaia, mentre il tracciato mensile usa il punto come
separatore **decimale** (`1550.0`, il 100% delle righe verificate). Ogni
importo risultava **moltiplicato per 10**.

Non è un dettaglio estetico: `frazionamento` e `concentrazione_diretti`
confrontano gli importi con soglie di legge — con i valori gonfiati avrebbero
prodotto red flag falsi su larga scala, cioè esattamente il danno che il
principio "segnalare, non giudicare" vuole evitare.

Corretto distinguendo i due formati sulla presenza della virgola (il tracciato
storico resta leggibile), con 3 test di regressione. **Le 176.827 righe già
inserite sono state cancellate e ricaricate**: invertire la corruzione a
posteriori sarebbe stato meno sicuro che rifare il caricamento.

**Verificato dal vivo:** un singolo mese (2025-01) scaricato in 21s →
**12.400 atti**, agganciati agli enti giusti (Palermo 2494, Catania 890,
Messina 795); l'annata intera in 316s → **176.827 atti su 470 enti**. `anac` resta fuori dal run notturno: il dataset si aggiorna
mensilmente, riscaricarlo ogni notte sarebbe mezzo giga al giorno per nulla.
Nuovo `--anac-anno` per scegliere l'annata.

Nota: aggirare il WAF con tecniche di evasione non è stata un'opzione in
nessun momento — stessa linea già tenuta per Leonforte e Messina. Non è
servito: le pagine del portale restano bloccate, i file di dati non lo sono
mai stati.

## 5. Stagnanti — non è codice

Gli scraper restituiscono gli atti che l'albo espone; sono gli **albi** ad
essere fermi. Verificato leggendo le date reali:

| Comune | Atto più recente esposto |
|--------|--------------------------|
| `rometta` | 2023-09-27 |
| `paceco` | 2025-07-04 |
| `mascalucia` | 2026-06-03 |
| `acate` (sano, confronto) | 2026-08-03 |

Controllato che non avessero migrato piattaforma: i siti istituzionali di
Mascalucia e Paceco **linkano proprio l'albo che leggiamo**. Su jCityGov il
tenant sano espone due risorse (`Albo pretorio`, `Storico atti`); questi tre
non ne espongono nessuna, quindi non è il caso "percorso alternativo" di
TAL-49.

**Indagine sospesa**: aprendo la pagina di Mascalucia con un browser è
scattato un WAF (`MDAWAF001`) su questo IP. Coerentemente con la linea del
progetto (rate-limiting prudente, niente evasione) ho smesso di interrogare
quell'host. Da riprendere a freddo, un comune alla volta.

## ✅ Task

- [x] hspromila: parser skin legacy + paginazione `__doPostBack` (7 test)
- [x] Floresta e Cianciana attivati (+110 atti)
- [x] 6 casi senza colpa nostra annotati nel registro con la causa precisa
- [x] Corleone: da `bloccato` ad `attivo` via `urbi.py` (+499 atti)
- [x] ANAC: URL mensili + alias colonne + filtro `regione` + aggancio ISTAT,
      **12.400 atti verificati su un mese** (6 test nuovi)
- [x] Stagnanti: esclusa la causa "bug dello scraper"
- [ ] Stagnanti: capire dove pubblicano oggi, a freddo

## 🔬 Tentativi

### 2026-08-19 — Tentativo 1 (hspromila)
**Approccio:** con Playwright sembrava che le righe comparissero solo dopo
aver inviato il form di ricerca; ho aggiunto un fallback POST.
**Esito:** ❌ falso — la GET le righe le ha già.
**Appreso:** il conteggio righe letto da Playwright subito dopo
`domcontentloaded` era prematuro. Verificando in HTTP puro, il problema era
un altro (la skin legacy). Fallback rimosso; la macchina VIEWSTATE costruita
lì è però servita davvero per la paginazione.

### 2026-08-19 — Tentativo 2 (regex del pager)
**Approccio:** prima regex del pager legata a uno spazio singolo fra gli
attributi.
**Esito:** ❌ rotta al primo a capo nel markup (l'ha trovata un test).
**Appreso:** esattamente la fragilità che CLAUDE.md elenca ("regex fragili
sull'HTML"). Resa tollerante a spaziatura e ordine degli attributi.
