# 03 — Architettura AWS

> Come portare TALIA su cloud: servizi, pipeline, costi, diagrammi.
> Branch: `analisi-kiro` | Data: 2026-06-28

---

## 1. Visione: da script locale a piattaforma cloud

Oggi TALIA è uno script Python che gira su un laptop. Per diventare un prodotto:
- Deve girare **H24** (scraping continuo)
- Deve servire **utenti concorrenti** (dashboard + analisi on-demand)
- Deve **scalare** da 50 a 391 comuni senza intervento manuale
- Deve costare il **minimo possibile** (progetto civico, non enterprise)

**Strategia: serverless-first** — paghi solo l'uso effettivo, zero costi quando idle.

---

## 2. Diagramma architetturale

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              AWS CLOUD                                        │
│                                                                              │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────────┐    │
│  │ CloudFront   │────▶│ S3 (static)  │     │  Amazon RDS PostgreSQL   │    │
│  │ (CDN + WAF)  │     │ Frontend SPA │     │  (db.t4g.micro — free)   │    │
│  └──────┬───────┘     └──────────────┘     └──────────┬───────────────┘    │
│         │                                              │                    │
│         ▼                                              │                    │
│  ┌──────────────┐     ┌──────────────┐                │                    │
│  │ API Gateway  │────▶│ Lambda       │────────────────┘                    │
│  │ (REST/HTTP)  │     │ (analisi +   │                                     │
│  └──────────────┘     │  query)      │──┐                                  │
│                       └──────────────┘  │                                  │
│                                         ▼                                   │
│  ┌──────────────────────────────────────────────┐                          │
│  │           EventBridge Scheduler               │                          │
│  │  (cron: scraping ogni 6h / red flags ogni 24h)│                          │
│  └──────────┬───────────────────────┬────────────┘                          │
│             │                       │                                       │
│             ▼                       ▼                                       │
│  ┌──────────────┐        ┌──────────────┐     ┌──────────────┐            │
│  │ Lambda       │        │ Lambda       │     │ S3 (data)    │            │
│  │ (spider)     │───────▶│ (red flags)  │     │ PDF + report │            │
│  └──────┬───────┘        └──────────────┘     └──────────────┘            │
│         │                                                                   │
│         ▼                                                                   │
│  ┌──────────────┐     ┌──────────────┐                                    │
│  │ SQS (queue)  │────▶│ Lambda       │  ← OCR pesante: Step Functions      │
│  │ atti da OCR  │     │ (OCR worker) │    per PDF > 10 pagine              │
│  └──────────────┘     └──────────────┘                                    │
│                                                                              │
│  ┌──────────────┐                                                           │
│  │ Bedrock      │  ← Check LLM: invocato SOLO su atti già flaggati          │
│  │ (Claude/     │    (filtro a imbuto: ~5% del totale)                      │
│  │  Mistral)    │                                                           │
│  └──────────────┘                                                           │
│                                                                              │
│  ┌──────────────┐     ┌──────────────┐                                    │
│  │ CloudWatch   │     │ SNS          │  ← Alert se spider fallisce          │
│  │ (logs+metrics)│    │ (notifiche)  │    o nuovi 🔴 rilevati              │
│  └──────────────┘     └──────────────┘                                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Servizi AWS — dettaglio componenti

### 3.1 Frontend & Delivery

| Servizio | Ruolo | Perché |
|----------|-------|--------|
| **S3** | Hosting SPA (React/Vue) + PDF/report archiviati | Costo ~$0.02/GB/mese |
| **CloudFront** | CDN + HTTPS + WAF | Latency bassa, DDoS protection inclusa |
| **Route 53** | DNS (opzionale) | Se serve dominio custom |

### 3.2 Compute — API & Analisi

| Servizio | Ruolo | Perché |
|----------|-------|--------|
| **API Gateway (HTTP)** | Endpoint REST per frontend | Pay-per-request, $1/milione di richieste |
| **Lambda (Python 3.11)** | Analisi fascicolo on-demand + query dashboard | 0 costo quando idle, 15 min max exec |
| **Step Functions** | Orchestrazione OCR pesante (PDF multi-pagina) | Gestisce timeout + retry nativamente |

**Lambda sizing per TALIA:**
- `analisi-fascicolo`: 1024 MB RAM, 60 sec timeout (PDF nativi), 300 sec (OCR)
- `query-dashboard`: 256 MB RAM, 10 sec timeout
- `spider`: 512 MB RAM, 300 sec timeout
- `red-flags-batch`: 512 MB RAM, 60 sec timeout

### 3.3 Scraping & Pipeline

| Servizio | Ruolo | Perché |
|----------|-------|--------|
| **EventBridge Scheduler** | Cron: spider ogni 6h, red flags ogni 24h | Gratis fino a 14M invocazioni/mese |
| **SQS** | Coda atti da processare (OCR, analisi) | Decoupling, retry built-in, DLQ |
| **Lambda (spider)** | Fetch + parsing HTML da albi pretori | Una Lambda per fonte (iCity, ANAC, GURS) |

### 3.4 Storage

| Servizio | Ruolo | Perché |
|----------|-------|--------|
| **RDS PostgreSQL** (db.t4g.micro) | DB relazionale: atti, entità, red flags | 750h/mese free tier, poi ~$13/mese |
| **S3** (bucket dati) | PDF originali + report HTML generati | Costo storage trascurabile |

**Alternativa ultra-low-cost:** Aurora Serverless v2 (0.5 ACU min) — si spegne a 0 quando idle, ma startup ~30 sec.

### 3.5 LLM / AI

| Servizio | Ruolo | Perché |
|----------|-------|--------|
| **Amazon Bedrock** | Check LLM (qualità motivazione) | Pay-per-token, no infra da gestire |
| Modello suggerito | Claude Haiku o Mistral 7B | Buon rapporto costo/qualità per italiano |

**Costo stimato:** con filtro a imbuto (solo ~5% degli atti arriva al LLM) e prompt da ~2000 token:
- 100 atti/giorno flaggati × 2000 token input + 500 output = ~250K token/giorno
- Con Claude Haiku: ~$0.03/giorno = **~$1/mese**

### 3.6 Monitoring & Alerting

| Servizio | Ruolo | Perché |
|----------|-------|--------|
| **CloudWatch** | Log centralizzati + metriche custom | Free tier generoso |
| **SNS** | Alert su email/Slack quando: spider KO, nuovi 🔴 | Costo trascurabile |
| **X-Ray** (opzionale) | Tracing distribuito | Per debug in produzione |

---

## 4. Pipeline di dati — flusso end-to-end

### 4.1 Scraping pipeline (batch, ogni 6 ore)

```
EventBridge (cron)
    │
    ▼
Lambda spider-icity ──────┐
Lambda spider-anac  ──────┼──▶ RDS (tabella atti)
Lambda spider-gurs  ──────┘         │
                                    ▼
                            EventBridge (daily)
                                    │
                                    ▼
                            Lambda red-flags-batch
                                    │
                                    ▼
                            RDS (tabella red_flags)
                                    │
                                    ▼ (se severity = alta)
                            SNS → email alert
```

### 4.2 Analisi on-demand (sincrona, user-triggered)

```
Utente carica PDF
    │
    ▼
Frontend (S3 + CloudFront)
    │
    ▼ (upload PDF a S3 presigned URL)
API Gateway
    │
    ▼
Lambda analisi-fascicolo
    ├── estrai_testo (nativo → OK in Lambda)
    ├── estrai_testo (OCR → Step Functions se > 10 pagine)
    ├── estrai_entita
    ├── esegui_checklist
    ├── [opzionale] Bedrock per check-3 LLM
    └── genera report
    │
    ▼
S3 (report HTML/JSON) + risposta API
```

### 4.3 Dashboard (lettura, real-time)

```
Frontend → API Gateway → Lambda query → RDS (read replica opzionale)
```

---

## 5. CI/CD — Pipeline di deploy

```
GitHub (push/merge)
    │
    ▼
GitHub Actions
    ├── lint + test (esistente)
    ├── build Lambda packages (zip/container)
    ├── deploy con AWS CDK / SAM
    └── smoke test post-deploy
```

**Strumento IaC suggerito:** AWS CDK (Python) — coerente con lo stack TALIA.

---

## 6. Stima costi mensili

### Scenario A: Sviluppo / Prototipo (< 50 comuni)

| Servizio | Costo stimato |
|----------|---------------|
| Lambda (tutte le funzioni) | $0 (free tier: 1M req + 400K GB-sec) |
| API Gateway | $0 (free tier: 1M req) |
| RDS db.t4g.micro (750h free) | $0 (primo anno) → $13/mese dopo |
| S3 (< 5 GB) | < $0.15 |
| CloudFront (< 1 TB) | $0 (free tier) |
| Bedrock (LLM, ~100 atti/giorno) | ~$1 |
| EventBridge | $0 |
| **TOTALE primo anno** | **~$1-2/mese** |
| **TOTALE dopo free tier** | **~$15-20/mese** |

### Scenario B: Produzione (391 comuni, ~1000 atti/giorno)

| Servizio | Costo stimato |
|----------|---------------|
| Lambda | ~$5/mese (3M req + compute) |
| API Gateway | ~$3.50 |
| RDS db.t4g.small (24/7) | ~$25/mese |
| S3 (~50 GB PDF + report) | ~$1.50 |
| CloudFront | ~$5 |
| Bedrock (LLM, ~500 atti/giorno flaggati) | ~$5 |
| CloudWatch | ~$5 |
| **TOTALE** | **~$50-60/mese** |

**Nota:** Con crediti AWS per progetti civici/accademici (AWS Activate, cloud credits for research), il costo effettivo potrebbe essere $0 per 1-2 anni.

---

## 7. Sicurezza cloud

| Layer | Implementazione |
|-------|----------------|
| Autenticazione utenti | Amazon Cognito (free tier: 50K utenti) |
| Autorizzazione API | JWT via Cognito + API Gateway authorizer |
| Encryption at rest | RDS + S3 encryption di default |
| Encryption in transit | HTTPS everywhere (CloudFront + API GW) |
| WAF | AWS WAF su CloudFront (rate limiting, geo-blocking) |
| Secrets | AWS Secrets Manager (chiavi LLM, DB credentials) |
| Network | Lambda in VPC privato per accesso RDS |
| Audit | CloudTrail per tutte le API call |

---

## 8. Scalabilità — da 50 a 391 comuni

| Dimensione | Bottleneck | Soluzione |
|------------|-----------|-----------|
| 50 comuni | Nessuno | Setup base |
| 100 comuni | Lambda concurrency | Increase reserved concurrency |
| 200 comuni | RDS connections | RDS Proxy |
| 391 comuni | Spider duration | Parallelismo: 1 Lambda per comune |
| 391 × storico | RDS storage | Scale storage (GP3, auto-scaling) |

**Lambda concurrency per spider:** 391 comuni × 1 invocazione/6h = ~65 invocazioni simultanee max → ben dentro i limiti default (1000).

---

## 9. Alternativa: Container (ECS Fargate)

Se Lambda risulta limitante (timeout 15 min per OCR pesante):

```
ECS Fargate (spot)
├── Task spider (scraping batch) — 0.25 vCPU, 512 MB — spot: ~$3/mese
├── Task OCR (PDF pesanti) — 1 vCPU, 2 GB — spot: ~$10/mese
└── Task API (dashboard + analisi) — 0.5 vCPU, 1 GB — ~$15/mese
```

**Quando preferire Fargate:**
- PDF con > 50 pagine (OCR > 15 min)
- Spider che richiedono sessioni lunghe (login, paginazione complessa)
- Se serve GPU per LLM locale (→ usare `g5.xlarge` EC2 spot)

---

## 10. Piano di migrazione (step incrementali)

### Fase 1 — Database in cloud (settimana 1)
- Creare RDS PostgreSQL (free tier)
- Migrare schema con Alembic
- Testare spider locali → RDS remoto

### Fase 2 — Spider in Lambda (settimana 2-3)
- Pacchettizzare spider come Lambda
- EventBridge scheduler per cron
- SQS per retry/DLQ

### Fase 3 — API + Frontend (settimana 3-4)
- Lambda per analisi on-demand + query dashboard
- API Gateway
- Frontend SPA su S3 + CloudFront

### Fase 4 — LLM + Monitoring (settimana 5-6)
- Integrazione Bedrock per check-3
- CloudWatch dashboard
- SNS alert

---

## 11. IaC — Struttura CDK suggerita

```
infra/
├── app.py                    # entry point CDK
├── stacks/
│   ├── database_stack.py     # RDS + security group
│   ├── storage_stack.py      # S3 buckets
│   ├── api_stack.py          # API Gateway + Lambda (analisi + query)
│   ├── scraping_stack.py     # Lambda spider + EventBridge + SQS
│   ├── frontend_stack.py     # S3 + CloudFront
│   └── monitoring_stack.py   # CloudWatch + SNS
└── requirements.txt          # aws-cdk-lib
```
