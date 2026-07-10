# TAL-51 — Scraper comuni Palermo/Trapani (TIER 1 + Trapani custom)

- **Epica:** E3 — Censimento comuni siciliani
- **Ruolo:** 🕷️ SCR + 🧭 TL
- **Priorità:** P2
- **Stato:** Backlog
- **Branch:** (futuro, partire da E3)

## 🎯 Obiettivo

Implementare scraper HTTP puro per 15 comuni Palermo/Trapani rimasti dopo TAL-50, divisi in 3 priorità di effort/ROI.

## 📚 Contesto

Sessione TAL-50 (2026-07-10) ha completato censimento PA/TP al 100% (107 comuni, ~4M abitanti), ma ha aggiunto al registry solo 9 comuni TIER 0 (già su piattaforme supportate jCityGov/portalepa/URBI). Restano 45 comuni non nel registry:
- **Trapani:** 4 comuni mancanti (Petrosino 7.7k, Pantelleria 7.5k, Calatafimi 6.7k, Poggioreale 1.5k) — tutti su piattaforme custom/WordPress
- **Palermo:** 41 comuni mancanti, di cui 11 >5k abitanti su varie piattaforme (ComuneWeb 6, Halley 1, HyperSIC 1, APKAPPA 1, SaturnWeb 1, custom 1)

## 📋 Spec

### Trapani (Priority 1 — Fast Path, ~5 giorni dev, ROI ★★★★★)

**4 comuni, 23k abitanti, 100% coverage Trapani.**

Reverse-engineering TAL-50 ha rivelato:
- **Petrosino (7.7k):** WordPress + div-grid pattern → scraper semplice
- **Pantelleria (7.5k):** HyperSIC/Drupal form-based → scraper hypernic.py
- **Calatafimi-Segesta (6.7k):** HyperSIC → scraper hypernic.py
- **Poggioreale (1.5k):** HyperSIC → scraper hypernic.py

**Output:** Nuovi moduli `wordpress-pa.py` (1 comune) e generalizzazione `hypernic.py` (3 comuni).

### Palermo >5k (Priority 2 — Medium effort, ~7 giorni, ROI ★★★★)

**11 comuni, 116k abitanti.**

Breakdown per piattaforma:
- **ComuneWeb (5+1 Piana degli Albanesi):** Ficarazzi, Santa Flavia, Trabia, Altofonte, Borgetto, Piana degli Albanesi (6 comuni, 60k ab)
  - Status: 5/6 HTTP 200 (Piana fail DNS)
  - Rischio: potrebbe essere SPA con API — verificare prima
  
- **Halley (1):** Belmonte Mezzagno (11.1k)
  - Status: DNS fail (ricerca WHOIS/contatto IT)
  
- **HyperSIC (1):** Altavilla Milicia (7.4k)
  - Status: DNS fail
  
- **APKAPPA (1):** Bisacquino (4.8k — sotto soglia, incluso per completezza)
  - Status: HTTP 200, pattern `albo.apkappa.it` generico
  
- **SaturnWeb (1):** Casteldaccia (10.8k)
  - Status: DNS fail

### Palermo <5k (Priority 3 — Low effort, ~5 giorni, ROI ★★)

**30 comuni piccolissimi, ~40k abitanti.**

Tutti su piattaforme custom/legacy (ComuneWeb variante, WordPress, EG0 proprietario, ecc.). Basso ROI (popolazione sparsa), alto effort per reverse-engineering.

## ✅ Task

### Fase 1 — Trapani Priority 1 (assegnare a scaper engineer)
- [ ] Implementare `wordpress-pa.py` generico per Petrosino (template: analizza div-grid pattern)
- [ ] Generalizzare `hypernic.py` per 3 comuni TP (Pantelleria, Calatafimi, Poggioreale)
- [ ] Aggiungere al registry (`scripts/run_scrapers.py`)
- [ ] 4-5 test per ogni scraper (fixture HTML reale)
- [ ] Merge su E3 + PR

**Outcome:** Trapani 100% coverage (25 comuni), +23k abitanti.

### Fase 2 — Palermo ComuneWeb (se prioritario)
- [ ] Verificare se ComuneWeb è SPA/API o HTML statico
- [ ] Se HTML: implementare `comuneweb.py` generico
- [ ] Se SPA: valutare Playwright vs. reverse-engineering API
- [ ] Aggiungere 6 comuni al registry

**Outcome:** +60k abitanti Palermo.

### Fase 3 — Palermo Halley/HyperSIC/APKAPPA/SaturnWeb (se tempo)
- [ ] Verificare accesso WHOIS/DNS per Belmonte, Altavilla, Casteldaccia
- [ ] Test scraper esistenti (halley.py, hspromila.py, apkappa.py) su questi comuni
- [ ] Se non funzionano: debug URL pattern

**Outcome:** +29k abitanti Palermo.

## 🔬 Metodologia reverse-engineering (nota per TAL-51+)

**Processo usato in TAL-50 per scoprire scraper fattibili:**

1. **Censimento web:** Google "albo pretorio [nome comune]" → raccogliere URL
2. **Test HTTP GET base URL:**
   ```bash
   curl -s -m 5 "https://[url]" | head -50
   ```
3. **Pattern matching su HTML:**
   - `<table>` → tabella HTML strutturata
   - `href.*albo` → link a pagina albo
   - `<form>` → form POST (potrebbe richiedere parametri)
   - `fetch()` / `XMLHttpRequest` → API JS (richiede Playwright)
4. **Complessità:**
   - **Basso:** table statica + `<tr>` per atti → regex semplice
   - **Medio:** form POST + parametri noti → HTTP client + form builder
   - **Alto:** API JSON/GraphQL → reverse-engineering endpoint, pagination
   - **Bloccante:** Playwright obbligatorio (rendering JS), certificati scaduti, WAF
5. **Criteri decisione:**
   - Se HTTP 200 + HTML statico → **implementare**
   - Se HTTP 200 + form sconosciuto → **investigazione WHOIS/contatto**
   - Se DNS fail / cert scaduto → **contatto IT del comune**
   - Se JS obbligatorio → **valutare Playwright se ROI > effort**

## ❓ Domande aperte

1. **ComuneWeb è SPA?** Verificare Ficarazzi/Borgetto con DevTools — se è API, decider per SPA (basso ROI) vs Playwright (medio ROI).
2. **Halley Belmonte — accesso reale?** Verificare WHOIS: potrebbe essere DNS fail falsa, o accesso limitato.
3. **SaturnWeb Casteldaccia — proprietario o generico?** Se generico, potrebbe avere 2-3 altri comuni su Sicilia.
4. **ComuneWeb 30 comuni <5k — worth it?** ROI basso, suggest skip se timeline stretta.

## 🔗 Dipendenze

- TAL-50 completato ✅ (censimento, documentazione, mappa)
- E3 (feat/E3-censimento-comuni-sicilia) — merge atteso

## 📝 Note metodologiche

**Lezione TAL-50:**
- Sweep automatico pattern identici (jCityGov, portalepa, Halley, URBI) funziona bene → 192 comuni +8 TAL-50
- Comuni custom/legacy richiedono ricerca manuale → 45 comuni rimasti
- SSL/cert issues e DNS fail sono più comuni di quanto previsto → contatto IT spesso necessario
- ComuneWeb dominante su PA (29% dei comuni non coperti) → opportunità scraper centralizzato se ROI giustificato

**Tool consigliati:**
- `curl -s -m 5 [url]` per test HTTP rapidi
- Firefox DevTools (Network tab) per API discovery
- WHOIS per diagnostica DNS
- Email a comuni per accesso/troubleshooting

