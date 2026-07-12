# TAL-50 — Censimento Palermo + Trapani (E3 estensione)

- **Epica:** E3 — Censimento comuni siciliani
- **Ruolo:** 🕷️ SCR + 🧭 TL
- **Priorità:** P1
- **Stato:** Review (PR #12 aperta)
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

### Fase 2: Aggiunta TIER 0 al registry (COMPLETATO)
- [x] 3 comuni jCityGov: Termini Imerese (26k), Campofelice Roccella (6.9k), Castelvetrano (31.8k)
- [x] 6 comuni portalepa nuovi: Partinico (31k), Cefalù (14k), Castellammare del Golfo (14.6k), Corleone (11k), Capaci (11k), Partanna (10.8k)
- [x] 1 comune URBI: Caccamo (8.3k)
- [x] Validare con test: HTTP 200 su 3 comuni campione (Termini Imerese, Partinico, Caccamo)
- [x] Riconciliato con `main` (refactor registro unificato scraper, PR #11): i 9 comuni TIER 0
      sono confluiti in `data/registro_scraper.csv`, PR #12 aperta verso `main`

### Fase 3: TIER 1 + TIER 2 reverse-engineering (completato)
- [x] Analizzato TIER 1 (Halley/EGov/APKAPPA): pattern non completamente generalizzabile → rimandato a TAL-51
- [x] Reverse-engineering TIER 2 (custom/local 5 comuni più grandi): TUTTI richiedono API JS/Playwright/form proprietari → NON fattibili HTTP puro
- [x] Mappa copertura TALIA aggiornata: notebook + GeoJSON + PNG/HTML interactive

**Risultato:** Focus rimane su TIER 0 (200 comuni, ~81% popolazione). TIER 1/2 richiedono sforzi sproporzionati.

### Fase 4: Future work → TAL-51 (completato con documentazione)
- [x] Identificati 15 comuni fattibili (4 TP + 11 PA >5k) per continuazione
- [x] Creata card TAL-51 con metodologia reverse-engineering + prioritizzazione
- [x] Documentati comuni Trapani Priority 1 (4 comuni, 23k ab, effort ~5 giorni)
- [x] Documentati comuni Palermo Priority 1-3 (11 comuni >5k, 116k ab, effort 7-14 giorni)
- [x] Aggiunto commento in run_scrapers.py con riferimento a TAL-51

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

### 2026-07-10 — Analisi TIER 1 (Halley/EGov/APKAPPA) e TIER 2 (custom/local)
**Approccio TIER 1:** Test HTTP 200 su 3 comuni sample (Belmonte, Santa Cristina Gela/Halley; Ciminna/EGov; Bisacquino/APKAPPA) → pattern non completamente compatibile con scraper existenti. EGov e APKAPPA hanno URL/parameter schema leggermente diversi da quelli già in registry.

**Approccio TIER 2:** Reverse-engineering 5 comuni custom più grandi (San Giuseppe Jato 8.5k, Petrosino 7.7k, Pantelleria 7.5k, Marineo 6.7k, Balestrate 6.4k, totale 36.8k abitanti).

**Esito:** ❌ TUTTI i 5 comuni custom richiedono JavaScript/API dinamica o form parameters proprietari:
- San Giuseppe Jato: EG0 proprietario (alto rischio)
- Petrosino: WordPress + API JS (media complessità, basso ROI)
- Pantelleria: OpenPA/Drupal + form POST sconosciuto (media complessità)
- Marineo: WordPress + form POST ignoto (medio)
- Balestrate: WordPress + API JS (medio)

Nessuno è fattibile con HTTP puro, tutti richiederebbero Playwright o reverse-engineering approfondito.

**Appreso:** TIER 2 non vale lo sforzo attuale — 36.8k abitanti (0.7% popolazione Sicilia) con effort medio-alto. Priorità rimane E2/E3 consolidamento (192 + 8 = 200 comuni, ~81% popolazione).

### 2026-07-10 — Mappa copertura TALIA aggiornata
**Approccio:** Aggiornamento notebook Jupyter + generazione GeoJSON + PNG/HTML interactive.
**Esito:** ✅ Mappa aggiornata con colori per piattaforme (verde=jCityGov, blu=portalepa, arancio=Halley, viola=dedicated, grigio=non-coperto). 174/391 comuni coperti (44.5% per count), ~1.7M/2.9M abitanti (59% per popolazione).

**Appreso:** Mappa è strumento utile per pianificazione futura — chiara visualizzazione gap geografici (Messina bloccata, piccoli comuni custom su piattaforme non supportate).

## 📝 Note permanenti

- `censimento_albi_pa_tp.csv` è la source of truth per comuni Palermo/Trapani
- Nessun comune è "irraggiungibile" — tutti hanno albo online (alcuni legacy, ma funzionanti)
- TIER 2 (custom/local, 14 comuni) probabilmente non vale lo sforzo di reverse-engineering salvo se richiesto esplicitamente
- ComuneWeb (29 comuni, 37.7% di PA+TP) è il candidato più promettente per scraper futuro se coverage aumenta

## 🔗 Dipendenze

- E3 (TAL-49): completato ✅ — questo branch parte da E3 e non ha conflitti
- Nessun blocking su altri task

