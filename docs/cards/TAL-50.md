# TAL-50 — Censimento Palermo + Trapani (E3 estensione)

- **Epica:** E3 — Censimento comuni siciliani
- **Ruolo:** 🕷️ SCR + 🧭 TL
- **Priorità:** P1
- **Stato:** In Progress
- **Branch:** `feat/E3-province-palermo-trapani`

## 🎯 Obiettivo

Completare il censimento albi pretori delle province di **Palermo** (52 comuni mancanti) e **Trapani** (9 comuni mancanti) per estendere la copertura da 192 a 250+ comuni di Sicilia (~80% della popolazione).

## 📚 Contesto

Il censimento E3 (TAL-49, completato il 2026-07-09) ha coperto 192 comuni con 8 piattaforme generalizzate (jCityGov, Halley, portalepa, URBI, e-pal, SISPI, ASP.NET, WordPress). Restano **61 comuni** di Palermo e Trapani non ancora mappati nel registry `scripts/run_scrapers.py`.

**Importanza:** Palermo + Trapani includono il capoluogo regionale (657k abitanti) e comuni di medie dimensioni (Termini Imerese 26k, Partinico 31k). La loro inclusione aumenta la copertura di ~400k abitanti (+10% della popolazione siciliana).

## ✅ Task

### Fase 1: Censimento sistematico (COMPLETATO)
- [x] Ricerca web di tutti i 61 comuni mancanti (PA 52 + TP 9)
- [x] Identificazione della piattaforma albo per ciascun comune
- [x] Generazione CSV `censimento_albi_pa_tp.csv` ordinato per popolazione
- [x] Classificazione per livello di implementazione (TIER 0/1/2)

**Risultato:** 77 comuni censiti, 100% con albo online, distribuzione:
- **TIER 0 (subito):** 12 comuni su piattaforme già supportate (portalepa 6, jCityGov 2, URBI 1, già nel registry 3)
- **TIER 1 (facile):** 18 comuni su Halley/EGov/APKAPPA varianti
- **TIER 2 (reverse-engineering):** 14 comuni custom/local
- **TIER 3 (fallback):** 1 comune (Gazzetta Amministrativa, aggregator)

### Fase 2: Aggiunta TIER 0 al registry (IN PROGRESS)
- [x] 2 comuni jCityGov: Termini Imerese (26k), Campofelice Roccella (6.9k)
- [x] 6 comuni portalepa nuovi: Partinico (31k), Cefalù (14k), Castellammare del Golfo (14.6k), Corleone (11k), Capaci (11k), Partanna (10.8k)
- [x] 1 comune URBI: Caccamo (8.3k)
- [ ] Validare con test: fetch dati reali da 3-5 comuni TIER 0
- [ ] Merge su E3, primo run su DB isolato

### Fase 3: TIER 1 (condizionato a tempo)
- [ ] Analizzare Halley/EGov/APKAPPA: verificare se usano stessi scraper o varianti
- [ ] Aggiungere 13 comuni Halley/EGov se feasible (senza new scraper)
- [ ] Aggiungere 4 comuni APKAPPA se pattern compatibile

### Fase 4: TIER 2/3 (future work, TAL-51)
- [ ] Documentare reverse-engineering per custom/local (14 comuni)
- [ ] Valutare ROI implementazione per ogni piattaforma

## 📋 Spec

**Input:**
- Lista comuni CA/TP da `data/comuni_sicilia.csv` (66 PA + 24 TP)
- Registry attuale in `scripts/run_scrapers.py` (14 PA + 16 TP già mappati)

**Output:**
- CSV `data/censimento_albi_pa_tp.csv` (77 comuni, 100% con URL albo trovato)
- Aggiornamento `scripts/run_scrapers.py` con TIER 0 (12 comuni nuovi, 6 in scoperta diretta)
- Documentazione per Fase 3/4 in `docs/wiki/15-censimento-palermo-trapani.md`

**Qualità:**
- Ogni URL albo testato via curl/browser (no false positive)
- Codici ISTAT verificati contro CSV ufficiale
- Piattaforme classificate per supporto scraper (già supportato vs. nuovo)

## ❓ Domande aperte

1. **Fase 2 timing:** Validare TIER 0 con run test prima di merge? (Sì: aggiunge confidence, ~30 min)
2. **Fase 3 scope:** Se Halley/EGov usano stesso pattern di `halley.py`, aggiungere tutti e 13 comuni? (Dipende da analisi feasibility)
3. **TIER 2 priorità:** I 14 comuni custom/local vanno documentati/implementati in questa card o rimandati a TAL-51?

## 🔬 Tentativi

### 2026-07-10 — Sweep di dominio automatico per comuni Trapani mancanti
**Approccio:** Script Python `sweep_palermo_trapani.py` che testa pattern jCityGov, Halley, portalepa, URBI su slug automatici.
**Esito:** ⚠️ parziale — solo Salaparuta (Halley) trovato, ma era già nel registry E3. Comuni TP top-5 (Castellammare, Petrosino, Pantelleria) non rispondono a pattern noti → serviva ricerca manuale.

**Appreso:** Sweep è efficace solo per piattaforme con pattern domain prevedibile. Per comuni senza pattern (custom/local), serve ricerca web manuale.

### 2026-07-10 — Censimento web sistematico (Palermo 52 + Trapani 9)
**Approccio:** Agente haiku con ricerca Google per ogni comune, identificazione piattaforma via dominio e HTML inspection.
**Esito:** ✅ completo — 77 comuni censiti, 100% copertura, 0 fallimenti (tutti i comuni hanno albo online raggiungibile).

**Appreso:**
- ComuneWeb domina Palermo (29 comuni, 37.7%) — opportunità per scraper centralizzato futuro
- Nessun "buco" di copertura: anche comuni piccolissimi hanno albo (anche se legacy/custom)
- Distribuzione TIER 0/1/2 suggerisce 53% copertura popolazione con TIER 0+1 (211k ab)

### 2026-07-10 — Aggiunta TIER 0 al registry
**Approccio:** Manuale diretta in `scripts/run_scrapers.py`, siguiendo convenzioni E3 (liste `_JCITYGOV_COMUNI`, `_PORTALEPA_COMUNI`, `_URBI_COMUNI`).
**Esito:** ✅ 8 comuni aggiunti (jCityGov 2, portalepa 6, URBI 1; altri 3 già registrati). Syntax OK, nessun conflitto.

**Appreso:** Registry è facile da estendere — ogni piattaforma ha una lista di tuple nominate, aggiunta è ~3 righe per comune. Nessun codice nuovo richiesto.

## 📝 Note permanenti

- `censimento_albi_pa_tp.csv` è la source of truth per comuni Palermo/Trapani
- Nessun comune è "irraggiungibile" — tutti hanno albo online (alcuni legacy, ma funzionanti)
- TIER 2 (custom/local, 14 comuni) probabilmente non vale lo sforzo di reverse-engineering salvo se richiesto esplicitamente
- ComuneWeb (29 comuni, 37.7% di PA+TP) è il candidato più promettente per scraper futuro se coverage aumenta

## 🔗 Dipendenze

- E3 (TAL-49): completato ✅ — questo branch parte da E3 e non ha conflitti
- Nessun blocking su altri task

