# TAL-46 — Engine catena v2: contenimento oggetto, guard-rail fuzzy, fix riferimenti

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🔤 NLP + 🧭 TL
- **Priorità:** P2
- **Stato:** Review
- **Branch:** `feat/TAL-30-dashboard-mvp` (come TAL-42…45)

## 🎯 Obiettivo

Rendere la ricostruzione catene affidabile **usando solo i metadati già scrapati**
(oggetto, tipo, numero, data_pub, url) — senza scaricare PDF né appesantire il DB —
correggendo i tre difetti emersi sul caso reale Palma di Montechiaro (proc. 674).

## 📚 Contesto

Caso di studio: `data/samples/1` (bando 7 operatori esperti + revoca in autotutela,
Palma di Montechiaro). Il DB ricostruisce la catena, ma:

1. il procedimento 674 fonde **3 selezioni distinte** (Operatori→Esperti,
   Esperti→Istruttori, Istruttori→Funzionari) + le 3 revoche in un'unica catena
   fuzzy `da_verificare` — il boilerplate CCNL domina il Jaccard sui trigrammi;
2. la strategia 2 (riferimenti incrociati) non scatta: `_RE_NUM_ATTO` non matcha
   "DETERMINAZIONE N. 33/2025" per esteso, e comunque `atti.numero` contiene il
   registro generale (932, 1706) mentre gli atti citano il numero settoriale (16, 35);
3. "APPROVAZIONE AVVISO DI SELEZIONE" viene classificata `altro` invece di `avvio`.

Osservazione chiave: **l'oggetto della revoca contiene verbatim l'oggetto del bando
originario** ("REVOCA IN AUTOTUTELA DELL'AVVISO … [titolo bando per esteso]").
È prassi amministrativa costante e più robusta dei riferimenti numerici — nel caso
reale la revoca RG 936 cita un numero *sbagliato* (33/2025 invece del proprio),
ma il titolo incorporato è corretto.

Vedi TAL-43 (strategie v1) e `docs/handoff/epica_E2.md`.

## 📋 Spec

### Interfaccia

```python
# --- Nuova strategia 2.5: contenimento oggetto (alta confidenza) ---
def collega_per_contenimento(conn: sqlite3.Connection, ente_id: int | None = None) -> int:
    """Collega atti 'derivati' (revoca/annullamento/modifica/proroga) all'atto
    originario il cui oggetto normalizzato è contenuto come sequenza di token
    nell'oggetto del derivato. Stesso ente. Ritorna n. collegamenti creati.
    metodo_individuazione = 'contenimento_oggetto'."""

def _oggetto_contenuto(contenitore: str, contenuto: str, min_token: int = 5) -> bool:
    """True se i token normalizzati di `contenuto` appaiono come sottosequenza
    contigua in `contenitore`. Sotto min_token → sempre False."""

# --- Guard-rail per strategia 3 (fuzzy) ---
def _slot_contraddittori(oggetto_a: str, oggetto_b: str) -> bool:
    """True se i due oggetti, pur simili, hanno slot discriminanti incompatibili:
    token numerici diversi (es. 'N. 7' vs 'N. 3') o insiemi di token rari
    (IDF alto nell'ente) disgiunti. Se True, il merge fuzzy è vietato."""

# --- Fix regex (nessuna nuova interfaccia) ---
# _RE_NUM_ATTO: aggiungere forme estese determinazione|deliberazione|ordinanza|decreto
# _PATTERN_RUOLO 'avvio': aggiungere avviso di selezione|selezione interna|approvazione avviso
```

`ricostruisci_catene` applica le strategie in ordine:
CIG (1) → riferimenti (2) → **contenimento (2.5)** → fuzzy con guard-rail (3) → LLM opt-in (4).

### Comportamento

- **Contenimento**: per ogni atto con ruolo derivato (revoca/annullamento/modifica/
  proroga) senza `procedimento_id`, cercare tra gli atti dello stesso ente un atto
  il cui oggetto normalizzato è sottosequenza contigua dell'oggetto del derivato.
  Match unico → collega allo stesso procedimento (creandolo se serve) con alta
  confidenza. Match multipli → nessun collegamento automatico, log WARNING.
- **Guard-rail fuzzy**: `collega_per_oggetto_simile` chiama `_slot_contraddittori`
  prima di aggiungere un atto al gruppo; se contraddittori, l'atto resta fuori
  anche sopra soglia Jaccard. La pesatura IDF per ente riduce il peso del
  boilerplate normativo nella similarità.
- **Ordine**: il contenimento gira prima del fuzzy, così i derivati "certi" sono
  già assegnati e il fuzzy lavora solo sul residuo.
- Tutto resta deterministico e metadata-only: nessun download PDF, nessuna
  colonna nuova obbligatoria nel DB.

### Casi limite

- Oggetto vuoto o < `min_token` token normalizzati → contenimento mai attivato.
- Revoca il cui oggetto contiene i titoli di **più** bandi (revoca cumulativa) →
  match multipli → nessun collegamento automatico, WARNING (revisione umana).
- Atti gemelli con oggetto identico e stessi slot (es. ripubblicazione) →
  il guard-rail non li separa: restano nello stesso procedimento (corretto).
- Numero citato nell'oggetto errato (caso reale RG 936) → il contenimento collega
  comunque per titolo; il riferimento numerico discordante NON deve bloccare.
- Ente con un solo atto → tutte le strategie ritornano 0 senza errori.
- Idempotenza: doppia esecuzione di `ricostruisci_catene` non duplica procedimenti
  né cambia i collegamenti già fatti.

## ❓ Domande aperte

- [x] **Numero settoriale** → **colonna dedicata** `atti.numero_settoriale`
      (deciso 2026-07-02). ⚠️ Scoperto in corso: lo scraper jCityGov scarica solo
      le pagine-lista, non i dettagli — popolare il campo richiede 1 richiesta
      HTTP extra per atto. In questa card: colonna + uso nel lookup strategia 2;
      arricchimento dal dettaglio = follow-up opt-in (vedi Note).
- [x] **Procedimenti fuzzy esistenti** → **reset + rerun** dei soli procedimenti
      `da_verificare`; quelli da CIG/riferimenti restano intatti (deciso 2026-07-02).
- [x] **Adiacenza ID pubblicazione jCityGov** → **rimandata** a card futura
      (deciso 2026-07-02).
- [x] **Soglia `min_token` contenimento** → **5 token**, da calibrare sui dati
      reali in corso d'opera (deciso 2026-07-02).

## ✅ Task

- [x] Fix `_RE_NUM_ATTO`: forme estese (determinazione/deliberazione/ordinanza/decreto)
- [x] Fix pattern `avvio`: avviso di selezione, selezione interna, approvazione avviso
- [x] `_oggetto_contenuto` + `collega_per_contenimento` (strategia 2.5)
- [x] `_gemelli_contraddittori` + integrazione in `collega_per_oggetto_simile`
      (guard-rail attivo solo sopra Jaccard 0.75: numeri o coda-6-token diversi ⇒ no merge)
- [x] ~~Pesatura IDF per ente~~ — non necessaria: contenimento + guard-rail hanno
      risolto il caso reale senza (vedi Tentativi); niente astrazioni speculative
- [x] Colonna `atti.numero_settoriale` in `_evolvi_schema` + lookup strategia 2
      esteso (`numero OR numero_settoriale`)
- [x] `reset_procedimenti_da_verificare` + flag `reset_da_verificare` in
      `ricostruisci_catene` (migrazione applicata a `talia.db` il 2026-07-02)
- [x] Integrazione in `ricostruisci_catene` (strategia 2.5 tra la 2 e la 3 + metriche)
- [x] Test con i 6 oggetti reali Palma (titoli di atti pubblici, nessun dato
      personale) — 3 catene avvio→revoca distinte ✓
- [x] Test casi limite (revoca cumulativa, oggetto corto, idempotenza, reset)
- [ ] Follow-up (fuori card): arricchimento `numero_settoriale` dal dettaglio
      jCityGov — richiede 1 fetch extra per atto, valutare flag opt-in nello scraper

## 🧪 Criteri di accettazione

- [x] Sul caso Palma (6 atti): 3 procedimenti distinti, ciascuno avvio→revoca,
      metodo `contenimento_oggetto`, stato `revocato` — niente più mega-catena 674
      (verificato sia in test sia sul DB reale: proc. 1170/1171/1172)
- [x] La revoca RG 936 (numero citato errato) è collegata al bando giusto
      (atto 3390 → proc. 1172 insieme all'avvio 3393)
- [x] `classifica_ruolo(oggetto="APPROVAZIONE AVVISO DI SELEZIONE…")` → `avvio`
- [x] `estrai_riferimenti("…determinazione n. 33/2025…")` trova `n.33/2025`
- [x] Nessuna regressione sui test TAL-43
- [x] Test passano (`pytest`: 290 verdi, di cui 41 in test_catena.py)
- [x] DoD rispettata (vedi CLAUDE.md)

## 🔬 Tentativi

### 2026-07-02 — Tentativo 0 (analisi, nessun codice)
**Approccio:** verifica sul DB reale se il fascicolo `data/samples/1` (Palma,
bando 7 operatori esperti + revoca) è ricostruibile dalle catene v1 (TAL-43).
**Esito:** ⚠️ parziale
**Appreso:** la catena esiste (proc. 674, stato `revocato`) ma solo grazie al
fuzzy, che ha sovra-aggregato 3 selezioni distinte; strategia 2 muta (regex non
matcha forme estese + numero DB ≠ numero citato); approvazioni classificate
`altro`. L'oggetto della revoca contiene verbatim il titolo del bando → il
contenimento è il segnale deterministico più forte disponibile nei soli metadati.

### 2026-07-02 — Tentativo 1
**Approccio:** suffisso di token normalizzati ancorato alla FINE dell'oggetto
originario (non contenimento pieno né Jaccard): il derivato aggiunge un prefisso
proprio ("REVOCA IN AUTOTUTELA … APPROVATO CON DETERMINAZIONE N. X,") ma
riproduce la coda del titolo, dove nei titoli PA sta l'oggetto specifico.
Soglie: ≥5 token e ≥50% dei token dell'originario. Guard-rail fuzzy solo sopra
Jaccard 0.75 (gemelli): numeri o ultima coda-6-token diversi ⇒ no merge.
**Esito:** ✅
**Appreso:** (1) il contenimento pieno NON funziona — il prefisso
"APPROVAZIONE AVVISO E MODELLO ISTANZA" dell'originario non compare nella
revoca; serve l'ancoraggio al suffisso. (2) `_token_oggetto` scarta i token ≤2
caratteri, quindi i numeri discriminanti "7"/"3" spariscono: il check numerico
del guard-rail da solo non basta, è la coda-sequenza a separare i gemelli.
(3) Pesatura IDF non necessaria dopo questi due fix. (4) Sul DB reale
(reset 523 fuzzy + rerun): 11 atti collegati per contenimento in 10 procedimenti
— incluso un bonus non previsto: bando ripubblicato come "[annullato] BANDO…"
agganciato al suo originale. 7 casi ambigui saltati con WARNING (by design).
(5) Strategia 2 resta a 0 collegamenti sul DB reale: senza `numero_settoriale`
popolato il lookup per numero non può matchare (follow-up scraper).

## 🔗 Dipendenze

TAL-42 ✅, TAL-43 ✅ (strategie v1).

## 📝 Note

- Vincolo di progetto: **metadata-only** — le catene M2 si costruiscono dagli
  oggetti scrapati, senza scaricare PDF (troppo peso su DB e banda).
- La sottosequenza contigua di token (non trigrammi) evita che il boilerplate
  produca contenimenti spuri tra atti non correlati.
- Il caso Palma è anche materiale per un futuro check di coerenza dei riferimenti
  (l'ente cita 33/2025 dove intende 35/2025): fuori scope qui, annotare in TAL-24
  o card dedicata se ricorre.
