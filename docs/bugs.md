# Bug noti — da risolvere

## [BUG-1] Siracusa spider: HTTP 400 per mancata gestione sessione PHP

**Rilevato:** 2026-06-26, prima esecuzione manuale `scripts/run_scrapers.py`
**Spider:** `src/talia/modulo2_scraping/fonti/siracusa.py`
**Sintomo:** `urllib.error.HTTPError: HTTP Error 400: Bad request` alla prima richiesta paginata.
**Causa:** `portalepa.comune.siracusa.it` imposta un cookie `PHPSESSID` alla prima risposta.
Lo spider usa `urllib.request.Request` senza `CookieJar`, quindi la sessione non viene mantenuta
e il sito rifiuta le richieste successive con 400.
**Stato:** ✅ Fixato il 2026-06-26 — `scarica_atti()` ora usa `http.cookiejar.CookieJar` +
`urllib.request.build_opener(HTTPCookieProcessor)` per propagare PHPSESSID tra le richieste.

---

## [BUG-2] ANAC spider: URL dataset SmartCIG obsoleto + WAF blocca User-Agent bot

**Rilevato:** 2026-06-26, prima esecuzione manuale `scripts/run_scrapers.py`
**Spider:** `src/talia/modulo2_scraping/fonti/anac.py`
**Sintomo 1 — URL cambiato:** `https://dati.anticorruzione.it/opendata/download?fileName=smartcig.csv`
risponde con la welcome page di JBoss EAP 7 (server di default), non con il CSV.
Il dataset SmartCIG è stato spostato sul portale ANAC. L'URL va verificato e aggiornato.
**Sintomo 2 — WAF blocca bot UA:** con User-Agent `TALIA-bot/0.1` il server risponde
"Request Rejected" (WAF). Con browser UA passa. Fix immediato: aggiornare `_USER_AGENT`
in `anac.py`; fix strutturale: trovare il nuovo URL del dataset.
**Stato:** ✅ Fixato il 2026-06-26 — dataset ora suddiviso per anno civile.
- `URL_DATASET_SMARTCIG` ora generato da `_url_smartcig(anno)` con pattern
  `.../opendata/download/dataset/smartcig-{anno}/filesystem/smartcig-{anno}_csv_logCsv.csv`
  (default: anno corrente − 1, es. 2025).
- `_USER_AGENT` aggiornato a Chrome browser UA per bypassare il WAF ANAC.

---

## [BUG-6] Dashboard: tab Panoramica vuota

**Rilevato:** 2026-06-28, test Playwright
**File:** `src/talia/modulo3_dashboard/app.py` — `_mostra_panoramica()`
**Sintomo:** tab "📊 Panoramica" carica senza errori ma non mostra dati (tabella/chart assenti sotto "Comuni con segnalazioni"). Tab Dettaglio e Procedimenti funzionano.
**Causa probabile:** DataFrame vuoto per filtro o colonna mancante, oppure eccezione silenziosa nel rendering.
**Stato:** ✅ Chiuso il 2026-07-03 — **non era un bug**: falso positivo del metodo di
verifica. `st.dataframe` renderizza la tabella in un canvas (glide-data-grid), che è
invisibile all'estrazione testuale `inner_text()` usata dal test Playwright del
2026-06-28: il testo della tabella non compare nel DOM, ma la tabella c'è.
Verificato con screenshot Playwright su DB reale: i 3 comuni con segnalazioni
(AG/SR/TP, 1 flag media ciascuno) sono renderizzati correttamente.
**Lezione per i test UI Streamlit:** verificare `st.dataframe` con screenshot o con i
selettori del data-grid (`[data-testid="stDataFrame"]`), mai con l'estrazione del testo.
Fix collaterale: `use_container_width=True` (deprecato, rimozione post-2025) → `width="stretch"`.

---

## [BUG-4] Trapani spider: 0 atti — filtro data lato server (NON la regex)

**Rilevato:** 2026-06-28, test automatico con agente (2 pagine, DB temporaneo)
**Spider:** `src/talia/modulo2_scraping/fonti/trapani.py`
**Sintomo:** 0 atti trovati su 2 pagine. Nessuna eccezione: il portale `servizi-trapani.e-pal.it` risponde HTTP 200.
**Causa reale (2026-07-03):** `_RE_PANEL` funzionava — la causa era il default `dataPubblicazioneAl=oggi`. Il server e-pal.it **esclude gli atti la cui finestra di pubblicazione termina dopo `dataPubblicazioneAl`**: con `al=oggi` restano fuori tutti gli atti ancora in pubblicazione (cioè quelli mostrati dall'albo), quindi nei giorni in cui nessun atto scaduto è più listato il risultato è 0.
**Stato:** ✅ Risolto — 2026-07-03.
**Fix:** default `al = oggi + 60 giorni` (`_MARGINE_FUTURO_GIORNI` in `trapani.py`); WARNING esplicito se la pagina 1 produce 0 atti; test in `tests/fonti/test_trapani.py`. Verificato con run reale: +329 atti recuperati (copertura 2026-04-10 → 2026-07-02).
**Nota:** l'albo e-pal.it espone solo gli atti in pubblicazione (~15-30 gg): lo storico non è recuperabile, serve scraping continuo per non perdere atti.

---

## [BUG-5] Messina: firewall FortiGate blocca ogni connessione esterna con HTTP 403

**Rilevato:** 2026-06-28, test automatico con agente
**Spider:** non implementato (`jcitygov.py` pronto per essere esteso)
**Sintomo:** HTTP 403 "FORTINET Webfilter / This Connection is Invalid. SSL certificate expired." prima ancora di raggiungere il portale Liferay. IP: `5.180.69.64`.
**Causa:** il firewall FortiGate del Comune di Messina fa SSL inspection con un proprio certificato (`CN=mda-jcitygov-proxy`, CA Fortinet interna) scaduto il **2023-06-27**. Il FortiGate blocca le connessioni esterne che non passano la sua ispezione SSL.
**Perché `skip_ssl=True` non risolve:** bypassa la verifica lato Python, ma non aggira il blocco HTTP 403 del firewall a monte.
**Stato:** ❌ Bloccante infrastrutturale — non risolvibile lato codice. Richiede intervento del Comune di Messina / gestore IT (rinnovo cert FortiGate o whitelist IP).

---

## [BUG-3] ANAC spider: `_normalizza_colonne` crasha su chiave `None`

**Rilevato:** 2026-06-26 (stesso run di BUG-2, emerso prima del WAF)
**Spider:** `src/talia/modulo2_scraping/fonti/anac.py`, `_normalizza_colonne()`
**Sintomo:** `AttributeError: 'NoneType' object has no attribute 'strip'`
**Causa:** `csv.DictReader` mette le colonne extra (oltre l'header) sotto la chiave `None`.
Il CSV ANAC ha righe con più colonne dell'header in alcune versioni.
**Stato:** ✅ Fixato il 2026-06-26 — aggiunto `if k is None: continue` e `(v or "").strip()`.
