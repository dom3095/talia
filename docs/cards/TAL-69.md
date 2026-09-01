# TAL-69 — Scraper "stagnanti": restituiscono righe ma nessun atto nuovo da settimane

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🕷️ SCR + ⚙️ OPS
- **Priorità:** P1
- **Stato:** To Do
- **Branch:** —

## 🎯 Obiettivo

Rilevare (e poi diagnosticare) un quarto modo di fallire che il riepilogo di
[TAL-66](TAL-66.md) **non intercetta**.

## 📚 Contesto

Domanda di Dom (2026-08-19): *"hai tenuto traccia degli scraper che non
funzionano e dei comuni che non tornano righe da qualche giorno?"* — risposta:
i primi sì, i secondi no.

`report_run.py` distingue tre stati, e nessuno copre questo caso:

| Stato | Condizione | Copre il caso? |
|-------|-----------|----------------|
| ❌ fallito | `errore` valorizzato | no — questi non danno errore |
| 🔇 muto | `n_trovati = 0` | no — questi trovano 20 righe |
| 🕒 fermo | non eseguito da N giorni | no — questi girano ogni notte |
| **🥶 stagnante** | righe trovate, **`n_inseriti = 0` da settimane** | **non esiste** |

Uno scraper stagnante è indistinguibile da uno sano in ogni metrica che
guardiamo oggi: gira, non dà errori, trova righe. Semplicemente le righe sono
sempre le stesse.

## 📊 Rilevazione (2026-08-19, `talia.db` reale)

Metrica: **giorni dall'ultimo inserimento** con righe ancora restituite
all'ultimo run. (Un primo tentativo contava i *run consecutivi* a zero
inserimenti: falsato dai run manuali ripetuti del 18/08, che facevano
comparire `pachino` e `barrafranca` come stagnanti il giorno stesso in cui
avevano inserito atti.)

**20 scraper su 263**, tutti con righe restituite all'ultimo run:

| Giorni senza atti nuovi | Scraper |
|---|---|
| 42 (dal 2026-07-07) | `mascalucia` (29.984 ab.), `villabate`, `rometta`, `montelepre`, `custonaci`, `favignana`, `blufi`, `casteldiiudica`, `sangiovannilapunta`, `paceco`, `alessandriadellarocca` |
| 35 | `campofeligerocchella`, `riposto` |
| 29 | `licata`, `salemi`, `troina` |
| 25 | `busetopalizzolo`, `carini`, `sangregoriodicatania`, `santamariadilicodia` |

I due casi peggiori, guardando l'atto più recente del comune:

* **`rometta`** — atto più recente **2023-09-27**, quasi 3 anni fa
* **`paceco`** — atto più recente **2025-07-04**

Un albo pretorio con finestra di pubblicazione di 15-30 giorni non può essere
fermo da 3 anni e continuare a restituire 20 righe: o lo scraper legge una
pagina d'archivio invece dell'albo vivo, o il comune ha migrato piattaforma
lasciando online la vecchia.

## ⚠️ Due cause note che spiegano *parte* dei casi (non tutti)

1. **Comuni con due scraper** (TAL-52, backlog P3): 5 comuni hanno due entry
   di registro con lo stesso codice ISTAT — `favignana`/`favignana_halley`,
   `racalmuto`/`racalmuto_halley`,
   `sangiovannilapunta`/`sangiovannilapunta_halley`,
   `villabate`/`villabate_portalepa`,
   `campofelicediroccella`/`campofeligerocchella` (quest'ultimo con lo slug
   storpiato, stesso ISTAT 082017). Il gemello fa il lavoro e l'altro ritrova
   gli stessi atti come duplicati: **stagnante ma non rotto**. Sono 4 dei 20.
2. **Comuni che pubblicano davvero poco**: `alessandriadellarocca` (3.118 ab.,
   5 righe in tutto) può essere legittimo. `mascalucia` (29.984 ab., 134 atti
   totali) quasi certamente no.

## 📋 Spec proposta (da concordare)

1. **Nuova categoria nel report**: `stagnante` = righe trovate all'ultimo run
   **e** nessun inserimento da più di N giorni (default 14 — sopra la finestra
   tipica di pubblicazione, sotto il mese).
2. **Non contarla come fallimento** nell'exit code, almeno all'inizio: 20 casi
   farebbero suonare la notifica ogni notte, l'errore già corretto in TAL-68.
   Sezione informativa finché la lista non è stata bonificata.
3. **Escludere i gemelli noti** (o, meglio, risolvere TAL-52).
4. **Diagnosi manuale** di `rometta` e `paceco` per primi: sono i due che non
   hanno spiegazione benigna.

## ❓ Domande aperte

- [ ] La soglia va sui giorni o va rapportata alla frequenza storica del
      singolo comune? Enna pubblica ~3 atti/mese (documentato in CLAUDE.md):
      una soglia fissa la segnalerebbe ingiustamente. Una soglia relativa
      ("silenzioso da 3× il suo intervallo mediano") sarebbe più giusta ma è
      più difficile da spiegare in un report.
- [ ] Contarla nell'exit code dopo la bonifica, o mai?

## 📎 Debito collegato emerso nello stesso audit

**`atti.fonte_scraper` contiene il modulo (13 valori: `jcitygov`, `halley`,
…), non lo slug dello scraper (263)**. Per i 5 comuni con scraper gemelli è
quindi impossibile attribuire un atto a una specifica entry di registro, e
capire quale dei due funziona. Non bloccante per questa card, ma è ciò che
impedisce una diagnosi automatica dei casi del punto 1.
