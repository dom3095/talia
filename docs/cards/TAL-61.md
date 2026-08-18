# TAL-61 — `enti` senza provincia/popolazione: mai incrociati con l'anagrafica comuni

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🕷️ SCR
- **Priorità:** P1
- **Stato:** Done
- **Branch:** `feat/TAL-60-streamlit-modulo1` (trovato nella stessa sessione, non
  legato a TAL-60 — card separata perché è un bug indipendente)

## 🎯 Obiettivo

Popolare `enti.provincia`/`enti.popolazione` per tutti i comuni, usando l'anagrafica
già presente in repo (`data/comuni_sicilia.csv`), mai incrociata con `enti`.

## 📚 Contesto

Segnalato da Dom guardando la tab Panoramica: "davvero non sappiamo le province dei
paesi e la popolazione? [...] che autorità dovremmo avere se non sappiamo che Ragusa
sta in provincia di Ragusa?".

**Causa:** `sincronizza_enti_da_registro()` (`registry.py`) passava `provincia` solo
da `EntryRegistro.provincia` (il campo `provincia` di `data/registro_scraper.csv`,
vuoto per quasi tutte le righe — noto e già documentato nel commento di
`upsert_ente`) e non passava mai `popolazione`. `data/comuni_sicilia.csv` (rif.
anagrafico statico dei 391 comuni, con provincia+popolazione per codice ISTAT) esiste
già in repo ma era usato solo dalla tab Mappa — mai incrociato con `enti`.

**Impatto misurato su `talia.db` reale prima del fix:** 307/307 enti (100%) con
popolazione NULL, 192/307 (63%) con provincia NULL — inclusi capoluoghi come Ragusa.

## ✅ Task

- [x] `_carica_comuni_sicilia()` in `registry.py`: legge `data/comuni_sicilia.csv`,
  ritorna `{codice_istat: (provincia, popolazione)}`.
- [x] `sincronizza_enti_da_registro()`: usa il riferimento come fallback — la
  provincia del registro resta prioritaria se presente (`entry.provincia or
  provincia_rif`); `upsert_ente` fa comunque `COALESCE` col valore già in DB, quindi
  niente di più specifico impostato altrove viene perso.
- [x] Nuovo parametro opzionale `comuni_sicilia_path` (stesso pattern di
  `carica_registro(percorso=None)`) per iniettare un CSV di test invece di dipendere
  dal riferimento reale a 391 righe nei test.
- [x] Backfill eseguito su `talia.db` reale (backup preso prima:
  `talia.db.bak-pre-backfill-provincia-pop-20260816`): 0/307 senza provincia (era
  192), 1/307 senza popolazione (era 307 — il residuo è Messina, codice ISTAT
  083053, riga di registro nota come obsoleta/bloccata, non legata a questo fix).

## 🧪 Criteri di accettazione

- [x] `enti.provincia`/`enti.popolazione` popolate per i comuni presenti in
  `data/comuni_sicilia.csv`.
- [x] Un valore più specifico già impostato (es. da uno scraper monocomune) non viene
  mai sovrascritto dal riferimento.
- [x] 3 nuovi test (`tests/test_db.py`): completamento, priorità del registro,
  nessun crash se il comune non è nel riferimento.

## 📝 Note

**Non fatto, deliberatamente fuori scope:** il residuo (Messina, 083053) è una riga
di registro obsoleta segnalata in una sessione precedente (HANDOFF 2026-07-26: codice
ISTAT sbagliato, corretto a 083048 nel registro corrente) — probabilmente una riga
`enti` mai ripulita dopo quella correzione. Non toccata qui: un solo comune, già
`bloccato`, non legato a questo bug.
