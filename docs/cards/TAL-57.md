# TAL-57 — Modulo 1: pulizia minore (check3, RAG, graduatoria)

- **Epica:** E1 — Motore + Modulo 1
- **Ruolo:** 🔤 NLP
- **Priorità:** P3
- **Stato:** Review
- **Branch:** `feat/TAL-53-nome-ruolo-graduatoria` (proseguito sullo stesso branch)

## 🎯 Obiettivo
Findings minori del `/code-review` multi-agente (2026-08-08) su codice del Modulo 1,
in parte introdotto nella stessa sessione (TAL-53/TAL-54): un rischio di correttezza in
`check3_motivazione.py`, una duplicazione di logica di troncamento citazioni, un costo
evitabile in `IndiceCorpus.cerca()`, e due costanti gemelle in `graduatoria.py`.

## 📋 Spec

### Comportamento
1. **`_RE_MOTIVAZIONE` (correttezza)**: il trigger di fine motivazione
   ("determina/decreta/dispone") ora richiede che la parola sia sola sulla riga
   (`\s*\n` subito dopo), non solo preceduta da un a-capo. Senza questo vincolo, la
   stessa parola comparsa a inizio riga *dentro* la motivazione (plausibile con testo
   estratto da PDF, dove gli a-capo seguono il layout visivo) troncava la motivazione
   al punto sbagliato — riprodotto con un caso concreto prima del fix.
2. **`_offset_fine_troncato()` (nuovo, condiviso)**: estrae l'aritmetica
   `offset_inizio + min(lunghezza_testo, limite)` duplicata tra `_cita_passaggio`
   (passaggi del corpus, limite 220) e la citazione della motivazione in
   `valuta_motivazione` (limite 200). Stesso comportamento, un solo punto da mantenere.
3. **`IndiceCorpus.cerca()` (efficienza)**: frequenze termine-per-documento e lunghezza
   documento ora precomputate una volta in `__init__`, non ricostruite da zero ad ogni
   chiamata di `cerca()`. Punteggi BM25 identici (verificato: stessi risultati su query
   reali contro il corpus vero, non solo sui test con stub).
4. **`graduatoria.py`**: `_FINESTRA_DATA_DOPO_APPROVATA`/`_FINESTRA_DATA_PRIMA_GRADUATORIA`
   (entrambe 80) unificate in una sola costante `_FINESTRA_DATA`.

### Deliberatamente non fatto
- **`check6_firmatari.py`: matching firmatari (`coppie`) vs `_ruolo_di()` non
  unificati.** I due loop iterano su tipi diversi (`Entita` con un set di indici già
  presi, `Attore` senza) con condizioni di guardia diverse: un helper davvero generico
  richiederebbe funzioni di ordine superiore per astrarre su tipo/guardia per soli 2
  chiamanti — esattamente l'astrazione prematura che CLAUDE.md chiede di evitare ("tre
  righe simili sono meglio di un'astrazione prematura"). La predicate function
  (`_stesso_firmatario`) è già condivisa; solo il loop di iterazione resta duplicato,
  a basso rischio.
- **`_cerca_passaggi_rag()` (TAL-54): non ridotto il numero di query BM25 per
  fascicolo.** Il finding di efficienza lo segnalava come "una scansione per ogni check
  flaggato"; ridurlo a una sola query combinata è esattamente l'approccio già provato e
  scartato in TAL-54 (Tentativo 1) perché diluiva il segnale dei check con pochi
  riferimenti (es. GDPR) — riunificarlo qui avrebbe reintrodotto il bug appena corretto.
  Il fix #3 sopra (precompute freq/dl) riduce comunque il costo reale di ogni singola
  scansione, che era la parte davvero economizzabile senza rischio.

## ❓ Domande aperte
_Nessuna._

## 📚 Contesto
Findings del `/code-review` (`main...HEAD`), angoli A (line-by-line), E (simplification),
F (efficiency).

## ✅ Task
- [x] Fix `_RE_MOTIVAZIONE` + 2 nuovi test (troncamento corretto, non-troncamento sul
      caso limite)
- [x] `_offset_fine_troncato()` condivisa, usata da entrambi i call site
- [x] `IndiceCorpus.cerca()`: freq/dl precomputate in `__init__`
- [x] `graduatoria.py`: costanti unificate

## 🧪 Criteri di accettazione
- [x] Nessuna regressione sui test esistenti (check3, rag, graduatoria)
- [x] Verificato anche sul corpus reale (non solo sugli stub dei test) che il refactor
      di `IndiceCorpus.cerca()` non cambia i risultati
- [x] Test passano (`pytest`)
- [x] DoD rispettata (vedi CLAUDE.md)

## 🔗 Dipendenze
TAL-53, TAL-54 (stesso codice).

## 📝 Note
Vedi sezione "Deliberatamente non fatto" sopra per i due findings del code-review
lasciati aperti per scelta, con motivazione.
