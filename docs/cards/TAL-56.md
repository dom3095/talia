# TAL-56 — Scraper: consolidare _strip()/tabella tipi + retry hspromila

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🕷️ SCR
- **Priorità:** P3
- **Stato:** Review
- **Branch:** `feat/TAL-53-nome-ruolo-graduatoria` (proseguito sullo stesso branch)

## 🎯 Obiettivo
Findings del `/code-review` multi-agente (2026-08-08) su duplicazione codice tra scraper
`modulo2_scraping/fonti/*.py`:
1. `_strip()` (rimozione tag HTML + unescape + collasso spazi) duplicata identica in
   5 file (`halley.py`, `hspromila.py`, `jcitygov.py`, `nicosia.py`, `serviziolinealbo.py`).
2. La tabella `_TIPI` (categoria/intestazione → tipo atto) duplicata in 3 file
   (`hspromila.py`, `nicosia.py`, `serviziolinealbo.py`), **già divergente**: l'ultima
   voce era `("avviso", "avviso")` in `nicosia.py` contro `("avvis", "avviso")` nelle
   altre due — `nicosia.py` non intercettava varianti come "avvisi" (plurale).
3. `hspromila.py` cattura solo `TimeoutError` nel retry, mentre `halley.py` (stesso
   pattern, stesso motivo dichiarato: host condiviso a volte sovraccarico) cattura anche
   `urllib.error.URLError` — drift già presente tra le due copie.

## 📋 Spec

### Interfaccia
```python
# modulo2_scraping/utils.py (nuovo)
def strip_html(html: str) -> str: ...
TIPI_ATTO_DEFAULT: tuple[tuple[str, str], ...]
```

### Comportamento
- `strip_html()` estratta in `utils.py`, importata come `_strip` (alias, per non
  toccare i call site) da `halley.py`, `hspromila.py`, `nicosia.py`,
  `serviziolinealbo.py`. Comportamento identico, zero cambi di logica.
- `TIPI_ATTO_DEFAULT` estratta in `utils.py` con la versione "corretta" dell'ultima voce
  (`"avvis"`, non `"avviso"`); `hspromila.py`/`nicosia.py`/`serviziolinealbo.py` ora
  puntano alla stessa costante (`_TIPI = TIPI_ATTO_DEFAULT`) — il fix del drift su
  `nicosia.py` è un effetto collaterale della deduplicazione, non un intervento separato.
- `hspromila.py`: retry allargato a `(TimeoutError, urllib.error.URLError)`, pari a
  `halley.py`.

### Casi limite / scelte di scope
- **`jcitygov.py` non toccato**: la sua copia di `_strip()`/`_fetch()` è preesistente e
  non fa parte del diff di questo branch (confermato dall'angolo "reuse" del
  code-review); è uno scraper già in produzione (`✅ OK`, nel default run) — cambiarlo
  qui sarebbe scope creep su codice non segnalato come nuovo problema, con rischio di
  regressione non giustificato dal beneficio.
- **Non unificato l'intero loop di retry-with-backoff** in un helper condiviso: le tre
  copie (`jcitygov._fetch`, `halley.scarica_atti`, `hspromila.scarica_atti`) differiscono
  per dettagli non banali (opener iniettabile per i test in jcitygov, contesto SSL
  opzionale in halley, nessuno dei due in hspromila) — unificarle avrebbe richiesto
  toccare la logica di fetch di tre scraper già verificati in produzione per un beneficio
  di deduplicazione modesto. Solo allargato l'except di hspromila (fix mirato, a basso
  rischio) invece di un refactor completo.
- **`serviziolinealbo.py` non consolidato con `agrigento.py`**: stessa logica di scope
  del punto sopra, già documentata nel docstring del modulo stesso — non affrontata qui
  (vedi anche nota del `/code-review`).

## ❓ Domande aperte
_Nessuna._

## 📚 Contesto
Findings del `/code-review` (`main...HEAD`), angoli D (reuse), E (simplification),
G (altitude).

## ✅ Task
- [x] `strip_html()` in `utils.py`, usata da 4 scraper (non `jcitygov.py`, vedi Note)
- [x] `TIPI_ATTO_DEFAULT` in `utils.py`, usata da 3 scraper — fix del drift avviso/avvis
- [x] `hspromila.py`: retry allargato a `(TimeoutError, urllib.error.URLError)`

## 🧪 Criteri di accettazione
- [x] Nessuna regressione sui test esistenti (`tests/fonti/`, `tests/test_jcitygov.py`)
- [x] Test passano (`pytest`)
- [x] DoD rispettata (vedi CLAUDE.md)

## 🔗 Dipendenze
Correlato a TAL-55 (stesso code-review, stesso file `serviziolinealbo.py`).

## 📝 Note
Due findings del code-review restano **non affrontati per scelta esplicita** (vedi
"Casi limite" sopra): l'unificazione completa del retry-with-backoff su 3 scraper e il
consolidamento `serviziolinealbo.py`/`agrigento.py`. Entrambi sono decisioni di
architettura (CLAUDE.md: "su architettura, proporre non decidere unilateralmente") con
rischio concreto su scraper già in produzione — proposti qui, non eseguiti.
