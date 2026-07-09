# TAL-49 — Censimento albi pretori e rollout scraper comuni siciliani

- **Epica:** E3 — Copertura territoriale
- **Ruolo:** 🕷️ SCR
- **Priorità:** P1
- **Stato:** In Progress
- **Branch:** `feat/E3-censimento-comuni-sicilia`

## 🎯 Obiettivo
Copertura scraper estesa oltre i capoluoghi: censimento piattaforma per tutti i 391 comuni siciliani (in ordine di popolazione) e attivazione degli scraper sulle piattaforme già supportate (jCityGov in primis).

## 📋 Spec

### Interfaccia
```text
data/comuni_sicilia.csv                # denominazione, provincia, codice_istat, popolazione (ordinato desc)
docs/wiki/14-censimento-albi.md        # tabella comune → URL albo → piattaforma → stato scraper
scripts/run_scrapers.py                # _JCITYGOV_COMUNI esteso; runner registrati dinamicamente
```

### Comportamento
1. Sweep deterministico del pattern `https://<slug>.trasparenza-valutazione-merito.it` (jCityGov) su tutti i comuni.
2. Ogni hit verificato con run reale a 2 pagine su DB isolato prima di entrare in `_JCITYGOV_COMUNI`.
3. Comuni non-jCityGov nella fascia alta di popolazione: esplorazione dedicata (agent economico) e classificazione piattaforma nella wiki.
4. Catania (URBI, HTTP puro) e Palermo (SISPI, Playwright) come scraper dedicati, card separate se non banali.

### Casi limite
- Slug non standard (es. `palmadimontechiaro` senza spazi, alias tipo Mojo/Moio) → verifica manuale, non inferire.
- Hit jCityGov con albo vuoto o portlet assente → il run di verifica a 2 pagine lo smaschera; non aggiungere al registro.
- Sito irraggiungibile → loggare in Tentativi e passare oltre, ritentare in coda.

## ❓ Domande aperte
- [ ] I nuovi comuni jCityGov verificati entrano subito nel default run o restano opt-in fino a conferma di Dom? (scelta provvisoria: entrano nel default; da confermare in review PR)

## 📚 Contesto
`CLAUDE.md` (tabella scraper, "Come aggiungere uno scraper"), `docs/wiki/13-scraper-status.md`.

## ✅ Task
- [x] Lista 391 comuni per popolazione (`data/comuni_sicilia.csv`)
- [x] Refactor registrazione dinamica runner jCityGov
- [x] Sweep jCityGov completo (391/391) + wiki censimento (`docs/wiki/14-censimento-albi.md`)
- [x] Verifica con 10 atti reali per ogni hit e aggiornamento `_JCITYGOV_COMUNI` (68 hit → 60 attivi)
- [x] Esplorazione Palermo → HTTP puro, `palermo.py` + 8 test, validato e2e
- [x] Scraper Catania (URBI) — `catania.py` + 6 test, validato e2e
- [x] Fix codici ISTAT errati (Caltanissetta/Siracusa/Enna/Palma) — migrazione DB da applicare
- [x] Tabella scraper in CLAUDE.md + BOARD aggiornati

## 🧪 Criteri di accettazione
- [ ] Ogni comune aggiunto ha un run di verifica riuscito su DB isolato (atti > 0, url_fonte validi)
- [ ] Wiki censimento con URL e piattaforma per ogni comune classificato
- [ ] Test passano (`pytest`)
- [ ] DoD rispettata (vedi CLAUDE.md)

## 🔬 Tentativi

### 2026-07-07 — Tentativo 1
**Approccio:** Lista comuni: join ISTAT (Elenco comuni italiani, regione 19) × Wikipedia (popolazione).
**Esito:** ✅ 391/391 (3 alias risolti a mano: Calatafimi-Segesta, Mojo/Moio Alcantara, Tripi/Tripi-Abakainon).
**Appreso:** l'elenco ISTAT non ha la popolazione; Wikipedia sì ma con grafie leggermente diverse — serve normalizzazione + alias espliciti.

### 2026-07-07 — Tentativo 2
**Approccio:** Catania URBI: GET su `servizionline.comune.catania.it` (ur1ME001.sto, DB_NAME=wt00041571), già funzionante nelle esplorazioni di fine giugno.
**Esito:** ❌ server irraggiungibile (porte 443 e 80 chiuse, anche www.comune.catania.it giù).
**Appreso:** non è un blocco anti-bot: l'intera infrastruttura del Comune non risponde. Ritentare più tardi; lo scraper si può scrivere sull'HTML già osservato, ma senza validazione live non si dichiara "OK".

### 2026-07-07 — Tentativo 3
**Approccio:** Sweep GET del pattern `<slug>.trasparenza-valutazione-merito.it` su tutti i 391 comuni (0.3s delay, fingerprint Liferay nel body).
**Esito:** ✅ completato su 391/391: 68 hit, 60 verificati e registrati (8 con portale presente ma albo vuoto via API: Milazzo, Noto, Aragona, Racalmuto, Ribera, Gaggi, Letojanni, Condrò).
**Appreso:** il parco jCityGov in Sicilia è 15× i 4 comuni già in registro: è il moltiplicatore principale della copertura (55% della popolazione siciliana ora coperta). Verificare sempre con atti reali: ~12% degli hit ha il portale ma non espone l'albo.

### 2026-07-07 — Tentativo 4
**Approccio:** Palermo: esplorazione delegata ad agent haiku, poi validazione diretta del flusso HTTP.
**Esito:** ✅ HTTP puro funziona — la nota storica "Playwright obbligatorio" era errata.
**Appreso:** il menu passa da `servizi.jsp` → `scelta_tipo_documento.jsp` → URL push; i TD delle card NON coincidono con quelli reali del push (TD=20 → TD=2010): mai hardcodare, scoprirli a runtime. Il dettaglio atto (`tabella-modifica.do?row=N`) è stateful e non linkabile: come url_fonte si usa lista+`#prot-<numero>`. Il push URL contiene spazi letterali in TDDES → percent-encoding necessario.

### 2026-07-07 — Tentativo 5
**Approccio:** cross-check dei codici ISTAT del registro contro il CSV ufficiale ISTAT.
**Esito:** ✅ trovati e corretti 4 codici errati pre-esistenti.
**Appreso:** Caltanissetta 085003 era Butera, Siracusa 089018 era Solarino, Enna e Palma off-by-one. Il codice ISTAT è la chiave dell'ente nel DB: gli errori contaminano anche i confronti con ANAC. Mai copiare codici a mano: derivarli dal CSV ISTAT.

### 2026-07-07 — Tentativo 6
**Approccio:** Catania: esplorazione wizard URBI delegata ad agent haiku, poi validazione diretta e implementazione.
**Esito:** ✅ HTTP puro anche qui, nessuna "enumerazione ID" necessaria.
**Appreso:** il wizard stepper `.sto` si riproduce con 2 POST (`StwEvent=910001` ricerca, `9100030` paginazione); il filtro data del portale è rotto (0 risultati) → enumerare senza filtri. La lista contiene già tutti i metadati; `IdMePubblica` dà un URL di dettaglio stabile (GET). L'albo ospita atti di altri enti mittenti: vanno scartati. Oltre l'ultima pagina il portale ripete l'ultima → stop su pagina identica. Al mattino il server era completamente giù: l'instabilità è del Comune, riprovare più tardi funziona.

### 2026-07-07 — Tentativo 7 (test run completo)
**Approccio:** run di tutti i 64 scraper su `talia.db` (dopo migrazione ISTAT, backup fatto). Richiesta di Dom: testare tutto e correggere alla bisogna.
**Esito:** ⚠️ 64/64 completati senza errori HTTP, ma trovato bug di parsing: 12 tenant jCityGov (Castel di Iudica, Lentini, Augusta, Santa Teresa di Riva, San Vito Lo Capo, Mazara del Vallo, Alcamo, Paternò, Pedara, Tremestieri Etneo, Castelvetrano, Comitini) non hanno la colonna "Anno e Numero Registro" → oggetto nel campo numero, date NULL. Fix: mapping colonne dall'header. 3915 atti corrotti ripuliti e ri-scaricati.
**Appreso:** i tenant jCityGov NON sono uniformi nelle colonne: il parser deve leggere l'header, mai indici fissi. La verifica "10 atti reali" non basta: bisogna controllare anche che i CAMPI siano giusti (date non NULL), non solo che gli atti arrivino. DB dopo il run: 65 enti, ~35k atti, 19 red flags.

### 2026-07-07 — Tentativo 8 (ricognizione 10 comuni non-jCityGov + fix Milazzo)
**Approccio:** 10 agenti haiku in parallelo (solo ricognizione, no scrittura codice) sui prossimi 10 comuni per popolazione non censiti: Gela, Vittoria, Barcellona P.G., Sciacca, Caltagirone, Monreale, Adrano, Favara, Milazzo, Partinico. Poi validazione diretta.
**Esito:** ✅ emerse 3 famiglie di piattaforma non ancora coperte:
- **Halley EG** (Vittoria, Sciacca, Adrano, Barcellona P.G.) — PHP, paginazione `?pag=N`, HTTP puro
- **SoluzioniPA** (Monreale, Gela*, Partinico) — `<slug>.soluzionipa.it/openweb/albo/`, HTTP puro (*Gela ha dominio proprio con lo stesso path, da confermare stesso vendor); Partinico potrebbe richiedere JS (bundle React) da verificare a mano
- **URBI Cloud** (Favara) — dialetto diverso da Catania: form POST tradizionale invece di stepper StwEvent

Inoltre **Milazzo era erroneamente segnato come "jCityGov 0 atti"**: in realtà l'albo è raggiungibile ma su un percorso diverso (`papca-ap/igrid/<id>` invece di `papca-g`). Ho verificato che lo stesso vale per altri 4 degli 8 comuni "morti" del censimento: **Aragona, Gaggi, Letojanni, Noto** hanno anch'essi atti reali sullo stesso percorso alternativo (Condrò, Racalmuto, Ribera restano genuinamente a 0). Implementato fallback automatico in `jcitygov.py::scarica_atti`: se il percorso standard ritorna "0 risultati", scopre il percorso alternativo dalla pagina menu `/web/trasparenza/albo-pretorio` (blocco `data-mainurl`) e lo usa per tutta la sessione di paginazione. 4 nuovi test (`test_jcitygov.py`), 326 test totali verdi. I 5 comuni sbloccati aggiunti a `_JCITYGOV_COMUNI` (verificati con run reale: 40/40 atti ciascuno, `--max-pagine 2`).
**Appreso:** "0 atti dalla API" nel censimento jCityGov non significa "albo vuoto" — può significare "istanza portlet sbagliata". Vale la pena ricontrollare Condrò/Racalmuto/Ribera più a fondo in futuro (magari con un `data-resource` diverso da "Albo pretorio"). Halley EG e SoluzioniPA sono vendor diffusi tra più comuni: convergere su scraper generici (`halley.py`, `soluzionipa.py`) invece di uno per comune, e valutare uno sweep di dominio per SoluzioniPA come già fatto per jCityGov.

### 2026-07-07 — Tentativo 9 (ricontrollo Condrò/Racalmuto/Ribera)
**Approccio:** su richiesta di Dom, prima di passare a Halley EG, ricontrollo a fondo i 3 comuni ancora a 0 atti dopo il Tentativo 8. La pagina menu `/web/trasparenza/albo-pretorio` espone in realtà **due** blocchi `data-resource`: "Albo pretorio" (corrente) e "Storico atti" (archivio), ciascuno con un proprio `igrid/<id>` — il fallback del Tentativo 8 provava solo il primo.
**Esito:** ✅ **Racalmuto** ha "Albo pretorio" vuoto ma **"Storico atti" con 3.384 atti reali** (2022-10-27 → 2022-11-14: dati storici, non un flusso continuo). Condrò e Ribera restano a 0 su entrambe le risorse — genuinamente senza atti pubblicati su questo portale. Generalizzato il fallback in `jcitygov.py`: prova "Albo pretorio" poi "Storico atti" in sequenza, si ferma alla prima non vuota; se nessuna funziona logga un WARNING esplicito (fragilità "0 atti silenzioso" già nota in CLAUDE.md). 2 nuovi test, 327 totali verdi. Racalmuto aggiunto a `_JCITYGOV_COMUNI` e verificato con run reale.
**Appreso:** i tenant jCityGov possono avere più "risorse" (correnti/storiche) con `igrid` diversi sotto lo stesso menu: quando una manca di dati non è detto che il tenant sia morto, vale la pena enumerare tutte le risorse del menu prima di arrendersi. Prossimo passo confermato: Halley EG.

### 2026-07-07 — Tentativo 10 (portalepa generalizzato + Halley EG implementato)
**Approccio:** prima di scrivere `soluzionipa.py` per Gela/Monreale/Partinico (ipotesi del Tentativo 8), verifica diretta della struttura HTML reale di ciascuno confrontata con `siracusa.py`.
**Esito:** ✅ **Gela e Monreale usano l'identica piattaforma "portalepa" di Siracusa** (stesso path `/openweb/albo/albo_pretorio.php`, stesse righe `<tr class="paginated_element">`, stesso meccanismo CSRF/paginazione): "SoluzioniPA" non è una piattaforma diversa, era un'etichetta imprecisa degli agenti di ricognizione. Generalizzato `siracusa.py` → nuovo modulo `portalepa.py` (base_url/codice_istat parametrici, `siracusa.py` lasciato intatto per non rischiare regressioni sul comune già in produzione), registrati Gela e Monreale. **Partinico** invece ha un layout colonne diverso (variante `_full`: link "Vai" invece di numero pubblicazione, una sola data invece di due) — non riusabile senza un mapping dedicato, lasciato in coda.

Poi implementato **`halley.py`** generico per Vittoria, Sciacca, Adrano, Barcellona Pozzo di Gotto: paginazione stateless via querystring `?pag=N` (nessuna sessione, nessun CSRF), parsing per coppie `<strong>etichetta</strong><div>valore</div>` (ogni riga appare 2 volte nell'HTML, variante desktop/mobile — si prende la prima occorrenza di ciascun campo). Validato con run reale su tutti e 4 i comuni prima di scrivere i test. 29 nuovi test (`test_portalepa.py`, `test_halley.py`), 356 totali verdi.

**Copertura**: 77 comuni attivi ≈ 2.878.107 abitanti (57,5% della popolazione, da 51,7%).
**Appreso:** non fidarsi delle etichette di piattaforma date da agenti di ricognizione haiku senza confronto diretto col codice esistente — "sembra nuovo" può nascondere un riuso a costo quasi zero (Gela/Monreale). Verificare sempre contro gli scraper già in repo prima di progettare un modulo nuovo.

### 2026-07-07 — Tentativo 11 (sweep di dominio Halley EG)
**Approccio:** su richiesta di Dom di "continuare gli sviluppi con Halley", niente nuovo scraper ma uno sweep di dominio sul modello jCityGov, adattato all'assenza di un pattern unico: provati i sottodomini noti (`trasparenza.`, `servizi.`, `servizionline.`, `www.`) su `comune.<slug>.<prov>.it/mc/mc_p_ricerca.php` per i 380 comuni non ancora coperti, fingerprint `"table-albo"` + `"Halley"` nel body. Script one-off in Python (non committato, in scratchpad), 24 thread paralleli, ~380×4 richieste.
**Esito:** ✅ **85 nuovi hit**, tutti verificati con `halley.scarica_atti()` reale (con retry su timeout transitori): 0 vuoti, 0 errori persistenti. 3 collisioni di nome con entry jCityGov già esistenti (Racalmuto, Favignana, San Giovanni la Punta — stesso comune, ISTAT identico, presente su entrambe le piattaforme): rinominate con suffisso `_halley`. Tutti aggiunti a `_HALLEY_COMUNI` (89 totali). **Copertura: 159 comuni unici, 3.375.276 abitanti (67,5% della popolazione, da 57,5%)**.
**Appreso:** il primo tentativo di fingerprint falliva silenziosamente (falso negativo su tutti, inclusi i 4 tenant noti) perché leggevo solo i primi 20KB della risposta — l'impronta Halley è più avanti nella pagina (~57KB). Sempre validare la funzione di fingerprint contro un caso noto-positivo E noto-negativo prima di lanciare lo sweep su scala. Un comune può avere l'albo attivo su più piattaforme contemporaneamente (Racalmuto: jCityGov "Storico atti" + Halley corrente) — non escludere un comune da un nuovo sweep solo perché già "coperto" altrove, potrebbe avere dati diversi/più recenti.

### 2026-07-07 — Tentativo 12 (sweep di dominio portalepa; controllo backfill)
**Approccio:** su richiesta di Dom ("tentativi a basso sforzo"): 1) controllo dell'esito del backfill storico lanciato manualmente da Dom nella sessione (2 lotti, 27 comuni jCityGov); 2) stesso sweep di dominio del Tentativo 11 ma per portalepa (`<slug>.soluzionipa.it` + `portale(pa).comune.<slug>.<prov>.it`), fingerprint validato prima su Siracusa/Gela/Monreale (noti) e un caso negativo.
**Esito:** ✅ Backfill: entrambi i lotti completati senza errori (`scraper_runs` pulito, unico run orfano è quello già noto delle 16:01 da ignorare). `talia.db`: 65 enti, 78.323 atti. ✅ Sweep portalepa: **16 nuovi hit**, tutti verificati con atti reali, aggiunti a `_PORTALEPA_COMUNI` (18 totali). Risultato più rilevante: **Caltagirone**, bloccata su jCityGov da WAF/cert scaduto, è raggiungibile su `caltagirone.soluzionipa.it` — sbloccata senza bisogno di intervento del Comune. Villabate era già coperta da jCityGov (rinominata `villabate_portalepa`). **Copertura: 174 comuni unici, 3.496.160 abitanti (69,9% della popolazione, da 67,5%)**.
**Appreso:** un comune può avere più sistemi di pubblicazione atti in parallelo (es. un vecchio jCityGov abbandonato con cert scaduto + un portalepa/SoluzioniPA più recente e funzionante) — non dare per "bloccato" un comune definitivamente solo perché una piattaforma è down, vale la pena controllare le altre famiglie note prima di rinunciare.

### 2026-07-08 — Tentativo 13 (run completo su talia.db; completamento provincia di Agrigento, gruppo 1/4)
**Approccio:** Dom ha lanciato il primo run completo con tutti i 177 scraper del default su `talia.db` (mai fatto prima con la copertura di oggi). In parallelo, richiesta di completare la provincia di Agrigento (43 comuni, 18 coperti): sweep mirato con le 3 famiglie note (jCityGov/portalepa/Halley) sui 25 mancanti, poi ricognizione a gruppi di 3 (agenti haiku) sui più popolosi per quelli non risolti dallo sweep.
**Esito:** ✅ Run completo: **174 enti, 92.948 atti, 22 red flags**, solo 2 errori SSL transitori (Misilmeri, Valledolmo — comuni già coperti, timeout isolato). ✅ Sweep mirato AG: solo 1 hit (Ribera su jCityGov, ma già noto vuoto — confermato). ✅ Ricognizione gruppo 1 (Favara, Ribera, Raffadali):
- **Favara** e **Raffadali**: entrambi **URBI Cloud** (`cloud.urbi.it`, stesso meccanismo POST/stepper di Catania, `DB_NAME` diverso per tenant) — generalizzato `catania.py` in un nuovo modulo `urbi.py` (base_url/qs_base/ente_mittente parametrici), `catania.py` lasciato intatto.
- **Ribera**: **non è jCityGov** (il tenant esistente era genuinamente vuoto) — l'albo vero è su **WordPress** del sito istituzionale (`comune.ribera.ag.it/atti-pubblici/albo-pretorio/`, tema "design-comuni-wordpress-theme"), piattaforma mai vista prima. Nuovo scraper dedicato `ribera.py` (paginazione stateless `?Pag=N`).

Tutti e 3 validati con run reale prima dei test (18 nuovi test tra `test_urbi.py` e `test_ribera.py`, 374 totali verdi). Registrati in `run_scrapers.py` (`_URBI_COMUNI`, `ribera` dedicato).
**Appreso:** un tenant "vuoto" su una piattaforma nota (Ribera su jCityGov) non implica che il comune non pubblichi affatto — può aver spostato l'albo su un sistema completamente diverso (qui il CMS istituzionale stesso). Il tema WordPress di Ribera potrebbe essere condiviso da altri comuni siciliani: da tenere presente per un futuro sweep.

### 2026-07-08 — Tentativo 14 (completamento Agrigento, gruppo 2/4)
**Approccio:** ricognizione gruppo 2 (Menfi, Ravanusa, Campobello di Licata), stesso schema del gruppo 1.
**Esito:** ✅ Tutti e 3 riusano piattaforme già coperte, **zero codice nuovo**:
- **Menfi**: Halley EG (sottodominio `servizi.comune.menfi.ag.it`, diverso da `trasparenza.` ma già gestito da `halley.py` senza modifiche) — 50 atti
- **Ravanusa**: URBI Cloud — l'agente di ricognizione aveva erroneamente concluso "serve Playwright" (aveva visto solo la GET iniziale con "Attendere prego" senza provare il POST StwEvent); verificato direttamente con `urbi.py` esistente: 20 atti, HTTP puro, nessun Playwright
- **Campobello di Licata**: URBI Cloud, confermato e funzionante con `urbi.py` — 20 atti

Tutti e 3 aggiunti ai registri esistenti (`_HALLEY_COMUNI`, `_URBI_COMUNI`), nessun nuovo modulo. 374 test invariati (nessun codice nuovo da testare).
**Appreso:** verificare SEMPRE le conclusioni di un agente di ricognizione con una chiamata diretta prima di accettarle — "serve Playwright" era falso per Ravanusa. I sottodomini Halley/URBI variano parecchio da comune a comune (`servizi.`, `trasparenza.`, `cloud.urbi.it` vs dominio proprio): gli scraper generici già gestiscono questa variabilità senza bisogno di modifiche, basta passare il base_url giusto.

### 2026-07-08 — Tentativo 15 (completamento Agrigento, gruppo 3/4)
**Approccio:** ricognizione gruppo 3 (Naro, Santa Margherita di Belice, Sambuca di Sicilia), con istruzione esplicita agli agenti di testare il POST URBI prima di concludere "serve Playwright" (lezione del gruppo 2).
**Esito:** ✅ **Naro** e **Santa Margherita di Belice**: entrambi URBI Cloud, confermati con `urbi.py` esistente senza modifiche (20 atti ciascuno). ✅ **Sambuca di Sicilia**: piattaforma genuinamente nuova, **Halley HSPromila** (ASP.NET, `hypersicapp.net` — diversa dalla Halley EG di `mc_p_ricerca.php`), HTTP puro (la tabella è già nell'HTML della prima GET). Nuovo scraper dedicato `sambucadisicilia.py`.

**Bug trovato e corretto in fase di test**: la piattaforma non espone link di dettaglio per singolo atto nella riga, quindi la prima versione usava lo stesso `url_fonte` (la pagina lista) per tutti gli atti — dato che la dedup del DB si basa su `(ente_id, url_fonte)`, solo il **primo** atto di ogni run sarebbe stato salvato, tutti gli altri scartati silenziosamente come "duplicati". Scoperto dal test `test_salva_atti_inseriti` (si aspettava 2 inseriti, ne arrivava 1). Fix: `url_fonte` = pagina lista + frammento `#<id_riga_interno>` (dalla colonna "key" nascosta), reso univoco per atto. Verificato dal vivo: 95/95 atti con `url_fonte` univoci dopo il fix.

10 nuovi test (`test_sambucadisicilia.py`), 384 totali verdi. Tutti e 3 registrati (`_URBI_COMUNI`, `sambucadisicilia` dedicato).
**Appreso:** quando una piattaforma non espone un link di dettaglio per atto, **non riusare l'URL della pagina lista come `url_fonte` senza renderlo univoco** — la dedup silenziosa (nessun errore, nessun warning) nasconde perdita di dati. Un test che verifica il conteggio di `inseriti` su un campione con ≥2 atti distinti avrebbe dovuto essere il primo test scritto per qualsiasi nuovo scraper, non un'aggiunta a posteriori.

### 2026-07-08 — Tentativo 16 (completamento Agrigento, gruppo 4/4 — ultimo)
**Approccio:** ricognizione gruppo 4 (Santo Stefano Quisquina, Siculiana, Realmonte), ultimo dei 12 comuni concordati.
**Esito:**
- **Siculiana**: Halley EG standard, ma con **catena di certificato TLS incompleta lato server** (cert valido fino al 2027, emesso da Actalis, ma manca l'intermedio — `curl`/macOS lo tollerano, Python no). Non è un cert scaduto come Messina: aggiunto parametro opzionale `skip_ssl` a `halley.py::scarica_atti` (stesso pattern già usato in `jcitygov.py`), con un set `_HALLEY_SKIP_SSL` in `run_scrapers.py` per i comuni che ne hanno bisogno.
- **Realmonte**: Halley EG su IP diretto (`http://80.88.89.218/realmonte`, HTTP semplice, no HTTPS) — funziona senza modifiche.
- **Santo Stefano Quisquina**: agente terminato per rate-limit di sessione prima di finire, ma aveva già annotato (erroneamente, come Ravanusa) "serve JavaScript/Playwright" per una piattaforma Halley HSPromila. Verificato a mano: stesso URL-pattern di Sambuca di Sicilia ma slug diverso (`cmsssquisquina` non `cmssantostefanoquisquina`, trovato via web search), funziona con semplice GET, 71 atti reali.

Dato che ora **2 comuni condividono Halley HSPromila** (Sambuca di Sicilia + Santo Stefano Quisquina), generalizzato `sambucadisicilia.py` → nuovo modulo parametrico `hspromila.py` (url/codice_istat parametrici), cancellati `sambucadisicilia.py`/`test_sambucadisicilia.py` (sostituiti da `hspromila.py`/`test_hspromila.py` — sicuro perché mai arrivato su `main`).

Tutti e 4 verificati con run reale (187 atti totali). 384 test totali verdi (invariati: `test_hspromila.py` sostituisce 1:1 `test_sambucadisicilia.py`).

**🎉 Provincia di Agrigento completata**: tutti i 12 comuni concordati (i più popolosi tra i 25 mancanti) censiti e integrati, in 4 gruppi da 3. Riepilogo piattaforme: 6 URBI Cloud (Favara, Raffadali, Ravanusa, Campobello di Licata, Naro, Santa Margherita di Belice), 4 Halley EG (Menfi, Siculiana, Realmonte + i 4 iniziali della sessione precedente), 2 Halley HSPromila (Sambuca di Sicilia, Santo Stefano Quisquina), 1 WordPress (Ribera).

**Appreso:** il pattern "l'agente conclude erroneamente serve Playwright" si è ripetuto 2 volte su 12 comuni (Ravanusa, Santo Stefano Quisquina) — sempre per piattaforme che mostrano un placeholder "Attendere prego" nell'HTML statico, scambiato per rendering client-side mancante. Regola pratica: qualunque conclusione "serve Playwright" da un agente di ricognizione va verificata con una richiesta HTTP diretta (GET semplice o, per URBI, il flusso POST a 2 step) prima di accettarla.

### 2026-07-09 — Tentativo 17 (Agrigento, seconda tranche: 6 dei 13 comuni rimanenti)
**Approccio:** su richiesta di Dom ("conviene fare altro?" → "non puoi fare nulla sui 13 comuni?"), ricognizione dei restanti 13 comuni non coperti della provincia (i più piccoli, esclusi dallo scope originale dei "12 più grandi"), a 5 gruppi paralleli (haiku), poi verifica diretta di ogni esito prima di scrivere codice, come da prassi.
**Esito:**
- ✅ **Santa Elisabetta, Montallegro, Lucca Sicula**: tutti Halley HSPromila, stesso schema URL già noto (`hypersicapp.net/cms<slug>/portale/albopretorio/albopretorioconsultazione.aspx?P=400`) — nessuna modifica a `hspromila.py`, solo registrazione.
- ✅ **Joppolo Giancaxio**: Halley EG, stessa catena certificato incompleta di Siculiana → aggiunto a `_HALLEY_SKIP_SSL`.
- ✅ **San Biagio Platani**: URBI Cloud standard (`cloud.urbi.it`), nessuna modifica.
- ✅ **Villafranca Sicula**: URBI, ma su un tenant proprio (`servizionline.comune.villafrancasicula.ag.it`) anziché `cloud.urbi.it` — l'agente di ricognizione aveva trovato un URL diverso (`ur1ME002.sto`, `StwEvent=101`, pagina ad albero); verificato che il flusso standard `urbi.py` (`ur1ME001.sto`, POST `StwEvent=910001`/`9100030`) funziona comunque, stesso DB_NAME.
- ⚠️ **7 comuni rimasti scoperti**, ciascuno su una piattaforma diversa non supportata: **Caltabellotta** e **Burgio** condividono **APKAPPA** (`albo.studiok.it`) ma la tabella HTML è vuota via GET diretto e non è stata trovata alcuna chiamata AJAX nei JS della pagina — richiede ulteriore investigazione (form POST? parametro mancante?). **Burgio** e **Calamonaci** condividono **Municipium** (API REST Spring Boot su `<slug>-api.municipiumapp.it`, risponde con JSON su path errati ma il path corretto per l'elenco atti non è stato individuato). **Bivona** (Alph@soft), **Cianciana** (ComuneWeb/Kibernetes) e **Sant'Angelo Muxaro** (piattaforma custom non identificata) sono ciascuno un caso isolato. Dato il rapporto costo/beneficio (7 comuni, ~19.500 abitanti totali, cioè lo 0,4% della popolazione siciliana, quasi tutti piattaforme a un solo comune), non si è proseguito: documentato in `docs/wiki/14-censimento-albi.md` per una ripresa futura.

Verificato con run reale su DB isolato: 168 atti totali sui 6 comuni aggiunti, 0 errori. 384 test invariati (nessun modulo nuovo, solo registrazioni). Copertura: **192 comuni, 3.644.530 abitanti, 72,9%** (da 186/72,6%).

**Appreso:** quando un agente di ricognizione trova un URL "alternativo" per una piattaforma già nota (es. `ur1ME002.sto` invece di `ur1ME001.sto`), non assumere che serva un parser diverso — verificare prima se il flusso standard funziona comunque con lo stesso tenant/DB_NAME. In questo caso ha funzionato, evitando di scrivere codice inutile.

## 🔗 Dipendenze
—

## 📝 Note
Messina resta esclusa (BUG-5, FortiGate lato Comune). I run di verifica usano sempre `--db /tmp/... --no-red-flags`, mai `talia.db`.

**Migrazione codici ISTAT per `talia.db` (da applicare prima del prossimo run, previa copia di backup):**

```sql
UPDATE enti SET codice_istat = '085004' WHERE codice_istat = '085003'; -- Caltanissetta
UPDATE enti SET codice_istat = '086009' WHERE codice_istat = '086010'; -- Enna
UPDATE enti SET codice_istat = '084027' WHERE codice_istat = '084028'; -- Palma di Montechiaro
UPDATE enti SET codice_istat = '089017' WHERE codice_istat = '089018'; -- Siracusa
```

Comuni jCityGov con portale attivo ma albo vuoto via API (esclusi dal registro, da ricontrollare in futuro): Milazzo, Noto, Aragona, Racalmuto, Ribera, Gaggi, Letojanni, Condrò.
