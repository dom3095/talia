# TAL-65 — `estrai_cig()`: CIG padre/derivato scambiati o persi, colonna `cig_padre`

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🕷️ SCR
- **Priorità:** P1 (impatta `catena.py`, usato da tutti gli scraper)
- **Stato:** Done
- **Branch:** `feat/TAL-60-streamlit-modulo1`

## 🎯 Obiettivo

Correggere l'estrazione del CIG quando un atto cita sia un "CIG padre"
(accordo quadro/convenzione) sia un "CIG derivato" (l'adesione/chiamata
specifica) — pattern reale e frequente (SMART CIG, convenzioni CONSIP).
Aggiungere una colonna `cig_padre` per non perdere l'informazione.

## 📚 Contesto

Emerso durante [TAL-64](TAL-64.md) (deduplicazione atti): Dom ha notato che
"i CIG possono avere dei CIG padre e figli". Verifica su `talia.db` reale:
578 atti contenevano pattern "CIG padre"/"CIG derivato"/"CIG originario" nel
testo, e la funzione condivisa `estrai_cig()` (usata da **14 scraper su 14**)
sbagliava quasi sempre — 127 falsi positivi (`cig` valorizzato con la parola
`"ORIGINARIO"` invece di un codice), 368 falsi negativi (`cig` NULL nonostante
il testo contenesse due codici veri). La stessa regex, con la stessa falla,
era copiata in altri due punti: `engine/entita.py::estrai_cig()` (Modulo 1) e
`engine/catena.py::estrai_riferimenti()` (collegamento catene).

Causa: "ORIGINARIO" è lungo esattamente 10 lettere — un fallback generico
`[A-Z0-9]{10}` dopo la parola "CIG" lo scambiava per un codice vero;
"PADRE"/"DERIVATO"/"MADRE" invece non sono 10 caratteri e rompevano il match,
lasciando `cig` a `NULL`.

Probabile causa (non confermata, da riprendere) della segnalazione "le
catene hanno dei problemi": `catena.py::collega_per_cig` raggruppa per CIG —
più atti con `cig='ORIGINARIO'` (garbage condiviso) verrebbero uniti in una
catena fittizia.

## 📋 Fix applicato

- **`engine/entita.py`**: tre regex distinte (`_RE_CIG_PADRE`,
  `_RE_CIG_DERIVATO`, `_RE_CIG_PLAIN` con lookahead negativo sulle etichette)
  invece di una sola con etichetta opzionale — evita che il fallback possa
  "inghiottire" la parola etichetta come se fosse il codice. Nuove funzioni
  pubbliche `trova_cig()` (tutti i match, con flag `e_padre`) e
  `estrai_cig_gerarchia()` (`(cig_proprio, cig_padre)`). `estrai_cig()`
  esistente (Modulo 1, ritorna `list[Entita]`) ora trova anche i CIG che
  prima si perdeva.
- **`modulo2_scraping/utils.py`**: `estrai_cig()` diventa un thin wrapper su
  `engine.entita.estrai_cig_gerarchia()` (stessa firma, backward compatible —
  nessuna modifica richiesta ai 14 scraper per il solo bugfix). Nuova
  `estrai_cig_padre()`.
- **`engine/catena.py::estrai_riferimenti()`**: usa `trova_cig()` e scarta
  esplicitamente i match `e_padre=True` — un CIG padre è condiviso da molte
  adesioni distinte, usarlo come riferimento incrociato collegherebbe atti
  non correlati.
- **Schema**: nuova colonna `atti.cig_padre` (+ indice), migrazione lazy
  `_estendi_atti()` (stesso pattern di `_estendi_enti`) per i DB esistenti.
  `AttoMetadato.cig_padre` + `inserisci_atto()` aggiornati.
- **Tutti e 14 gli scraper** (`fonti/*.py`) ora passano anche
  `cig_padre=estrai_cig_padre(oggetto)` accanto a `cig=estrai_cig(oggetto)`.
- 12 nuovi test (`test_entita.py`, `test_scraping_utils.py` nuovo,
  `test_catena.py`, `test_db.py`): caso padre+derivato distinti, caso
  "ORIGINARIO" non scambiato, caso padre senza derivato, persistenza in DB,
  esclusione dai riferimenti incrociati di `catena.py`.

## 🔬 Tentativi

### 2026-08-18 — Backfill su `talia.db` reale

**Approccio:** ricalcolato `(cig, cig_padre)` da `atti.oggetto` (già in DB,
nessuna nuova richiesta HTTP) con la regex corretta, su tutte le 132.317
righe con oggetto non nullo. Backup preso prima
(`talia.db.bak-pre-fix-cig-padre-tal65-20260818`).

**Esito:** ✅
**Appreso:** primo giro, 3585 righe corrette (3571 con `cig` sbagliato,
189 con `cig_padre` popolato per la prima volta) — ma 3 righe residue
mostravano ancora `cig='ORIGINARIO'`: pattern non previsto,
`"CIG. ORIGINARIO:[7990085AB8]"` (codice tra parentesi quadre, "CIG."
abbreviato con punto prima dell'etichetta). Corretta la classe di separatori
per includere `[` e `.` prima dell'etichetta; rieseguito il backfill (script
idempotente, sicuro rilanciarlo), altre 235 righe corrette. **Residuo
garbage finale: 0/38.560 atti con CIG**. Un caso limite resta noto e
documentato ma non risolto: `"CIG. ORIGINARIO CONVENZIONE: NNNNNNNNNN"` (una
parola aggiuntiva tra etichetta e codice) non estrae il padre — fallisce in
modo sicuro (`None`), non produce garbage.

## 📝 Note

Non ancora verificato l'impatto reale su `catena.py` (quante catene
cambiano/si correggono con `cig` ora pulito) — collegato alla segnalazione
di Dom "le catene hanno dei problemi", ancora da approfondire specificamente.
