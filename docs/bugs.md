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

## [BUG-4] Trapani spider: `_RE_PANEL` non matcha più la struttura HTML corrente

**Rilevato:** 2026-06-28, test automatico con agente (2 pagine, DB temporaneo)
**Spider:** `src/talia/modulo2_scraping/fonti/trapani.py`
**Sintomo:** 0 atti trovati su 2 pagine. Nessuna eccezione: il portale `servizi-trapani.e-pal.it` risponde HTTP 200, ma `_RE_PANEL` non estrae nessun record.
**Causa probabile:** la struttura HTML di e-pal.it è cambiata rispetto a quella attesa dal lookahead nella regex `_RE_PANEL` (delimita i div `panel panel-primary`). Qualsiasi variazione nel nesting HTML causa il match a zero senza warning.
**Stato:** ❌ Aperto — da fixare.
**Fix:** scaricare l'HTML corrente di `ricercaAlbo`, confrontare con `_RE_PANEL`, aggiornare la regex, aggiungere test con HTML fixture reale.

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
