# HANDOFF.md — Stato sessione

> Aggiornato: 2026-08-09 (branch `feat/TAL-53-nome-ruolo-graduatoria`, staccato da
> `feat/sweep-comuni-mancanti`: check 6 arricchisce il messaggio col ruolo del firmatario
> e incrocia la sovrapposizione con la tempistica della graduatoria (TAL-53); check 3
> ora arricchisce il retrieval RAG coi riferimenti dei check già flaggati (TAL-54),
> timeout LLM alzato 300s→900s e temperatura fissata a 0 per un giudizio riproducibile.
> `/code-review` multi-agente lanciato su tutto il branch (17 findings consolidati); i
> più rilevanti corretti nella stessa sessione, con 4 nuove card (TAL-55/56/57/58: log
> silenziosi negli scraper, deduplicazione codice scraper, pulizia Modulo 1, dashboard).
> 6 card in Review (TAL-53…TAL-58). PR #17 aperta; risolti i conflitti di merge con
> `main` (assorbito PR #16 — sweep comuni, Pachino/Barrafranca, Nicosia — già confluito
> qui in sviluppo, conflitti reali solo su HANDOFF.md/BOARD.md). 598 test verdi.)

---

## Sessione 2026-08-07 — TAL-53: check 6 nome↔ruolo + tempistica graduatoria

**Richiesta di Dom:** "stacca un nuovo branch a partire da questo, comincia a
implementare l'associazione nome-ruolo firmatari e l'incrocio con la tempistica
graduatoria" — i due gap lasciati esplicitamente aperti nei Consuntivi di TAL-5 e TAL-9
(colonna Review di BOARD.md dal 2026-07-25). Branch `feat/TAL-53-nome-ruolo-graduatoria`
staccato da `feat/sweep-comuni-mancanti` (PR #16 ancora aperta, non merge-blocking:
questo branch parte dal lavoro scraper esistente per convenzione "stacca da questo",
non da `main`). Nuova card **TAL-53** (spec-driven, nessuna domanda bloccante — vedi
sotto per l'unica assunzione documentata).

**Scoperta preliminare:** l'associazione nome↔ruolo esisteva già come estrazione
generale in `engine/attori.py` (TAL-13, Done da tempo) ma non era mai stata agganciata
al check 6 — il lavoro vero non era "costruire l'associazione" ma *usarla* dentro il
check, più costruire da zero l'estrazione della tempistica graduatoria (che non
esisteva).

**Fatto:**
- **Refactor minimo** (`checklist/_date_utils.py`): `filtra_date_ccnl`/`data_estrema`
  estratte da `check2_termini.py` (private, duplicate altrimenti) in un helper
  condiviso, ora usato anche da check 6 per calcolare la data dell'annullamento.
  Nessuna regressione (stessi test di check 2 verdi).
- **`engine/graduatoria.py`** (nuovo): `estrai_data_graduatoria()` — euristica
  deterministica su "graduatoria" + "approvat[ao]"/"approvazione" + data vicine.
  Punto delicato trovato **durante lo sviluppo dei test, non dopo**: ancorare la
  data più vicina alla parola "graduatoria" sceglieva a volte una data estranea solo
  perché testualmente più vicina (es. la data dell'annullamento stesso, scritta prima
  di "graduatoria" nello stesso paragrafo) invece della data che segue realmente
  "approvat[ao]... del gg/mm/aaaa". Corretto ancorando la ricerca della data alla
  parola di approvazione (finestra più stretta, 80 caratteri dopo), con fallback a
  prima di "graduatoria" per il pattern raro inverso ("in data X è stata approvata la
  graduatoria").
- **`check6_firmatari.py`**: arricchito, non riscritto — stesso algoritmo di matching
  firmatari di prima (`_stesso_firmatario`, sottoinsieme di token). Aggiunte: (1) il
  messaggio nomina il ruolo (via `attori.estrai_attori`) quando individuabile, es. "il
  Segretario Generale Mario Rossi" invece del solo nome; (2) se la sovrapposizione dei
  firmatari coincide con un annullamento entro **60 giorni** dalla graduatoria trovata,
  l'esito sale da 🟡 a 🔴 con la graduatoria citata in più. Degrado sempre verso il
  comportamento precedente (🟡) se ruolo o graduatoria non sono disponibili — **nessuna
  regressione sui 5 test di check 6 preesistenti**, verificato prima di aggiungerne di
  nuovi.
- **Assunzione documentata, non normativa** (come già il termine dei 12 mesi in check
  2): la soglia dei 60 giorni per "a ridosso della graduatoria" è una scelta euristica
  di prodotto, esplicitamente segnalata nella card TAL-53 come da validare con ⚖️ LEX
  su fascicoli reali (nessuno dei fascicoli TAL-12 letti finora cita esplicitamente
  l'approvazione della graduatoria nell'atto di autotutela).
- 10 nuovi test (6 `test_graduatoria.py`, 4 in `test_checklist.py`): ruolo nel
  messaggio, escalation 🔴, graduatoria lontana → resta 🟡, nessuna menzione →
  comportamento invariato.

**582 test verdi (erano 572), ruff pulito** (nota: `ruff format` locale su Python 3.12
proponeva di riformattare ~30 file preesistenti non toccati in questa sessione — stesso
scarto di versione già documentato nell'entry del 20/07 più sotto; applicato `ruff
format` solo ai file toccati, non all'intero repo).

**Non fatto:** nessuna verifica su un fascicolo reale con menzione di graduatoria (i
fascicoli TAL-12 disponibili non ne hanno una) — resta un'euristica testata solo su
casi sintetici, da validare al primo fascicolo reale che la contiene. Nessun
`/code-review` multi-agente lanciato (solo self-review manuale, vedi sotto).

**Self-review post-commit (stesso giorno):** rilettura mirata del diff dopo il primo
commit ha trovato un bug reale in `_esito_graduatoria` — la citazione della graduatoria
veniva attribuita al testo sbagliato (identità su un'entità ricreata da una chiamata di
estrazione separata, che quindi non coincide mai con l'oggetto già presente
nell'atto). Nessun crash (gli offset vengono clampati in silenzio da `estratto()`), ma
una citazione vuota/sbagliata — violazione dell'esplicabilità. Corretto tenendo
esplicita la provenienza invece di ridedurla per identità; aggiunto un test che
verifica il *contenuto* della citazione, non solo il conteggio (dettaglio in TAL-53,
Tentativo 2). Nuovo commit separato (`e6c17df`, non un amend — coerente con la
convenzione di preferire commit nuovi), ancora 582 test verdi.

---

## Sessione 2026-08-08 — TAL-54: check 3, retrieval RAG cieco ai check già flaggati

**Richiesta di Dom:** dopo aver chiesto come è coinvolto l'LLM nel progetto, ha chiesto
di lanciare davvero check 3 (LLM, TAL-11) con Ollama locale sui fascicoli reali di
TAL-12, invece di limitarsi a spiegarlo. Restato sullo stesso branch
`feat/TAL-53-nome-ruolo-graduatoria` su richiesta esplicita di Dom ("rimani su questo
branch"), pur essendo un tema diverso da TAL-53 — nuova card **TAL-54** invece di un
nuovo branch.

**Trovato girando l'LLM reale (non mockato) su fascicoli reali:**
1. **Timeout insufficiente**: `llm._TIMEOUT_SECONDI = 300` non basta su questa macchina
   (CPU) per un prompt reale — 344.8s sul fascicolo 1, 423.8s sul fascicolo 3, sempre
   in timeout con la CLI (`talia analizza --llm`). Non ancora corretto in questa
   sessione (segnalato a Dom, non ancora confermato se alzarlo).
2. **Retrieval RAG cieco a temi già noti alla pipeline** (bug sostanziale, poi corretto
   — vedi TAL-54): sul fascicolo 1, i 5 passaggi normativi recuperati da BM25 per il
   check 3 non includevano mai il GDPR, nonostante (a) il corpus lo contenga
   (`ue/gdpr-679-2016.md`), (b) sia recuperabile con una query mirata, e (c) il tema sia
   esattamente quello già individuato dal check 7 deterministico (GDPR breach, 🔴 con i
   riferimenti giusti). Causa: la motivazione dell'atto usa "segretezza"/"riservatezza",
   mai "dati personali"/"GDPR" — zero overlap lessicale col documento normativo, pur
   trattandosi dello stesso tema concettuale. Limite classico del BM25 lessicale puro.
3. **Nessun vincolo di grounding nel prompt**: la `spiegazione` del LLM non citava mai i
   passaggi allegati, pertinenti o meno — nessuna garanzia verificabile che il giudizio
   ne tenesse conto.

**Fix (`check3_motivazione.py`):**
- `_cerca_passaggi_rag()`: oltre alla query sulla motivazione, una query BM25 separata
  per ciascun check 🟡/🔴 precedente sui suoi `riferimenti_normativi`, un passaggio
  garantito a testa, dedup, **nessun troncamento finale**. Primo tentativo (concatenare
  tutti i riferimenti in un'unica query) verificato insufficiente: il contributo GDPR (3
  voci) restava annegato dal punteggio cumulato di check con più voci (dettaglio in
  TAL-54, Tentativi 1-2).
- Prompt: istruzione esplicita a dichiarare in `spiegazione` il passaggio normativo usato
  (fonte tra parentesi quadre) o l'assenza di uno pertinente.
- 7 nuovi test (stub `_IndiceSelettivo` che riproduce il caso GDPR) + verificato anche
  sul fascicolo reale (`genera` mockato, `esegui_checklist` reale): `ue/gdpr-679-2016.md`
  ora compare in `riferimenti_normativi`, prima assente.

**589 test verdi (erano 582), ruff pulito** (solo sui file toccati).

**Timeout LLM corretto (stessa sessione, dopo conferma di Dom):** `llm._TIMEOUT_SECONDI`
alzato da 300s a **900s**, coi tempi reali misurati (344.8s/423.8s) nel commento —
margine ampio per fascicoli più pesanti dei due testati.

**Verifica aggiuntiva su check-7 (GDPR, TAL-14):** richiesto da Dom un controllo se
servissero altri fix lato GDPR oltre al retrieval di check 3. Riletto `check7_gdpr.py`
e i suoi test: nessun bug trovato. Riverificato anche su fascicolo 3 (🔴 su fascicolo 1,
dove il breach è descritto; ⚪ NON_APPLICABILE su fascicolo 3, che non ne parla —
comportamento atteso, non un falso negativo). Il gap GDPR di questa sessione era
interamente nel retrieval di check 3 (già corretto sopra), non nel check 7 stesso.

**Non fatto:** il retrieval resta comunque cieco ai temi che **nessun** check
deterministico ha ancora individuato (limite noto, documentato in TAL-54): il fix riusa
segnale già calcolato, non risolve il problema alla radice. Un retrieval a embedding
locale (gratuito, coerente con budget≈0) lo risolverebbe in generale, ma è un cambio di
architettura proposto e non deciso in questa sessione. Il check-8 (DPO = Segretario →
conflitto di interessi, già annotato come feature futura in memoria di progetto) resta
fuori scope: richiede dati esterni (TAL-25).

**Instabilità del giudizio scoperta rilanciando check 3 (stessa sessione, dopo richiesta
di Dom di rieseguirlo su fascicolo 1 salvando l'output):** due run identici sullo stesso
fascicolo hanno dato giudizi diversi (🟡 poi 🟢) — il secondo riproduceva esattamente il
falso negativo che TAL-11 aveva già corretto (motivazione basata su un fatto "presunto"
letto come accertato). Causa: `check3_motivazione.genera(prompt)` non fissava mai la
temperatura di campionamento di Ollama (`engine.catena.classifica_ruolo_llm` aveva già
il pattern giusto, ma a un livello più basso). Fix: `genera()` accetta ora `opzioni`,
check 3 chiama sempre con `temperature: 0`. Verificato con 2 run reali consecutivi
post-fix: esito e spiegazione **identici byte per byte** (dettaglio in TAL-54,
Tentativo 3). 592 test verdi (erano 589).

**`/code-review` multi-agente (8 angoli, `main...HEAD`):** trovati 2 bug reali nel
codice di questa card, corretti nello stesso ciclo (dettaglio in TAL-53, Tentativo 3):
(1) `graduatoria.py` poteva scegliere la data sbagliata quando più occorrenze di
"approvat[ao]" comparivano nella finestra attorno a "graduatoria" (ora sceglie la più
vicina, non la prima in assoluto); (2) `check6_firmatari.py` poteva dare un 🔴 con
`delta=0` fuorviante quando la data della graduatoria era anche l'unica/più recente
data dell'atto (ora esclusa dal pool prima di calcolare la data di annullamento). 594
test verdi (erano 592). Gli altri findings del code-review (duplicazione retry-logic
tra scraper, mancato logging 0-atti in `serviziolinealbo.py`, query dashboard non
cachate, ecc.) riguardano commit precedenti a questa sessione, non toccati: riportati
ma non corretti qui — vedi report `/code-review` per l'elenco completo.

**Aperte 4 card di follow-up dal `/code-review` (stessa sessione, richiesta esplicita di
Dom "apri le card, ma sistemali in questo branch"), tutte corrette e testate:**
- **TAL-55** (scraper, fallimenti silenziosi): `serviziolinealbo.py` ora logga WARNING
  su atto scartato (anchor/span mancante) e su 0 atti totali; aggiunto il test "pagina
  corrotta" che mancava (convenzione CLAUDE.md).
- **TAL-56** (scraper, deduplicazione): `strip_html()`/`TIPI_ATTO_DEFAULT` estratte in
  `utils.py`, usate da 4-5 scraper — effetto collaterale: corretto un drift già presente
  (`nicosia.py` non intercettava "avvisi", le altre copie sì). `hspromila.py` allarga il
  retry a `(TimeoutError, urllib.error.URLError)` come `halley.py`. **Non toccati**
  `jcitygov.py` (pre-esistente, fuori dal diff) né l'unificazione completa del retry
  su 3 scraper né il consolidamento `serviziolinealbo.py`/`agrigento.py` — decisioni di
  architettura proposte, non eseguite (rischio su scraper già in produzione).
- **TAL-57** (Modulo 1, pulizia minore): `_RE_MOTIVAZIONE` non tronca più la motivazione
  se "determina/decreta/dispone" compare a inizio riga *dentro* il testo (solo se è
  un'intestazione isolata); troncamento citazioni deduplicato (`_offset_fine_troncato`);
  `IndiceCorpus.cerca()` precompute frequenze invece di ricostruirle ad ogni chiamata
  (verificato anche sul corpus reale, stessi risultati); due costanti gemelle in
  `graduatoria.py` unificate. **Non unificato** il matching firmatari di check6
  (astrazione prematura per 2 soli chiamanti con tipi diversi).
- **TAL-58** (dashboard): `_carica_enti`/`_carica_flags_per_ente` caricate una volta in
  `main()` invece che duplicate tra tab; avviso privacy piccoli comuni unificato in un
  helper; ternario annidato → dict lookup; somma copertura riusata invece di
  ricalcolata. Verificato **dal vivo**, non solo staticamente: DB di test reale +
  `streamlit.testing.v1.AppTest` (esegue l'intero script) → 0 eccezioni.

598 test verdi (erano 594), ruff pulito. I findings restanti del `/code-review` (vedi
`ReportFindings` nella conversazione) sono tutti o pre-esistenti a questa sessione o
scelte di architettura deliberatamente rimandate, documentate nelle rispettive card.

**Prossimo passo:** PR #17 aperta (https://github.com/dom3095/talia/pull/17), conflitti
di merge con `main` risolti; in attesa di review/merge di Dom su tutte le 6 card
(TAL-53…TAL-58).

---

## Sessione 2026-08-06 (continua) — Pachino/Barrafranca con Playwright

**Richiesta di Dom:** "non possiamo usare playwright?" (dopo aver segnalato Pachino e
Barrafranca come "stessa famiglia di Agrigento, richiede Playwright, non approfondito
per limiti di tempo"). Verificato che Playwright è già installato e funzionante
(Chromium incluso, usato per Agrigento) — nessun ostacolo tecnico, solo non ancora fatto.

Con Playwright, navigando fino a `/ServiziOnLine/AlboPretorio/AlboPretorio`, confermato
che Pachino e Barrafranca usano la **stessa identica piattaforma DevExpress di
Agrigento** (stesso DOM: span `text-custom p-1`, permalink `data-link`, paginazione PBN).
Nuovo scraper **generico** `src/talia/modulo2_scraping/fonti/serviziolinealbo.py`
(parametrico su base_url/codice_istat) invece di duplicare `agrigento.py` — che resta
intatto e dedicato, per non introdurre rischio su uno scraper già verificato in
produzione senza necessità concreta.

Unica variazione reale tra i due tenant: il titolo a volte include un riferimento
settoriale finale ("- NNNN/YYYY del DD/MM/YYYY", visto su Barrafranca, assente su
Pachino) — gestito scartandolo prima della classificazione del tipo atto. Bug trovato e
corretto durante lo sviluppo: la prima versione usava l'anno invece del numero come
chiave del dizionario permalink→URL, causando il filtro quasi totale degli atti
(1/178 sopravvissuto); poi riscritta seguendo lo stesso approccio più robusto già
verificato in `agrigento.py` (permalink-first, span ancorato via `data-bs-target`)
invece del mio primo tentativo più fragile (scan sequenziale con finestra euristica).

Verificato con `scarica_atti()` reale: **178 atti Pachino, 90 atti Barrafranca**.
Entrambi `escluso_default` nel registro (come Agrigento: Playwright più lento, non nel
run automatico — vanno lanciati esplicitamente con `--scrapers pachino barrafranca`).
16 nuovi test (`tests/fonti/test_serviziolinealbo.py`).

Tentato anche un bypass di **Leonforte** (Cloudflare, segnalato come bloccato
nell'esplorazione precedente) con Playwright: la sfida Cloudflare resta attiva
indefinitamente anche con un browser reale (non un problema di rendering JS ma di
bot-detection attiva). Non tentato un bypass più aggressivo di proposito — aggirare una
misura anti-bot attiva non è nello spirito del progetto, stessa linea già seguita per
il WAF ANAC e per Messina (entrambi richiedono intervento lato server, non evasione).

**Copertura risultante: 258 comuni attivi (era 256), 4.132.778 abitanti (83,0%, era
82,0%)**. Restano **85 comuni mai censiti**.

**572 test verdi (erano 556), ruff pulito, registro validato (312 righe).**

---

## Sessione 2026-08-06 (continua) — Esplorazione manuale 10 comuni residui

**Richiesta di Dom:** "puoi continuare a esplorare altri 10 dei comuni mancanti? crea
gli scraper se puoi" (dopo i due sweep automatici, sui 10 comuni residui più popolosi:
Comiso, Aci Catena, Floridia, Pachino, Bronte, Carlentini, Palagonia, Nicosia,
Barrafranca, Leonforte).

A differenza degli sweep automatici (pattern noti su tanti comuni), qui ogni comune è
stato esplorato singolarmente (link "albo pretorio" in homepage, sottodomini noti,
`wp-sitemap.xml` per i siti WordPress) — nessun pattern comune tra i 10, ognuno è un
caso a sé.

**2 attivati:**
- **Aci Catena** (28.749 ab.): jCityGov standard, ma su dominio proprio
  (`trasparenza.comune.acicatena.ct.it`) invece del vendor condiviso
  `trasparenza-valutazione-merito.it` — non lo intercetta lo sweep automatico, che
  controlla solo quel dominio. **Nessun codice nuovo**: `jcitygov.py` accetta già
  `base_url` come parametro. +1.000 atti (backfill storico completo).
- **Nicosia** (14.272 ab.): WordPress "Developers Italia" (stesso tema di Corleone, ma
  qui la tassonomia "Albo Pretorio" è viva). **Nuovo scraper dedicato**
  `src/talia/modulo2_scraping/fonti/nicosia.py` (stesso schema di `ribera.py`): lista
  paginata via tassonomia + una fetch di dettaglio per atto (data reale e descrizione
  non sono nella pagina lista). Solo atti in pubblicazione (~12, non uno storico) —
  serve scraping continuo, stesso pattern di Palermo/Catania. 11 nuovi test
  (`tests/fonti/test_nicosia.py`).
  Nota per il futuro: il backend reale di Nicosia è **URBI** (`asp.urbi.it`, DB_NAME
  `n201401` esposto nei link "Scarica documento"), ma con un frontend più recente
  ("Bootstrap ITALIA") che non risponde al flusso HTTP di `urbi.py` (costruito per
  l'interfaccia di Catania/Favara/Raffadali) — non approfondito ora. Se in futuro
  emergono altri comuni sulla stessa piattaforma nuova, conviene investire lì invece di
  replicare scraper WordPress uno per uno.

**8 approfonditi, non ancora scriptabili in modo economico** (dettagli e piattaforma
identificata per ciascuno in
[14-censimento-albi.md](docs/wiki/14-censimento-albi.md)): Comiso (JSF/PrimeFaces
stateful), Pachino e Barrafranca (ASP.NET DevExpress, famiglia Agrigento → Playwright),
Bronte (URBI ma flusso da reverse-engineerare come Catania), Leonforte (Cloudflare bot
protection), Floridia e Palagonia (nessuna piattaforma identificata), Carlentini
(sottodominio WordPress separato, struttura non chiarita).

**Copertura risultante: 256 comuni attivi (era 254), 4.096.733 abitanti (82,0%, era
81,0%)**. Restano **87 comuni mai censiti**.

**556 test verdi (erano 545), ruff pulito, registro validato (310 righe).**

---

## Sessione 2026-08-06 (continua) — Secondo sweep comuni residui (106 → 89 mancanti)

**Richiesta di Dom:** "lavorerei a censire gli altri comuni" (i 106 rimasti dopo lo
sweep del 26/07). Aggiunto allo stesso branch `feat/sweep-comuni-mancanti`/PR #16 già
aperta (un branch separato creato per errore e poi riportato qui su richiesta di Dom).

**Metodologia** (stessa dei sweep precedenti, con 2 estensioni): più varianti di slug
per comune (calibrate confrontando lo slug atteso con l'host reale dei 195 comuni già
censiti — 191/195 combaciavano con la concatenazione semplice) + pattern Halley "EGOV"
scoperto lo stesso giorno con Cefalù.

**Bug critico trovato e corretto nel proprio script di sweep** (non nel codice di
produzione): il fingerprint jCityGov si basava sullo status HTTP, ma
`trasparenza-valutazione-merito.it` risponde **403 con una pagina di errore generica per
qualsiasi sottodominio, anche inesistente** — un catch-all del vendor. Risultato del
primo giro: **106/106 "hit"**, tutti falsi. Diagnosticato testando un sottodominio
palesemente inventato (stesso 403) e un comune jCityGov reale noto (marker
`jcitygov-albi-theme` nel body, assente nel falso positivo). Corretto richiedendo quel
marker; rilanciato: **17 hit reali** su 106.

**Verifica end-to-end** (come da principio ormai consolidato — mai attivare dal solo
fingerprint): tutti e 17 chiamati con le funzioni `scarica_atti()` di produzione.
**16 con atti reali** → attivati. **1** (Valguarnera Caropepe, Halley EG) con
fingerprint corretto ma pagina vuota (0 righe in tabella, verificato anche con una
seconda chiamata isolata) → lasciato `pending`. **1** (Mirabella Imbaccari) richiedeva
`skip_ssl` (stessa causa di Siculiana: certificato valido, catena incompleta).

**Copertura risultante: 254 comuni attivi (era 238), 4.053.712 abitanti (81,0%, era
79,0%)** — numeri confermati anche dalla nuova tab Mappa copertura della dashboard
(`streamlit.testing.v1.AppTest` su `talia.db` reale). Restano **89 comuni mai censiti**
(~500.000 abitanti), nessun pattern di piattaforma noto trovato — candidati per
ricognizione manuale, non più sweepabili in automatico con i pattern esistenti.

**545 test verdi (invariato — solo dati di registro, nessun codice nuovo), ruff pulito,
registro validato (308 righe).** Dettagli completi in
[14-censimento-albi.md](docs/wiki/14-censimento-albi.md). Script di sweep/verifica non
committati (one-off in scratchpad, stessa convenzione).

---

## Sessione 2026-08-06 (continua) — Dashboard: tab Statistiche + Mappa copertura (TAL-30)

**Richiesta di Dom:** dashboard con statistiche di ingestione (documenti raccolti negli
ultimi giorni, aggregati) + mappa interattiva della Sicilia con i comuni colorati per
copertura scraper.

**Fatto** in `src/talia/modulo3_dashboard/app.py`:
- **Tab 📈 Statistiche**: KPI (atti totali, comuni con atti, atti ultimi 7/30gg), trend
  atti ingeriti per giorno (`st.bar_chart`, finestra configurabile 7-90gg), aggregati per
  provincia/tipo atto/piattaforma scraper. Tutto da query dirette su `atti`/`enti`
  (`data_accesso`, non `data_atto` — è la data di *ingestione*, coerente con la richiesta).
- **Tab 🗺️ Mappa copertura**: `pydeck.Layer("GeoJsonLayer")` su
  `data/comuni_sicilia_confini.geojson` (391 comuni, già presente in repo), colorato per
  `enti.stato_scraper` (verde=attivo/escluso_default, arancio=pending, rosso=bloccato,
  grigio=non censito/assente da `enti`). KPI popolazione coperta incrociando
  `data/comuni_sicilia.csv`. Nessuna dipendenza nuova: `pydeck` è già incluso in
  Streamlit (verificato: `pip show streamlit` lo elenca in `Requires`), niente token
  Mapbox (`map_provider="carto"`).
- **Unica eccezione al principio "la dashboard legge solo dal DB"**: la mappa incrocia
  anche i due file statici sopra, perché i confini geografici e l'elenco dei comuni mai
  censiti (assenti da `enti` per definizione) non possono venire dal DB. Documentato in
  un commento in cima alla sezione mappa di `app.py` e nella card TAL-30.
- Verificato end-to-end con `streamlit.testing.v1.AppTest` su `talia.db` reale (nessuna
  API browser disponibile in sessione): 0 eccezioni, metriche coerenti con lo stato noto
  del progetto (238 comuni coperti, 79% popolazione, 128.585 atti totali).
- 10 nuovi test (`tests/test_dashboard.py`), **545 test verdi totali**, ruff pulito.

**Non fatto:** nessuna vista storica multi-run (la mappa/statistiche riflettono solo lo
stato corrente del DB, non uno storico di run passate — coerente con la scelta del resto
della dashboard).

---

## Sessione 2026-08-05 — Riconciliazione PR #16 + run completa scraper + fix halley.py

**Contesto:** Dom aveva già mergiato PR #14 (TAL-11 check-3 LLM) e PR #15 (fix
skip_ssl/base_url) direttamente su `main` senza notifica in sessione. `feat/sweep-comuni-mancanti`
(PR #16) risultava quindi `CONFLICTING`/`DIRTY`. Riconciliato con `git merge origin/main`
(merge a 2 parent verificato con `git cat-file -p`, nessun duplicato residuo in
BOARD.md/HANDOFF.md/registro — controllato esplicitamente dopo l'incidente di stash
della sessione precedente). 533 test verdi, `ruff check` pulito, `registry.py::valida_registro`
senza errori. Push riuscito, **PR #16 ora `MERGEABLE`**.

**Run completa scraper** (`caffeinate -i python scripts/run_scrapers.py`, su `talia.db`
reale, 244 scraper attivi): **234/244 OK (95,9%)** → DB: 286 enti, 128.050 atti, 631 red
flags. 10 falliti al primo giro, tutti errori di rete (nessun parsing rotto). Analisi
dei 10 via query diretta su `scraper_runs` (più affidabile del parsing log — stdout
bufferizzato e stderr non bufferizzato si interlacciano nel file quando redirect
combinato `2>&1`, l'ordine delle righe non riflette l'ordine reale degli eventi):
- **7 flaky Halley** (`calatafimisegesta`, `maletto`, `mussomeli`, `sancipirello`,
  `sangiuseppejato`, `grammichele`, `altavillamilicia`): `ConnectionRefusedError`
  transitorio, confermato con retry manuale/`curl` a distanza di secondi — stesso
  pattern host-condiviso-sovraccarico già risolto per `hspromila.py` il 26/07, ma su
  un IP Halley diverso (`195.231.11.215`, condiviso da almeno 3 dei falliti).
  **Fix: retry con backoff 2s in `halley.py::scarica_atti`** (stesso pattern
  `jcitygov.py`/`hspromila.py`, cattura `TimeoutError` + `urllib.error.URLError`; prima
  non aveva *nessun* retry). 2 nuovi test di regressione. Dopo il fix, recuperati 5/7 al
  retry immediato (`maletto`, `altavillamilicia`, `calatafimisegesta`, `sancipirello`,
  `mussomeli`); `sangiuseppejato`/`grammichele` ancora giù al terzo tentativo — confermato
  con `curl` diretto che il server è genuinamente irraggiungibile in questo momento, non
  un bug: da ritentare in un run successivo.
- **3 non recuperabili col retry — piattaforma migrata** (bug reale, non transitorio):
  `cefalù` (spostato a `egov.comune.cefalu.pa.it`, piattaforma Zucchetti "zf", diversa da
  portalepa), `corleone` (path `/openweb/messi/public/albo.php` su IP diretto, layout
  diverso), `partanna_tp` (usa Gazzetta Amministrativa, piattaforma terza generica,
  non portalepa/halley). Già segnalati come aperti nella sessione PR #15 del 26/07 con
  la stessa causa sospettata ("base_url reale non trovato" / "layout HTML diverso") —
  confermato oggi con verifica diretta del sito. Richiedono un nuovo scraper dedicato o
  un adattamento del parser portalepa, non ancora fatto.

**535 test verdi (erano 533), ruff pulito.**

**Prossimo passo (superato, vedi sezione "Seguito stesso giorno" sotto):**
~~decidere se investire in scraper dedicati per `cefalù`/`corleone`/`partanna_tp`~~ —
risolto lo stesso giorno: Cefalù e Partanna erano solo `base_url` sbagliata (già Halley
EG), Corleone scartato (nessun registro atti reale). Resta aperto solo: valutare se il
retry di `halley.py` va esteso con un secondo tentativo (backoff più lungo), dato che
l'host condiviso `195.231.11.215` è rimasto giù per minuti, non secondi, in questa
sessione — non ancora fatto.

**Seguito stesso giorno — indagine sui 3 comuni "piattaforma migrata":**
- **Cefalù**: non serviva un nuovo scraper. Il vero portale trasparenza è
  `egov.comune.cefalu.pa.it/cefalu` (link "Albo pretorio" nel menu del sito puntava a
  `mc/mc_p_ricerca.php`, lo stesso endpoint standard di `halley.py`) — solo la `base_url`
  in registro era sbagliata (puntava al sito istituzionale `comune.cefalu.pa.it`, non al
  portale trasparenza). Corretta. **440 atti storici recuperati** (2017→2026).
- **Partanna**: stessa causa — vero portale `servizi.comune.partanna.tp.it` (Halley EG
  standard). **Ma esisteva già una riga di registro corretta e attiva per lo stesso
  comune sotto lo slug `partanna`** (non `partanna_tp`), con 570 atti già raccolti
  regolarmente: `partanna_tp` era un **duplicato di registro** con URL sbagliata, non un
  comune scoperto. Rimossa la riga `partanna_tp` invece di "fixarla" (avrebbe fatto
  girare lo stesso scraper due volte sullo stesso server). Verificato con
  `awk`/`uniq -d` sul CSV che **non ci sono altri duplicati per errore**: gli altri 5
  codici ISTAT doppi nel registro (Favignana, Campofelice di Roccella, Villabate,
  Racalmuto, San Giovanni la Punta) sono intenzionali — stesso comune su **due
  piattaforme diverse** (jCityGov + Halley/portalepa), già coperto dal backlog
  **TAL-52** (deduplicazione atti tra scraper ridondanti).
- **Corleone**: **non risolto, deliberatamente scartato**. Il sito è WordPress con un
  custom post type `documento_pubblico` ("Albo Pretorio"), ma il sitemap XML
  (`wp-sitemap-posts-documento_pubblico-1.xml`) rivela **solo 12 documenti totali**,
  quasi tutti caricati lo stesso giorno (2024-08-05, probabile migrazione una-tantum:
  giuramento sindaco, nomine settori) — non un registro atti attivo. Nessun sottodominio
  Halley (`servizi.comune.corleone.pa.it` esiste ma è una pagina Plesk di default, non
  Halley) né altra piattaforma nota trovata. Lasciato `bloccato` in registro con nota
  esplicita, per il principio "mai attivare uno scraper a 0 atti reali" (CLAUDE.md).

**535 test verdi (nessun nuovo test: solo correzioni di registro, nessun codice nuovo), ruff pulito, registro validato (291 righe).**

---

## Sessione 2026-07-26 — Sweep comuni mai censiti + fix scraper (PR #15 + questo branch)

**Contesto:** su richiesta di Dom ("possiamo fare qualcosa sugli scraper che non
funzionano o su quelli mancanti"), prima diagnosticati e corretti 4 dei 7 scraper falliti
nel run del 25/07 — **PR #15** (`fix/scraper-registro-cert-url`, branch separato da
questo): `brolo`/`pozzallo`/`sortino` (Halley, catena certificato incompleta →
`skip_ssl=true`) e `castellammare_golfo` (portalepa, `base_url` sbagliato in registro,
corretto a `castellammare.soluzionipa.it`); restano aperti `corleone` (layout HTML
diverso, serve parser dedicato) e `cefalù`/`partanna_tp` (base_url reale non trovato).
Poi, su richiesta esplicita di continuare con gli scraper mancanti: primo conteggio
sistematico di quanti comuni siciliani non avessero **nessuna**
riga nel registro (né attivo né pending) → **153 comuni, 1.072.324 abitanti**, un gap
più grande di quanto la documentazione esistente (TAL-49/50/51) suggerisse.

**Sweep di dominio** (stessa metodologia 2026-07-07: pattern noti jCityGov/Halley
EG/portalepa + fingerprint, più **Halley HSPromila** mai sweepato sistematicamente
prima): script one-off in scratchpad, lanciato sotto `caffeinate` (branch dedicato
`feat/sweep-comuni-mancanti`, indipendente da PR #14/#15). **47 hit** su 153 (34
HSPromila, 11 Halley, 2 jCityGov).

**A differenza degli sweep precedenti, ogni hit verificato con una vera chiamata a
`scarica_atti()`** (moduli di produzione), non solo il fingerprint HTTP:
- **40 confermati con atti reali** (contenuto controllato a campione: titoli di atti
  plausibili, es. "ESTATE RIESINA 2026 PRIMA PARTE - IMPEGNO DI SPESA") → attivati
- **7 con fingerprint corretto ma 0 atti estratti** (Cianciana, San Michele di Ganzaria,
  Oliveri, Monterosso Almo, Acquaviva Platani, Novara di Sicilia, Floresta) → lasciati
  `pending` con nota — non abbastanza per attivarli senza capire se l'albo è
  genuinamente vuoto o la struttura HTML è diversa (principio "mai attivare uno scraper
  a 0 atti silenzioso", CLAUDE.md)

**2 bug reali trovati durante l'integrazione (non dai test, dal test end-to-end):**
1. **Codice ISTAT di Messina sbagliato nel registro** (083053 — in realtà **Moio
   Alcantara**, mai testato per questo conflitto silenzioso). Corretto a 083048.
   Verificato che Moio Alcantara non è comunque raggiungibile sui pattern noti.
2. **Timeout sistemico su HSPromila**: un primo run reale con `run_scrapers.py` sui 40
   nuovi comuni ha dato 16/40 falliti per timeout — non un problema per singolo tenant,
   ma l'host condiviso `hspromilaprod.hypersicapp.net` (34 tenant in più sullo stesso
   dominio, prima solo 6) che non regge richieste sequenziali ravvicinate per comuni
   diversi. Verificato isolando una richiesta fallita: risponde 200 pulito se non
   preceduta da altre richieste ravvicinate — non un fallimento persistente. Fix: retry
   con backoff 2s in `hspromila.py::scarica_atti` (stesso pattern già in `jcitygov.py`),
   2 nuovi test di regressione (mock su `urllib.request.urlopen`). Dopo il fix: **37/40**
   al secondo run (3 falliti, in linea col rumore di rete storico ~3-7%).

**Copertura risultante: 238 comuni attivi (era 198), 3.889.697 abitanti (77,8%, era
74,0%)**, +7 pending verificati. Restano **106 comuni mai censiti da nessuno sweep**
(624.607 abitanti) — candidati per un prossimo giro, probabilmente su piattaforme non
ancora coperte da TALIA (nessun hit sui pattern jCityGov/Halley/portalepa/HSPromila).

**495 test verdi (erano 493), ruff pulito.** Dettagli completi in
[14-censimento-albi.md](docs/wiki/14-censimento-albi.md). Script di sweep non
committato (one-off in scratchpad, stessa convenzione degli sweep precedenti).

**Prossimo passo:** aprire PR per `feat/sweep-comuni-mancanti` (indipendente da PR
#14/#15). Poi considerare un giro di reverse-engineering manuale sui 106 comuni residui
(prossima estensione naturale di TAL-51, finora limitato a Palermo/Trapani).

---

## TAL-12: 8 fascicoli candidati preparati da catene problematiche (2026-07-21)

Nuovo `scripts/prepara_fascicoli_candidati.py`: combina `procedimenti_da_riapertura()` +
`procedimenti_critici()` (TAL-47/48, con dedup — una catena già coperta da una riapertura
non è anche "critica"), scarica i PDF, li copia in `data/samples/<id>/` e lancia il
Modulo 1 (`talia analizza`) per un report automatico. Eseguito su `talia.db`: 9 candidati
selezionati (tutti riaperture — più narrabili delle catene critiche semplici), 8 con
report completo (`data/samples/3,6,7,8,9,10,12,13`), 1 (`data/samples/11`, 63 PDF) senza
report — OCR troppo lento su un documento scansionato grande, interrotto dopo 15+ min.
Include **Palma proc. 692→703** (`data/samples/7`), uno dei 3 casi noti della card TAL-48.
Dettaglio completo, incluso l'esito automatico di ciascuno, in
[TAL-12.md](docs/cards/TAL-12.md#-fascicoli-2-9--preparati-in-attesa-di-lettura-lex-2026-07-21).
Resta da fare: lettura umana ⚖️ LEX su ciascuno (non automatizzabile).

**Fix collaterale:** `.gitignore` escludeva solo `*.pdf` sotto `data/samples/`, non i
`report.json`/`report.md`/`fonte.json` generati qui — che contengono dati reali estratti
dai PDF (firmatari, oggetti), stesso livello di sensibilità dei PDF. Aggiunta
`data/samples/[0-9]*/` all'ignore (i campioni sintetici con nome non numerico, es.
`fascicolo_coerente/`, restano tracciati come prima).

**Anomalia non spiegata:** `data/samples/2/` (2 PDF preesistenti, materiale di test
isolato non legato a nessuna card) è sparito dal filesystem durante la sessione. Nessun
comando eseguito lo cancella (verificato: nessun comando di cancellazione nel codice
toccato); causa non identificata. Dati non sensibili (PIAO + determina generici), ma
segnalato per trasparenza — da tenere d'occhio se ricapita.

**Tesseract installato in locale** (`brew install tesseract tesseract-lang`, lingua
`ita` disponibile) — prima mancava, necessario per l'OCR dei PDF scansionati.

493 test verdi (erano 490), lint pulito. Tutto committato e pushato su PR #13.

## TAL-48: bugfix data_atto (esteso a tutto il motore) + pdf_download + backfill (2026-07-20/21)

**PR #13 aperta:** https://github.com/dom3095/talia/pull/13 (branch `feat/TAL-48-pdf-riaperture`).

**Aggiornamento 2026-07-21 rispetto a quanto scritto sotto (Tentativo 2, 20/07):** il bug
non era isolato a `riapertura_revoca.py`. `grep data_atto` su tutto `src/talia/` ha trovato
lo stesso problema in `engine/catena.py` (5 punti: calcolo `data_avvio`/`data_chiusura` di
**tutti** i procedimenti) e in `concentrazione.py`/`frazionamento.py`/`catena_revoca.py`,
che con `WHERE data_atto IS NOT NULL` escludevano in silenzio l'**80% degli atti del DB**
(non solo jCityGov: anche catania, urbi, hspromila, ribera al 100%, halley al 12%). Stesso
fix `COALESCE(data_atto, data_pub)` applicato ovunque, 5 nuovi test di regressione.

**Poi backfill** (`scripts/backfill_date_procedimenti.py`, nessuna richiesta HTTP, solo
dati già in DB, idempotente, backup di `talia.db` preso prima): eseguito sui 28.523
procedimenti esistenti. `data_avvio` NULL: 22.893 → 278 (i residui sono procedimenti senza
alcun atto con data disponibile — non un bug). `data_chiusura` NULL: 25.021 → 11.094 (i
residui sono procedimenti con un solo atto datato — nessuna "chiusura" distinta
dall'avvio, per design). 490 test verdi totali.

**Python allineato a 3.12 ovunque** (`pyproject.toml`, ruff, CI, wiki, CLAUDE.md) — la 3.14
non è ancora la versione su cui si lavora davvero; vedi nota sotto per il perché.

Dettagli completi (4 Tentativi) in [TAL-48.md](docs/cards/TAL-48.md). Candidati nuovi per
TAL-12 in [TAL-12.md](docs/cards/TAL-12.md#-candidati-per-i-prossimi-fascicoli-da-tal-48-2026-07-20).

**Nota permanente:** `talia.db.bak-pre-backfill-20260721` (133 MB, non versionato) resta in
root — da eliminare quando il backfill è verificato stabile.

### Sessione 2026-07-20 (dettaglio originale)

Branch `feat/TAL-48-pdf-riaperture` (il vecchio `feat/TAL-48-riapertura-dopo-revoca`
locale era rimasto indietro di 5 commit rispetto a `main` — il suo MVP era già mergiato
via PR #9 il 2026-07-10, il branch stesso non serviva più).

**Bug trovato e corretto:** `rileva_riapertura_dopo_revoca` filtrava su `atti.data_atto`,
che è **NULL per il 100% degli atti jCityGov** (79.462 su 104.812 atti totali, piattaforma
dominante — inclusi tutti e 3 i casi reali documentati nella card). Risultato: 0
rilevazioni su `talia.db` reale nonostante 449 catene revocate/annullate disponibili; i 12
test esistenti non lo prendevano perché le fixture impostano sempre `data_atto` a mano.
Fix in `red_flags/riapertura_revoca.py`: query riscritte con `COALESCE(data_atto,
data_pub)`, senza toccare l'engine catena condiviso. Da 0 → **78 riaperture rilevate**.

**Integrazione `pdf_download.py` (TAL-47):** nuove `scarica_pdf_atto()` (atto singolo
senza catena), `procedimenti_da_riapertura()` + `scarica_pdf_riapertura()` (scarica
entrambi i bandi di una riapertura + un `motivo_riapertura.json` esplicativo), flag CLI
`--riaperture`. Validato end-to-end su `talia.db` reale: PDF scaricati per Ragusa proc.
11306 e **Palma proc. 692→703** (uno dei 3 casi noti della card, confermato dal vivo).

**Trovato anche:** `run_scrapers.py` calcolava `riapertura_dopo_revoca` nel report red
flags ma non lo stampava mai — riga aggiunta.

**Esito:** 480 test verdi (erano 473), lint pulito. Dettagli/Tentativi completi in
[TAL-48.md](docs/cards/TAL-48.md). Candidati nuovi per TAL-12 annotati in
[TAL-12.md](docs/cards/TAL-12.md#-candidati-per-i-prossimi-fascicoli-da-tal-48-2026-07-20).

**⚠️ Attenzione locale/CI:** durante questa sessione `ruff format` su questo venv locale
(Python 3.12.3) ha riscritto `except (urllib.error.URLError, TimeoutError):` in
`pdf_download.py` nella forma senza parentesi (`except urllib.error.URLError,
TimeoutError:`) — **sintassi valida solo da Python 3.14 (PEP 758)**, quindi un
`SyntaxError` su questo venv. Il progetto dichiara `requires-python = ">=3.14"` e CI usa
3.14 (`ci.yml`), ma il venv locale (`.venv`) è su 3.12.3: **`ruff format` locale può
produrre codice che non gira in locale.** Ripristinato manualmente alle parentesi (valide
su entrambe le versioni). Non ancora deciso se aggiornare il venv locale a 3.14 o
convivere con la cautela su `ruff format`.

**Prossimo passo (stato al 20/07, superato — vedi sopra):** ~~aprire PR per
`feat/TAL-48-pdf-riaperture`~~ fatto, PR #13.

---

## Run scraper 2026-07-20

Lanciato `python3 scripts/run_scrapers.py` su `talia.db` locale (nessun flag, quindi i 204
scraper `attivo` di default + red flags + catene). Ultimo run precedente: 2026-07-14.

**Esito:** 204/204 scraper eseguiti, **6 falliti** (~3%, in linea col rumore storico) —
6071 atti nuovi (10382 trovati, resto duplicati). DB ora: **238 enti | 104.812 atti |
163 red flags**. Nuovi red flags calcolati in questo run: concentrazione 139, tempi
anomali 1, revoche in catena 43 (frazionamento 0).

Scraper falliti in questo run (non bloccanti, riprovare al prossimo run):
- **halley** (2): `brolo`, `sortino`
- **portalepa** (4): `castellammare_golfo`, `cefalù`, `corleone`, `partanna_tp`

Nota: i 4 falliti portalepa sono sulla stessa piattaforma già segnalata per il blocco WAF
Akamai da GH Actions (vedi sezione sotto) — ma questo run era **locale**, non da CI, quindi
non è lo stesso blocco per IP/ASN Azure. Da tenere d'occhio se si ripete sistematicamente;
per ora trattato come rumore di rete (log completo in `/tmp/talia_scraper_run_20260720_130806.log`,
non committato).

Il run in sé non ha prodotto commit — ha solo scritto su `talia.db` locale (gitignored).
I commit di questa sessione sono la sincronizzazione doc (vedi sopra) + il lavoro TAL-48.
Resta **non committato** un cambio preesistente (non fatto in questa sessione, trovato già
nel working tree) a `.github/workflows/health-check.yml`
che commenta il trigger `schedule:` — coerente con la decisione del 2026-07-12 di non
attivare il cron per via del blocco Akamai, ma non risulta mai committato. Da chiedere a
Dom se va committato via branch+PR o scartato.

## Stato branch (storico, entrambe le PR ora mergiate)

`feat/E3-province-palermo-trapani` (PR #12) e `feat/config-scraper-registro` (PR #11) sono
**mergiate in `main`** dal 2026-07-12. `main` è attivo e aggiornato (`git status`: pulito a
parte una modifica locale non committata a `.github/workflows/health-check.yml`, vedi sotto).

Riepilogo di cosa è cambiato (per chi riprende in mano il progetto): le liste hardcoded
`_JCITYGOV_COMUNI`/`_PORTALEPA_COMUNI`/`_URBI_COMUNI`/`_SCRAPERS` in `scripts/run_scrapers.py`
sono state sostituite da un registro CSV (`data/registro_scraper.csv`, 245 righe) letto da
`registry.py` via `_FACTORY_PER_MODULO`. I 9 comuni TIER 0 di TAL-50 (Termini Imerese,
Campofelice di Roccella, Partinico, Cefalù, Castellammare del Golfo, Corleone, Capaci,
Partanna, Caccamo) sono nel registro consolidato.

**Nota (decisione presa, non un problema da risolvere):** il CSV ha due comuni registrati due
volte su piattaforme diverse con lo stesso `codice_istat` — Campofelice di Roccella
(`campofelicediroccella` halley + `campofeligerocchella` jcitygov, 082017) e Partanna
(`partanna` halley + `partanna_tp` portalepa, 081015). **Tenuti entrambi deliberatamente**
(scelta di Dom, 2026-07-12): ridondanza a costo zero — se una piattaforma cambia HTML o va
giù, l'altra continua a coprire il comune senza bisogno di failover esplicito, dato che
`filtra_eseguibili()` esegue entrambe le righe ad ogni run indipendentemente. Costo:
doppia scrittura sull'ente ad ogni sincronizzazione (`sincronizza_enti_da_registro`, innocua
per via del `COALESCE`) ed eventuali atti duplicati se le due fonti espongono lo stesso atto
con URL diversi — non osservato finora. Tracciato in **[TAL-52](docs/cards/TAL-52.md)**
(backlog, P3): dedup atti tra scraper ridondanti sullo stesso comune.

**Fatto:** test (473 verdi) + lint puliti, push del branch, **PR #12 mergiata in `main`
il 2026-07-12.**

### Health-check: trovato blocco WAF Akamai su portalepa (2026-07-12)

Primo trigger manuale di `health-check.yml` dopo il merge di PR #11 (run `29193148678`):
**195/244 OK**, 32 falliti inattesi. Analisi del pattern (falliti incrociati con i totali
per modulo nel registro) invece di trattarli come 32 comuni scollegati:

| Piattaforma | Attivi in registro | Falliti | % |
|---|---|---|---|
| portalepa (+ `siracusa`, stessa piattaforma) | 24 | 21 | **87%** — sistemico |
| hspromila | 6 | 3 | 50% — campione troppo piccolo per concludere |
| halley | 93 | 7 | 7,5% — coerente con rumore/burst di concorrenza, non blocco |

Diagnosi mirata (script temporaneo `scripts/_debug_egress.py`, rimosso da questo branch
dopo l'uso — vedi run `29194988894`): 3 varianti di richiesta (HEAD minimal, GET minimal,
GET con header da browser) verso `aliminusa.soluzionipa.it` e `caltagirone.soluzionipa.it`
danno **sempre** `403` con header `X-Cache: CONFIG_NOCACHE` (firma Akamai). Header/metodo
non contano: è un **blocco Akamai per IP/ASN** dei runner GitHub Actions (che girano su
Azure), non un problema di come formuliamo la richiesta — quindi non risolvibile lato
codice scraper.

Valutate le opzioni (self-hosted runner locale, Oracle Cloud Always Free, VM AWS/Azure a
pagamento — analisi completa non committata, in scratchpad di sessione) e un'estensione
verso un possibile tool on-demand pubblico (Modulo 1) con relativi impatti privacy/legali
se si toglie il vincolo di budget zero. **Decisione di Dom (2026-07-12): per ora restiamo
in locale, nessuna migrazione cloud.** Il blocco portalepa (23 comuni + Siracusa) resta
quindi un limite noto e documentato, non ancora risolto — da riprendere se/quando si
riconsidera un self-hosted runner o si attiva davvero il cron su GH Actions.

**Implicazione per la pre-cron checklist**: il cron su GH Actions, se attivato oggi,
perderebbe silenziosamente la copertura dei ~23 comuni portalepa. Vedi nota in "Prossimi
passi".

## Refactor "Registro unificato scraper" (PR #11, già mergiata in `main`)

`feat/config-scraper-registro` — **Refactor: Registro unificato scraper + health-check**,
parte da `main` con PR #8/#9/#10 già mergiate (censimento E3, TAL-48, TAL-50 Palermo/Trapani).
Piano: `.claude/plans/smooth-wibbling-teapot.md`.

**Tutte e 5 le PR del piano sono completate e committate su questo branch, in attesa di
review complessiva da Dom prima del merge** (nessun push, main resta protetto):

1. `6027328` — **PR1**: `data/registro_scraper.csv` (206 righe consolidate) + `registry.py`
   loader + validazione fail-fast + 15 test.
2. `94d0bb6` — **PR2**: parametrizzazione dei 6 moduli monocomune (palermo, catania, trapani,
   siracusa, ribera, agrigento) — `base_url` (+ `qs_base`/`ente_mittente` per catania)
   propagati a `scarica_atti()`/`prepara_ente()` e helper interni. Default = comportamento
   invariato. 7 test di parametrizzazione.
3. `72da866` — **PR3**: `scripts/run_scrapers.py` legge dal registro per tutti gli 11 moduli
   (5 famiglie parametriche + 6 monocomune) via `costruisci_scrapers(registro)` uniforme
   (`_FACTORY_PER_MODULO`). Rimosse le 5 liste hardcoded + `_HALLEY_SKIP_SSL` (ora
   `entry.skip_ssl`). **Verificato lossless**: `_SCRAPERS`/`_SCRAPERS_DEFAULT` prima/dopo
   sono insiemi identici (205 scraper, 203 di default). Rimossi i CSV di censimento
   ridondanti, wiki 14 aggiornata. 12 nuovi test.
4. `075a6f6` — **PR4**: schema DB `enti` esteso (`modulo`/`url_base`/`stato_scraper`) via
   migrazione lazy `_estendi_enti()` (compatibile con `talia.db` locali esistenti).
   `sincronizza_enti_da_registro()` in `registry.py`, chiamata in `main()`. `upsert_ente`
   usa `COALESCE` sulle 3 colonne nuove per non azzerarle sui run scraper "vecchio stile".
   Verificato su DB reale: 205 righe registro → 199 enti distinti (comuni con più endpoint
   scraper collassano sullo stesso `codice_istat`). 9 nuovi test.
5. `693bcbe` — **PR5**: `scripts/health_check_registro.py` (stdlib puro, HEAD+fallback GET,
   `ThreadPoolExecutor`, exit code non-zero solo su righe attivo/escluso_default fallite) +
   `.github/workflows/health-check.yml` (schedule lunedì 05:00 UTC + `workflow_dispatch`,
   notifica via issue GitHub persistente label `health-check`). Verificato su rete reale
   (7 comuni campione OK, Messina bloccata fallisce come atteso senza alzare l'exit code).
   20 nuovi test.

**Totale sessione: 458 test verdi (erano 411 a inizio sessione), ruff pulito su tutto il
codice nuovo/modificato** (gli 8 errori E501 residui in `tests/test_registry.py` sono
preesistenti da PR1, non introdotti in questa sessione).

### Code review multi-angolo (2026-07-11) — 8 findings, bug corretti

Eseguita `/code-review` (8 angolazioni parallele + verifica 1-voto) sull'intero diff
`main...HEAD`. 6 findings confermati, 2 plausibili (bassa severità, non corretti — vedi
sotto). Bug corretti in un commit successivo alle 5 PR:

1. **`trapani.py`**: `_parse_page()` ignorava `base_url` e costruiva `url_fonte` sempre
   dalla costante di modulo — bug di correttezza reale introdotto in PR2 (violava
   l'esplicabilità: un `base_url` custom avrebbe prodotto link alla fonte sbagliati).
   Fix: `base_url` propagato a `_parse_page`. 2 nuovi test.
2. **`db.py::upsert_ente`**: `provincia`/`popolazione`/`sito_web` non erano protette da
   `COALESCE` come `modulo`/`url_base`/`stato_scraper` — ogni run di `run_scrapers.py`
   (che sincronizza *tutto* il registro ad ogni invocazione) azzerava silenziosamente la
   provincia dei comuni non inclusi nel run corrente (205/206 righe hanno provincia vuota
   nel CSV). Fix: `COALESCE` esteso a tutti i campi opzionali. 2 nuovi test.
3. **`registry.py::_row_to_entry`**: `stato` non applicava il default `"attivo"` su una
   cella CSV presente-ma-vuota (solo su chiave mancante) — una riga malformata sarebbe
   silenziosamente sparita da tutto lo scraping senza errore di validazione. Fix: pattern
   `or` coerente con gli altri campi. 1 nuovo test.
4. **`registry.py::valida_registro`**: nessuna validazione che `qs_base`/`ente_mittente`
   fossero *presenti* per righe catania/urbi attive (solo che fossero assenti altrove) —
   gap che avrebbe prodotto un URL con `?None` a runtime. Fix: nuovo controllo + aggiunto
   `modulo="pending"` come pseudo-modulo valido (serviva per il recupero dei 39 comuni,
   vedi sotto). 4 nuovi test.

**Sistemati anche i 3 findings non bloccanti** (su richiesta esplicita di Dom):

5. **`run_scrapers.py`**: `_REGISTRO`/`_SCRAPERS` non si costruiscono più a import
   time — nuova funzione `_registro_e_scrapers()` (`functools.lru_cache`) chiamata
   lazy da `_parse_args()`/`main()`. Un CSV malformato fallisce solo all'uso reale
   della CLI, non ad ogni import del modulo (es. dai test). Import verificato
   ~istantaneo (niente parsing), prima chiamata reale ~3ms.
6. **ANAC centralizzato**: era special-casato come stringa letterale in 6 punti
   sparsi tra `registry.py` e `run_scrapers.py`. Ora un'unica costante nominata
   `registry.MODULI_SENZA_ENTE = frozenset({"anac"})`; in `run_scrapers.py` ANAC
   è dispatchato uniformemente via `_FACTORY_PER_MODULO` come ogni altro modulo
   (rimossi sia il seed hardcoded `{"anac": _run_anac}` sia lo skip esplicito nel
   loop) — **verificato lossless** (206 scraper prima e dopo).
7. **`db.py`**: aggiunta `azzera_info_scraper(conn, codice_istat)` — via esplicita
   per azzerare `modulo`/`url_base`/`stato_scraper` (impossibile tramite
   `upsert_ente` dopo il fix COALESCE del punto 2). Non chiamata automaticamente
   (nessuna riconciliazione automatica dei comuni tolti dal registro — scelta
   deliberata, fuori scope).

6 nuovi test per questi 3 fix (473 test totali verdi, erano 467).

### Recupero 39 comuni censiti

La review ha anche scoperto che la rimozione dei CSV di censimento (PR3) aveva perso i
dati (piattaforma/URL) di 39 comuni PA/TP censiti in TAL-50 senza scraper — il piano
originale prevedeva di migrarli come righe `stato=pending`, passo non eseguito. Recuperati
da `git show main:data/censimento_albi_pa_tp.csv` e riaggiunti al registro con
`modulo=pending`. Di questi, **Altavilla Milicia** (etichettata "HyperSIC" nel censimento)
usa in realtà lo stesso URL pattern già gestito da `hspromila.py` — verificato dal vivo
(102 atti reali) e attivato subito (`modulo=hspromila`, `stato=attivo`), zero nuovo codice.
Dettagli in `docs/wiki/14-censimento-albi.md`.

**Registro dopo il recupero: 245 righe (204 attive di default, 38 pending, 2 escluso_default,
1 bloccato).** 467 test totali verdi.

Working tree pulito (tutto committato). Nessun dato nominativo committato.

### Prossimo passo

Review complessiva da parte di Dom (richiesta esplicitamente: "facciamo review alla fine
di tutto" → eseguita `/code-review`, bug corretti). Dopo l'approvazione: push del branch +
apertura PR su GitHub, oppure squash/riorganizzazione dei commit se Dom preferisce una
history diversa — da concordare in fase di review, non ancora deciso.

## Sessione 2026-07-10 — TAL-50: Censimento Palermo + Trapani (E3 estensione)

### Cosa contiene il branch `feat/E3-province-palermo-trapani`

**Fase 1 (censimento) — Completato:**
- Ricerca web sistematica: 77 comuni mancanti PA/TP
- Risultato: **100% con albo online raggiungibile** (nessun gap)
- Distribuzione per piattaforma:
  - **TIER 0 (subito):** 12 comuni su piattaforme già supportate
    - jCityGov: Termini Imerese (26k), Campofelice Roccella (6.9k)
    - portalepa: Partinico (31k), Cefalù (14k), Castellammare (14.6k), Corleone (11k), Capaci (11k), Partanna (10.8k)
    - URBI: Caccamo (8.3k)
    - + 3 comuni già nel registry E3 (Gibellina, Vicari, Lercara Friddi, Campobello di Mazara)
  - **TIER 1 (facile):** 18 comuni su Halley/EGov/APKAPPA varianti
  - **TIER 2 (reverse-eng):** 14 comuni custom/local
  - **TIER 3 (fallback):** 1 comune (Gazzetta Amministrativa)
- CSV: `data/censimento_albi_pa_tp.csv` (77 righe ordinato per popolazione)
- Card TAL-50 con dettagli implementazione futura

**Fase 2 (registry update) — Completato:**
- [x] Aggiunta 9 comuni TIER 0 a `scripts/run_scrapers.py` (2 jCityGov + 6 portalepa + 1 URBI)
  - jCityGov: Termini Imerese, Campofelice Roccella
  - portalepa: Partinico, Cefalù, Castellammare del Golfo, Corleone, Capaci, Partanna
  - URBI: Caccamo
- [x] Validazione: HTTP 200 su 3 comuni campione (Termini Imerese, Partinico, Caccamo) ✅
- [x] Deduplicazione: rimosso Castelvetrano jCityGov (già in E3), rinominato Capaci portalepa a `capaci_pa` per evitare collisione con E3

**Fase 3 (TIER 1 + TIER 2 reverse-eng) — Completato:**
- [x] Analizzato TIER 1 (Halley/EGov/APKAPPA): pattern non completamente generalizzabile → rimandato a TAL-51
- [x] Reverse-engineering TIER 2 (5 comuni custom più grandi): TUTTI richiedono API JS/Playwright → NON fattibili HTTP puro, ROI basso
- [x] Mappa copertura TALIA aggiornata: notebook `copertura_scraper_sicilia.ipynb` + GeoJSON + PNG/HTML interactive

**Copertura finale TAL-50:**
- Pre-merge E3: 192 comuni (~73% popolazione)
- **Post-merge E3 + TAL-50 completo: 200 comuni (~81% popolazione) ← PRONTO ORA**
- Potenziale TIER 1 (se implementato): 218 comuni (~85%) — rimandato a TAL-51
- TIER 2 custom: NON prioritario (36.8k abitanti, alto effort)

### Modifiche non committate

Nessuna (working tree pulito).

## DB attuale

`talia.db` locale (gitignored), non toccato da questa sessione (refactor PR1-3 è solo
configurazione/codice, zero scraping reale eseguito). Le sezioni sotto (backfill,
copertura) sono storico di sessioni precedenti (PR #8/#9/#10, già mergiate in main)
e non sono state riverificate in questa sessione.

## 🤝 Istruzioni per la prossima sessione

1. PR #11 (registro unificato + health-check) e PR #12 (riconciliazione TAL-50) — vedi
   stato aggiornato in cima al file. Dopo il merge di PR #12: valutare un run completo
   con `_SCRAPERS_DEFAULT` su `talia.db`.
2. **Blocco portalepa da GH Actions (WAF Akamai, vedi sopra) resta aperto.** Prima di
   attivare per davvero il cron su GH Actions (pre-cron checklist), decidere come
   trattare i ~23 comuni portalepa: accettare la lacuna, riprendere in considerazione
   un self-hosted runner, o altro. Non bloccante per il resto (91% dei comuni copre
   correttamente da GH Actions).
3. Vale la pena ripetere lo sweep di dominio (Halley/portalepa) periodicamente: nuovi
   comuni potrebbero attivare l'albo o cambiare piattaforma nel tempo.

### Regole di sempre

- MAI push su main, MAI merge: branch + PR, il merge lo conferma sempre Dom.
- Ogni tentativo significativo va nella card di riferimento, sezione 🔬 Tentativi.
- Prima di dichiarare una piattaforma "nuova", verificare contro gli scraper già esistenti
  nel repo (portalepa era etichettato erroneamente "SoluzioniPA" da un agente di ricognizione
  — era in realtà lo stesso codice di `siracusa.py`).
- Validare sempre la funzione di fingerprint di uno sweep contro un caso noto-positivo E
  noto-negativo prima di lanciarlo su scala (il primo sweep Halley falliva silenziosamente
  per un limite di lettura troppo basso sulla risposta HTTP).

## Storico modifiche (sessioni precedenti, già mergiate in main)

La tabella sotto è lo storico di cosa conteneva un'ondata di commit precedente (2026-07-02/03):

| File | Contenuto |
|------|-----------|
| `scripts/run_scrapers.py` | Palma aggiunta; `--no-stop`; `scraper_runs`; stop-on-known; coverage summary; `--anac-file`; **`--llm-modello`, `--llm-limite`** |
| `src/talia/modulo2_scraping/db.py` | Tabella `scraper_runs`; `inizia_run`, `termina_run`, `ultimo_run_riuscito` |
| `src/talia/modulo2_scraping/fonti/jcitygov.py` | Timeout 30s + 1 retry |
| `src/talia/engine/catena.py` | Engine catena di eventi (TAL-43); pattern AFFIDAMENTO + LIQUIDAZIONE; stato "concluso"; Strategia 4 LLM (Ollama); **TAL-46: strategia 2.5 contenimento, guard-rail gemelli, regex estese, colonna `numero_settoriale`, `reset_procedimenti_da_verificare`** |
| `src/talia/modulo2_scraping/red_flags/catena_revoca.py` | Red flag revoca in catena (TAL-44) — nuovo file |
| `src/talia/modulo2_scraping/red_flags/runner.py` | Aggiunto `revoche_catena`; **parametri LLM passati a `ricostruisci_catene()`** |
| `src/talia/modulo3_dashboard/app.py` | Tab ⛓️ Procedimenti (TAL-45) |
| `tests/test_catena.py` | **41 test** (erano 29) — nuovi: AFFIDAMENTO, LIQUIDAZIONE, LLM fallback, **TAL-46: contenimento caso Palma, revoca cumulativa, guard-rail gemelli, reset** |
| `docs/cards/TAL-46.md` | **Nuova card (Spec-Driven): engine catena v2 — in Review** |
| `tests/red_flags/test_catena_revoca.py` | 6 test red flag revoca |
| `docs/wiki/02-architettura.md` | Pipeline due fasi |
| `docs/wiki/05-red-flags-batch.md` | 6 check PDF + caso studio Palma |
| `docs/cards/BOARD.md` | TAL-42..45 aggiunte in Review |
| `docs/cards/TAL-42..45.md` | Nuove card catena |
| `docs/cards/_TEMPLATE.md` | **Sezioni `## 📋 Spec`, `## ❓ Domande aperte`, `## 🔬 Tentativi`** |
| `docs/cards/TAL-11.md` | **Spec compilata (interfaccia + domande aperte)** |
| `CLAUDE.md` | **Loop di esecuzione; convenzioni Tentativi, Spec/Domande aperte; delega ad agente economico** |

---

## Test scraper 2026-06-28

9 agenti paralleli (uno per capoluogo siciliano). Dettaglio: [`docs/wiki/13-scraper-status.md`](docs/wiki/13-scraper-status.md).

| Comune | Esito | Note |
|--------|-------|------|
| Agrigento | ✅ 224 atti | Playwright installato, funziona |
| Caltanissetta | ✅ 40 atti | OK |
| Catania | ❌ non implementato | URBI/Maggioli (non HCL Domino); HTTP puro fattibile con enumerazione ID |
| Enna | ✅ 40 atti | Portale attivo, bassa frequenza |
| Messina | ⛔ bloccato | FortiGate HTTP 403 + cert scaduto 2023; non risolvibile lato codice (BUG-5) |
| Palermo | ❌ non implementato | SISPI JSP; Playwright obbligatorio; URL: `albopretorio.comune.palermo.it` |
| Ragusa | ✅ 40 atti | OK |
| Siracusa | ✅ 30 atti | OK; mancano test unitari |
| Trapani | ⚠️ 0 atti | `_RE_PANEL` non matcha più l'HTML → BUG-4 |

---

## Bug aperti

Nessuno bloccante. **BUG-6 chiuso il 2026-07-03: non era un bug** — falso positivo
del test Playwright del 28/06, che verificava la tabella con `inner_text()`;
`st.dataframe` renderizza in canvas (glide-data-grid), invisibile all'estrazione
testuale. Screenshot su DB reale conferma il rendering corretto. Dettagli e lezione
per i test UI in [`docs/bugs.md`](docs/bugs.md).

---

## Sessione 2026-07-02 — Cosa è cambiato

### Catena eventi: 81% dei procedimenti sconosciuto risolti

Prima di questa sessione, `ricostruisci_catene()` lasciava 574 procedimenti con `stato_finale = 'sconosciuto'` perché mancavano i pattern per le fasi normali di un procedimento amministrativo.

Aggiunti due pattern in `src/talia/engine/catena.py`:
- **AFFIDAMENTO** → ruolo `aggiudicazione` (es. "affidamento diretto ai sensi", "affidamento del servizio")
- **LIQUIDAZIONE** → ruolo `liquidazione` (es. "liquidazione fattura", "liquidazione sal") → nuovo stato finale **"concluso"**

Risultato: da 574 a ~109 sconosciuto (-81%).

### Strategia 4 — LLM locale (opt-in)

Per i restanti 109, aggiunta classificazione via Ollama HTTP API come Strategia 4 in `ricostruisci_catene()`.

- Opt-in: `--llm-modello llama3.2` (default: skip)
- Graceful degradation: se Ollama non risponde, warning nel log e skip silenzioso
- Tracciabilità: procedimenti classificati via LLM hanno `metodo_individuazione` con suffisso `_llm`
- Limite configurabile: `--llm-limite N` (default 200 per run)

### Processo di lavoro aggiornato

Aggiornati `CLAUDE.md` e `docs/cards/_TEMPLATE.md` con:
- **Loop di esecuzione** formale per card (Spec check → Esecuzione → Bugfix → Refactor → Lint → Doc)
- **`## 🔬 Tentativi`**: log strutturato degli approcci provati (persistente tra sessioni)
- **`## 📋 Spec` + `## ❓ Domande aperte`**: spec compilata prima di toccare codice; se ci sono domande aperte, bloccarsi
- **Delega esplorativa**: per task pesanti, delegare a haiku, consolidare, validare

---

## Prossimi passi

### 0 — ~~Review e merge PR #8 (TAL-49)~~ ✅ FATTO — mergiata (#8), insieme a #9 (TAL-48) e #10 (TAL-50)

### 1 — Approfondimento Palermo e Catania

**Palermo** (`palermo.py`) e **Catania** (`catania.py`) sono già implementati e HTTP puro
(non richiedono Playwright come per Agrigento). Entrambi espongono solo atti in pubblicazione
(~15-30 gg), quindi il primo run su `talia.db` post-merge avrà dati recenti ma no storico.

Verificare da `talia.db` dopo merge:
- Palermo: `SELECT COUNT(*) FROM atti WHERE ente_codice_istat = '082053'`
- Catania: `SELECT COUNT(*) FROM atti WHERE ente_codice_istat = '087003'`

Se i numeri sono bassi (< 100 atti), consider fare un backfill manuale via
`--no-stop --max-pagine 500` su un DB separato per capire quanto storico è
recuperabile.

### 2 — Comuni restanti della provincia di Agrigento (7, molto piccoli)

Caltabellotta, Bivona, Cianciana, Castrofilippo, Burgio, Sant'Angelo Muxaro, Calamonaci:
ciascuno su una piattaforma diversa (APKAPPA, Alph@soft, ComuneWeb, custom, Municipium).
Vedi documentazione dettagliata in `docs/wiki/14-censimento-albi.md` e `docs/cards/TAL-49.md`
(Tentativo 17) per chi vuole riprenderli in futuro.


### 0 — ~~Fix Trapani~~ ✅ FATTO (2026-07-03, branch `fix/BUG-4-trapani-filtro-data`)

**La regex era innocente**: `_RE_PANEL` matchava ancora. La causa era il default
`dataPubblicazioneAl=oggi` — il server e-pal.it esclude gli atti la cui finestra di
pubblicazione termina dopo `al`, cioè proprio quelli in pubblicazione. Fix: `al = oggi+60gg`
(`_MARGINE_FUTURO_GIORNI`), WARNING su 0 atti, 4 test nuovi (23 totali su Trapani).
Run reale: +329 atti. **Nota strutturale**: l'albo espone solo atti in pubblicazione
(~15-30 gg), lo storico non è recuperabile → serve scraping continuo per non perdere atti.
Dettagli in `docs/bugs.md` (BUG-4). **Da fare: mergiare il branch su `main`.**

### 1 — ~~Commit~~ ✅ FATTO (2026-07-03)

Tutto committato, mergiato su `main` e pushato; branch cancellato. BUG-6 chiuso
(falso positivo del test UI — vedi `docs/bugs.md`).

### 2 — ~~Backfill storico Palma di Montechiaro~~ ✅ GIÀ FATTO (2026-06-26)

Il backfill era già stato eseguito il 2026-06-26 (688 inseriti, vedi `scraper_runs`):
la voce "60 atti / backfill da fare" nell'HANDOFF era stantia. Rerun di verifica del
2026-07-03: 748 trovati, 748 duplicati, 0 nuovi → l'albo espone 748 atti totali
(2018-05-11 → 2026-06-05), tutto lo storico disponibile è in DB.

### 3 — ~~Validare la catena sul DB reale~~ ✅ FATTO (2026-07-02, TAL-46)

Il fascicolo Palma (`data/samples/1`) È ricostruibile dal DB, ma il fuzzy v1 aveva
fuso 3 selezioni distinte in una mega-catena (proc. 674). Risolto con TAL-46:
strategia 2.5 (contenimento oggetto) + guard-rail gemelli. Migrazione applicata
a `talia.db`: reset di 523 procedimenti fuzzy + rerun → ora 646 da CIG, 10 da
contenimento (alta confidenza, incluse le 3 catene Palma: proc. 1170/1171/1172),
521 fuzzy da_verificare. Dettagli in `docs/cards/TAL-46.md` (sezione Tentativi).

### 4 — TAL-14: check GDPR + numero atto incoerente

Card in Review. Casi concreti trovati su fascicolo Palma:
- Bozza graduatoria divulgata prima dell'ufficializzazione → `gdpr_breach_non_notificato`
- Revoca cita "N. 33/2025" ma l'atto in DB è "N. 35/2025" → `numero_atto_incoerente`

### 5 — ~~Fase 2 pipeline: PDF on-demand (MVP)~~ ✅ AVVIATA (2026-07-06, TAL-47)

Downloader jCityGov funzionante e validato (vedi sezione sessione 2026-07-05/06).
Restano: selezione automatica catene, estrazione testo, check sui PDF, altre piattaforme.

### 6 — ANAC

WAF blocca urllib (TLS fingerprinting). Workaround attuale: `--anac-file <csv>`.
Alternativa: Playwright headless.

### 7 — Messina: bloccato, non azione immediata

FortiGate HTTP 403 + certificato scaduto 2023-06-27. `skip_ssl=True` non aggira il 403.
Richiede intervento IT del Comune. Vedi BUG-5 in `docs/bugs.md`.

## Sessione 2026-07-10 — TAL-48: red flag riapertura dopo revoca/annullamento (MVP)

**Fatto:**
- Nuovo modulo `src/talia/modulo2_scraping/red_flags/riapertura_revoca.py`:
  - `rileva_riapertura_dopo_revoca(conn, soglia_similarita=0.5)`: query procedimenti
    revocati/annullati, ricerca atti stesso ente con oggetto simile
  - Tokenizzazione normalizzata: stopword dominio, regex `\b\w+\b`, ≥3 char
  - Similarità Jaccard su token
  - Guardia anti-periodicità: ≥3 atti simili nel tempo → skip (routine admin)
- Integrazione runner: `_salva_riapertura_dopo_revoca()`, nuovo campo RapportoRunner
- Test: 12 nuovi (tokenizzazione, Jaccard, 4 casi reali: Palma 656, Ragusa 1079, Enna 924 periodico, edge case)
- **320 test verdi totali** (312 base + 8 suite nuove)
- 2 commit: feat TAL-48 MVP + doc update (BOARD, card)
- Spec: due domande aperte rimangono aperte per dom (conferma soglia, scopo PDF confronto)

**Branch:** `feat/TAL-48-riapertura-dopo-revoca` — non ancora pushato (locale)

**Prossimi passi:**
1. Push branch e apertura PR (opzionale, dipende da necessità dom)
2. Integrazione con pdf_download: scaricare PDF di entrambi i bandi (rivocato + riapertura)
3. Confronto testuale bando originale vs rilanciato (richiede estrazione testo dai PDF, card futura)
4. Test su fascicolo Palma reale con DB completo (dopo merge PR #8)
5. Calibrazione soglia Jaccard dopo run completo (domanda aperta 1)

---

## Note permanenti

- `data/samples/1/` — fascicoli reali locali, **mai committare**
- `talia.db` — **mai committare**
- Architettura E2: [`docs/handoff/epica_E2.md`](docs/handoff/epica_E2.md)
- Stato scraper: [`docs/wiki/13-scraper-status.md`](docs/wiki/13-scraper-status.md)
- Bug aperti: [`docs/bugs.md`](docs/bugs.md)
