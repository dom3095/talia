# HANDOFF.md — Stato sessione

> Aggiornato: 2026-09-02 (branch `feat/TAL-66-run-giornaliero-aggregati`, da
> `main`, **PR aperta**). La sessione precedente (`feat/TAL-60-streamlit-modulo1`,
> TAL-60…65) è stata mergiata in `main` come **PR #19** (`520d697`) — il
> resoconto dettagliato di quella sessione resta più sotto.

---

## Sessione 2026-09-02 — audit dei run notturni girati da soli (TAL-72)

Il branch era fermo dal 21/08 con il codice completo (731 test verdi, ruff
pulito) e **nessuna PR aperta**; nel frattempo l'agente launchd ha continuato a
girare ogni notte. Leggendo `scraper_runs` invece che i soli log è emerso che
TAL-71 aveva risolto il collo di bottiglia sbagliato — o meglio, quello giusto
ma non l'unico.

**Il run supera le 24h e fa saltare i giorni successivi.** Run del 2026-09-01:
scraping 01:45→16:28 UTC (**14,7h**), red flags ~2h, fine alle 20:41 locali. Il
run del 22/08 è finito il **24/08 alle 20:22**, quello del 27/08 il **28/08 alle
11:00**. Conseguenza misurata in `scraper_runs`: **23, 24 e 28 agosto non hanno
avuto alcun run** — il lock di `run_daily.sh` ha correttamente rifiutato il
secondo avvio, ma il risultato netto è esattamente la perdita definitiva di
copertura che TAL-66 esisteva per prevenire. Il lock ha fatto il suo mestiere; è
la durata a essere il difetto.

**La lentezza non è distribuita: ~10 scraper su 266 fanno il 98% del tempo.**
Somma delle durate dei 266 run del 01/09: 53.011s. Di cui `adrano` 11.566s
(3h12m, per 32 atti trovati), `baucina` 7.293s **finendo in timeout con 0 atti**,
`catania` 6.782s idem, `condro` 4.976s (handshake SSL), `acibonaccorsi` 4.901s.
Non esiste un tetto di tempo per singolo scraper: un host lento o semi-morto può
tenere in ostaggio l'intero run notturno. È lo stesso ragionamento di TAL-68
(misurare il costo a regime prima di lasciare qualcosa nel run) applicato al
livello sopra.

**Il 31/08 è stato perso quasi per intero senza che nessuno se ne accorgesse**:
232 scraper su 266 in errore, di cui **225 con lo stesso
`URLError [Errno 8] nodename nor servname`** — un guasto DNS locale, non 225
portali rotti. 115 atti inseriti in tutta la giornata. Non esiste recupero del
giorno perso né riconoscimento del pattern "fallimento di massa con una sola
causa": il report elenca 26 righe e lascia il lettore a distinguere le rotture
vere dal rumore transitorio.

Card [TAL-72](docs/cards/TAL-72.md). **Nota positiva emersa dallo stesso audit**:
Agrigento non è più muto (161 trovati / 28 inseriti il 01/09) — la segnalazione
in coda alla sessione TAL-71 è superata.

---

## Sessione 2026-08-21 — TAL-71 la fase red flags girava 11 ore

**Regressione introdotta da TAL-70**, trovata controllando lo stato del run
notturno. Il caricamento ANAC è corretto, ma non ne era stato valutato il
costo a valle.

**Sintomo:** il run del 2026-08-20 è finito dopo **18 ore** (scraper chiusi
alle 10:34, fine alle 21:45); quello del 2026-08-21 era ancora in corso dopo
17h ed è stato terminato a mano. Processo al 98% di CPU, `STAT RN`: calcolo,
non attesa di rete.

**Causa:** `collega_per_contenimento` e `collega_per_oggetto_simile` sono
O(n²) *dentro il singolo ente*. I 176.827 contratti SmartCIG si sono
concentrati sui capoluoghi — **Palermo è passata a 37.709 atti, di cui 35.719
ANAC (94,7%)**. Finché il DB conteneva solo atti d'albo su 190+ comuni nessun
ente era grande abbastanza da farlo emergere.

Il rapporto costo/beneficio era indifendibile: `cig` 199.360 procedimenti,
`oggetto_simile` 20.550, **`contenimento_oggetto` 263**. Undici ore per 263
collegamenti.

**Fix:** le due strategie fuzzy escludono `tipo = 'contratto_anac'`. Un
contratto SmartCIG non è un atto deliberativo dell'albo: non ha un originario
da riconoscere per somiglianza del titolo, e il collegamento corretto passa
già dal CIG (strategia 1, match esatto). Gli atti ANAC **restano** nelle
strategie 1 e 2, lineari. Su Palermo: contenimento **2,1s**, oggetto simile
**10,0s**.

**Fase intera cronometrata sul DB reale: 1816s (30 min), da 11+ ore.** Le due
strategie quadratiche pesano ora 7 minuti su 30. Il collo di bottiglia
residuo non è quadratico: la strategia CIG costa 1075s (59%) per iterare
199.330 CIG distinti, rifacendo ogni notte il lavoro su quelli già collegati —
ottimizzabile, non urgente. La misura vale per il **run notturno** (DB con
procedimenti già assegnati); una ricostruzione a freddo costerebbe di più.

**731 test verdi** (erano 728; 3 nuovi, incluso quello che verifica che il
collegamento per CIG continui a funzionare). Dettaglio in
[TAL-71](docs/cards/TAL-71.md).

### Da guardare, non affrontato

- **I red flag sono passati da 665 a 13.964, e 12.892 sono `frazionamento`.**
  Non è solo questione di volume: SmartCIG contiene *per definizione*
  affidamenti sotto soglia, quindi una regola che cerca frazionamento
  artificioso sotto le soglie di legge lì trova un terreno dove quasi tutto
  somiglia a un segnale. Stimare i falsi positivi su un campione **prima**
  di pubblicare.
- **220.173 procedimenti su 327.704 atti**, 199.360 creati dal CIG: quasi uno
  per contratto. Corretto in senso stretto, ma svuota di significato la
  nozione di procedimento nelle aggregazioni.
- **Agrigento restituisce 0 atti** da almeno due run consecutivi (12s, nessun
  errore): pattern "muto" già visto con Caccamo (TAL-68).

---

## Sessione 2026-08-18 (2) — TAL-66 run giornaliero automatico + TAL-67 aggregati dashboard

**Richiesta di Dom:** wiring per i run degli scraper, automazione giornaliera
"come su Pathosphere", dashboard con aggregati mensili/settimanali/trimestrali/
semestrali per comune e provincia + dettaglio giornaliero dei documenti
ingeriti. Più: "credi ci sia altro che valga la pena fare? ci sono problemi da
affrontare che non possiamo rimandare".

### Il problema urgente trovato leggendo lo stato (TAL-66, P0)

**L'ultimo run scraper era del 2026-08-06: 12 giorni prima.** La cadenza reale
dei run è "quando qualcuno se ne ricorda" (5-11 giorni di intervallo). Non è
un problema di igiene: quasi tutti gli scraper leggono l'**Albo Pretorio**,
che espone solo gli atti *in pubblicazione* (finestra 15-30 giorni). Gli atti
usciti dalla finestra **non sono più raccoglibili da lì, nessun backfill li
recupera**. Il grafico di ingestione giornaliera della nuova tab lo mostra a
colpo d'occhio: 13 giorni consecutivi a zero.

### Fatto — TAL-66 (automazione)

- **`scripts/run_daily.sh`**: lock (`mkdir` atomico + PID, con riconoscimento
  del lock orfano — un run completo dura ~4h40m su 260 scraper e due run
  sovrapposti si contenderebbero lo stesso SQLite), `caffeinate -i`, backup
  del DB via `sqlite3 .backup` (consistente in WAL, a differenza di `cp`),
  rotazione log/backup, notifica macOS su problemi.
- **`scripts/setup_launchd.sh`**: agente `com.talia.scrapers`
  (`--ora/--minuto/--status/--uninstall`). **Installato e caricato: 03:30 ora
  locale, ogni giorno.**
- **`src/talia/modulo2_scraping/run_report.py`** + **`scripts/report_run.py`**:
  riepilogo con exit code non-zero sui problemi, che tiene **distinti** tre
  stati con cause diverse — *fallito* (eccezione), *muto* (completato con 0
  atti trovati: la fragilità nota "fallimento silenzioso" di CLAUDE.md, che
  nessun exit code intercetterebbe) e *fermo* (attivo nel registro ma non
  eseguito da N giorni: esattamente la condizione che ha prodotto questo
  ritardo). Segnala esplicitamente quando l'ultimo run supera i 15 giorni.
- **Due difetti dello schema Pathosphere non riportati qui**: il suo plist usa
  `StartInterval` insieme a `KeepAlive true`, che su un job che *termina*
  significa rilancio immediato in loop — su un run di 4-5h verso 260 server
  comunali sarebbe stato un martellamento. Qui `StartCalendarInterval` +
  `KeepAlive false` + `RunAtLoad false`, più `Nice`/`ProcessType Background`.
- **Fix collaterale trovato guardando l'output reale, non i test**:
  `scraper_runs.errore` conservava i *primi* 500 caratteri del traceback,
  cioè quasi sempre senza la riga che nomina l'eccezione — il riepilogo
  mostrava `esito = fn(` invece di `ConnectionRefusedError: ...`. Ora
  l'eccezione è messa in testa prima di troncare, e `sintesi_errore()` sa
  leggere anche il formato vecchio già in DB.
- **Buco trovato nella soluzione stessa, verificando quali scraper girerebbero
  davvero**: `agrigento` (capoluogo), `pachino` e `barrafranca` sono
  `escluso_default` nel registro perché richiedono Playwright ed erano lenti
  *per un run manuale* — motivazione che in un run notturno non vale più,
  mentre la conseguenza sì (perdere per sempre gli atti di un capoluogo).
  Aggiunto `--extra-scrapers` a `run_scrapers.py` (aggiunge alla lista invece
  di sostituirla) e i tre al run notturno, sovrascrivibile con
  `TALIA_EXTRA_SCRAPERS`. Costo reale misurato: **Pachino 9s**, non i ~3 min
  stimati in CLAUDE.md. `anac` resta fuori (richiede `--anac-file`).
- **Run reale di recupero lanciato** il 2026-08-18 alle 13:44 (backup preso
  prima: `backups/talia.db.20260818`).

### Fatto — TAL-67 (aggregati dashboard)

- **`src/talia/modulo3_dashboard/aggregati.py`**: funzioni pure, nessun import
  di Streamlit (testabili senza avviare l'app). Granularità giornaliera /
  settimanale / mensile / trimestrale / semestrale, filtri per provincia e
  comune, intervallo `da`/`a`.
- **Due assi temporali tenuti esplicitamente distinti**: `atto`
  (`COALESCE(data_atto, data_pub)` — l'80% degli atti reali ha `data_atto`
  NULL, la trappola già costata un bug in TAL-48) e `ingestione`
  (`date(data_accesso)`, salute della pipeline). La UI avvisa che sull'asse di
  ingestione un backfill storico concentra anni di atti in un giorno solo.
- Settimana ancorata al **lunedì** (`date(d,'weekday 0','-6 days')`) invece di
  `strftime('%W')`: etichetta = data vera, ordinabile, senza ambiguità a
  cavallo d'anno.
- Date non plausibili escluse (sul DB reale esiste `0202-06-16`), ma il limite
  superiore è oggi+90gg e non "oggi": `data_pub` è la data di *inizio*
  pubblicazione e alcuni albi pubblicano con decorrenza futura — confermato
  sui dati veri (una settimana `2026-08-31` con 1 atto).
- **Tab 📅 Aggregati** in `app.py`: selettori territorio/granularità/asse,
  serie con variazione sul periodo precedente, dettaglio giornaliero di
  ingestione **con gli zeri espliciti** (un giorno omesso dal grafico
  nasconderebbe proprio l'informazione utile), classifiche per provincia e per
  comune, sezione "Stato degli scraper" che riusa `run_report`.
- Nessuna nuova dipendenza: `st.bar_chart` con lista di dict + `x=`/`y=`.

**698 test verdi (erano 655), ruff pulito.** Verificato dal vivo con
`AppTest.from_file` su `talia.db` reale: 0 eccezioni.

### Documentazione

Nuova wiki [`docs/wiki/15-run-automatico.md`](docs/wiki/15-run-automatico.md)
(perché locale e non CI, perché la continuità è critica, come si installa,
cosa guardare quando qualcosa non torna). Card
[TAL-66](docs/cards/TAL-66.md) e [TAL-67](docs/cards/TAL-67.md), entrambe in
Review. TAL-60 spostata da Review a Done (PR #19 mergiata).

### Non fatto / da decidere con Dom

- **Nessuna PR aperta**: commit e push, come da convenzione il merge lo
  conferma Dom.
- **`--llm-modello` non è nel run automatico**: la classificazione LLM dei
  procedimenti resta opt-in manuale.
- **Amministrazione Trasparente ancora scollegata** dal run (TAL-62, due
  decisioni aperte) — è la mitigazione strutturale del problema della
  finestra di pubblicazione, non solo un'estensione di copertura.
- **Se il Mac è spento, non gira niente.** launchd recupera il run al
  risveglio, ma un Mac spento due settimane riproduce lo stesso buco.
- **`anac` è muto da 41 giorni** (0 atti trovati, nessun errore): è il WAF
  ANAC noto, che richiede `--anac-file`. Nel run automatico continuerà a
  risultare "muto" finché non si decide se escluderlo dal default o
  automatizzare il download.

### TAL-68 — due scraper rotti, emersi dal primo report automatico

Non cercati: sono comparsi da soli nel primo `report_run.py` eseguito dopo un
run vero, che è precisamente il motivo per cui è stato scritto.

- **`caccamo`** era **muto da almeno il 2026-07-14**: 5 run consecutivi con
  `n_trovati=0`, `n_inseriti=0` e **mai un errore**. Causa: il portale URBI di
  quel tenant risponde HTTP 200 con *"Attenzione: per procedere occorre
  selezionare la tipologia"* e tabella vuota — `Tipologia=""` significa
  "Tutte" per ogni altro tenant URBI (ed è anche l'etichetta della sua prima
  `<option>`), ma questo la rifiuta. Verificato per confronto a parità di
  codice: Raffadali 10 atti, Caccamo 0; con `Tipologia=44` Caccamo 7.
  `urbi.py` ora scopre le tipologie dalla `<select>` e ripete una ricerca per
  ciascuna — **da 0 a 181 atti**. La condizione di attivazione è il messaggio
  del portale, non "zero atti": legarla a zero atti farebbe partire 26
  ricerche inutili ad ogni run su un albo genuinamente vuoto. Nessun fallback
  per i tenant che già funzionano, verificato dal vivo (Raffadali 20, Favara
  19).
- **`sangiuseppejato`**: `CERTIFICATE_VERIFY_FAILED`, catena servita
  incompleta — stessa causa già nota per Siculiana/Joppolo/Mirabella.
  `skip_ssl=true` nel registro, verificato: 14 atti.

**Difetto del mio primo fix, trovato dal test e non dal run**: azzerare il
contatore stop-on-known al confine di tipologia non bastava, perché lo stop
scattava *prima* di arrivarci e `break` usciva dall'intera scansione — dal
secondo run in poi lo scraper sarebbe tornato muto, stavolta in modo più
subdolo perché con atti in DB a dare l'impressione che funzionasse.
`_run_urbi_comune` ora distingue `break` (tenant normali, una sola scansione)
da `salta_tipologia` (riprende dalla tipologia successiva). 2 test di
regressione dedicati.

**Costo a regime misurato prima di lasciarlo nel run notturno** — e non
andava bene: il fix funzionava ma Caccamo costava **40 minuti** (2500s il
primo run con 547 atti nuovi, 2412s il secondo con 0 inserimenti: lo
stop-on-known filtra gli atti ma non ferma la paginazione, perché il
generatore non conosce lo stato del DB). Un'ipotesi è stata scartata dalla
misura invece che seguita: pensavo si scaricassero righe di altri enti per
tenerne poche (la select `EnteMittente` ha 304 voci) e che bastasse filtrare
server-side — misurato, pagine 2-6 danno 48 righe su 50 già di Caccamo, con e
senza filtro. Il tempo è archivio vero (la sola tipologia elettorale supera
le 50 pagine). Rimedio: tetto di 3 pagine per tipologia, disattivato dal
backfill `--no-stop`, sicuro perché dentro ogni tipologia l'albo elenca dal
più recente (verificato sui dati). **2412s → 152s.**

**713 test verdi (erano 699), ruff pulito.**

### Audit di copertura del run notturno (2026-08-19, richiesto da Dom)

Domande: *"abbiamo collegato Agrigento? ci sono scraper scollegati e/o non
verificati?"* e *"hai tenuto traccia degli scraper che non funzionano e dei
comuni che non tornano righe da qualche giorno?"*

**Copertura**: **263 dei 264 scraper eseguibili** sono nel run notturno
(Agrigento incluso, via `--extra-scrapers`, sia nel runner sia nel report).
Zero mai eseguiti, zero che non abbiano mai inserito nulla. L'unico
eseguibile escluso è `anac` (richiede `--anac-file`).

**Fuori dal run, per stato di registro**:
- **38 `pending` senza modulo** — comuni censiti in TAL-51, nessuno scraper
  mai scritto (comuni piccoli);
- **8 `pending` con piattaforma riconosciuta ma 0 atti estratti**
  (`acquavivaplatani`, `cianciana`, `floresta`, `monterossoalmo`,
  `novaradisicilia`, `oliveri`, `sanmichelediganzaria`,
  `valguarneracaropepe`) — **stessa classe di Caccamo/TAL-68**: piattaforma
  giusta, estrazione vuota, accantonati a luglio/agosto senza diagnosi;
- **2 `bloccato`** (Messina, Corleone).

**Fuori dal registro**: Amministrazione Trasparente (TAL-62) resta non
collegata a `run_scrapers.py` — deliberato, non dimenticato.

**Nota importante sul primo scatto automatico**: alle 00:24 del 19/08
l'agente risultava `runs = 0`. Non è un guasto — le 03:30 non erano ancora
arrivate; il trigger è correttamente armato (`watching = 1`, Hour 3 /
Minute 30). **Il primo run automatico vero non è ancora stato osservato**:
va verificato.

**Tracciamento — risposta onesta: parziale.** Falliti, muti e fermi sono
tracciati (storico completo in `scraper_runs`: 1484 run dal 26/06, 67 errori
conservati) e mostrati dal report. Gli **stagnanti** (righe restituite ma
nessun atto nuovo da settimane) **non erano tracciati da niente**: trovati
con una query a mano durante questo audit. Ora sono una card,
[TAL-69](docs/cards/TAL-69.md): **20 scraper su 263**, di cui 11 fermi da 42
giorni; i due senza spiegazione benigna sono `rometta` (atto più recente
**2023-09-27**) e `paceco` (**2025-07-04**), entrambi che continuano a
restituire 20 righe ad ogni run. Nota metodologica: la prima metrica provata
(run consecutivi a 0 inserimenti) era falsata dai run manuali ripetuti del
18/08 — sostituita con i giorni dall'ultimo inserimento.

Debito collegato emerso qui: **`atti.fonte_scraper` contiene il modulo (13
valori), non lo slug (263)** — per i 5 comuni con scraper gemelli (TAL-52) è
impossibile capire quale dei due funzioni.

### TAL-70 — bonifica scraper (mai diagnosticati, Corleone, ANAC, stagnanti)

Richiesta di Dom: *"sistema anac con playwright, fai lo scraper nuovo per
corleone. Sistema anche i mai diagnosticati, stagnanti e muti"*. Dettaglio in
[TAL-70](docs/cards/TAL-70.md); qui i punti che cambiano il quadro.

- **Muti: nessuno.** La categoria è vuota da TAL-68.
- **Corleone: +499 atti senza uno scraper nuovo.** Era `bloccato` con la nota
  "WordPress con CPT `documento_pubblico`": diagnosi errata — l'API REST non
  espone quel tipo e la pagina albo contiene `DB_NAME`/`StwEvent`/`urbi`. È
  un **URBI self-hosted**, quindi è bastato configurare `urbi.py`.
- **hspromila leggeva una sola delle due skin del portale**: i tenant su
  template legacy (`<tr class="itemstyle">`, 6 colonne invece di 10)
  rispondevano 200 con la tabella piena e venivano letti come vuoti — stessa
  lezione di Caccamo. Aggiunto `_parse_legacy` + paginazione `__doPostBack`
  (con cookie di sessione condiviso, senza il quale WebForms risponde 200 e
  zero righe). **Floresta 0→40, Cianciana 0→70**, attivati.
- **6 casi restanti non sono colpa nostra**, e ora il registro lo dice con la
  causa esatta invece di "0 atti, da verificare": 4 albi realmente vuoti
  ("non ha prodotto risultati" / "Nessuna pubblicazione estratta") e 2 con
  **"Errore 5052"** lato server.
- **ANAC — risolto, ma non con Playwright, e dopo una mia conclusione
  sbagliata.** Primo giro: avevo concluso che il CSV fosse stato dismesso e
  restasse solo RDF Turtle da 1,8 GB per file. **Falso**, e l'ha fatto emergere
  una domanda di Dom (*"su quale URL sei andato?"*): ero andato solo sull'URL
  configurato nel codice — un **manifest** — e da quell'inventario avevo
  dedotto quali risorse esistessero, invece di provare l'URL dei CSV per
  analogia col nome dei TTL. I CSV ci sono: `smartcig_csv_{anno}_{mese}.zip`,
  **~40 MB zippati a mese**, e anche per il **2025**, che il codice dava per
  non pubblicato.
  Resta vero il resto della diagnosi: l'URL configurato non è il dataset ma un
  indice di 1288 byte — **è questa la ragione per cui ANAC era muto**, non il
  WAF — e Playwright non serve (le pagine del portale sono respinte anche con
  Chromium reale, i file di dati non sono mai stati bloccati).
  Altri due bug emersi solo caricando i dati veri, che avrebbero lasciato ANAC
  a zero anche con l'URL giusto: le colonne del tracciato sono
  `*_appaltante`/`oggetto_lotto`/`importo_lotto` (aggiunti gli alias), e il
  filtro `sezione_regionale == "Sicilia"` non matcha mai — quel campo vale
  `"SEZIONE REGIONALE SICILIA"` e per alcuni enti siciliani perfino
  `"SEZIONE REGIONALE CENTRALE"` (Casa di reclusione di San Cataldo): **si
  perdevano righe in silenzio**, ora si filtra su `regione`. Aggiunto anche
  l'aggancio dell'ente via `istat_comune` (esatto) invece del solo LIKE sul
  nome. **Un quarto bug, trovato solo guardando i totali**: caricata l'annata 2025
  (176.827 atti), la somma degli importi dava **98 mila miliardi di euro**.
  `_parse_importo` era scritto per il formato italiano (`4.500,00`) e trattava
  il punto come separatore di migliaia, mentre il tracciato mensile usa il
  punto come **decimale** (`1550.0`, 100% delle righe): ogni importo
  moltiplicato per **10^(numero di decimali)** — `"1046.2459"` diventava
  10.462.459, ×10.000. Non è estetica — `frazionamento` e
  `concentrazione_diretti` confrontano gli importi con soglie di legge, quindi
  avrebbero prodotto red flag falsi su larga scala. Corretto distinguendo i
  due formati sulla virgola (3 test di regressione); **le righe già inserite
  sono state cancellate e ricaricate** invece di tentare di invertire la
  corruzione.
  **Verificato: 12.400 atti da un mese in 21s, 176.827 su 470 enti per
  l'annata intera in 316s**, con gli importi ricontrollati riga per riga
  contro il CSV sorgente su un campione casuale (10/10) e aggregati
  plausibili (media 1.449 €, massimo 184.987 €). `anac` resta fuori dal run notturno (dataset
  mensile), con il nuovo `--anac-anno`.
- **Stagnanti: non è codice.** Gli albi sono fermi davvero (`rometta`
  2023-09-27, `paceco` 2025-07-04, `mascalucia` 2026-06-03, contro `acate`
  sano al 2026-08-03), i siti istituzionali linkano proprio l'albo che
  leggiamo e non espongono risorse alternative. **Indagine sospesa**: aprendo
  la pagina di Mascalucia con un browser è scattato un WAF (`MDAWAF001`) su
  questo IP — coerentemente con la linea del progetto ho smesso di
  interrogare quell'host, da riprendere a freddo.

**721 test verdi (erano 714).**

### Problemi misurati e segnalati a Dom (non affrontati in questa sessione)

Numeri presi su `talia.db` reale il 2026-08-18, prima del run di recupero:

1. **`testo_estratto` è 0 su 133.726 atti.** Ogni red flag, ogni catena e
   ogni estrazione CIG lavorano sul solo `oggetto` (in media 205 caratteri,
   88 atti sotto i 10). È il tetto strutturale su tutta la qualità del
   Modulo 2 — ed è la stessa decisione già aperta in TAL-62 (#2, persistenza
   del testo).
2. **32% dei link è già morto** (41.700 atti su 130.358 con `data_scadenza`
   già passata). Contro il principio n°1 del progetto ("nessun indicatore
   senza link alla fonte"). La risposta strutturale è Amministrazione
   Trasparente (TAL-62), bloccata su due decisioni che ora hanno numeri veri
   dal notebook TAL-64 — non servono altre misurazioni, serve decidere.
3. **`enti` ha "Comune di Messina" due volte** (`083053` e `083048`, entrambi
   `bloccato`, 0 atti): riga di registro obsoleta già notata in TAL-61, mai
   rimossa. Impatto basso ma gonfia i conteggi e compare doppia nei menù.
4. **I backup stanno sullo stesso disco** del DB: `run_daily.sh` protegge da
   una corruzione o da un backfill sbagliato, non da un guasto del Mac. Il DB
   (154 MB, non versionato) è l'unico asset non riproducibile del progetto —
   gli atti scaduti dall'albo non si riscaricano.
5. **32% dei procedimenti ha `stato_finale='sconosciuto'`** (11.602 su
   35.772) — probabilmente per lo stesso motivo del punto 1.

---
> **Correzione rispetto alla voce precedente (che descriveva TAL-59 come "nessun
> commit ancora, in attesa di conferma"):** verificando lo stato reale del repo
> a inizio sessione è emerso che TAL-59 era in realtà già stato completato,
> committato (3 commit, non 1: il fix iniziale + una verifica critica su un
> campione casuale di 40 procedimenti mai ispezionati, che ha trovato 2 lacune
> reali nella prima regex + una guardia minori/tutela da code review) e
> **mergiato in `main` come PR #18 il 2026-08-13** — questo HANDOFF non era mai
> stato aggiornato dopo quel merge. Nessun contenuto perso: solo la
> documentazione era rimasta indietro rispetto ai commit reali. BOARD.md
> corretto di conseguenza (TAL-59 spostata da Review a Done).
>
> **Nuova card TAL-60** (stessa sessione, su richiesta di Dom dopo aver
> discusso cosa manca per un MVP/PoC dimostrabile di Modulo 1): tab "📁 Analisi
> fascicolo" nella dashboard Streamlit esistente (Modulo 3) — upload PDF/txt,
> analisi via il motore esistente (`analizza_testi`), nessuna persistenza dei
> file caricati. Decisioni prese in conversazione: solo uso locale (non pensata
> per hosting pubblico — riaprirebbe il tema privacy, dati nominativi nei
> fascicoli reali), tab nella dashboard già esistente invece di un'app separata
> (riusa Streamlit già presente come dipendenza del Modulo 3). Riconcilia
> esplicitamente la decisione precedente di TAL-10 ("niente Streamlit per il
> Modulo 1"): quella riguardava il formato del report (resta HTML/JSON), questo
> è un front-end opzionale in più, non una sostituzione.
>
> **Bug reale trovato solo con un run live**, non dai test pytest: gli import
> relativi (`from ..engine...`) nelle nuove funzioni fallivano in modalità
> `streamlit run src/talia/modulo3_dashboard/app.py` (script standalone, nessun
> contesto di pacchetto) — `attempted relative import with no known parent
> package`. I test pytest non lo intercettavano perché importano il modulo
> come parte del pacchetto `talia`, dove gli stessi import funzionano.
> Individuato con `streamlit.testing.v1.AppTest.from_file(...)` (che replica
> l'avvio reale) + upload simulato + click sul bottone "Analizza": 0 eccezioni
> dopo il fix (import assoluti). Dettaglio in [TAL-60](docs/cards/TAL-60.md),
> Tentativo 1.
>
> **Bug collaterale corretto** (pre-esistente, non introdotto in questa
> sessione): `main()` in `app.py` renderizzava le tab Statistiche e Mappa due
> volte ciascuna (blocco duplicato dopo il merge di PR #17) — doppie query DB
> ad ogni rerun. Rimossa la duplicazione.
>
> **TAL-60 esteso, stesso giorno** (feedback di Dom dopo aver provato il tab dal
> vivo): upload sostituito da una catena di box "allega file + descrizione" (un
> documento alla volta; il box successivo compare solo dopo aver caricato il
> precedente). La descrizione non è solo estetica: `classifica_ruolo()` /
> `punteggi_ruolo()` ora accettano una `descrizione` opzionale che concorre ai
> punteggi con le stesse regex del testo — aggancia un allegato con poco testo
> proprio (es. solo tabelle) al ruolo giusto quando da solo risulterebbe
> SCONOSCIUTO. Filo fino a `Report`/`AttoMeta` (compare accanto al documento
> nel report). Verificato dal vivo con `AppTest` (box 1→2→3 in sequenza,
> descrizioni sull'atto giusto).
>
> **TAL-61** (bug trovato da Dom guardando la tab Panoramica: "non sappiamo
> nemmeno la provincia di Ragusa?"): `sincronizza_enti_da_registro()` non
> passava mai `popolazione` e passava `provincia` solo se il registro scraper
> la conteneva (raro). `data/comuni_sicilia.csv` (rif. anagrafico dei 391
> comuni) esisteva già ma non era mai stato incrociato con `enti`. Prima del
> fix: 307/307 enti senza popolazione, 192/307 senza provincia. Corretto +
> backfill eseguito su `talia.db` reale (backup preso prima:
> `talia.db.bak-pre-backfill-provincia-pop-20260816`): ora 0/307 senza
> provincia, 1/307 senza popolazione (residuo: Messina, riga di registro
> obsoleta da una sessione precedente, non legata a questo fix).
>
> **628 test verdi (erano 614 a inizio sessione), ruff pulito.**
>
> **Discussione con Dom sui link morti nei red flag** (partita da un'altra
> segnalazione dal vivo: due link di red flag irraggiungibili, Acate e Aci
> Bonaccorsi): confermato sistemico, non isolato — su `talia.db` reale, la
> maggioranza degli atti già scrapati su quasi tutte le piattaforme (halley
> 77%, portalepa 86%, catania 86%...) ha già superato `data_scadenza`, un
> campo che catturiamo da sempre e non usiamo mai. Discusse e scartate tre
> proposte (archiviazione su terzi tipo Wayback Machine → manutenzione che il
> progetto non si può permettere; disclaimer "link forse scaduto" → cosmetico,
> non risolve nulla; cattura locale via Playwright → stesso problema di fiducia
> di una copia self-hosted, il tool di cattura è irrilevante). **Svolta di
> Dom**: questi atti sono per legge tenuti da qualche parte più a lungo di
> quanto duri l'Albo Pretorio — la sezione "Amministrazione Trasparente"
> (D.lgs. 33/2013), già segnalata come target ideale in `talia.md`/
> `docs/wiki/07-fonti-dati.md` fin dall'inizio del progetto ma **mai
> implementata da nessuno scraper** (tutti leggono solo l'Albo Pretorio, la
> bacheca temporanea).
>
> **Verifica di fattibilità su jCityGov** (la piattaforma più grande, 85.435
> atti): confermato con Playwright (curl non basta, è Liferay/JS) che
> "Amministrazione Trasparente" è un archivio permanente reale — "Bandi di
> concorso" su Ragusa mostra cartelle per anno **dal 2018**, non i 15-30gg
> dell'Albo Pretorio. Il contenuto si raggiunge con GET semplici (URL Liferay
> "render", `p_p_lifecycle=0`), non con azioni POST/sessione come temuto —
> quindi i permalink dovrebbero essere stabili, non l'ipotesi opposta
> ipotizzata su Acate. Due complicazioni reali per l'implementazione: (1) l'ID
> numerico di ogni categoria non è costante tra comuni (Bandi di concorso =
> pagina 18623 su Ragusa, 38979 su Palma di Montechiaro — va scoperto per
> tenant); (2) la selezione dell'anno è un `<select>`, non un link diretto,
> gestione form non ancora verificata. **Non ancora verificato**: il livello
> più profondo (link al singolo bando dentro un anno) — quello che conta
> davvero per la stabilità del permalink. **Nota collaterale**: richieste
> ravvicinate su un singolo tenant (Acate) hanno fatto scattare un WAF
> (sbloccato su un altro comune) — stesso principio di rate-limiting prudente
> già usato per jcitygov.py/halley.py.
>
> **`playwright` installato in questo venv locale in questa sessione**
> (`pip install playwright && playwright install chromium`) — era già usato da
> `agrigento.py`/`serviziolinealbo.py`/`palermo.py` (import lazy dentro le
> funzioni) ma **non è mai stato dichiarato come dipendenza in `pyproject.toml`**
> — funzionava solo perché qualcuno l'aveva installato manualmente in passato.
> **Corretto**: nuovo gruppo extra `playwright` in `pyproject.toml`.
>
> **TAL-60/TAL-61 committati e pushati** (3 commit: `a066f79` TAL-60,
> `8e892f6` TAL-61, `08ea525` doc). Branch pushato su origin, **nessuna PR
> aperta ancora** — solo commit+push richiesti esplicitamente, non l'apertura
> della PR.
>
> **TAL-62 — Amministrazione Trasparente jCityGov + Halley, implementata e
> verificata dal vivo** (Dom: "partirei a implementare jcity e halley...
> controlla che sia tutto funzionante", poi è uscito di casa chiedendo di
> continuare con `caffeinate` — sessione proseguita in autonomia da qui):
>
> - **jCityGov**: scoperta fondamentale — Amministrazione Trasparente usa lo
>   **stesso motore "igrid"** dell'Albo Pretorio (stessa struttura di riga,
>   stesso portlet, stessa paginazione), solo una categoria diversa — non
>   un'applicazione separata. `scopri_categorie_trasparenza()` +
>   `scarica_atti_trasparenza()` in `jcitygov.py` riusano `_parse_pagina`/
>   `_RE_NEXT` già esistenti, **nessun parser nuovo**. Playwright è servito
>   solo per la ricognizione iniziale (capire l'URL delle categorie): a
>   runtime bastano richieste HTTP dirette, verificato con `curl` puro dopo
>   la scoperta. Trovata anche un'eccezione da escludere: alcune categorie
>   (es. "Titolari di incarichi", e su Acate anche "Bandi di concorso" — non
>   uniforme tra tenant) puntano a un portlet "Soggetti" (registro persone,
>   non atti) con path `/pas/...` invece di `/papca-*/...`: filtrate.
>   Verificato dal vivo su Ragusa: 35 atti raccolti su più pagine,
>   `data_scadenza` in anni futuri (2031) confermata. 6 nuovi test.
> - **Halley**: **applicazione completamente separata** dall'Albo Pretorio
>   (Zend Framework, `/zf/index.php/trasparenza/...` — non `/mc/mc_p_*.php`):
>   HTML diverso, nessun riuso di codice possibile con `halley.py` esistente,
>   parser nuovo scritto da zero. Categorie scoperte da link diretti nel menu
>   (`.../categoria/<id>`), righe documento via `<tr data-href="...">`,
>   paginazione via path (`.../page/<N>`). **Nessuna data di scadenza sulle
>   righe** (a differenza dell'Albo Pretorio) — ulteriore segnale di
>   ritenzione permanente. Un export CSV esiste ma senza URL del documento,
>   inutile per lo scraping. Verificato dal vivo su Aci Bonaccorsi (lo stesso
>   comune del link morto originale!): 20 atti su 2 pagine, **17 pagine
>   totali** disponibili solo per "Bandi di concorso" — storico profondo
>   confermato. Trovata anche eterogeneità reale: un secondo tenant provato
>   (Vittoria) usa una piattaforma Halley più recente ("Stanza del
>   cittadino") senza il path `/zf/...` (404, gestito senza crash) — fuori
>   scope qui. 9 nuovi test.
>
> **643 test verdi (erano 634), ruff pulito.** Card [TAL-62](docs/cards/TAL-62.md)
> creata, **Stato: In Progress** (non Done): 2 domande bloccanti esplicite
> prima della messa in produzione, entrambe segnalate da Dom prima di uscire
> e non ancora decise:
> 1. **Deduplicazione con l'Albo Pretorio**: un bando pubblicato sull'Albo
>    probabilmente compare anche in Amministrazione Trasparente (stesso
>    atto, due URL diversi) — impatto su `engine/catena.py` (rischio
>    procedimenti duplicati), imparentato con TAL-52 ma dentro la stessa
>    piattaforma invece che tra piattaforme diverse.
> 2. **Download/persistenza del testo**: la discussione che ha originato
>    questa card aveva sollevato anche se scaricare/estrarre il testo (non
>    solo l'URL) per gli atti citati nei red flag — non ancora affrontato,
>    `testo_estratto`/`hash_sha256` restano vuoti anche qui.
>
> **Le funzioni non sono collegate a `run_scrapers.py`/registry**: esistono,
> sono testate e verificate dal vivo, ma non fanno ancora parte del run
> automatico — deliberato, in attesa delle due decisioni sopra.
>
> **TAL-62 committato e pushato** (`6666445`), stesso branch.
>
> **Quantificata dal vivo la deduplicazione con l'Albo Pretorio** (lavoro
> autonomo dopo che Dom è uscito, con `caffeinate`), per dare numeri reali
> alla discussione invece di procedere a intuito — dettaglio completo in
> [TAL-62](docs/cards/TAL-62.md#-domande-aperte-bloccanti-prima-della-messa-in-produzione):
> il profilo è **opposto tra le due piattaforme**, non un problema unico.
> **jCityGov** (Ragusa): 80/80 atti (100%) di "Bandi di concorso" già
> presenti in `talia.db` con lo **stesso `url_fonte` esatto** — stesso
> backend "igrid" di Albo Pretorio, la deduplicazione è già gratuita via
> `UNIQUE(ente_id, url_fonte)`, ma con un effetto collaterale da decidere:
> se l'atto esiste già come `fonte_scraper="jcitygov"`, la versione
> `"jcitygov_trasparenza"` non verrebbe mai scritta (`inserisci_atto` è
> insert-if-not-exists, non upsert) — l'informazione "ritenzione lunga"
> andrebbe persa in silenzio per gli atti già noti. **Halley** (Aci
> Bonaccorsi): 0/50 atti (0%) già presenti, né per URL né per oggetto
> normalizzato — applicazione separata, nessuna sovrapposizione strutturale
> di URL, ma nemmeno deduplicazione automatica: un atto pubblicato oggi su
> entrambe le sezioni creerebbe due righe distinte.
>
> **TAL-63 (P0) — Dom è tornato e ha rilanciato la domanda su jCityGov**:
> "anche per jCity se clicco su un riferimento va su una pagina sballata",
> con l'URL esatto di Acate già visto all'inizio del filone. Verificato con
> Playwright (non solo curl): il formato `url_fonte` generato da
> `_url_dettaglio()` — usato per **ogni** atto jCityGov, non solo
> Amministrazione Trasparente — dà sempre errore server-side
> ("Errore: contattare l'amministratore del Portale"), a sessione fredda e
> con sessione attiva, confermato anche nell'HTML grezzo via curl puro (non
> un problema di rendering JS) su due tenant diversi. Trovato il formato
> vero cliccando davvero il bottone "Apri Dettaglio" nel portale:
> `/-/papca/display/<id>?p_p_state=pop_up`, verificato a freddo.
> `pdf_download.py` lo sapeva già (`_url_display_format`, usata per gli
> allegati) ma come ottimizzazione, mai riportato a monte in
> `_url_dettaglio()` — il link mostrato agli utenti è rimasto rotto.
> **Corretto** (anche un bug collaterale: `papca_path` era hardcoded,
> sbagliato per i 6 tenant TAL-49 con percorso alternativo). 643 test
> verdi, committato e pushato (`5aac84d`).
>
> **Non ancora fatto — bloccante, serve conferma esplicita di Dom**: backfill
> sugli **85.435 atti già in `talia.db`** con il vecchio formato non
> funzionante. Il fix vale solo per i run futuri finché non si esegue la
> migrazione (script non ancora scritto — estrarre `pub_id` da ogni
> `url_fonte` esistente, ricostruire con `_url_dettaglio()`, backup del DB
> prima come già fatto per TAL-61).
>
> **TAL-63 chiusa** (Dom, di ritorno: "sì, procedi"). Backfill di prova su
> Acate prima (41 atti): ha rivelato che la dashboard non legge i link da
> `atti.url_fonte` ma da `red_flags.atti_cig`, una copia JSON denormalizzata
> mai sincronizzata — corretta anche quella. Prima di estendere a tutto il
> DB, controllata anche **Halley** su richiesta di Dom: nessun bug analogo
> (Albo Pretorio ok; Amministrazione Trasparente scarica il PDF diretto,
> comportamento corretto). Backfill completo eseguito: **85.394 atti** +
> **2019 voci in 341 `red_flags.atti_cig`** corrette, verificate con
> Playwright su due campioni casuali indipendenti (14/14 funzionanti).
> Backup preso prima (`talia.db.bak-pre-backfill-tal63-completo-20260816`).
> 643 test verdi, tutto committato e pushato (`bf41fe9`).
>
> **⚠️ Segnalato da Dom, non ancora approfondito**: "le catene hanno dei
> problemi" — nessun dettaglio ancora, discussione rimandata esplicitamente
> a valle della decisione di deduplicazione TAL-62 in corso. Da riprendere
> chiedendo a Dom cosa ha osservato prima di ipotizzare la causa.
>
> **TAL-64 aperta** — deduplicazione atti Albo Pretorio / Amministrazione
> Trasparente. Spec concordata con Dom (schema `atti`/`atti_fonti`
> normalizzato, `data_pub` per-fonte non canonica, CIG esatto-o-niente) ma
> **non ancora implementata**: prima, su richiesta di Dom, un esperimento coi
> dati reali. Ingest sperimentale di 1053 atti di Amministrazione Trasparente
> in tabella di staging separata (`atti_trasparenza_staging`, script
> `scripts/tal64_staging_trasparenza.py`, non tocca `atti`) su 7 comuni
> jCityGov + 1 Halley (Aci Bonaccorsi). Trovato: le categorie di default non
> generalizzano (riforma ANAC 2023 ha frammentato "Bandi di gara e
> contratti" in sotto-categorie su jCityGov; su Halley nessun tenant tranne
> Aci Bonaccorsi ha categorie con "bandi" nel nome), `data_atto` è 0/1053
> (la chiave di fallback `tipo+numero+data_atto` della spec va rivista senza
> `data_atto`), `numero="0"` è una sentinella in 135/1053 righe (esclusa dal
> matching). Matching CIG/numero+tipo su jCityGov: 479/928 confermati (0
> falsi positivi), ma tutti con lo stesso `url_fonte` (dedup già gratuita
> lì) — non ancora testato il caso interessante URL-diverso-stesso-atto.
> **Halley: 0/125 match — indagato (Tentativo 2)**: non è un bug del parser,
> le righe di Amministrazione Trasparente su Halley espongono **solo**
> descrizione + data inserimento, nessun campo numero/CIG in HTML (a
> differenza dell'Albo Pretorio, che il "Numero atto" ce l'ha); il link
> apre un **PDF diretto**, non una pagina di dettaglio — CIG/numero
> recuperabili solo scaricando e leggendo il PDF, la stessa decisione
> aperta di TAL-62 (#2, persistenza del testo). Per Halley l'identità
> dovrà appoggiarsi a `oggetto` esatto + `data_pub`, o restare senza
> deduplicazione automatica — non ancora deciso.
>
> **Notebook `notebooks/tal64_dedup_jcitygov.ipynb`** (su richiesta di Dom,
> per rendere l'esperimento ripetibile): trovato che la conclusione "CIG: 0
> falsi positivi" del primo giro era sbagliata — controllava solo se un
> match esisteva, non se fosse quello giusto. Rifatto con precisione: **il
> 40% dei CIG copre più di un atto reale** (una gara produce più atti nel
> tempo, tutti con lo stesso CIG), il CIG da solo fonderebbe atti distinti.
> Chiave rivista: `(ente_id, cig, numero)`, ambigua solo nel 6,2% dei casi.
> Il caso vero da deduplicare (stesso atto, URL diverso) esiste ma è raro:
> **1 solo caso su 1048** atti di staging (148 erano già dedup gratuita via
> URL condiviso). Trovato anche un bug collaterale: il campo `cig` a volte
> contiene la stringa `"ORIGINARIO"` invece di un CIG vero (91 atti su un
> comune) — non ancora indagato, non bloccante.
>
> **Verificato che le gare Halley sono già nell'Albo Pretorio** (non altrove,
> ipotesi di Dom controllata e non confermata): 3626/28160 atti Halley hanno
> già CIG. Il gap reale che Amministrazione Trasparente colma sono i
> **concorsi**, che non hanno mai CIG per natura — nessuna terza sezione
> trovata sui siti istituzionali testati.
>
> **Fattibilità download+estrazione PDF per Halley confermata** (5 PDF di
> prova, Aci Bonaccorsi): `engine.pdf_text.estrai_testo()` (già esistente,
> nessuna nuova dipendenza) estrae il numero atto su 3/5 PDF (es.
> "Determinazione n. 1217"); CIG assente in tutti e 5, atteso (concorsi).
> Conferma che vale la pena decidere la persistenza del testo (TAL-62 #2)
> almeno per questo caso — non ancora implementato in produzione.
>
> Todo list completa dei prossimi passi in
> [TAL-64](docs/cards/TAL-64.md#-task). Tabella di staging lasciata nel DB
> reale (1048 jCityGov + 125 Halley) per proseguire senza riscaricare.
>
> **TAL-65 (P1) — bug reale trovato e risolto**: Dom ha notato "i CIG possono
> avere dei CIG padre e figli" — verificato su `talia.db`: 578 atti citano
> pattern "CIG padre"/"CIG derivato"/"CIG originario" (accordi quadro,
> convenzioni CONSIP), e `estrai_cig()` — **usata da 14 scraper su 14**, più
> due copie quasi identiche in `engine/entita.py` (Modulo 1) e
> `engine/catena.py` (collegamento catene) — li estraeva quasi sempre male:
> 127 falsi positivi (`cig` valorizzato con la parola `"ORIGINARIO"`, che è
> lunga esattamente 10 lettere e ingannava il fallback generico), 368 falsi
> negativi (`cig` NULL nonostante il testo avesse due codici veri). Corretto
> con tre regex distinte (padre/derivato/semplice, lookahead negativo per
> evitare che il fallback inghiottisca la parola etichetta) invece di una
> sola con etichetta opzionale. Nuova colonna `atti.cig_padre` (migrazione
> lazy `_estendi_atti()`, stesso pattern di `_estendi_enti`), tutti i 14
> scraper aggiornati meccanicamente. `catena.py::estrai_riferimenti()` ora
> scarta esplicitamente i CIG padre dai riferimenti incrociati (un CIG padre
> è condiviso da molte adesioni distinte — usarlo collegherebbe atti non
> correlati, probabile causa non confermata di "le catene hanno dei
> problemi"). 12 nuovi test, **655 test verdi (erano 643)**.
>
> **Backfill completo su `talia.db` reale** (backup preso prima:
> `talia.db.bak-pre-fix-cig-padre-tal65-20260818`): ricalcolato `cig`/
> `cig_padre` da `atti.oggetto` già in DB (nessuna nuova richiesta HTTP) su
> 132.317 righe. Primo giro: 3585 corrette, ma 3 residue con un pattern non
> previsto (codice tra parentesi quadre + "CIG." abbreviato) — corretta la
> regex, rieseguito (idempotente): altre 235 corrette. **Risultato finale:
> 0 righe con CIG-garbage residuo, 38.560 atti con CIG, 200 con CIG padre.**
> Card [TAL-65](docs/cards/TAL-65.md), Stato: Done.
>
> **Non ancora fatto**: verificare l'impatto reale su `catena.py` (quante
> catene cambiano ora che `cig` è pulito) — è il collegamento diretto con la
> segnalazione di Dom su "le catene hanno dei problemi", ancora da
> approfondire specificamente con lui prima di concludere che sia risolta.
>
> **Prossimi passi** (da riprendere con Dom): le due domande bloccanti di
> TAL-62 (dedup — con i numeri già raccolti, non più a intuito — e
> download/persistenza) prima di collegare Amministrazione Trasparente al
> run automatico; poi verificare fattibilità Amministrazione Trasparente
> sulle piattaforme restanti (portalepa, catania, palermo, urbi, trapani,
> hspromila — 14% dei dati) e se il bug TAL-63 esiste anche lì (Halley già
> controllata, pulita). Poi, non ancora ripreso: TAL-12 (validazione umana
> ⚖️ LEX sui candidati rimasti — 6, 7, 8, più 13 da verificare); rigenerare
> `data/samples/` di TAL-12 scartando i candidati falsi positivi
> individuati da TAL-59 (3, 9, 10, 11,
> 12); bug 2b (Jaccard, noto da TAL-59); TAL-3 (PDF scansionato campione);
> backlog P2/P3 (TAL-51, TAL-41, TAL-24, TAL-52, TAL-40).

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

**Prossimo passo (superato, vedi banner in cima al file):** ~~PR #17 aperta, in attesa
di review/merge~~ — mergiata il 2026-08-09.

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
