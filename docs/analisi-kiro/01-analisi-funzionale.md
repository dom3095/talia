# 01 — Analisi Funzionale

> Analisi dei gap funzionali, copertura dei check, priorità di sviluppo.
> Branch: `analisi-kiro` | Data: 2026-06-28

---

## 1. Stato attuale — cosa funziona

### Modulo 1 — Analisi fascicolo on-demand ✅ (80% completato)

Pipeline end-to-end funzionante:
```
PDF/TXT → estrazione testo (nativo + OCR) → entità (regex) → checklist → report
```

**Check implementati (5 su 7 previsti):**

| # | Check | Stato | File |
|---|-------|-------|------|
| 1 | Base giuridica (21-quinquies / 21-nonies) | ✅ Funzionante | `check1_base_giuridica.py` |
| 2 | Termini autotutela (≤ 12 mesi) | ✅ Funzionante | `check2_termini.py` |
| 3 | Qualità motivazione (LLM) | ❌ Non implementato | — |
| 4 | Classificazione violazione autodichiarata | ❌ Non implementato | — |
| 5 | Comunicazione avvio procedimento (art. 7) | ✅ Funzionante | `check5_avvio.py` |
| 6 | Coerenza firmatari | ✅ Funzionante | `check6_firmatari.py` |
| 7 | Data breach GDPR non notificato | ✅ Funzionante | `check7_gdpr.py` |

**Formati di output:** Markdown, JSON, HTML statico — tutti via CLI (`talia analizza`).

### Modulo 2 — Scraping continuo ✅ (70% completato)

| Componente | Stato |
|------------|-------|
| Schema DB (SQLite) + CRUD | ✅ |
| Spider iCity (albi pretori) | ✅ |
| Pipeline ANAC open data | ✅ |
| Red flags batch: frazionamento | ✅ |
| Red flags batch: concentrazione | ✅ |
| Red flags batch: tempi anomali | ✅ |
| Runner unificato | ✅ |

### Modulo 3 — Dashboard ❌ (0%)

Solo `__init__.py` vuoto. Nessuna interfaccia utente.

---

## 2. Gap funzionali critici

### 2.1 Check LLM — qualità motivazione (P1)

**Perché è critico:** È il check con più valore differenziante. Le regole deterministiche catturano violazioni formali; la qualità della motivazione richiede comprensione testuale. Un annullamento con motivazione generica ("ripristino della legalità") è una red flag seria che oggi TALIA non rileva.

**Cosa serve:**
- Modello LLM locale (Mistral/Qwen/Llama) o API
- Prompt engineering specifico per giuridico italiano
- RAG con corpus normativo (L. 241/90, giurisprudenza CGA/TAR)
- Soglia deterministica a monte: il LLM si invoca SOLO se i check 1-2-5-6-7 non hanno già prodotto 🔴

**Rischio:** Senza LLM, TALIA rileva solo violazioni "meccaniche". Le irregolarità più insidiose (motivazione pretestuosa, conflitti mascherati) sfuggono.

### 2.2 Validazione su fascicoli reali (P1)

**Situazione:** Solo 2 fascicoli sintetici in `data/samples/`. Zero fascicoli reali validati da un esperto giuridico.

**Impatto:** Non è possibile misurare:
- Tasso di falsi positivi (check troppo aggressivi)
- Tasso di falsi negativi (anomalie non rilevate)
- Robustezza OCR su scansioni reali

**Azione:** Servono almeno 10-20 fascicoli reali da comuni siciliani (già pubblici negli albi pretori), anonimizzati. Il tuo amico può trovarli come data analyst.

### 2.3 Dashboard utente (P1)

**Nessuna interfaccia visuale.** L'unica interazione è la CLI. Per un prodotto proponibile serve almeno:
- Vista aggregata per comune: quante red flags, di che tipo, trend
- Drill-down: dalla flag → all'atto → al PDF/URL sorgente
- Disclaimer sempre visibile
- Anonimizzazione automatica per comuni piccoli

### 2.4 Fonti dati mancanti

| Fonte prevista in talia.md | Stato |
|----------------------------|-------|
| Albi pretori (iCity) | ✅ Spider fatto |
| ANAC/BDNCP | ✅ Pipeline fatta |
| GURS (Gazzetta Ufficiale Regione Siciliana) | ❌ |
| UREGA (gare centralizzate) | ❌ |
| giustizia-amministrativa.it (sentenze) | ❌ — è il ground truth! |
| OpenCUP / OpenCoesione | ❌ |
| SIOPE (flussi finanziari) | ❌ |
| Amministrazione Trasparente | ❌ |
| Albi pretori non-iCity (altri software) | ❌ |

**Impatto:** Il Modulo 2 copre solo 2 fonti su 9+. Per una visione reale della regione servono almeno GURS, UREGA e le sentenze TAR (ground truth).

### 2.5 Red flags mancanti

Previsti in `talia.md` ma non implementati:

| Red flag | Complessità | Valore |
|----------|-------------|--------|
| Catene di proroghe contrattuali | Media | Alto |
| Varianti che gonfiano oltre soglia | Media | Alto |
| Revoche ricorrenti + riaffidamento | Media | Molto alto |
| Somma urgenza sistematica | Bassa | Alto |
| Fondi PNRR: concentrazione affidamenti diretti | Bassa | Molto alto |
| Mancata/tardiva pubblicazione (D.lgs. 33/2013) | Bassa | Alto |
| Imprese interdette con nuova ragione sociale | Alta | Molto alto |

---

## 3. Matrice priorità/impatto

```
        IMPATTO ALTO                    IMPATTO MEDIO
    ┌───────────────────────────┬──────────────────────────┐
P   │ • Check LLM motivazione  │ • Ground truth sentenze  │
R   │ • Dashboard MVP          │ • Spider GURS/UREGA      │
I   │ • Fascicoli reali        │ • Red flag proroghe      │
O   │                          │ • Red flag PNRR          │
R   ├───────────────────────────┼──────────────────────────┤
I   │ • Architettura AWS       │ • OpenCUP/SIOPE          │
T   │ • Frontend utente        │ • NER con spaCy          │
À   │ • CI/CD avanzata         │ • Antimafia (interditte) │
    │                          │                          │
B   └───────────────────────────┴──────────────────────────┘
A
S
S
A
```

---

## 4. Roadmap proposta (prossimi 3-6 mesi)

### Sprint A — Consolidamento (2-3 settimane)
1. Recuperare 10+ fascicoli reali da albi pretori siciliani
2. Validare i check esistenti (misurare falsi positivi/negativi)
3. Dashboard Streamlit MVP (la TAL-30 già pianificata)

### Sprint B — Intelligence (4-6 settimane)
4. Check LLM: qualità motivazione (TAL-11)
5. RAG con corpus normativo (L. 241/90 + giurisprudenza)
6. Nuovi red flags: proroghe, revoche ricorrenti, PNRR

### Sprint C — Scale-up (6-8 settimane)
7. Architettura AWS (vedi `03-architettura-aws.md`)
8. Spider aggiuntivi (GURS, UREGA, sentenze)
9. Frontend web utente (vedi `04-applicativo-utente.md`)
10. Pipeline di deploy automatizzata

---

## 5. Metriche di successo (KPI)

| Metrica | Target | Come si misura |
|---------|--------|----------------|
| Precision (check) | > 85% | Fascicoli validati da esperto LEX |
| Recall (check) | > 70% | Confronto con sentenze TAR (ground truth) |
| Copertura fonti | ≥ 5 su 9 | Fonti attive nel Modulo 2 |
| Comuni coperti | ≥ 50 (su 391) | DB con atti da ≥ 50 comuni |
| Tempo analisi fascicolo | < 30 sec | Benchmark CI |
| Uptime dashboard | > 99% | Monitoring AWS |

---

## 6. Rischi e dipendenze

| Rischio | Probabilità | Mitigazione |
|---------|-------------|-------------|
| Nessun esperto giuridico nel team | Alta | Coinvolgere docente/praticante diritto amm.vo |
| OCR di bassa qualità su scansioni | Media | Fallback + segnalazione nel report |
| Cambio normativo (D.lgs. 36/2023 correttivi) | Media | RAG aggiornabile, non fine-tuning |
| Resistenza PA alla trasparenza | Bassa | Posizionamento positivo (virtuosi, non solo criticità) |
| Costi cloud in crescita | Media | Serverless + monitoraggio budget |
