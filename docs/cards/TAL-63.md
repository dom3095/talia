# TAL-63 — jCityGov: link `url_fonte` mai stato un permalink funzionante

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🕷️ SCR
- **Priorità:** P0 (esplicabilità — principio 1 CLAUDE.md, non negoziabile)
- **Stato:** Done (codice corretto, backfill completo eseguito e verificato sul DB reale)
- **Branch:** `feat/TAL-60-streamlit-modulo1`

## 🎯 Obiettivo

Correggere il formato dell'URL di dettaglio (`url_fonte`) generato da `jcitygov.py`
per ogni atto: quello usato finora **non è un link funzionante** per un utente che ci
clicca sopra da un red flag/report TALIA.

## 📚 Contesto

Segnalato da Dom durante la discussione su Amministrazione Trasparente: "cionontoglie
che anche per jCity se clicco su un riferimento va su una pagina sballata", con
l'esempio esatto del link che aveva già segnalato per Acate (l'episodio che aveva
aperto tutto il filone TAL-62).

## 🔬 Tentativi

### 2026-08-16 — Verifica con Playwright (browser reale, non curl)
**Approccio:** aprire l'URL esatto segnalato da Dom (`.../papca-g?p_p_id=...&_..._id=
5557692&_..._action=mostraDettaglio`) con un browser reale, sia a sessione fredda
(nessuna visita precedente) sia dopo aver visitato prima l'albo (sessione stabilita).
**Esito:** ❌ (confermato il bug, poi ✅ trovato il fix)
**Appreso:**
- **Entrambi i casi mostrano lo stesso errore**: "Errore! Errore: contattare
  l'amministratore del Portale". Non è un problema di sessione/cookie.
- **Confermato anche con `curl` puro** (nessun JS): la risposta HTTP contiene
  l'errore già nell'HTML grezzo — è il backend di jCityGov stesso a rifiutare
  questa combinazione di parametri, non un problema di rendering client-side.
- **Verificato su due tenant diversi** (Ragusa con un id raccolto durante TAL-62,
  Acate con l'id esatto segnalato da Dom): stesso esito su entrambi — bug
  sistemico della piattaforma, non specifico di un comune.
- **Trovato il link vero** cliccando realmente il bottone "Apri Dettaglio" nella
  pagina lista igrid (non deducendolo): `.../papca-g/-/papca/display/<id>
  ?p_p_state=pop_up`. Verificato funzionante **a freddo** (nessuna sessione
  precedente) su entrambi i tenant, incluso l'id esatto di Acate segnalato da Dom.
- **Trovato che il problema era già parzialmente noto**: `pdf_download.py` ha già
  una funzione `_url_display_format()` che converte da formato `mostraDettaglio`
  a `/papca/display/<id>` — ma la tratta come un'ottimizzazione ("più veloce e
  diretto"), non come la correzione di un link rotto. Il fix non era mai stato
  riportato a monte in `jcitygov.py::_url_dettaglio()`, la funzione che genera
  effettivamente lo `url_fonte` salvato nel DB e mostrato agli utenti — solo
  `pdf_download.py` (uso interno, fetch di allegati) ne beneficiava.

## 📋 Fix applicato

- `_url_dettaglio(base_url, papca_path, pub_id)` in `jcitygov.py`: ora genera
  `{base_url}{papca_path}/-/papca/display/{pub_id}?p_p_state=pop_up` invece del
  vecchio formato query-string con `action=mostraDettaglio`.
- `_parse_pagina()` ora riceve `papca_path` (era hardcoded su `_PAPCA_PATH`,
  quindi sbagliato anche per i 6 tenant con percorso alternativo — Milazzo,
  Aragona, Gaggi, Letojanni, Noto, Racalmuto, TAL-49 — che usano `papca-ap`, non
  `papca-g`): sia `scarica_atti()` sia `scarica_atti_trasparenza()` già tracciano
  il `papca_path` corretto localmente, ora lo passano.
- 1 test aggiornato (`test_url_dettaglio_usa_il_formato_display_funzionante`),
  regressione esplicita sul vecchio formato.
- **`pdf_download.py` non toccato**: `_url_display_format()` resta utile come
  normalizzatore tollerante (converte sia il vecchio sia il nuovo formato) durante
  la transizione, prima che il backfill sui dati esistenti sia completato.

## 🔬 Tentativo 2 — backfill di prova su Acate (41 atti)

**Approccio:** su richiesta di Dom ("prima fammi vedere se funziona"), backfill
limitato al solo Comune di Acate (41 atti `fonte_scraper='jcitygov'`): estratto
`pub_id`/`papca_path` da ogni `url_fonte` esistente via regex, ricostruito con
`_url_dettaglio()` corretta, `UPDATE` diretto (backup preso prima:
`talia.db.bak-pre-backfill-tal63-acate-20260816`). Verificato con Playwright, 5
atti a campione, sessione fresca per ciascuno: tutti mostrano il dettaglio vero.

**Esito:** ⚠️ parziale — Dom ha comunque trovato link rotti nella dashboard
("riapre sempre la stessa pagina").
**Appreso:** i 41 `atti.url_fonte` erano corretti, ma il tab "Dettaglio comune →
Segnalazioni per il comune" **non li legge da `atti.url_fonte`** — legge da
`red_flags.atti_cig`, un campo JSON che **contiene una copia propria dell'URL**,
scritta al momento in cui il red flag fu calcolato (denormalizzazione, mai
sincronizzata col backfill su `atti`). Ogni link mostrava quindi ancora il
vecchio formato rotto — e siccome tutti gli URL rotti danno lo stesso identico
messaggio di errore, sembrava "sempre la stessa pagina", non semplicemente "link
diversi tutti rotti".

**Corretto anche questo** per Acate: riletti i 5 `id` in `red_flags.atti_cig`
(unico red flag per questo comune, `concentrazione_diretti`), sostituito `url`
con il valore ora corretto di `atti.url_fonte` per lo stesso `id`, `UPDATE` su
`red_flags`. Riverificato dal vivo con Playwright: tutti e 5 i link ora aprono il
dettaglio vero. **Implicazione per il backfill completo (85.435 atti)**: non
basta correggere `atti.url_fonte` — va corretto **anche** `red_flags.atti_cig`
per ogni voce che referenzia un atto jCityGov (631 red flags totali nel DB, non
ancora contato quanti abbiano voci jCityGov da correggere).

## 🔬 Tentativo 3 — backfill completo (85.394 atti + 341 red flags)

**Approccio:** stesso script di Acate, esteso a tutto `talia.db` (backup preso
prima: `talia.db.bak-pre-backfill-tal63-completo-20260816`). Due passate:
1. `atti`: 85.394 righe con `fonte_scraper='jcitygov'` e URL nel vecchio formato
   (85.435 totali − 41 già corrette su Acate) — tutte matchate dalla regex ed
   aggiornate, **0 righe con formato inatteso**.
2. `red_flags.atti_cig`: 2024 voci totali che referenziano un atto jCityGov,
   trovate in 341 red flags distinti — 2019 aggiornate (5 già corrette su Acate).

**Esito:** ✅
**Appreso:** verificato con Playwright su due campioni casuali indipendenti — 8
atti da 8 comuni diversi (Rometta, Palma di Montechiaro, Augusta, Modica,
Gravina di Catania, Nicolosi, Ragusa, Giarre) presi da `atti.url_fonte`, e 6 URL
casuali presi direttamente da `red_flags.atti_cig`: **14/14 funzionanti**. Il
fix generalizza correttamente oltre ai due tenant già testati (Ragusa, Acate) a
tutta la piattaforma.

**Verificato anche Halley** prima di procedere con questo backfill, su
richiesta di Dom: **nessun bug analogo**. L'Albo Pretorio (`mc_p_dettaglio.php`)
mostra correttamente la pagina di dettaglio; Amministrazione Trasparente
(`visualizza-documento-generico`) non è una pagina HTML ma un download diretto
del PDF originale (`Content-Type: application/pdf`, verificato negli header
HTTP) — comportamento corretto, non un errore (Playwright lo segnala come
eccezione "Download is starting", non un fallimento del link).

## 📝 Note

Non è un problema introdotto da TAL-62: è un bug preesistente in `jcitygov.py`
dall'inizio (probabilmente da quando lo scraper è stato scritto), che TAL-62 ha
solo reso più visibile perché usava la stessa funzione `_url_dettaglio()`. Interessa
la piattaforma più grande del progetto (85.435 atti, più di tutte le altre insieme)
— è l'esplicabilità del principio 1 di CLAUDE.md che non ha mai funzionato per
questa fetta di dati, non solo un dettaglio tecnico.

Non ancora fatto: verificare se lo stesso bug esiste sulle altre piattaforme oltre
Halley (già controllata, pulita) con un meccanismo di dettaglio simile — non
controllato sistematicamente.
