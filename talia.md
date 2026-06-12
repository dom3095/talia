# TALIA — Trasparenza Atti Locali: Indicatori e Analisi

> *Taliàri* (sic.): guardare, osservare. **Talia!** = "Guarda!"

Strumento civico open source per l'analisi di atti delle Pubbliche Amministrazioni siciliane.
Rileva **red flags** (anomalie e possibili criticità normative) negli atti pubblici — gare, concorsi,
delibere, revoche e annullamenti — **senza emettere giudizi**: ogni segnalazione è esplicabile,
verificabile e collegata al documento originale.

---

## 1. Visione e principi

- **Segnalare, non giudicare.** Output = red flags da verificare, mai accuse o verdetti.
- **Esplicabilità totale.** Ogni indicatore è cliccabile fino all'atto pubblico che lo ha generato.
- **Simmetria.** Si evidenziano anche i procedimenti e i comuni *virtuosi*, non solo le criticità.
- **Prudenza sui dati personali.** Aggregazione/anonimizzazione nelle viste pubbliche; il dettaglio
  nominativo resta per usi interni o autorità competenti. Attenzione ai piccoli comuni dove i
  soggetti sono identificabilissimi.
- **Budget ≈ 0.** Stack gratuito/open source, regole deterministiche prima degli LLM, scope piccolo
  e verificabile, crescita tramite open source / università / civic tech.

## 2. Architettura — tre moduli, un motore

```
            ┌─────────────────────────────────────────────┐
            │           MOTORE DI ANALISI COMUNE           │
            │  OCR (Tesseract) → estrazione testo PDF      │
            │  Estrazione entità: date, importi, CIG,      │
            │  firmatari, norme citate (regex + spaCy)     │
            │  Checklist deterministiche (regole/SQL)      │
            │  RAG normativo + LLM (solo casi filtrati)    │
            └───────┬──────────────┬──────────────┬────────┘
                    │              │              │
        ┌───────────▼───┐  ┌───────▼───────┐  ┌──▼───────────────┐
        │ MODULO 1      │  │ MODULO 2      │  │ MODULO 3         │
        │ Analisi       │  │ Scraping      │  │ Dashboard        │
        │ fascicolo     │  │ continuo      │  │ aggregata        │
        │ on-demand     │  │ (batch)       │  │ per comune       │
        └───────────────┘  └───────────────┘  └──────────────────┘
```

### Modulo 1 — Analisi fascicolo on-demand (PRIORITÀ 1)
L'utente carica un fascicolo (es. delibera di indizione concorso + atto di annullamento) e
ottiene un report strutturato: check verde/giallo/rosso, passaggio testuale citato, norma o
giurisprudenza di riferimento, disclaimer.

### Modulo 2 — Pipeline di scraping
Raccolta continua degli atti pubblicati (albi pretori, ANAC, GURS, UREGA) per alimentare lo
storico e le statistiche. Parte da **un solo software di albo pretorio** o una sola provincia.

### Modulo 3 — Dashboard per comune
Aggregazioni dei risultati: indici, trend, confronti tra pari (comuni di taglia simile), drill-down
fino al documento sorgente.

## 3. Checklist Modulo 1 — caso revoca/annullamento (concorsi e gare)

| # | Check | Metodo | Red flag se… |
|---|-------|--------|--------------|
| 1 | Base giuridica dichiarata | regex su "21-quinquies" / "21-nonies" (L. 241/90) | assente, o istituto incoerente con la motivazione (revoca ≠ annullamento) |
| 2 | Termini dell'autotutela | estrazione date atto originario / atto di annullamento | annullamento d'ufficio oltre **12 mesi** dall'atto |
| 3 | Qualità della motivazione | LLM: specifica vs boilerplate; densità; requisiti giurisprudenziali (interesse pubblico concreto e attuale, comparazione con affidamenti dei privati) | motivazione generica, di poche righe, mero "ripristino di legalità" |
| 4 | Violazione autodichiarata | LLM/NER: estrazione e classificazione dell'illegittimità dichiarata nell'atto | — (non è red flag: è dato prezioso per le statistiche) |
| 5 | Comunicazione avvio procedimento (art. 7 L. 241) | ricerca menzione nell'atto | assente nei confronti dei partecipanti |
| 6 | Coerenza firmatari | confronto firmatari indizione vs annullamento | stesso dirigente che si auto-annulla a ridosso della graduatoria |
| 7 | Follow-up | collegamento con atti successivi (scraping) | ribandito con requisiti modificati in modo mirato; riaffidamento a soggetto diverso dopo revoca |

## 4. Red flags batch (regole deterministiche, no LLM)

- **Frazionamento artificioso**: affidamenti diretti ripetuti sotto soglia, stesso oggetto/fornitore.
- **Concentrazione**: stesso fornitore ricorrente, specialmente con lo stesso RUP; gare a offerente unico.
- **Tempi anomali**: finestre di pubblicazione bandi anormalmente brevi.
- **Catene di proroghe** contrattuali; **varianti** che gonfiano l'importo oltre soglia.
- **Revoche ricorrenti** seguite da riaffidamento.
- **Somma urgenza / emergenza** usata sistematicamente (dissesto, rifiuti) per bypassare le gare.
- **Fondi a scadenza** (PNRR, PO-FESR): concentrazione di affidamenti diretti.
- **Trasparenza**: mancata/tardiva pubblicazione obbligatoria (D.lgs. 33/2013) — oggettiva e misurabile.
- **Antimafia (specifico Sicilia)**: imprese interdette che ricompaiono con altra ragione sociale o nei subappalti.

## 5. Corpus normativo (approccio RAG, non fine-tuning: le norme cambiano)

**Nazionale**
- D.lgs. 36/2023 — Codice contratti pubblici (+ correttivi)
- L. 241/1990 — procedimento amministrativo (artt. 7, 21-quinquies, 21-nonies)
- L. 190/2012 — anticorruzione; PTPCT
- D.lgs. 33/2013 — trasparenza
- GDPR + Codice privacy (dati personali pubblicati per errore negli atti)
- D.lgs. 39/2013 e art. 6-bis L. 241 — conflitti d'interesse, inconferibilità

**Sicilia (statuto speciale)**
- Leggi regionali di recepimento del Codice appalti (verificare stato recepimento D.lgs. 36/2023; storicamente L.R. 12/2011 e ss.)
- L.R. 7/2019 — procedimento amministrativo regionale
- Disciplina **UREGA** (gare centralizzate sopra soglia)
- Normativa antimafia: protocolli di legalità, white list, interdittive
- Giurisprudenza: **CGA** (Consiglio di Giustizia Amministrativa), TAR Palermo, TAR Catania

## 6. Fonti dati (tutte pubbliche e gratuite)

| Fonte | Contenuto | Note |
|-------|-----------|------|
| Albi pretori dei 391 comuni siciliani | delibere, determine, bandi | pochi fornitori software → 4-5 scraper coprono gran parte della regione |
| Amministrazione Trasparente | struttura standardizzata per legge | ottima per scraping |
| ANAC / BDNCP | CIG, aggiudicazioni, varianti | filtrare per codice ISTAT regione 19 |
| GURS | Gazzetta Ufficiale Regione Siciliana | |
| UREGA | gare centralizzate | punto di osservazione unico |
| giustizia-amministrativa.it | sentenze TAR PA/CT e CGA | **ground truth**: atti effettivamente annullati |
| OpenCUP, OpenCoesione, SIOPE | parte finanziaria | |
| Liberi Consorzi / Città Metropolitane | atti ex province | spesso le meno trasparenti |

**Dataset etichettati "gratis"**: atti dei comuni sciolti per infiltrazione mafiosa e sentenze di
annullamento → esempi reali di "atti che hanno preceduto un problema accertato" per derivare
indicatori statistici difendibili.

## 7. Stack a budget zero

| Componente | Scelta | Costo |
|------------|--------|-------|
| Scraping | Python + Scrapy/BeautifulSoup, cron su GitHub Actions | 0 |
| Storage | SQLite → Postgres free tier (Supabase/Neon) | 0 |
| OCR | Tesseract (molti atti sono scansioni!) | 0 |
| NER/estrazione | regex + spaCy | 0 |
| LLM | filtro a imbuto: regole prima, LLM **solo** su documenti già flaggati e solo per il check "motivazione"; modelli open locali (Llama/Mistral/Qwen) o Colab | ~0 |
| Dashboard | Streamlit / Datasette | 0 |
| Hosting | GitHub Pages / Streamlit Cloud / HF Spaces | 0 |

**Principio**: il 95% dei controlli è regex + SQL. L'LLM è l'eccezione, non la regola.

## 8. Roadmap

1. **Prototipo Modulo 1**: script che prende 2-3 PDF (indizione + annullamento) e produce il
   report con la checklist §3. Validare su ~10 fascicoli reali.
2. **Scraper pilota**: un solo software di albo pretorio (il più diffuso) o una sola provincia.
3. **Dashboard Streamlit** sui dati pilota.
4. Scalare ai 391 comuni; arricchire indicatori con il ground truth giurisprudenziale.
5. Crescita: open source su GitHub, community civic tech (OpenPolis, onData), tesi universitarie,
   crediti cloud per progetti civici, collaborazioni con testate locali.

## 9. Avvertenze legali e di posizionamento

- Disclaimer ovunque: **segnalazioni da verificare, non accertamenti**.
- Mai punteggi senza link alla fonte (rischio diffamazione).
- Anonimizzare le viste pubbliche nei piccoli comuni.
- Posizionamento: *strumento di trasparenza*, non "cacciatore di corrotti" — apre le porte delle
  PA virtuose invece di chiuderle.
