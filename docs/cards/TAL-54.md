# TAL-54 — Check 3: retrieval RAG cieco ai temi già individuati dai check deterministici

- **Epica:** E1 — Motore + Modulo 1
- **Ruolo:** 🔤 NLP
- **Priorità:** P2
- **Stato:** Review
- **Branch:** `feat/TAL-53-nome-ruolo-graduatoria` (proseguito sullo stesso branch, non ne apre uno nuovo)

## 🎯 Obiettivo
Il retrieval BM25 di check 3 (TAL-11) interroga il corpus normativo con il solo testo
della motivazione. Su un fascicolo reale (TAL-12/fascicolo 1) questo manca completamente
il GDPR — pur essendo il corpus normativo a contenerlo, e pur essendo il tema già
individuato correttamente dal check deterministico 7 — per un semplice scarto di
vocabolario tra l'atto ("segretezza", "riservatezza") e la norma ("dati personali",
"violazione"). Il LLM produce quindi un giudizio senza alcun aggancio verificabile al
corpus, anche quando un aggancio pertinente esiste ed è già stato trovato altrove nella
pipeline.

## 🔬 Come è stato scoperto (sessione 2026-08-08)

Girando check 3 (LLM reale via Ollama, non mockato) su due fascicoli reali già presenti
in `data/samples/` (fascicolo 1 — TAL-12, e fascicolo 3), il giudizio del LLM è arrivato
coerente con quanto già stabilito manualmente il 2026-07-21 (stesso caso: motivazione
specifica ma basata su un fatto presunto, senza istruttoria autonoma). Osservando però i
5 passaggi normativi effettivamente recuperati dal BM25 per il fascicolo 1:

```
nazionale/dlgs-165-2001.md   (commissioni concorso, aggiornamenti)
nazionale/dlgs-165-2001.md   (idem)
nazionale/dlgs-267-2000.md   (contabilità enti locali)
nazionale/dlgs-36-2023.md    (imparzialità commissioni gara)
nazionale/dlgs-36-2023.md    (diligenza nell'esecuzione)
```

Nessuno di questi tratta il tema reale (motivazione basata su un fatto presunto/non
verificato). Verificato che:
- Il corpus **contiene** il GDPR (`ue/gdpr-679-2016.md`, 2154 righe).
- Interrogando l'indice con termini GDPR espliciti ("violazione dati personali garante
  notifica") il documento **esce primo** — il retrieval funziona, il problema è la query.
- La motivazione dell'atto non usa mai le parole "dati personali"/"GDPR"/"privacy"/
  "garante" — solo "segretezza"/"riservatezza delle operazioni concorsuali" — zero
  overlap lessicale con la norma pertinente, nonostante l'overlap concettuale sia forte
  (una bozza di graduatoria trapelata è dato personale).
- Il check-7 (GDPR breach, deterministico, TAL-14) su questo stesso fascicolo aveva già
  dato 🔴 **con i riferimenti giusti** (`Art. 33/34 GDPR`, `Art. 4(12) GDPR`) — il segnale
  esisteva già nella pipeline, semplicemente non veniva riusato dal retrieval di check 3.

Un secondo problema, distinto ma collegato: la `spiegazione` del LLM non cita mai
esplicitamente nessuno dei passaggi allegati al prompt, nemmeno quando sono pertinenti —
il report mostra i `riferimenti_normativi` come se fossero il fondamento del giudizio, ma
non c'è alcuna garanzia che lo siano davvero.

## 📋 Spec

### Interfaccia
```python
# check3_motivazione.py
def _cerca_passaggi_rag(
    indice: IndiceCorpus,
    motivazione: str,
    esiti_precedenti: list[EsitoCheck],
    *,
    k_motivazione: int = 3,
) -> list[Passaggio]: ...
```

### Comportamento
- **Retrieval arricchito**: oltre alla query sulla sola motivazione (`k_motivazione`
  passaggi), per **ciascun check precedente con esito 🟡/🔴** si esegue una query BM25
  separata sui suoi `riferimenti_normativi` e si aggiunge il suo passaggio migliore
  (1 per check, deduplicato per `(fonte, offset_inizio)`), **senza troncare il risultato
  finale**: un check con pochi riferimenti (es. check-7, 3 voci) non deve perdere il suo
  slot per via di un check con una lista più lunga (es. check-1, 9 voci) — bug osservato
  nella prima versione del fix, dove un taglio secco a `k=5` sul totale scartava proprio
  il passaggio GDPR perché aggiunto per ultimo nell'ordine di iterazione dei check.
  Motivazione della scelta (query separate, non un'unica query concatenata): concatenare
  tutti i riferimenti in una sola query BM25 **non basta** — verificato che il contributo
  GDPR (3 voci brevi) resta comunque sotto la soglia dei primi 5 risultati, annegato dal
  punteggio cumulato di check con più voci su documenti più densi (`dlgs-165-2001.md`,
  `dlgs-36-2023.md`).
  - Solo check 🟡/🔴 partecipano: un check 🟢/⚪ non segnala un problema specifico da
    rinforzare nella ricerca (stesso principio già usato per decidere se attivare check 3).
  - Check senza `riferimenti_normativi` (lista vuota) sono ignorati silenziosamente.
- **Grounding nel prompt**: il prompt istruisce esplicitamente il LLM a dichiarare, nella
  `spiegazione`, se il giudizio si fonda su uno dei passaggi elencati (citandone la fonte
  tra parentesi quadre) o se nessuno è pertinente. Nessun nuovo campo JSON obbligatorio
  (rischio di rompere il parsing già fragile su modelli "thinking", vedi
  `_estrai_giudizio`): resta nel campo `spiegazione` già esistente.

### Casi limite
- Nessun check precedente flaggato con riferimenti normativi non vuoti → comportamento
  identico a oggi (solo query sulla motivazione).
- Stesso passaggio recuperato sia dalla query sulla motivazione sia da una query di
  arricchimento → non duplicato (dedup per fonte+offset).
- Fascicolo con molti check flaggati (fino a 4 nell'attuale registry: check-1/5/6/7) →
  fino a `k_motivazione + 4` passaggi nel prompt; accettabile con l'attuale numero di
  check deterministici, da rivedere se il registry crescesse molto.

## ❓ Domande aperte
_Nessuna domanda bloccante._ Non si introduce un dizionario di sinonimi ad hoc né un
retrieval a embedding (cambio di architettura più grande, discusso ma non deciso in
questa sessione — vedi Note): il fix riusa un segnale che la pipeline calcola già
(`riferimenti_normativi` dei check deterministici), niente di nuovo da mantenere.

## 📚 Contesto
Segue [TAL-11](TAL-11.md) (check 3, RAG+LLM) e [TAL-14](TAL-14.md) (check 7, GDPR breach,
la cui uscita è il segnale riusato qui). Scoperto rilanciando check 3 con Ollama reale sui
fascicoli di [TAL-12](TAL-12.md) durante una sessione di verifica manuale, non da un test
automatico.

## ✅ Task
- [x] `_cerca_passaggi_rag()`: query motivazione + query per riferimenti dei check 🟡/🔴,
      dedup, nessun troncamento del contributo per-check
- [x] Prompt: istruzione esplicita a dichiarare il fondamento (o l'assenza) nella spiegazione
- [x] Test di regressione (7 nuovi, con stub `_IndiceSelettivo` che riproduce il caso GDPR:
      query sulla motivazione cieca, query sui riferimenti del check flaggato che invece
      trova il passaggio)
- [x] Nessuna regressione sui test esistenti di check 3 (589 test verdi, erano 582)
- [x] Verificato anche sul caso reale (fascicolo 1, `data/samples/1/`, `genera` mockato):
      `ue/gdpr-679-2016.md` ora compare in `riferimenti_normativi`, prima assente

## 🧪 Criteri di accettazione
- [x] Un fascicolo con check-7 (GDPR) flaggato produce sempre almeno un riferimento dal
      corpus GDPR in check 3, anche se il testo della motivazione non usa vocabolario GDPR
- [x] Test passano (`pytest`)
- [x] DoD rispettata (vedi CLAUDE.md)

## 🔬 Tentativi

### 2026-08-08 — Tentativo 1
**Approccio:** concatenare tutti i `riferimenti_normativi` dei check 🟡/🔴 in un'unica
query BM25 aggiuntiva (oltre a quella sulla motivazione).
**Esito:** ❌
**Appreso:** verificato sul caso reale che il documento GDPR restava comunque fuori dai
primi 5 risultati: i 3 riferimenti di check-7 (GDPR) venivano annegati nel punteggio
cumulato dei 9 riferimenti di check-1 su documenti più densi (`dlgs-165-2001.md`,
`dlgs-36-2023.md`). Una singola query "grande" non basta a garantire lo spazio a temi
minoritari.

### 2026-08-08 — Tentativo 2
**Approccio:** query separata per ciascun check flaggato (un passaggio garantito a testa),
senza troncare il totale finale.
**Esito:** ✅
**Appreso:** funziona, ma la prima implementazione troncava comunque a `k=5` sul totale
combinato — scartando in pratica il passaggio del check aggiunto per ultimo
nell'iterazione (proprio GDPR, essendo check-7 l'ultimo check registrato). Rimosso il
troncamento finale: la dimensione del prompt resta comunque limitata dal numero fisso di
check nel registry (attualmente 4 check "flaggabili" + `k_motivazione`).

### 2026-08-08 — Tentativo 3 (instabilità del giudizio, scoperta rilanciando il check)
**Approccio:** rilanciato check 3 (Ollama reale) sul fascicolo 1 per verificare il fix del
retrieval; poi richiesto da Dom di rieseguirlo di nuovo salvando l'output.
**Esito:** ⚠️ trovato un secondo bug, poi corretto nello stesso ciclo di lavoro.
**Appreso:** i due run sullo stesso identico fascicolo/prompt hanno dato **giudizi
diversi** (`carenza_istruttoria: true` → 🟡 la prima volta; `carenza_istruttoria`
implicitamente false → 🟢 la seconda), il secondo dei quali riproduceva esattamente il
falso negativo che TAL-11 aveva già corretto in passato su questo stesso fascicolo
(vedi TAL-12). Causa: `check3_motivazione.genera(prompt)` non passava mai `opzioni` a
Ollama, quindi il campionamento restava sul default stocastico del modello — nessuna
temperatura fissata. `engine.catena.classifica_ruolo_llm` aveva già il pattern giusto
(`opzioni={"temperature": 0}`), ma passa da `chiama_ollama` direttamente, non dal
wrapper `genera()` usato da check 3. Fix: `genera()` ora accetta `opzioni` e la propaga;
check 3 chiama sempre `genera(prompt, opzioni={"temperature": 0})`. Verificato con 2 run
reali consecutivi post-fix: **esito e spiegazione identici byte per byte**, e corretti
(🟡, non più il falso 🟢). 3 nuovi test (2 in `test_llm.py` sul passthrough di
`opzioni`, 1 in `test_check3_motivazione.py` che verifica la chiamata con
`temperature: 0`). Lezione generale: un check "a giudizio" non deterministico per
natura (LLM) va comunque reso il più riproducibile possibile a parità di input — la
temperatura di default di un modello non va mai lasciata implicita in un check di
produzione.

## 🔗 Dipendenze
TAL-11, TAL-14.

## 📝 Note
Non risolve il problema in generale (un check deterministico che non ha ancora individuato
il tema pertinente non lascia comunque alcun segnale da riusare): resta un limite noto del
retrieval lessicale puro. Un retrieval a embedding locale (gratuito, nessuna chiamata a
pagamento, coerente con budget≈0) risolverebbe il problema alla radice invece che solo nei
casi già coperti da un altro check — ma è un cambio di architettura da proporre e discutere
a parte (principio CLAUDE.md: "su architettura, proporre non decidere unilateralmente"),
non deciso in questa sessione.
