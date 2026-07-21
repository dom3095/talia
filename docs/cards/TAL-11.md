# TAL-11 — Check 3: qualità motivazione (LLM)

- **Epica:** E1 — Motore + Modulo 1
- **Ruolo:** 🔤 NLP
- **Priorità:** P2
- **Stato:** Review
- **Branch:** `feat/TAL-11-check3-motivazione`

## 🎯 Obiettivo
Check 3: valutare la qualità della motivazione (specifica vs boilerplate). **Unico check che usa LLM**,
e solo sui documenti già flaggati.

## 📋 Spec

### Interfaccia
```python
def check_motivazione(testo_atto: str, contesto: CheckContext) -> CheckResult:
    # CheckContext: atti già flaggati da check precedenti
    # CheckResult: esito ("verde"|"giallo"|"rosso"), citazione, spiegazione
```

### Comportamento
Analizza la sezione "motivazione" di un atto **già flaggato** da almeno un check deterministico.
Valuta densità e specificità della motivazione rispetto ai requisiti giurisprudenziali (interesse pubblico concreto e attuale, comparazione con affidamenti dei privati). Usa LLM open locale con RAG sul corpus normativo. Restituisce sempre una citazione testuale del passaggio valutato.

### Casi limite
- Se la sezione motivazione è assente o < 50 caratteri → 🔴 automatico senza chiamata LLM
- Se l'atto non è flaggato da check precedenti → skip (non chiamare il check)
- Se il modello LLM non è disponibile → eccezione esplicita, nessun fallback silenzioso

## ❓ Domande aperte
- [x] Quale modello LLM locale di riferimento? → **qwen3:4b via Ollama** (già installato in
      locale, 2.5GB, zero setup aggiuntivo, gratuito).
- [x] Soglia minima di lunghezza motivazione per considerarla "robusta"? → **nessuna soglia
      numerica oltre ai <50 caratteri = 🔴 automatico**: sopra quella soglia il giudizio
      verde/giallo/rosso è demandato interamente al LLM (densità/specificità), coerente col
      principio "determinismo prima" applicato qui come scelta esplicita di delega.
- [x] Il RAG deve coprire solo le norme citate nell'atto o tutto il corpus? → **intero corpus**,
      top-k (5) via retrieval BM25: anche norme/giurisprudenza non esplicitamente citate
      nell'atto possono emergere come pertinenti.

## 📚 Contesto
[wiki/04](../wiki/04-checklist-modulo1.md) check 3. Filtro a imbuto: regole prima, LLM eccezione ([wiki/03](../wiki/03-stack.md)).

## ✅ Task
- [x] Isolare la sezione "motivazione" dell'atto
- [x] Prompt che valuta: densità, specificità, requisiti giurisprudenziali (interesse pubblico concreto e attuale, comparazione con affidamenti dei privati)
- [x] LLM **open locale** (qwen3:4b via Ollama) — mai a pagamento di default
- [x] RAG sul corpus normativo per ancorare il giudizio ([wiki/06](../wiki/06-corpus-normativo.md))
- [x] Esito 🟢 (motivazione robusta) / 🟡 / 🔴 (generica, mero "ripristino di legalità")
- [x] Output con citazione del passaggio valutato

## 🧪 Criteri di accettazione
- [x] Eseguito **solo** su atti già flaggati da altri check (non su tutti)
- [x] 🔴 su motivazione boilerplate di poche righe (caso campione)
- [x] Output sempre con citazione testuale, mai verdetto secco
- [x] Funziona con modello locale, nessuna API a pagamento richiesta
- [x] Test con motivazione robusta vs generica

## 🔗 Dipendenze
TAL-3, TAL-6, corpus normativo (TAL/E... per RAG).

## 🏗️ Implementazione

Tre moduli nuovi, nessuna nuova dipendenza pip (coerente con "budget ≈ 0" anche sul lato
librerie):

- **`src/talia/engine/rag.py`** — `IndiceCorpus`: retrieval BM25 in puro stdlib (niente
  embedding/vector store: il corpus è piccolo, ~16 file curati, un retrieval lessicale è
  sufficiente). Chunking per paragrafo, `cerca(query, k)` ritorna i passaggi più pertinenti
  con provenienza (`Passaggio.fonte`) per tracciabilità.
- **`src/talia/engine/llm.py`** — client minimale per Ollama (`genera(prompt, modello, opener)`
  via `urllib`, nessuna dipendenza pip). Solleva `LLMNonDisponibile` esplicitamente se il
  servizio non risponde: **nessun fallback silenzioso** (spec).
- **`src/talia/engine/checklist/check3_motivazione.py`** — `valuta_motivazione(contesto,
  esiti_precedenti, indice=None)`. A differenza degli altri check **non è registrato** nel
  registry automatico di `checklist/base.py`: richiede sia gli esiti dei check precedenti sia
  una chiamata di rete, quindi va invocato esplicitamente. Wiring in
  `modulo1_fascicolo/analisi.py` (`analizza_fascicolo/testi/pdf(..., valuta_llm=False)`,
  disattivato di default) e CLI (`talia analizza ... --llm`).

**Bug reali scoperti col modello vero (qwen3:4b via Ollama), non dai test mockati:**
1. Timeout di default (120s) insufficiente: qwen3 è un modello "thinking" che ragiona ad alta
   voce anche su prompt brevi (~18-28s anche per un JSON banale) — portato a 300s.
2. `_estrai_giudizio` con un singolo regex greedy `\{.*\}` falliva il parsing quando il modello
   ripeteva lo schema JSON del prompt come "esempio" prima della risposta vera (due oggetti
   `{...}` nella risposta → il greedy cattura tutto in mezzo, JSON non valido). Fix: si
   estraggono tutti gli oggetti JSON non annidati e si prende l'**ultimo** valido con chiave
   `giudizio`. Test di regressione in `test_check3_motivazione.py`.
3. **Riferimenti al corpus non puntuali** (osservazione di Dom): `riferimenti_normativi`
   riportava solo il nome del file (es. `nazionale/l-241-1990.md`), senza testo né locatore —
   in violazione del principio di esplicabilità applicato altrove (ogni citazione porta offset
   + testo esatto). Fix: `Passaggio` ora porta `offset_inizio`/`offset_fine` (posizione di
   carattere nel file sorgente); `_cita_passaggio` produce riferimenti nello stile
   `file (car. A-B): «testo»`, verificabile.
4. **Conseguenza del fix precedente**: verificando gli offset sul corpus reale è emerso che
   `l-241-1990.md` è un unico blocco di ~103k caratteri, quasi senza righe vuote (dump grezzo
   da Normattiva) — il chunking per paragrafo non spezzava mai il file, che diventava un solo
   `Passaggio` enorme: il ranking BM25 degradava a corrispondenza per intero file e l'offset
   "puntuale" copriva comunque tutto il documento. Fix: `_dividi_paragrafo_lungo` spezza i
   paragrafi che eccedono la dimensione massima di chunk in frammenti a lunghezza fissa
   (taglio al primo spazio utile, per non spezzare le parole). Verificato: il corpus reale
   (3719 passaggi totali) ora ha chunk di ~1200 caratteri max invece di file interi, e la
   qualità del retrieval è visibilmente migliorata (il passaggio recuperato per un caso di
   revoca ora è l'art. 21-quater/21-quinquies pertinente, non il boilerplate di intestazione
   della pagina Normattiva).

5. **Stesso bug di offset anche sulla citazione dell'atto**: `offset_fine` era impostato alla
   fine dell'**intera** motivazione, ma il testo citato (`Citazione.testo`) era troncato a 200
   caratteri per leggibilità — l'offset dichiarava quindi un intervallo più ampio di quanto
   effettivamente riportato tra virgolette. Stesso principio del fix precedente sul corpus:
   `offset_fine` ora corrisponde esattamente a dove finisce il testo citato (troncato incluso).
   Verificato: per una motivazione lunga l'offset passa da 309–665 (sbagliato, copriva testo
   mai mostrato) a 309–509 (corretto, coincide col troncamento a 200 caratteri).

Verificato end-to-end con Ollama reale (`talia analizza data/samples/fascicolo_critico --llm`),
**tre volte** (prima del fix chunking, dopo, e dopo il fix dell'offset citazione): l'ultimo run
mostra sia citazioni al corpus puntuali e pertinenti (es. `nazionale/l-241-1990.md (car.
76501-77703): «...Art. 21-quater... la revoca determina la inidoneità del provvedimento
revocato...»`) sia un offset dell'atto coerente col testo mostrato. Il giudizio del LLM resta
un dato da verificare (⚖️ LEX), non un accertamento — coerente col resto del progetto.

## 📝 Note
Determinismo prima: questa card non sblocca il prototipo, segue la validazione iniziale
(TAL-12). Prossimo passo naturale: usare questo check sugli 8 fascicoli TAL-12 già preparati
per iniziare a costruire il ground truth falsi positivi/negativi anche sul check LLM.
