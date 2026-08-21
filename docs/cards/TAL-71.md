# TAL-71 — La fase red flags del run notturno girava 11 ore

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🕷️ SCR
- **Priorità:** P0
- **Stato:** Review
- **Branch:** `feat/TAL-66-run-giornaliero-aggregati`

## 🎯 Problema

Dal caricamento ANAC (TAL-70) il run notturno non finiva più in tempo utile:

| Run | Scraper finiti | Fine effettiva | Durata totale |
|-----|----------------|----------------|---------------|
| 2026-08-20 | 10:34 | 21:45 | **18h** |
| 2026-08-21 | 09:14 | terminato a mano alle 20:38 | **>17h** |

Gli scraper chiudevano in ~6 ore; il resto era **fase red flags**, con il
processo al 98% di CPU (`STAT RN`) — quindi calcolo, non attesa di rete.

**È una regressione introdotta da TAL-70.** Il caricamento ANAC è corretto, ma
non era stato valutato il costo a valle.

## 🔍 Causa

`collega_per_contenimento` (strategia 2.5) e `collega_per_oggetto_simile`
(strategia 3) confrontano **ogni atto con ogni altro atto dello stesso ente**:
sono O(n²) *per ente*. Finché il DB conteneva solo atti d'albo distribuiti su
190+ comuni, nessun ente era abbastanza grande da farlo notare.

I 176.827 contratti SmartCIG si sono concentrati sui capoluoghi:

| Ente | Atti con oggetto | di cui ANAC |
|------|------------------|-------------|
| Palermo | 37.709 | 35.719 (**94,7%**) |
| Catania | 15.214 | — |
| Caltanissetta | 14.841 | — |

Il rapporto costo/beneficio era indifendibile:

| Metodo | Procedimenti creati |
|--------|---------------------|
| `cig` | 199.360 |
| `oggetto_simile_da_verificare` | 20.550 |
| **`contenimento_oggetto`** | **263** |

Undici ore di CPU per 263 collegamenti.

## ✅ Fix

Un contratto SmartCIG **non è un atto deliberativo dell'albo**: non esiste un
"originario" da riconoscere per somiglianza del titolo, e il collegamento
corretto passa già dal CIG (strategia 1, match esatto). Le due strategie fuzzy
ora escludono `tipo = 'contratto_anac'`.

Il taglio è mirato: gli atti ANAC **restano** nelle strategie 1 (CIG) e 2
(riferimenti incrociati), che sono match esatti e a costo lineare. Perdiamo
solo un collegamento probabilistico che su quei dati sarebbe stato comunque
sbagliato.

Misurato su Palermo, l'ente peggiore: le strategie fuzzy passano da 37.709 a
1.990 atti. `collega_per_contenimento` **2,1s**, `collega_per_oggetto_simile`
**10,0s**.

### Fase intera cronometrata, strategia per strategia

Su copia di `talia.db` (327.704 atti, 471 enti). Misurata a granularità fine
proprio perché il primo tentativo — un unico cronometro sull'intera
`esegui_tutti` — non avrebbe distinto "risolto" da "bloccato da un'altra
parte".

| Fase | Tempo | Prodotto |
|------|------:|---------:|
| 1. cig | 1075,3s | 199.330 |
| 2. riferimenti incrociati | 96,0s | 3 |
| **2.5 contenimento** | **39,5s** | 3 |
| **3. oggetto simile** | **377,3s** | 201 |
| rf frazionamento | 218,5s | 12.892 |
| rf concentrazione | 2,5s | 900 |
| rf tempi anomali | 0,4s | 16 |
| rf revoche catena | 0,1s | 49 |
| rf riapertura | 6,2s | 11 |
| **TOTALE** | **1816,0s (30 min)** | |

**Da 11+ ore a 30 minuti.** Le due strategie quadratiche ora pesano 7 minuti
su 30.

⚠️ **Come leggere questi numeri:** la misura gira su un DB con i procedimenti
**già assegnati** — la strategia 3 lavora solo sugli atti con
`procedimento_id IS NULL` e la 2.5 salta quelli già collegati. È lo stato in
cui il run notturno si trova ogni notte, quindi è il numero giusto per la
produzione, ma una **ricostruzione a freddo** (`reset_da_verificare=True`)
costerebbe sensibilmente di più.

### Il collo di bottiglia residuo non è quadratico

La strategia 1 costa ora il **59% della fase**: 18 minuti per iterare 199.330
CIG distinti, uno `collega_per_cig` ciascuno. È lineare, quindi non riporta il
problema di questa card — ma è lavoro rifatto ogni notte su CIG i cui atti
hanno già un `procedimento_id`. Ottimizzazione possibile (saltare i CIG
interamente già collegati), non urgente.

## ⚠️ Da valutare a parte

- **Red flags passati da 665 a 13.964, e 12.892 sono `frazionamento`.**
  Da guardare prima di esporli in dashboard, per una ragione di merito e non
  solo di volume: SmartCIG contiene **per definizione** affidamenti sotto
  soglia, quindi una regola che cerca il frazionamento artificioso *sotto le
  soglie di legge* trova lì un terreno dove quasi tutto somiglia a un segnale.
  Il tasso di falsi positivi va stimato su un campione prima della
  pubblicazione — è esattamente il rischio che "segnalare, non giudicare"
  esiste per evitare. Nota: il conteggio è di *rilevazioni*, non di flag
  salvati (il runner deduplica in `_salva_frazionamento`).
- **220.173 procedimenti su 327.704 atti**, di cui 199.360 creati dal CIG:
  è quasi un procedimento per contratto. Corretto in senso stretto (ogni CIG
  *è* un procedimento) ma rende poco informativa la nozione di procedimento.
- **Agrigento restituisce 0 atti** da almeno due run (12s, nessun errore) —
  pattern "muto" già visto con Caccamo (TAL-68). Non collegato a questa card.

## ✅ Task

- [x] Diagnosi: fase red flags, non rete; O(n²) per ente
- [x] Esclusione `contratto_anac` dalle strategie fuzzy 2.5 e 3
- [x] 3 test di regressione (esclusione da entrambe le strategie + prova che
      il collegamento per CIG continua a funzionare)
- [x] Misura su Palermo dopo la patch
- [x] Fase intera cronometrata strategia per strategia: **11h → 30 min**
- [ ] Verificare un campione dei 12.892 `frazionamento` prima di esporli
- [ ] Valutare se `collega_per_cig` può saltare i CIG già interamente
      collegati (59% della fase residua)

## 🔬 Tentativi

### 2026-08-21 — Tentativo 1
**Approccio:** diagnosi del run bloccato leggendo `%CPU` e `STAT` del processo
invece di presumere un hang di rete.
**Esito:** ✅ decisivo — `98% CPU`, `STAT RN` escludeva subito la rete e
puntava a un loop di calcolo; la coda del log (`── RED FLAGS ──` senza righe
successive) individuava la fase.
**Appreso:** su un run che "non finisce" la prima domanda è *sta lavorando o
sta aspettando?*. Un `ps` risponde in un secondo ed evita di andare a cercare
timeout inesistenti.

### 2026-08-21 — Tentativo 2
**Approccio:** prima di scrivere la patch, contare i procedimenti prodotti da
ciascuna strategia.
**Esito:** ✅ ha cambiato la decisione.
**Appreso:** i 263 collegamenti del contenimento contro i 199.360 del CIG
hanno reso evidente che la strategia fuzzy sugli ANAC non stava comprando
nulla. Senza quel conteggio la tentazione era ottimizzare il loop (indici,
blocking sui token) invece di **non eseguirlo affatto** sui dati sbagliati.
