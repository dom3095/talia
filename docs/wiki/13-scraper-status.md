# 13 — Stato scraper per capoluogo

[← Home](00-home.md)

Ultimo test: **2026-06-28** (9 agenti in parallelo, `--max-pagine 2`, DB temporaneo isolato).
Per aggiornare: `python scripts/run_scrapers.py --scrapers <nome> --max-pagine 2 --db /tmp/test.db --no-red-flags`.

---

## Mappa di copertura

| Comune | Codice ISTAT | Scraper | Piattaforma | Stato |
|--------|-------------|---------|------------|-------|
| Agrigento | 084001 | `agrigento.py` | ASP.NET + DevExpress (Playwright) | ✅ OK |
| Caltanissetta | 085003 | `jcitygov.py` | jCityGov/Liferay (Maggioli) | ✅ OK |
| Catania | 087015 | — | URBI/Maggioli | ❌ da implementare |
| Enna | 086010 | `jcitygov.py` | jCityGov/Liferay (Maggioli) | ✅ OK |
| Messina | 083048 | — | jCityGov/Liferay (Maggioli) | ⛔ bloccato |
| Palermo | 082053 | — | SISPI JSP | ❌ da implementare |
| Ragusa | 088009 | `jcitygov.py` | jCityGov/Liferay (Maggioli) | ✅ OK |
| Siracusa | 089019 | `siracusa.py` | portalepa PHP | ✅ OK |
| Trapani | 081021 | `trapani.py` | e-pal.it | ⚠️ ROTTO |

Altri comuni scraper attivi (non capoluogo): **Palma di Montechiaro** (084028, jCityGov).

---

## Report per comune

### Agrigento — ✅ OK

- **URL portale:** albo pretorio su ASP.NET + DevExpress (sito comunale)
- **Scraper:** `src/talia/modulo2_scraping/fonti/agrigento.py` — Playwright
- **Test 2026-06-28:** 224 atti trovati in 1 pagina (periodo 2026-06-03 → 2026-06-26). Nessun errore.
- **Escluso dal default run:** richiede Playwright installato (`playwright install chromium`). ~3 min/run per le attese fisse.
- **Problemi noti:**
  - Selettore paginazione `a[href*="PBN"]` fragile: cambio di markup DevExpress → stop silenzioso
  - Attese fisse (4s goto + 2s click): inadeguate su connessioni lente o server sotto carico
  - Regex `_RE_PERMALINK` dipende dall'ordine dei parametri querystring (`anno=` prima di `numero=`): se invertiti, i dati si corrompono silenziosamente
  - Finestra di match HTML hardcoded a 800 char: oggetti lunghi → atti saltati senza log

---

### Caltanissetta — ✅ OK

- **URL portale:** `https://caltanissetta.trasparenza-valutazione-merito.it`
- **Scraper:** `src/talia/modulo2_scraping/fonti/jcitygov.py`
- **Test 2026-06-28:** 40 atti su 2 pagine (2026-06-25 → 2026-06-26). Nessun errore. ~16s per 2 pagine (delay 0.5s/pag).
- **Problemi noti:** vedi sezione [Fragilità comuni jCityGov](#fragilità-comuni-jcitygov).

---

### Catania — ❌ da implementare

- **Piattaforma rilevata:** URBI/Maggioli (**non** HCL Domino NSF come ipotizzato in precedenza)
- **URL reale:** `https://servizionline.comune.catania.it/urbi/progs/urp/ur1ME001.sto?DB_NAME=wt00041571&w3cbt=S`
  (il link su `www.comune.catania.it/albo-pretorio` restituisce body vuoto, richiede JS)
- **Struttura:** interfaccia multi-step POST con `StwEvent` come parametro chiave. Categorie: DELIBERA (606 atti), ART.60 (77), ORDINANZE, MATRIMONIO, ecc.
- **Paginazione:** stateful server-side via POST `ElencoPubblicazioni_PaginaCorrente=N`; senza sessione JS ritorna sempre pagina 1
- **Approcci fattibili:**
  - **Opzione A (raccomandato):** enumerazione diretta per `IdMePubblica` (interi sequenziali, range noto ~108405–109443 per giugno 2026) via POST `StwEvent=91000302` — funziona senza sessione, ~30% di richieste a vuoto su ID mancanti
  - **Opzione B:** finestre temporali strette (DaData/AData giornaliero, <10 risultati → niente paginazione) — da validare
  - **Opzione C:** Playwright (browser headless mantiene sessione, paginazione standard)
- **Nota:** URBI/Maggioli è diffusa in molti comuni italiani; uno scraper `urbi.py` parametrico (cambia solo `DB_NAME`) potrebbe coprire altri comuni con zero sforzo aggiuntivo.

---

### Enna — ✅ OK

- **URL portale:** `https://enna.trasparenza-valutazione-merito.it`
- **Scraper:** `src/talia/modulo2_scraping/fonti/jcitygov.py`
- **Test 2026-06-28:** 40 atti su 2 pagine (2025-04-23 → 2026-06-26). Nessun errore. ~2s.
- **Nota importante:** l'ipotesi di "portale stale da aprile 2025" è **smentita**. L'atto più recente è del 2026-06-26. Il comune di Enna ha semplicemente una bassa frequenza di pubblicazione (~3 atti/mese). Aggiornare il DB e la documentazione di conseguenza.
- **Problemi noti:** vedi sezione [Fragilità comuni jCityGov](#fragilità-comuni-jcitygov).

---

### Messina — ⛔ bloccato (infrastrutturale)

- **URL portale:** `https://messina.trasparenza-valutazione-merito.it`
- **Scraper:** non implementato (`jcitygov.py` pronto per essere esteso con entry in `_JCITYGOV_COMUNI`)
- **Blocco:** firewall **FortiGate** con SSL inspection che risponde HTTP 403 con messaggio "This Connection is Invalid. SSL certificate expired."
  - Certificato FortiGate (`CN=mda-jcitygov-proxy`, CA Fortinet interna) scaduto il **2023-06-27** (~3 anni fa)
  - L'IP del portale è `5.180.69.64`; TLS handshake TLSv1.3 va a buon fine, ma il FortiGate blocca a livello HTTP prima di raggiungere Liferay
- **Perché `skip_ssl=True` non basta:** il parametro bypassa la verifica del certificato lato Python, ma non aggira il blocco HTTP 403 del firewall. Il problema è infrastrutturale, non certificativo.
- **Possibili soluzioni:**
  1. Contattare il Comune di Messina / gestore IT per rinnovare il certificato FortiGate
  2. Verificare se il portale è accessibile da browser reali (potrebbe richiedere browser challenge)
  3. Cercare feed alternativi (sezione Amministrazione Trasparente su `messina.it`)
- **Entry da aggiungere** (quando il blocco sarà risolto):
  ```python
  # in scripts/run_scrapers.py, lista _JCITYGOV_COMUNI
  ("messina", "https://messina.trasparenza-valutazione-merito.it", "083048", "Comune di Messina"),
  # e in _run_jcitygov_comune passare skip_ssl=True
  ```

---

### Palermo — ❌ da implementare

- **URL portale:** `https://albopretorio.comune.palermo.it/albopretorio/jsp/home.jsp`
  (attenzione: `https://www.comune.palermo.it/albopretorio.php` → 404)
- **Piattaforma:** SISPI S.p.A. — "Albo Pretorio v.1.0.1 by SISPI S.p.A." (software house municipale di Palermo, CF 03711390827)
- **Struttura:** navigazione a 3 livelli — (1) categoria `ARECOD=70`, (2) tipo documento (TD=40 DELIBERA, TD=30 DETERMINA, ecc.), (3) lista atti via POST `tabella-aggiorna.do`
- **Paginazione:** POST `tabella-aggiorna.do` con parametri `siglaStato=L`, `row=<n>`, `chiave=<key>`, `provieneDa=...`. Tutto stateful server-side.
- **Approccio obbligatorio:** **Playwright** — il bottone "Aggiorna" esegue JS che imposta `form.action` dinamicamente prima del submit; senza browser la lista risulta sempre vuota (confermato con >15 tentativi HTTP puri).
- **Template:** `agrigento.py` è il modello diretto (stesso approccio Playwright, adattare i selettori CSS per SISPI).
- **Flusso Playwright:**
  1. `page.goto("...home.jsp?modo=info&info=servizi.jsp&ARECOD=70&SERCOD=-1")`
  2. Click sul bottone della categoria desiderata (es. DELIBERA)
  3. Click "Aggiorna" → attendere la tabella
  4. Estrarre righe: `ALB_NUMPROT`, `ALB_DESANNOPROT` (anno), `SET_COD` (settore), `ALB_DESOGGETTO` (oggetto)
  5. Paginare via click "Successiva" fino a disabilitato
- **Nota:** SISPI è potenzialmente usata da altri comuni siciliani (domini affiliati: `*.sispi.it`, `*.amat.pa.it`)

---

### Ragusa — ✅ OK

- **URL portale:** `https://ragusa.trasparenza-valutazione-merito.it`
- **Scraper:** `src/talia/modulo2_scraping/fonti/jcitygov.py`
- **Test 2026-06-28:** 40 atti su 2 pagine (2026-04-15 → 2026-06-26). Nessun errore.
- **Problemi noti:** vedi sezione [Fragilità comuni jCityGov](#fragilità-comuni-jcitygov).

---

### Siracusa — ✅ OK

- **URL portale:** `https://portalepa.comune.siracusa.it`
- **Scraper:** `src/talia/modulo2_scraping/fonti/siracusa.py`
- **Test 2026-06-28:** 30 atti su 2 pagine (data 2026-06-26). Nessun errore. ~3s.
- **Problemi noti:**
  - Paginazione via regex su CSRF token nell'URL (`_RE_NEXT`): se il server cambia il parametro `tabella_albo[page]=N`, lo scraper si ferma silenziosamente alla pagina 1
  - Parsing righe (`_RE_ROW`) dipende dalla classe CSS `paginated_element`: cambio di classe → zero righe senza eccezione
  - Celle data (`cells[3]`/`cells[4]`) lette con guard `if len(cells) > N`, ma senza log se la struttura è inattesa
  - **Nessun test unitario** (da aggiungere con HTML fixture)

---

### Trapani — ⚠️ ROTTO

- **URL portale:** `https://servizi-trapani.e-pal.it/AlboOnline/ricercaAlbo`
- **Scraper:** `src/talia/modulo2_scraping/fonti/trapani.py`
- **Test 2026-06-28:** **0 atti su 2 pagine**. Nessuna eccezione (il portale risponde HTTP 200), ma `_RE_PANEL` non estrae nessun record.
- **Causa probabile:** la struttura HTML di `e-pal.it` è cambiata rispetto a quella attesa dalla regex `_RE_PANEL` (lookahead per delimitare il div `panel panel-primary`). Da verificare scaricando la pagina grezza e confrontando con la regex.
- **Fix necessario:** scaricare l'HTML corrente, aggiornare `_RE_PANEL` e aggiungere un test con fixture HTML.
- **Vedi:** [BUG-4 in bugs.md](../bugs.md)

---

## Fragilità comuni jCityGov

Valgono per tutti i comuni su `*.trasparenza-valutazione-merito.it` (Caltanissetta, Enna, Ragusa, Palma; Messina quando sbloccata):

| Fragilità | Impatto | Fix suggerito |
|-----------|---------|--------------|
| Paginazione `_RE_NEXT` cerca solo la stringa, non estrae l'URL | Stop silenzioso se Liferay cambia parametri | Estrarre l'URL reale dal link o verificare lo status della risposta paginata |
| Retry fisso a 1, solo `TimeoutError` | Errori HTTP 4xx/5xx propagano senza retry | Estendere `_fetch` a gestire `urllib.error.HTTPError` + backoff |
| 0 atti non logga WARNING | Impossibile distinguere "albo vuoto" da "sito rotto" | Aggiungere `if n_trovati == 0: logger.warning(...)` |
| `skip_ssl=True` non logga | Cert scaduti passano in silenzio | Aggiungere warning quando `skip_ssl=True` è attivo |

---

## Prerequisiti per run programmate

Prima di schedulare via cron/GitHub Actions, soddisfare almeno:

- [ ] Fix Trapani (`_RE_PANEL`)
- [ ] Canary check: exit code != 0 se scraper attivo → 0 atti
- [ ] Alerting su failure (GitHub Actions: step `if: failure()` → issue/email)
- [ ] Agrigento: `playwright install chromium` nel workflow CI
- [ ] ANAC: decidere se mantenere `--anac-file` manuale o implementare Playwright headless

Vedi anche: [pre-cron checklist](../memory/pre-cron-checklist.md) con i 7 prerequisiti completi.

[→ 14 Roadmap scraper](08-roadmap.md) | [← 12 Schema DB](12-schema-db.md)
