# TAL-62 — Scraper "Amministrazione Trasparente" (jCityGov + Halley)

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🕷️ SCR
- **Priorità:** P1
- **Stato:** In Progress
- **Branch:** `feat/TAL-60-streamlit-modulo1` (continua sullo stesso branch, su
  richiesta di Dom — tema diverso da TAL-60/61 ma stessa sessione)

## 🎯 Obiettivo

Raccogliere atti anche dalla sezione "Amministrazione Trasparente" (D.lgs. 33/2013),
**in aggiunta** all'Albo Pretorio esistente, non in sostituzione. Motivazione: l'Albo
Pretorio è una bacheca temporanea (15-30gg di pubblicazione legale) — verificato in
TAL-59/discussione precedente che la maggioranza degli atti già raccolti ha già
superato la propria `data_scadenza`, quindi il link sorgente citato nei red flag è
spesso già morto. Amministrazione Trasparente ha obblighi di ritenzione molto più
lunghi per legge.

## 📚 Contesto

Emerso da una segnalazione di Dom (link morti su due red flag reali, Acate e Aci
Bonaccorsi) che ha portato a scartare tre proposte di "conservare noi una copia"
(archivio terzo tipo Wayback Machine, disclaimer, cattura locale via Playwright — tutte
respinte per manutenzione/mancanza di verificabilità indipendente) prima di arrivare
alla soluzione reale: il comune è già obbligato per legge a tenere questi atti altrove
più a lungo. `talia.md`/`docs/wiki/07-fonti-dati.md` segnalavano già Amministrazione
Trasparente come fonte ideale fin dall'inizio del progetto — mai implementata.

## 🔬 Tentativi

### 2026-08-16 — Tentativo 1: ricognizione jCityGov
**Approccio:** Playwright (rendering reale, curl non basta: la sezione è Liferay/JS)
su Ragusa e Acate per capire come si raggiunge il contenuto di Amministrazione
Trasparente.
**Esito:** ✅
**Appreso:**
- jCityGov serve Amministrazione Trasparente con lo **stesso motore "igrid"**
  dell'Albo Pretorio (stessa struttura di riga `master-detail-list-line`/`data-id`,
  stesso portlet `jcitygovalbopubblicazioni_WAR_jcitygovalbiportlet`, stessa
  paginazione `paginationAction=NEXT`) — solo una categoria diversa, non
  un'applicazione separata.
- Le categorie (e i relativi path `igrid/<id>`) si scoprono con la stessa tecnica già
  usata da `_scopri_risorse_alternative` (TAL-49, attributi `data-resource`/
  `data-mainurl`), puntata su `/web/trasparenza/trasparenza` invece che su
  `/web/trasparenza/albo-pretorio`. **Playwright non serve a runtime**, solo per la
  ricognizione iniziale — sia la scoperta categorie sia il fetch delle pagine sono
  richieste HTTP dirette (verificato con `curl` puro dopo la scoperta).
- Confermata la premessa: un atto in "Bandi di concorso" (Ragusa) aveva
  `data_scadenza = 2031-12-31`, non giorni di distanza.
- **Trovata anche un'eccezione**: alcune categorie (es. "Titolari di incarichi...", e
  su Acate anche "Bandi di concorso") puntano a un path `/pas/-/pas/igrid/<id>`
  invece che `/papca-*/-/papca/igrid/<id>` — portlet `jcitygovalbosoggetti` (registro
  di persone/incarichi, non di atti): stessa regex di riga, 0 risultati, perché la
  struttura è diversa, non perché la categoria sia vuota. Filtrate esplicitamente
  (solo famiglia "papca").

### 2026-08-16 — Tentativo 2: implementazione jCityGov
**Approccio:** `scopri_categorie_trasparenza()` + `scarica_atti_trasparenza()` in
`jcitygov.py`, che riusano `_parse_pagina`/`_RE_NEXT` già esistenti (nessun parser
nuovo: stesso motore, solo entry point diverso).
**Esito:** ✅
**Appreso:** verificato dal vivo su Ragusa (088009): 35 atti raccolti su "Bandi di
concorso" attraverso più pagine (paginazione confermata), tutti con
`fonte_scraper = "jcitygov_trasparenza"` e `data_scadenza` in anni futuri (2031), URL
`mostraDettaglio` nello stesso formato stabile dell'Albo Pretorio. 6 nuovi test
(`tests/test_jcitygov.py`) con fixture che ricalcano l'HTML reale.

### 2026-08-16 — Tentativo 3: ricognizione + implementazione Halley
**Approccio:** stessa metodologia su Aci Bonaccorsi (Halley).
**Esito:** ✅ con una scoperta importante
**Appreso:**
- Halley serve Amministrazione Trasparente con un'**applicazione completamente
  separata** dall'Albo Pretorio: Zend Framework (`/zf/index.php/trasparenza/...`),
  non `/mc/mc_p_*.php` — HTML diverso, nessun riuso di codice possibile con
  `halley.py` esistente (a differenza di jCityGov). Nessuna sessione richiesta, come
  l'Albo Pretorio.
- Menu categorie: link diretti `<a href='.../categoria/<id>'>Nome</a>` — l'ID è già
  nell'URL, scoperta più semplice che su jCityGov.
- Righe documento: `<tr data-href="...">` con link a
  `visualizza-documento-generico/categoria/<cat>/documento/<id>`, data "Inserita
  il ...". **Nessuna data di scadenza sulle righe** (a differenza dell'Albo
  Pretorio, che la espone sempre) — un segnale in più a favore della ritenzione
  permanente. Paginazione via path (`.../page/<N>`), non querystring.
- Esiste un export CSV (`esporta-csv/categoria/<id>`) ma **senza l'URL del
  documento** — utile solo per un umano in Excel, non per lo scraping (serve
  comunque la tabella HTML per `url_fonte`, obbligatorio per l'esplicabilità).
- Verificato dal vivo su Aci Bonaccorsi (087001): 20 atti raccolti su 2 pagine di
  "Bandi di concorso"; il menu espone **17 pagine totali** per quella sola categoria
  — storico profondo, coerente con l'ipotesi di ritenzione lunga.
- **Trovata anche una variabilità reale**: un secondo tenant provato (Vittoria) usa
  una piattaforma Halley più recente ("Stanza del cittadino") **senza il path
  `/zf/...`** (404, gestito senza crash — ritorna `{}`) — stessa eterogeneità già
  documentata per altri vendor nel progetto (jCityGov "papca-ap" vs "papca-g", TAL-49).
  Fuori scope qui: comune specifico da riprendere se/quando serve.
- 9 nuovi test (`tests/fonti/test_halley.py`) con fixture reali.

## 📋 Spec (v1, come implementato)

- Nuove funzioni `scopri_categorie_trasparenza()` + `scarica_atti_trasparenza()` in
  `jcitygov.py` e `halley.py` (non un modulo/file nuovo: stesso vendor, stesso
  `base_url`/codice ISTAT già gestiti dal registro).
- `fonte_scraper` distinto (`jcitygov_trasparenza` / `halley_trasparenza`) — non
  sovrascrive né sostituisce gli atti dell'Albo Pretorio esistente, che restano
  `jcitygov` / `halley`.
- Categorie di default limitate a `("Bandi di concorso", "Bandi di gara e
  contratti")` — le uniche rilevanti per i red flag esistenti (TAL-23/48); la
  tassonomia D.lgs. 33/2013 ne ha decine (bilanci, organigramma, consulenti...),
  fuori scope per ora.
- Nessuna registrazione in `registry.py`/`run_scrapers.py` ancora: le funzioni esistono
  e sono testate/verificate dal vivo, ma non fanno ancora parte del run automatico.

## ❓ Domande aperte (bloccanti prima della messa in produzione)

- [ ] **Deduplicazione con l'Albo Pretorio**: un bando pubblicato sull'Albo probabilmente
  compare anche in Amministrazione Trasparente (stesso atto, due URL diversi,
  `UNIQUE(ente_id, url_fonte)` non lo intercetta). Impatto su `engine/catena.py` (rischio
  di procedimenti duplicati/doppi conteggi nei red flag) — imparentato con TAL-52
  (dedup atti tra scraper ridondanti), stesso problema concettuale ma dentro la stessa
  piattaforma invece che tra piattaforme diverse. **Non ancora deciso come gestirlo.**
- [ ] **Download/persistenza del documento**: la discussione che ha originato questa
  card aveva anche sollevato se scaricare/estrarre il testo (non solo l'URL) per gli
  atti citati nei red flag. Non ancora affrontato — `testo_estratto`/`hash_sha256`
  restano vuoti anche per gli atti raccolti qui.
- [ ] Wiring in `registry.py`/`run_scrapers.py` per il run automatico (oggi le funzioni
  sono richiamabili ma non collegate).
- [ ] Estensione alle altre piattaforme (portalepa, catania, palermo, urbi, trapani,
  hspromila — 14% dei dati, non ancora verificate per fattibilità).

## 🧪 Criteri di accettazione (per ora)

- [x] `scarica_atti_trasparenza()` funzionante e verificata dal vivo su jCityGov
  (Ragusa) e Halley (Aci Bonaccorsi) — non solo su fixture.
- [x] Non tocca/non rischia gli scraper Albo Pretorio esistenti (funzioni nuove,
  nessuna modifica al comportamento di `scarica_atti()`).
- [x] Test con fixture realistiche per entrambe le piattaforme.
- [ ] Deduplicazione con l'Albo Pretorio (bloccante prima del run automatico).
- [ ] Decisione su download/persistenza (bloccante prima del run automatico, vedi
  discussione in HANDOFF.md 2026-08-16).

## 📝 Note

**Playwright non dichiarato come dipendenza** (trovato durante la ricognizione): era
già usato da `agrigento.py`/`palermo.py`/`serviziolinealbo.py` (import lazy) ma mai in
`pyproject.toml` — funzionava solo perché installato manualmente in passato. Corretto
con un nuovo gruppo extra `playwright` (non serve a runtime per questa card, solo per
la ricognizione — ma è comunque un gap reale per chi installa da zero).
