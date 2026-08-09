# TAL-55 — Scraper: fallimenti silenziosi in serviziolinealbo.py

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🕷️ SCR
- **Priorità:** P3
- **Stato:** Review
- **Branch:** `feat/TAL-53-nome-ruolo-graduatoria` (proseguito sullo stesso branch su richiesta
  esplicita, non ne apre uno nuovo — findings emersi da `/code-review` sull'intero branch)

## 🎯 Obiettivo
Findings del `/code-review` multi-agente (2026-08-08) su `serviziolinealbo.py`
(scraper Pachino/Barrafranca, TAL-49 sweep del 2026-08-06): due punti in cui uno o più
atti vengono scartati senza alcun log, in violazione della convenzione esplicita in
CLAUDE.md § "Fragilità comuni" ("Sempre aggiungere un log quando `len(atti) == 0`",
estesa qui al caso di scarto per-atto), e manca il test "pagina corrotta" richiesto
da CLAUDE.md § "Come aggiungere uno scraper", punto 5.

## 📋 Spec

### Comportamento
- `_parse_html`: quando un permalink viene trovato ma l'anchor `#collapseNNNN_YYYY`
  corrispondente è assente, o è assente lo `<span>` di dettaglio, l'atto viene scartato
  **con un `logger.warning`** che riporta comune/numero/anno — invece di un `continue`
  silenzioso.
- `scarica_atti`: se il totale di atti estratti su tutte le pagine è 0, `logger.warning`
  (stesso messaggio/pattern già usato da `nicosia.py`).
- Nessun cambio di comportamento sui casi già gestiti correttamente (dedup, tipo con/senza
  riferimento settoriale): solo aggiunta di log sui rami di scarto esistenti.

### Casi limite
- Pagina con alcuni atti validi e uno scartato per anchor mancante → gli atti validi
  restano estratti normalmente, solo quello scartato produce un WARNING (non un errore
  bloccante).

## ❓ Domande aperte
_Nessuna._

## 📚 Contesto
Findings del `/code-review` (`main...HEAD`) lanciato dopo TAL-53/TAL-54, angoli A
(line-by-line) e H (convenzioni CLAUDE.md). Non tocca `agrigento.py` (stessa piattaforma
ma file distinto, non in scope qui).

## ✅ Task
- [x] `logger.warning` su atto scartato per anchor/span mancante (`_parse_html`)
- [x] `logger.warning` su 0 atti totali (`scarica_atti`), stesso pattern di `nicosia.py`
- [x] Test "pagina corrotta": anchor mancante → lista vuota, senza crash
- [x] Test che verifica il WARNING viene effettivamente loggato (`caplog`)

## 🧪 Criteri di accettazione
- [x] Nessuna regressione sui test esistenti di `serviziolinealbo.py`
- [x] Test passano (`pytest`)
- [x] DoD rispettata (vedi CLAUDE.md)

## 🔗 Dipendenze
Nessuna. Correlato a TAL-56 (dove il retry di `hspromila.py`, altro finding dello stesso
code-review, viene sistemato consolidando la logica in un helper condiviso).

## 📝 Note
Il finding "atto scartato per anchor mancante" (Angle A) è rimasto senza `verdict`
CONFIRMED nel report `/code-review` (marcato PLAUSIBLE, nessuna riproduzione diretta in
quella fase): qui è stato riprodotto concretamente con una fixture HTML dedicata prima
di scrivere il fix.
