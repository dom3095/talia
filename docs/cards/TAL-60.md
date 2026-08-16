# TAL-60 — UI Streamlit per il Modulo 1 (tab "Analisi fascicolo")

- **Epica:** E1 — Motore + Modulo 1
- **Ruolo:** 📊 FE
- **Priorità:** P1
- **Stato:** Review
- **Branch:** `feat/TAL-60-streamlit-modulo1`

## 🎯 Obiettivo

Dare al Modulo 1 un'interfaccia oltre la CLI (`talia analizza`): un tab nella dashboard
Streamlit già esistente dove caricare un fascicolo (PDF/txt) e vedere il report
verde/giallo/rosso senza terminale.

## 📚 Contesto

Emerso discutendo con Dom cosa manca prima di un MVP/PoC dimostrabile: il motore dei 7
check del Modulo 1 è sostanzialmente completo (solo il check 4, statistico e non
bloccante, resta da fare), ma resta utilizzabile solo da terminale.

## ❓ Domande aperte (risolte in conversazione, non nella card)

- [x] Ambito: solo locale, non pensata per hosting pubblico (niente policy di
  ritenzione/anonimizzazione da progettare ora — se in futuro si vuole ospitarla
  pubblicamente, va riconsiderato: chiunque potrebbe caricare un PDF con dati di terzi).
- [x] Collocazione: nuovo tab nella dashboard Modulo 3 esistente (`modulo3_dashboard/app.py`),
  non un'app separata — riusa Streamlit già presente come dipendenza.

## 📋 Spec

- Nuovo tab "📁 Analisi fascicolo", primo nell'elenco (Modulo 1 = priorità 1).
- Catena di box "allega file (`type=["pdf", "txt"]`) + descrizione/osservazioni" — un
  documento alla volta, il box successivo compare solo dopo l'upload del precedente
  (Tentativo 2). La descrizione è opzionale, concorre alla classificazione del ruolo
  (`classifica_ruolo`) e compare nel report accanto al documento.
- Checkbox opzionale per il check 3 (LLM, richiede Ollama locale) — disattivato di default,
  stessa cautela della CLI (`--llm`).
- Riusa il motore esistente (`analizza_testi`), non lo reimplementa.
- **Nessuna persistenza**: i file caricati vivono in una `tempfile.TemporaryDirectory()`
  cancellata subito dopo l'estrazione del testo. Nessuna scrittura sul DB.
- Esito renderizzato con gli stessi componenti di stile delle altre tab (`st.expander`,
  `st.metric`, emoji di `Stato`), più un bottone per scaricare lo stesso HTML statico
  prodotto dalla CLI (`report.to_html()`).

## ✅ Task

- [x] `_analizza_file_caricati()` in `modulo3_dashboard/app.py`: nome+bytes → `Report`,
  isolata da `UploadedFile`/widget Streamlit per essere testabile senza `AppTest`.
- [x] `_mostra_analisi_fascicolo()` + `_mostra_report_fascicolo()`: upload, checkbox LLM,
  bottone, rendering esiti, download HTML.
- [x] `descrivi_citazione()` resa pubblica in `report.py` (era `_descr_citazione`) per
  essere riusata dalla dashboard senza duplicare il formato citazione.
- [x] Wiring in `main()`: nuovo tab, `st.session_state` per sopravvivere ai rerun
  (altrimenti il report sparisce al primo click su un expander).
- [x] `_raccogli_box_fascicolo()`: catena di box dinamica (Tentativo 2).
- [x] `descrizione` filtrata fino a `AttoAnalizzato`/`AttoMeta`/`Report` (`engine/fascicolo.py`,
  `modulo1_fascicolo/analisi.py`, `report.py`) e usata da `punteggi_ruolo()`/
  `classifica_ruolo()` per la classificazione del ruolo, non solo mostrata.

## 🔬 Tentativi

### 2026-08-16 — Tentativo 1
**Approccio:** import relativi (`from ..engine.models import ...`) dentro le nuove funzioni,
come nel resto del file.
**Esito:** ❌
**Appreso:** `streamlit run src/talia/modulo3_dashboard/app.py` (il modo documentato di
avviare l'app, vedi docstring del modulo) esegue il file come script standalone, senza
contesto di pacchetto — gli import relativi falliscono a runtime
(`attempted relative import with no known parent package`). I test pytest non lo
intercettavano: importano il modulo come parte del pacchetto `talia`, dove gli import
relativi funzionano normalmente. Scoperto solo con un run live via
`streamlit.testing.v1.AppTest.from_file(...)` (che replica l'avvio reale, a differenza di
`AppTest.from_string`/import diretto), non dai test unitari. Corretto passando ad import
assoluti (`from talia.engine...`) in tutte le funzioni nuove. Verificato di nuovo con lo
stesso `AppTest.from_file` + upload simulato (`file_uploader.set_value(...)`) + click sul
bottone: 0 eccezioni, metriche/expander/download button tutti presenti e coerenti.

### 2026-08-16 — Tentativo 2 (dopo aver provato il tab dal vivo)
**Approccio:** Dom ha provato il tab e ha chiesto di sostituire il singolo
`st.file_uploader(accept_multiple_files=True)` con una catena di box "allega file +
descrizione" (un documento alla volta, il box successivo compare solo dopo l'upload del
precedente) — per poter annotare ogni documento con le proprie osservazioni.
**Esito:** ✅
**Appreso:** la descrizione non doveva restare solo testo decorativo: concorre ora ai
punteggi di `classifica_ruolo()`/`punteggi_ruolo()` (stesse regex del testo dell'atto),
così un allegato con poco testo proprio (es. solo tabelle numeriche) che da solo
risulterebbe SCONOSCIUTO viene comunque agganciato al ruolo giusto se l'utente scrive
"revoca in autotutela" o simili. La catena di box si regge su `st.session_state`: le
chiavi dei widget sono stabili per indice (`tal60_file_{i}`/`tal60_desc_{i}`), Streamlit
conserva i valori tra un rerun e l'altro, quindi non serve un contatore esplicito né un
bottone "+" — si mostrano tanti box quanti sono i file già caricati, più uno vuoto.
Verificato dal vivo con `AppTest`: box 1→2→3 compaiono in sequenza dopo ogni upload,
descrizioni finiscono sull'atto giusto nel report, nessuna eccezione.

## 🧪 Criteri di accettazione

- [x] Analisi di un fascicolo reale (sample `fascicolo_coerente`) tramite la tab, via
  `AppTest` con upload simulato: 0 eccezioni, esiti coerenti con quelli della CLI sullo
  stesso fascicolo (`tests/test_cli.py`).
- [x] Nessun file caricato persiste su disco oltre la richiesta (directory temporanea).
- [x] Disclaimer visibile nel report renderizzato.
- [x] Test automatici sulla logica pura (`_analizza_file_caricati`), non solo smoke import.

## 📝 Note

**Riconcilia la decisione di TAL-10** ("niente Streamlit per il Modulo 1: zero deps;
Streamlit resta per il Modulo 3", 12/06/2026): quella decisione riguardava il **formato
del report** (rimasto HTML statico + JSON, zero dipendenze, adatto a essere pubblicato
accanto agli atti scrapati). Questa card non lo cambia — aggiunge solo un front-end
interattivo *opzionale* per chi non usa il terminale, che internamente produce lo stesso
report e lo stesso HTML scaricabile. Dato che Streamlit è già una dipendenza del Modulo 3,
il ragionamento "zero deps" del 12/06 non si applica qui.

**Bug collaterale trovato e corretto nello stesso file** (non introdotto in questa
sessione): `main()` renderizzava le tab Statistiche e Mappa due volte ciascuna (blocco
`with tab_statistiche` / `with tab_mappa` duplicato subito dopo l'originale) — doppie
query DB ad ogni rerun. Rimossa la duplicazione.

**Non fatto:** nessuna gestione di un `talia.db` assente specifica per questa tab — la
tab eredita lo stesso gate esistente in `main()` (serve comunque un DB valido per
raggiungere le tab, anche se questa non lo legge). Non ristrutturato l'avvio dell'app per
rimuovere questo vincolo: fuori scope, la dashboard lo richiedeva già prima.
