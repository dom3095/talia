# TAL-63 — jCityGov: link `url_fonte` mai stato un permalink funzionante

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🕷️ SCR
- **Priorità:** P0 (esplicabilità — principio 1 CLAUDE.md, non negoziabile)
- **Stato:** In Progress (codice corretto, backfill sul DB reale non ancora eseguito)
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

## ❓ Non ancora fatto (bloccante prima di poter dire "risolto")

- [ ] **Backfill su `talia.db` reale**: 85.435 atti `fonte_scraper='jcitygov'` hanno
  oggi un `url_fonte` nel vecchio formato non funzionante. Il codice corretto vale
  solo per i **prossimi** run scraper — gli atti già scritti restano rotti finché
  non si riscrivono. Serve uno script di migrazione (estrarre `pub_id` da ogni
  `url_fonte` esistente via regex, ricostruire con `_url_dettaglio()`) — **non
  ancora eseguito, in attesa di conferma esplicita di Dom** prima di una modifica
  così ampia (85k righe) sul DB reale, anche con backup preventivo.
- [ ] Verificare se lo stesso bug esiste su altre piattaforme con un meccanismo di
  dettaglio simile (nessun segnale per ora, ma non controllato sistematicamente).

## 📝 Note

Non è un problema introdotto da TAL-62: è un bug preesistente in `jcitygov.py`
dall'inizio (probabilmente da quando lo scraper è stato scritto), che TAL-62 ha
solo reso più visibile perché usava la stessa funzione `_url_dettaglio()`. Interessa
la piattaforma più grande del progetto (85.435 atti, più di tutte le altre insieme)
— è l'esplicabilità del principio 1 di CLAUDE.md che non ha mai funzionato per
questa fetta di dati, non solo un dettaglio tecnico.
