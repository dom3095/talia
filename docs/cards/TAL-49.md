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
