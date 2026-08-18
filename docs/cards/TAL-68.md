# TAL-68 — Due scraper rotti in silenzio: `caccamo` (URBI) e `sangiuseppejato` (SSL)

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🕷️ SCR
- **Priorità:** P1
- **Stato:** Review
- **Branch:** `feat/TAL-66-run-giornaliero-aggregati`

## 🎯 Obiettivo

Riparare i due scraper che il primo riepilogo automatico di
[TAL-66](TAL-66.md) ha fatto emergere.

## 📚 Contesto

Non sono stati cercati: sono comparsi da soli nel primo `report_run.py`
eseguito dopo un run vero. È esattamente ciò per cui il riepilogo è stato
scritto — in particolare la categoria "muto", che nessun exit code
intercetterebbe.

| Scraper | Stato nel report | Da quando |
|---------|------------------|-----------|
| `caccamo` | 🔇 muto (0 atti, nessun errore) | almeno **2026-07-14**, 5 run consecutivi |
| `sangiuseppejato` | ❌ fallito (`CERTIFICATE_VERIFY_FAILED`) | rilevato il 2026-08-18 |

`caccamo` è il caso interessante: 5 run consecutivi con `n_trovati=0`,
`n_inseriti=0` e **mai un errore**. Senza la distinzione fallito/muto sarebbe
rimasto invisibile a tempo indeterminato.

## 📋 Diagnosi e fix

### `sangiuseppejato` — catena di certificato incompleta

`CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`.
Verificato: con `verify_mode=CERT_NONE` la stessa URL risponde HTTP 200. È lo
stesso pattern già noto e già gestito per Siculiana, Joppolo Giancaxio e
Mirabella Imbaccari — certificato valido, catena servita incompleta.

**Fix:** `skip_ssl=true` nel registro. Verificato con `halley.scarica_atti`
reale: **14 atti** (prima: eccezione).

### `caccamo` — il tenant pretende una `Tipologia` esplicita

Il portale risponde **HTTP 200** con un avviso e una tabella vuota:

> *Attenzione: per procedere occorre selezionare la tipologia.*

`_FORM_RICERCA` invia `Tipologia=""`, che per ogni altro tenant URBI significa
"Tutte" (ed è anche l'etichetta della prima `<option>` di Caccamo). Questo
tenant lo rifiuta. Verificato per confronto: con lo stesso codice Raffadali
restituisce 10 atti e Caccamo 0; con `Tipologia=44` Caccamo ne restituisce 7.

**Fix in `urbi.py`:** se la ricerca normale incontra quell'avviso, si
scoprono le tipologie dalla `<select>` della pagina di ricerca
(`estrai_tipologie()`) e si ripete una ricerca per ciascuna.

Due scelte deliberate:

1. **La condizione è il messaggio del portale, non "zero atti".** Legarla a
   zero atti farebbe partire 26 ricerche inutili ad ogni run su un albo
   genuinamente vuoto.
2. **Nessun cambiamento per i tenant che già funzionano**: il fallback non
   scatta mai per loro. Verificato dal vivo dopo il fix — Raffadali 20 atti,
   Favara 19, nessun fallback nei log.

**Risultato:** Caccamo passa da **0 a 181 atti** (con `max_pagine=3`).

## 🔬 Tentativi

### 2026-08-18 — Tentativo 1
**Approccio:** fallback per tipologia in `urbi.py`, con reset del contatore
stop-on-known al cambio di tipologia lato runner.
**Esito:** ❌ insufficiente — **trovato dal test, non dal run**.
**Appreso:** azzerare il contatore *al confine* non basta, perché lo stop
scatta **prima** di arrivarci: `break` usciva dall'intera scansione, quindi
la prima tipologia tutta già nota avrebbe chiuso anche tutte le successive.
Dal secondo run in poi lo scraper sarebbe tornato muto — in modo più subdolo
di prima, perché stavolta con atti in DB a dare l'impressione che funzionasse.
Corretto distinguendo i due casi in `_run_urbi_comune`: `break` per i tenant
normali (una sola scansione), `salta_tipologia` per quelli con tipologie, che
riprende dalla successiva. 2 test di regressione dedicati, uno per ciascun
comportamento.

## ✅ Task

- [x] `skip_ssl=true` per `sangiuseppejato` nel registro (verificato: 14 atti)
- [x] `estrai_tipologie()` + fallback in `urbi.py`
- [x] `_run_urbi_comune`: stop-on-known per tipologia
- [x] 5 test nuovi (3 in `tests/fonti/test_urbi.py`, 2 in
      `tests/test_run_scrapers_registry.py`) — **706 verdi** (erano 699)
- [x] Nessuna regressione sui tenant URBI funzionanti (verificato dal vivo)
- [ ] Run dei due scraper sul DB reale — in corso alla stesura della card

## 📎 Note per il futuro

Gli altri 8 tenant URBI (`campobellodilicata`, `naro`, `ravanusa`,
`sanbiagioplatani`, `santamargheritadibelice`, `villafrancasicula`, oltre a
Favara e Raffadali) non mostrano il problema oggi, ma il fallback ora li
copre automaticamente se un domani lo mostrassero: la scoperta è a runtime,
non una configurazione per tenant.
