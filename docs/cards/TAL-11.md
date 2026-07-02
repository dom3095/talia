# TAL-11 — Check 3: qualità motivazione (LLM)

- **Epica:** E1 — Motore + Modulo 1
- **Ruolo:** 🔤 NLP
- **Priorità:** P2
- **Stato:** To Do
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
- [ ] Quale modello LLM locale di riferimento? (Llama 3 / Mistral / Qwen — vedi wiki/03)
- [ ] Soglia minima di lunghezza motivazione per considerarla "robusta"?
- [ ] Il RAG deve coprire solo le norme citate nell'atto o tutto il corpus?

## 📚 Contesto
[wiki/04](../wiki/04-checklist-modulo1.md) check 3. Filtro a imbuto: regole prima, LLM eccezione ([wiki/03](../wiki/03-stack.md)).

## ✅ Task
- [ ] Isolare la sezione "motivazione" dell'atto
- [ ] Prompt che valuta: densità, specificità, requisiti giurisprudenziali (interesse pubblico concreto e attuale, comparazione con affidamenti dei privati)
- [ ] LLM **open locale** (Llama/Mistral/Qwen) o Colab — mai a pagamento di default
- [ ] RAG sul corpus normativo per ancorare il giudizio ([wiki/06](../wiki/06-corpus-normativo.md))
- [ ] Esito 🟢 (motivazione robusta) / 🟡 / 🔴 (generica, mero "ripristino di legalità")
- [ ] Output con citazione del passaggio valutato

## 🧪 Criteri di accettazione
- [ ] Eseguito **solo** su atti già flaggati da altri check (non su tutti)
- [ ] 🔴 su motivazione boilerplate di poche righe (caso campione)
- [ ] Output sempre con citazione testuale, mai verdetto secco
- [ ] Funziona con modello locale, nessuna API a pagamento richiesta
- [ ] Test con motivazione robusta vs generica

## 🔗 Dipendenze
TAL-3, TAL-6, corpus normativo (TAL/E... per RAG).

## 📝 Note
Decidere modello LLM locale di riferimento (scelta aperta wiki/03). Determinismo prima: questa card non sblocca il prototipo, può seguire la validazione iniziale.
