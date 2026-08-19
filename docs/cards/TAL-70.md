# TAL-70 — Bonifica scraper: mai diagnosticati, Corleone, ANAC, stagnanti

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🕷️ SCR
- **Priorità:** P1
- **Stato:** Review (ANAC: bloccata su una decisione)
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
| ANAC | **la premessa era sbagliata**: Playwright non c'entra, serve una decisione |
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

## 4. ANAC — la premessa non regge ⚠️ decisione richiesta

La richiesta era "sistemalo con Playwright", perché un WAF bloccherebbe il
download del CSV. Verificato punto per punto:

1. **Il download non è bloccato.** L'URL configurato risponde `200`… con
   **1288 byte**: non è il dataset, è un **manifest** che elenca le risorse.
   Lo scraper lo scaricava e ci cercava dentro i contratti — *ecco perché
   ANAC risultava muto*, non per il WAF.
2. **Il CSV non esiste più.** Dal 2023 SmartCIG è pubblicato **solo in RDF
   Turtle**: 12 risorse per il 2024, 36 per il 2023, zero in formato CSV.
   2025 e 2026 non ancora pubblicati (404).
3. **Playwright non aiuta.** Le pagine del portale sono respinte da un WAF F5
   ("Request Rejected") **anche con Chromium reale**; gli endpoint SPARQL
   idem. I file di dati invece si scaricano benissimo in HTTP semplice: il
   browser non serve dove funziona, e non passa dove non funziona.
4. **Il costo vero è il volume**: un singolo file mensile pesa **1,8 GB**
   (`Content-Length` misurato) → ~21 GB per il solo 2024.

**Non implementato di proposito.** L'unica strada praticabile è uno streaming
del TTL con filtro Sicilia al volo, senza mai salvare i file interi; ma è un
impegno di banda/tempo che non rientra nel "budget ≈ 0" senza una scelta
esplicita, e non è la cosa che era stata chiesta (Playwright). Serve decidere:

- [ ] investire nel lettore TTL in streaming (una esecuzione occasionale, mai
      nel run notturno), oppure
- [ ] tenere `--anac-file` come unica via ed escludere `anac` dal registro
      così non risulta perennemente "muto".

Nota: aggirare il WAF con tecniche di evasione **non** è un'opzione — stessa
linea già tenuta per Leonforte (Cloudflare) e Messina.

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
- [x] ANAC: diagnosi completa; **implementazione bloccata su decisione**
- [x] Stagnanti: esclusa la causa "bug dello scraper"
- [ ] ANAC: scelta fra lettore TTL streaming e `--anac-file`
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
