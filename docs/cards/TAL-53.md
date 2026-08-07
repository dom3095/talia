# TAL-53 — Check 6: associazione nome↔ruolo + incrocio tempistica graduatoria

- **Epica:** E1 — Motore + Modulo 1
- **Ruolo:** 🔤 NLP
- **Priorità:** P2
- **Stato:** Review
- **Branch:** `feat/TAL-53-nome-ruolo-graduatoria`

## 🎯 Obiettivo
Chiudere i due gap lasciati aperti da TAL-5 e TAL-9: (1) il check 6 deve poter dire *chi*
(ruolo) firma, non solo il nome; (2) quando lo stesso firmatario compare in indizione e
annullamento, incrociare la sovrapposizione con la vicinanza temporale all'approvazione
della graduatoria — un annullamento a ridosso della graduatoria è un segnale più forte di
uno distante nel tempo.

## 📋 Spec

### Interfaccia
```python
# src/talia/engine/graduatoria.py
def estrai_data_graduatoria(atto: TestoAtto) -> Entita | None: ...

# src/talia/engine/checklist/_date_utils.py (estratto da check2_termini.py)
def filtra_date_ccnl(date_entita: list[Entita], testo: str) -> list[Entita]: ...
def data_estrema(date_entita: list[Entita], *, piu_recente: bool) -> tuple[date | None, Entita | None]: ...

# check6_firmatari.py: CheckCoerenzaFirmatari.valuta() esteso, stessa firma pubblica.
```

### Comportamento
- **Nome↔ruolo**: per ogni coppia di firmatari sovrapposti (già individuata dal check),
  cercare il ruolo via `attori.estrai_attori()` su entrambi gli atti (stesso matching
  nome già usato per i firmatari — ordine invertito, secondo nome omesso). Se trovato,
  il messaggio nomina il ruolo ("Il Segretario Generale Mario Rossi…") invece del solo
  nome. Se il ruolo non è identificabile, il messaggio resta quello attuale (nessuna
  regressione).
- **Tempistica graduatoria**: `estrai_data_graduatoria()` cerca, per ogni menzione di
  "graduatoria" nel testo, una data entro una finestra di 150 caratteri **in cui compare
  anche "approvat[ao]"** (bidirezionale: copre sia "graduatoria approvata... del gg/mm/aaaa"
  sia "determina di approvazione della graduatoria n. X del gg/mm/aaaa"); tra tutte le
  corrispondenze tiene la data più vicina alla menzione di "graduatoria". Cercata prima
  nell'atto di autotutela (dove tipicamente si richiama l'atto approvato), poi
  nell'originario se assente.
- **Escalation**: se esiste sovrapposizione di firmatari **e** una data di graduatoria **e**
  la data dell'annullamento (data più recente non-CCNL dell'atto di autotutela, stessa
  logica già in check 2) dista ≤ **60 giorni** dalla graduatoria → 🔴 invece di 🟡, con
  citazione della graduatoria in più. Altrimenti resta 🟡 (comportamento attuale,
  nessuna regressione sui test esistenti).

### Casi limite
- Nessuna menzione di "graduatoria" nell'atto → nessuna escalation, comportamento
  identico a oggi (🟡 con eventuale ruolo in più se disponibile).
- "Graduatoria" menzionata ma senza "approvat[ao]" vicino, o senza data nella finestra →
  trattata come assente (nessun errore, nessuna escalation).
- Delta negativo (annullamento prima della graduatoria trovata) → nessuna escalation
  (la graduatoria individuata probabilmente non è quella pertinente); resta 🟡.

## ❓ Domande aperte
_Nessuna domanda bloccante._ Un punto resta un'assunzione documentata (come già in
check 2 per i 12 mesi/30 gg di tolleranza), non normativa: la soglia dei **60 giorni**
per "a ridosso della graduatoria" è una scelta euristica di prodotto, non un termine di
legge — da validare con ⚖️ LEX quando si leggeranno fascicoli reali con questo pattern
(nessuno dei fascicoli TAL-12 letti finora menziona esplicitamente l'approvazione della
graduatoria nell'atto di autotutela).

## 📚 Contesto
[wiki/04](../wiki/04-checklist-modulo1.md) check 6. Chiude i gap annotati nei Consuntivi
di [TAL-5](TAL-5.md) (associazione nome↔ruolo rinviata) e [TAL-9](TAL-9.md) (incrocio
tempistica graduatoria rinviato). L'associazione ruolo→nome esiste già come estrazione
generale in `engine/attori.py` (TAL-13): qui si tratta di *usarla* dentro il check 6, non
di riscriverla.

## ✅ Task
- [x] Estrarre `filtra_date_ccnl`/`data_estrema` da `check2_termini.py` in un helper
      condiviso (`checklist/_date_utils.py`), riusato da check 2 e check 6
- [x] `engine/graduatoria.py`: `estrai_data_graduatoria()` + test dedicati
- [x] `check6_firmatari.py`: arricchire il messaggio con il ruolo via `attori.py`
- [x] `check6_firmatari.py`: escalation 🟡→🔴 su vicinanza temporale alla graduatoria
- [x] Test di regressione (i 5 test check-6 esistenti restano verdi) + nuovi casi
      (ruolo trovato, escalation 🔴, graduatoria lontana → resta 🟡)

## 🧪 Criteri di accettazione
- [x] Nessuna regressione sui test esistenti di check 2 e check 6
- [x] 🔴 quando stesso firmatario + graduatoria ≤ 60gg dall'annullamento
- [x] Messaggio con ruolo quando disponibile, invariato quando non disponibile
- [x] Test passano (`pytest`)
- [x] DoD rispettata (vedi CLAUDE.md)

## 🔬 Tentativi

### 2026-08-07 — Tentativo 1
**Approccio:** implementazione come da Spec sopra, in un'unica sessione.
**Esito:** ✅
**Appreso:** l'associazione nome↔ruolo era già pronta in `attori.py` (TAL-13, mai
agganciata al check 6); il grosso del lavoro nuovo è l'estrazione della data di
graduatoria e l'escalation, non l'associazione in sé.

### 2026-08-07 — Tentativo 2 (self-review post-commit)
**Approccio:** rilettura critica del diff dopo il primo commit (nessun `/code-review`
multi-agente lanciato: solo lettura manuale mirata delle parti nuove).
**Esito:** ⚠️ parziale — trovato un bug reale, poi corretto nello stesso commit.
**Appreso:** `_esito_graduatoria` ridatava l'atto di provenienza della graduatoria
controllando `any(e is ent for e in atto.entita.entita)` — ma `estrai_data_graduatoria`
richiama `estrai_date()` internamente su un nuovo `TestoAtto`, quindi l'entità
restituita non è mai la stessa istanza già presente in `atto.entita.entita`: il
controllo per identità falliva sempre, e la citazione della graduatoria finiva
sistematicamente attribuita al testo sbagliato (offset dell'atto di autotutela letti
sul testo dell'originario → citazione vuota o garbled, mai un crash perché
`estratto()` clampa gli offset in silenzio). Fix: tenere esplicita la provenienza
(quale `TestoAtto` ha prodotto il match) invece di ridedurla dopo per identità. Lezione
generale: quando un'entità viene ricreata da una chiamata di estrazione separata,
**mai confrontarla per identità con entità di un'altra pipeline** — o si traccia la
provenienza esplicitamente, o si confronta per valore/offset. Aggiunto un test che
verifica il *contenuto* della citazione (non solo il conteggio), che avrebbe
catturato il bug da subito.

## 🔗 Dipendenze
TAL-5, TAL-9, TAL-13.

## 📝 Note
I nomi restano dato personale (come TAL-5/TAL-9): nessuna vista pubblica non
anonimizzata. Nessuna dipendenza nuova, nessuna chiamata LLM: check deterministico.
