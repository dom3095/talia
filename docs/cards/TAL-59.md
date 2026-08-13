# TAL-59 — Falsi positivi in riapertura_dopo_revoca: tag "[annullato]" + dominio mancante

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🔤 NLP + ⚖️ LEX
- **Priorità:** P1
- **Stato:** Review
- **Branch:** `feat/TAL-59-fix-riapertura-falsi-positivi`

## 🎯 Obiettivo

Ridurre i falsi positivi del red flag `riapertura_dopo_revoca` (TAL-48), scoperti
rileggendo i fascicoli candidati di TAL-12 su richiesta di Dom ("il sample 11 mi
sembra troppo lungo, di che si tratta? controlla anche le altre cartelle").

## 📚 Contesto

Sample 11 di TAL-12 (`data/samples/11/`, 63 PDF) si è rivelato non un bando
revocato/riaperto ma l'adozione della **Variante Generale al P.R.G. del Comune di
Alcamo** — un procedimento urbanistico, non un appalto/concorso. Controllando tutti
gli altri fascicoli candidati (3, 6, 7, 8, 9, 10, 11, 12, 13) contro `talia.db`
reale, **5 su 9 (56%) sono falsi positivi**, non solo il sample 11:

| Sample | Ente | Esito | Causa |
|---|---|---|---|
| 6 | Ragusa | ✅ valido | CIG condiviso, annullamento sostanziale esplicito |
| 7 | Palma di Montechiaro | ✅ valido | già noto/validato in TAL-48 |
| 8 | Marsala | ✅ valido | "revoca in autotutela della gara" esplicita |
| 13 | San Giovanni la Punta | ⚠️ ambiguo | CIG ok, ma probabile correzione contabile — da far leggere a LEX |
| 11 | Alcamo | ❌ falso positivo | tag `[annullato]` (bug 1) su atto di pianificazione |
| 10 | Acireale | ❌ falso positivo | tag `[annullato]` (bug 1) |
| 3 | Caltanissetta | ❌ falso positivo | due contenziosi diversi concatenati per boilerplate (bug 2, non corretto qui) |
| 9 | Bagheria | ❌ falso positivo | match Jaccard tra atto on-topic e atto fuori tema (bug 2, non corretto qui) |
| 12 | Giarre | ❌ falso positivo | contenzioso (non bando), "annullamento" nel testo si riferisce alla richiesta del ricorrente, non all'atto (bug 2, non corretto qui) |

**Causa tecnica identificata (investigazione con sotto-agente + verifica manuale):**

1. **Bug 1 — tag di stato scambiato per atto sostanziale.** jCityGov (e altre
   piattaforme) prependono `[annullato] ` all'`oggetto` quando una *pubblicazione*
   viene ritirata/corretta sull'albo — non è un annullamento sostanziale del
   procedimento. `classifica_ruolo()` in
   [`engine/catena.py:101-119`](../../src/talia/engine/catena.py) non lo riconosce:
   la regex `\bannull(?:a|amento|ato|ati)\b` scatta sul tag. **151 atti nel DB
   hanno questo prefisso, 120 classificati erroneamente come `annullamento`.**
2. **Bug 2 — nessun filtro di dominio.**
   [`riapertura_revoca.py:rileva_riapertura_dopo_revoca`](../../src/talia/modulo2_scraping/red_flags/riapertura_revoca.py)
   non limita la ricerca a procedimenti di tipo gara/appalto/concorso — il suo
   stesso scopo dichiarato ("bando 'su misura' ripubblicato"). **532/555 (95,9%)**
   dei procedimenti con `stato_finale IN ('annullato','revocato')` non hanno
   *nessun* atto di tipo gara/concorso/bando.
3. **Bug 2b — Jaccard su oggetto lega atti scorrelati.** Anche quando il
   procedimento di partenza è genuinamente un appalto, il match per riapertura
   (stesso ente + oggetto simile ≥ soglia) può agganciare un atto successivo
   completamente estraneo (es. Bagheria: un atto di pubblicazione bando viene
   letto come "revoca" perché **in coda al titolo** cita la revoca di una
   *diversa* determina di spesa; la "riapertura" trovata è un rimborso oneri di
   riscossione slegato). Non ha niente a che fare col dominio: è un limite
   strutturale del matching lessicale puro (già noto da TAL-54 per il RAG). **Non
   affrontato in questa card** — richiederebbe un criterio di verifica più forte
   (numero atto/determina condiviso, non solo Jaccard sull'oggetto).

## 📋 Spec

- **Fix 1** (`engine/catena.py::classifica_ruolo`): rimuovere un prefisso tra
  parentesi quadre da `oggetto` prima della classificazione (es. `[annullato] `,
  `[Annullato] `) — è un tag di stato della piattaforma, non testo dell'atto.
  Generico (qualunque tag tra `[]`), non specifico a jCityGov.
- **Fix 2** (`red_flags/riapertura_revoca.py`): filtro di dominio — un
  procedimento entra in `rileva_riapertura_dopo_revoca` solo se il suo `oggetto`
  contiene una **frase** del dominio gara/appalti ("determina a
  contrarre/contrattare", "affidamento diretto/dei/del/della/delle",
  "procedura di gara/aperta/negoziata/ristretta", gara/appalto/bando/concorso/
  capitolato/aggiudicazione). **Non** parole isolate ("servizio", "procedura",
  "lavori" da sole): un primo tentativo su singole parole, verificato contro
  tutti i flag residui su `talia.db` reale, lasciava passare il 30% dei casi
  ancora fuori dominio (Tentativo 2 sotto) — serve il contesto giuridico
  specifico, non la sola parola.
- Test di regressione con i casi reali anonimizzati trovati (tag `[annullato]`
  + procedimento fuori dominio) come esempio positivo del fix, più un caso
  negativo (non deve rompere Ragusa/Marsala/Palma).
- **Non in scope**: bug 2b (Jaccard lega atti scorrelati anche in dominio) — da
  aprire come card separata se Dom conferma che vale la pena affrontarlo (soglia
  più alta? richiedere un riferimento numerico condiviso oltre alla similarità
  testuale?).
- **Non in scope**: rigenerare `data/samples/` con candidati puliti — card
  separata/attività manuale successiva a questo fix.

## ❓ Domande aperte

Nessuna bloccante — fix meccanico e testabile, verificato manualmente contro i 9
casi reali di TAL-12 prima di scrivere il codice.

## 🔬 Tentativi

### 2026-08-13 — Tentativo 1
**Approccio:** Ipotesi iniziale: il bug 2 fosse dovuto a `classifica_ruolo()` che
scandisce `testo[:2000]` (corpo del PDF) oltre all'oggetto, prendendo menzioni di
"annullamento"/"revoca" nel body.
**Esito:** ❌ scartata.
**Appreso:** `atti.testo_estratto` è `NULL` per tutti gli atti coinvolti (i dati
vengono dalla sola pagina-lista dell'albo, non dal PDF) — il match arriva sempre
da `oggetto`, non dal body. Il vero meccanismo del bug 2 è la lunghezza dei
titoli reali (spesso >200 caratteri, con più soggetti concatenati) e il matching
lessicale puro via Jaccard, non uno scope errato dei campi scandagliati.

### 2026-08-13 — Tentativo 2
**Approccio:** Implementati Fix 1 (`classifica_ruolo`, strip tag `[...]`) e Fix 2
(filtro dominio in `rileva_riapertura_dopo_revoca`). 8 nuovi test (regressione sui
9 test esistenti + casi reali anonimizzati Alcamo/Caltanissetta). Verificato anche
**dal vivo su `talia.db` reale** (non solo sui test sintetici): confronto diretto
codice originale vs. modificato sullo stesso DB (`git stash`/`pop`), non contro lo
snapshot storico in `red_flags` (che riflette un run passato, non comparabile 1:1
per via della guardia anti-periodicità che evolve col DB).
**Esito:** ✅, con un limite residuo documentato.
**Appreso:**
- **Fix 2 (filtro dominio) è la leva principale sui dati reali**: da **82 a 23
  flag** (-72%) sullo stesso DB. Confermati esclusi: Alcamo/PRG (10359),
  Caltanissetta/contenzioso (897, 22326, 22366, 22742), Bagheria/abbonamento corsi
  (18582), Acireale/tag-bug (20124), 15 delle 20 catene contenzioso/delibere di
  Giarre. Confermati mantenuti: Ragusa (26206), Palma (692), Marsala (20443),
  Alcamo/concorso (10393) — tutti i casi giudicati validi durante la verifica
  manuale.
- **Fix 1 (tag `[annullato]`) non è retroattivo**: `classifica_ruolo()` viene
  chiamata solo in fase di ricostruzione catene (scraping/ricostruzione), non
  letta a runtime da `rileva_riapertura_dopo_revoca` — quindi non cambia nulla sui
  dati già in `talia.db` finché non gira un nuovo run scraper (o un backfill di
  riclassificazione, non eseguito qui: tocca il DB reale locale, richiede conferma
  esplicita di Dom prima di lanciarlo).
### 2026-08-13 — Tentativo 3
**Approccio:** Dom ha giudicato il Tentativo 2 (filtro a parole chiave isolate:
"servizio", "procedura", "lavori" come token) troppo superficiale. Verificato
manualmente **tutti e 23** i flag residui dopo quel filtro contro `talia.db`
reale (non un campione): **7/23 (30%) erano ancora falsi positivi**, tutti per
la stessa causa — una singola parola generica bastava a far passare il filtro
anche fuori dominio: "SERVIZIO" in "autovetture DI SERVIZIO" (censimento
veicoli, Bompietro), "SERVIZI" nel nome di un ufficio ("servizi demografici",
Calatabiano), "PROCEDURA" in "procedura di revoca dell'accoglienza" (un
progetto SAI/SIPROMI di accoglienza migranti, Lercara Friddi), convenzioni/
adesioni societarie tra enti che citano "servizi" solo nel nome dell'oggetto
sociale (Sant'Agata li Battiati, 3 casi), oltre al caso "lavori di
manutenzione" già noto (Giarre, ordinanza chiusura strada).
**Esito:** ✅ sostituito il filtro a parole con un filtro a **frasi** (regex):
richiede il contesto giuridico specifico ("determina a contrarre/contrattare",
"affidamento diretto/dei/del/della/delle", "procedura di gara/aperta/
negoziata/ristretta", oltre a gara/appalto/bando/concorso/capitolato/
aggiudicazione), non la sola presenza di una parola isolata.
**Appreso:**
- Verificato dal vivo sullo stesso DB reale (`talia.db`): **82 → 23 → 10 flag
  (8 procedimenti distinti)**, una riduzione del 90% rispetto al codice
  originale. Gli 8 rimasti sono tutti genuinamente gara/appalto/concorso, letti
  a mano uno per uno: Palma (692, affidamento diretto sorveglianza sanitaria),
  Custonaci (6487, bando di gara alienazione immobili), Alcamo (10393,
  concorso 2 dirigenti tecnici), Giarre (11812, affidamento diretto servizio
  centro anziani con CIG; 23666, concorso di idee), Marsala (20443, revoca in
  autotutela esplicita), Ragusa (26206, accordo quadro), Sperlinga (34796,
  annullamento in autotutela di una procedura negoziata).
- **Trade-off esplicito, non nascosto**: il filtro più stringente esclude anche
  2 casi minori genuinamente in dominio ma senza le frasi richieste — San
  Gregorio di Catania (24909, "liquidazione fattura... servizio di
  derattizzazione", un contratto di piccolo valore) e Adrano (31392,
  "annullamento in autotutela" di un impegno per "lavori di somma urgenza" ex
  art. 140 D.Lgs 36/2023, senza le frasi "determina a contrarre"/"affidamento
  X"). Scelta deliberata: per uno strumento civico dove un falso positivo
  rischia diffamazione (principio CLAUDE.md), la precisione vale più del
  recall su casi di basso valore/severità — ma è un costo reale, non gratuito.
- 5 nuovi test sui casi reali che hanno motivato il filtro a frasi (censimento
  veicoli, procedura di revoca accoglienza, convenzione tra enti), oltre ai 3
  già scritti nel Tentativo 2. **611 test verdi (erano 606)**, ruff pulito.
