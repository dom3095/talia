# 05 — Presentazione TALIA

> Cosa fa, perché è valida, come proporla, potenzialità e impatti.
> Branch: `analisi-kiro` | Data: 2026-06-28

---

## 1. Cosa fa TALIA — in sintesi

TALIA è un **sistema automatico di analisi degli atti pubblici** delle Pubbliche Amministrazioni siciliane. Legge delibere, bandi, determine, revoche e annullamenti — e segnala anomalie procedurali verificabili.

### Il problema che risolve

Gli atti delle PA sono pubblici per legge, ma **nessuno li legge sistematicamente**. Un comune può annullare un concorso dopo 14 mesi con una motivazione generica di 2 righe, e nessuno se ne accorge — tranne chi ha perso il posto.

### Come funziona (pipeline)

```
PDF/scansione atto pubblico
    │
    ▼  OCR (Tesseract) se scansione
Testo estratto
    │
    ▼  Regex + NLP
Entità: date, firmatari, importi, CIG, norme citate
    │
    ▼  Checklist deterministica (regole + SQL)
Semafori: 🟢 conforme  🟡 da verificare  🔴 anomalia
    │
    ▼  [Solo su atti già flaggati] LLM per analisi semantica
Report esplicabile: ogni flag → passaggio testuale → norma violata
```

### Esempio concreto

Input: un bando di concorso + il suo annullamento d'ufficio.

Output:
- 🔴 **Termini superati** — annullamento dopo 14 mesi (max 12, art. 21-nonies L. 241/90)
- 🔴 **Base giuridica incoerente** — cita revoca (21-quinquies) ma descrive illegittimità
- 🟡 **Comunicazione avvio** — nessuna menzione art. 7 ai partecipanti
- 🟢 **Firmatari coerenti** — dirigenti diversi per indizione e annullamento

Ogni segnalazione è linkata al passaggio esatto del documento sorgente.

---

## 2. Quanto è valida come idea

### Forza dell'idea: 9/10

| Criterio | Valutazione |
|----------|-------------|
| **Problema reale** | ✅ La corruzione/inefficienza nella PA costa miliardi. I dati esistono, nessuno li analizza |
| **Timing** | ✅ PNRR ha riversato miliardi su piccoli comuni con zero controlli automatici |
| **Competitor** | ✅ Nessun competitor diretto. OpenPolis lavora a livello macro, non sui singoli atti |
| **Scalabilità** | ✅ Da 1 comune a 391 (Sicilia) → 7.900+ (Italia) → Europa |
| **Difendibilità** | ✅ Il corpus normativo italiano è una barriera d'ingresso (servono competenze giuridiche + tech) |
| **Budget** | ✅ Stack a costo quasi zero, dati pubblici, open source |
| **Impatto sociale** | ✅ Trasparenza, legalità, cittadinanza attiva — temi con forte supporto istituzionale |

### Perché proprio adesso

- **PNRR** (2021-2026): miliardi in affidamenti rapidi → terreno fertile per frazionamento e anomalie
- **D.lgs. 36/2023** (nuovo Codice Appalti): PA in fase di adattamento, molti errori procedurali
- **ANAC** sta spingendo per monitoraggio automatizzato ma non ha risorse per i singoli comuni
- **AI Act EU**: l'approccio "segnalare, non giudicare" è perfettamente compliant

---

## 3. Come proporla a enti e stakeholder

### 3.1 Cloud Computing

**Pitch:**
> "È un caso d'uso reale di architettura serverless end-to-end: data ingestion da fonti pubbliche, processing batch e on-demand, AI/LLM con filtro a imbuto, dashboard interattiva. Budget ~$50/mese per coprire un'intera regione. "

**Leve:**
- Portfolio di competenze cloud completo in un singolo progetto
- Caso d'uso presentabile a clienti (PA, civic tech, media)
- Costo marginale → ROI altissimo anche come investimento formativo
- Potenziale proposta ad AWS come caso d'uso civico (AWS Activate, credit program)

### 3.2 Data Science

**Pitch:**
> "È NLP applicato al dominio giuridico italiano — un campo sottosviluppato con dataset gratuiti (atti pubblici + sentenze TAR come ground truth etichettato). Combina estrazione entità, classificazione documenti, anomaly detection, e LLM su dati reali. Pubblicabile come paper e presentabile a conferenze."

**Leve:**
- Dataset etichettato gratis: sentenze del TAR che annullano atti = labeled data
- Modello predittivo: "questo atto ha le stesse caratteristiche di atti poi dichiarati illegittimi"
- NLP giuridico in italiano è una nicchia con poca competizione accademica
- Applicabile a progetti ANAC, Corte dei Conti, Garante

### 3.3 A enti pubblici / fondazioni

| Ente | Angolo | Cosa chiedere |
|------|--------|---------------|
| **ANAC** | Complemento al loro monitoraggio (loro coprono macro, TALIA il micro) | Partnership dati, validazione |
| **Università (UniPA, UniCT)** | Tesi, paper, ricerca | Tesisti, computing, credibilità |
| **Fondazioni (Ferrara, Cariplo, Compagnia SanPaolo)** | Innovazione civica | Grant €10-50K |
| **OpenPolis / onData** | Civic tech, open data | Community, visibilità, co-sviluppo |
| **Regione Sicilia** | Trasparenza, compliance | Accesso dati, endorsement |
| **Testate giornalistiche** | Data journalism | Uso del tool, visibilità |
| **AWS / Google / Azure** | Caso d'uso civico | Cloud credits (€5-50K) |

### 3.4 Template pitch (30 secondi)

> "TALIA analizza automaticamente gli atti delle PA siciliane — bandi, delibere, revoche — e segnala anomalie procedurali: termini scaduti, motivazioni generiche, frazionamento degli appalti. È open source, costa quasi zero, e non esiste nulla di simile in Italia. Segnala, non giudica: ogni flag è verificabile e linkato al documento originale."

---

## 4. Potenzialità di crescita

### Breve termine (3-6 mesi)
- **391 comuni siciliani** coperti con scraping automatico
- **Dashboard pubblica** consultabile da cittadini e giornalisti
- **10+ red flags** deterministiche attive
- **Check LLM** sulla qualità delle motivazioni

### Medio termine (6-18 mesi)
- **Espansione nazionale**: stesse regole valgono per tutti i 7.900+ comuni italiani
- **API pubblica** per giornalisti e ricercatori
- **Self-audit per PA**: modulo SaaS per funzionari (revenue)
- **Integrazioni**: ANAC, Corte dei Conti, prefetture
- **Paper accademico** su NLP giuridico / anomaly detection nella PA

### Lungo termine (18+ mesi)
- **Modello europeo**: gli obblighi di trasparenza sono simili in tutta l'UE
- **Predittivo**: "questo atto ha l'85% di probabilità di essere annullato dal TAR"
- **Real-time**: segnalazione entro 24h dalla pubblicazione dell'atto
- **Community-driven**: contributor open source, segnalazioni crowdsourced

---

## 5. Sblocchi di miglioramento — cosa fa la differenza

### Sblocco 1: Fascicoli reali validati
**Stato:** 2 fascicoli sintetici. **Serve:** 10-20 reali con validazione di un esperto.
**Impatto:** Passa da "proof of concept" a "strumento credibile". Misura precision/recall.

### Sblocco 2: Check LLM (qualità motivazione)
**Stato:** Non implementato. **Serve:** Integrazione Bedrock/Ollama + prompt engineering.
**Impatto:** Rileva le anomalie più insidiose (motivazioni pretestuose, conflitti mascherati).

### Sblocco 3: Dashboard utente
**Stato:** Solo CLI. **Serve:** Streamlit MVP → poi React.
**Impatto:** Rende il progetto utilizzabile da non-tecnici. Moltiplicatore di audience 100x.

### Sblocco 4: Ground truth (sentenze TAR)
**Stato:** Non implementato. **Serve:** Spider per giustizia-amministrativa.it.
**Impatto:** Labeled data gratuito → model validation → paper pubblicabile.

### Sblocco 5: Deploy cloud
**Stato:** Solo locale. **Serve:** CDK + pipeline CI/CD.
**Impatto:** Da "progetto su un laptop" a "piattaforma H24". Credibilità ×10.

---

## 6. Impatti nel Cloud Computing

| Area | Impatto | Dettaglio |
|------|---------|-----------|
| **Architettura serverless** | Caso d'uso completo | Lambda + Step Functions + EventBridge + SQS |
| **Data pipeline** | Ingestion multi-fonte | Spider → SQS → Processing → DB → Dashboard |
| **IaC** | CDK Python | Tutto il deploy in codice, riproducibile |
| **AI/ML in cloud** | Bedrock + RAG | LLM as a service con filtro a imbuto (costi controllati) |
| **Costi** | Ottimizzazione estrema | $50/mese per coprire un'intera regione — case study di efficienza |
| **Sicurezza** | Zero-trust | Cognito + WAF + encryption + VPC |
| **Scalabilità** | Da 0 a N senza redesign | Serverless scala automaticamente |
| **DevOps** | CI/CD completa | GitHub Actions → CDK deploy → smoke test |

**Valore come portfolio:** Un singolo progetto che dimostra padronanza di 15+ servizi AWS, architettura event-driven, costi controllati, e impatto reale.

---

## 7. Impatti nel Data Science

| Area | Impatto | Dettaglio |
|------|---------|-----------|
| **NLP** | Estrazione entità da testi giuridici italiani | Date, norme, firmatari, importi — dominio sottosviluppato |
| **Anomaly detection** | Pattern statistici su dati strutturati | Frazionamento, concentrazione, tempi — regole interpretabili |
| **Classification** | Classificazione tipo atto e ruolo | Originario vs autotutela — euristica a punteggio pesato |
| **LLM applied** | Valutazione qualitativa di testi | Check motivazione: generico vs specifico vs pretestuoso |
| **RAG** | Retrieval su corpus normativo | Norme + giurisprudenza per contestualizzare i flag |
| **Ground truth** | Sentenze TAR come labeled data | Atti annullati = "veri positivi" gratuiti |
| **Explainability** | AI spiegabile by design | Ogni output è tracciabile al passaggio sorgente |
| **Fairness** | Confronto tra pari | Comuni della stessa fascia demografica — no bias dimensionale |

**Valore come ricerca:** Pubblicabile su conferenze di NLP applicato (CLIC-it, EVALITA) o civic tech (CSCW, CHI). Tesi di laurea/dottorato naturale.

---

## 8. Prossimi passi concreti

1. **Oggi:** Raccogliere 5 fascicoli reali da albi pretori siciliani (sono pubblici, basta scaricarli)
2. **Settimana 1:** Validare i check esistenti sui fascicoli reali, misurare falsi positivi
3. **Settimana 2:** Dashboard Streamlit MVP — rendere il tutto visuale
4. **Settimana 3:** Deploy AWS (RDS + Lambda spider) — il progetto gira H24
5. **Settimana 4:** Demo a stakeholder con dati reali e dashboard funzionante

**Obiettivo a 1 mese:** Una demo viva, su dati reali, deployata in cloud, presentabile a chiunque.
