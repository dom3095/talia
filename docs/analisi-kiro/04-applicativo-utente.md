# 04 — Applicativo Utente

> Design dell'interfaccia utente, flussi, UX, frontend, implementazione concreta.
> Branch: `analisi-kiro` | Data: 2026-06-28

---

## 1. Visione del prodotto

TALIA deve servire **tre tipologie di utente**:

| Persona | Chi è | Cosa vuole |
|---------|-------|------------|
| **Cittadino** | Giornalista, attivista, consigliere comunale | Capire se gli atti del suo comune hanno anomalie. Vista semplice, aggregata |
| **Analista** | Data analyst, ricercatore, tesista | Esplorare dati, drill-down, esportare, confrontare comuni |
| **Operatore PA** | Funzionario, responsabile trasparenza | Verificare i propri atti prima della pubblicazione (self-audit) |

---

## 2. Funzionalità principali

### 2.1 Analisi fascicolo on-demand

L'utente carica uno o più PDF e riceve il report con la checklist.

**Flusso:**
```
[Upload PDF] → [Attesa analisi 5-30 sec] → [Report interattivo]
                                                    │
                                    ┌───────────────┼────────────────┐
                                    ▼               ▼                ▼
                              Semafori        Citazioni          Download
                              (🟢🟡🔴)       (link al testo)    (PDF/HTML/JSON)
```

**Caratteristiche:**
- Drag & drop di più file (indizione + annullamento)
- Progress bar durante l'analisi
- Report interattivo: click su un check → mostra il passaggio del testo
- Disclaimer sempre visibile in alto
- Download del report in HTML/PDF/JSON
- Nessun login richiesto per l'uso base

### 2.2 Dashboard per comune

Vista aggregata delle red flags rilevate dallo scraping continuo.

**Flusso:**
```
[Mappa Sicilia / Lista comuni] → [Seleziona comune] → [Dashboard dettaglio]
                                                              │
                                           ┌──────────────────┼─────────────┐
                                           ▼                  ▼             ▼
                                     Red flags          Storico        Confronto
                                     attive             temporale      tra pari
```

**Viste:**
1. **Panoramica regionale** — mappa coropletica con indice aggregato per comune
2. **Dettaglio comune** — tabella red flags, trend mensile, top anomalie
3. **Drill-down flag** — dalla red flag → lista atti coinvolti → URL fonte (albo pretorio)
4. **Confronto tra pari** — comuni della stessa fascia demografica
5. **Sezione "virtuosi"** — comuni con zero red flags (posizionamento positivo)

### 2.3 Self-audit per PA

Funzionalità premium/separata: il funzionario verifica il proprio atto PRIMA di pubblicarlo.

**Flusso:**
```
[Login PA] → [Upload bozza atto] → [Report privato] → [Suggerimenti correttivi]
```

**Valore:** Previene le anomalie alla fonte. Può diventare un modello di business (SaaS per PA).

---

## 3. Wireframe — schermate principali

### 3.1 Home page

```
┌─────────────────────────────────────────────────────┐
│  🔍 TALIA — Trasparenza Atti Locali                 │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │                                             │    │
│  │     [Trascina qui i tuoi PDF]              │    │
│  │     oppure clicca per selezionare           │    │
│  │                                             │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  ─── oppure ───                                     │
│                                                     │
│  📊 Esplora la dashboard per comune                 │
│  🗺️ Mappa anomalie Sicilia                         │
│                                                     │
│  ────────────────────────────────────────────────   │
│  ⚠️ Le segnalazioni sono anomalie da verificare,   │
│  non accertamenti. Dettagli legali →                │
└─────────────────────────────────────────────────────┘
```

### 3.2 Report interattivo

```
┌─────────────────────────────────────────────────────┐
│  📋 Report — Fascicolo "Concorso istruttore 2024"  │
│                                                     │
│  ⚠️ Disclaimer: segnalazioni da verificare...       │
│                                                     │
│  Atti: 📄 indizione.pdf (originario, 3 pp.)         │
│        📄 annullamento.pdf (autotutela, 2 pp.)      │
│                                                     │
│  Esiti: 🟢 2  🟡 1  🔴 2  ⚪ 2                      │
│  ─────────────────────────────────────────────────  │
│                                                     │
│  🔴 Base giuridica                    [▼ espandi]   │
│  │  Cita 21-quinquies ma descrive illegittimità     │
│  │  > «...per violazione dell'art. 35-bis...»       │
│  │  Rif: Art. 21-quinquies L. 241/1990             │
│  │                                                  │
│  🔴 Termini autotutela                [▼ espandi]   │
│  │  Annullamento dopo 14 mesi (soglia: 12)          │
│  │  > «Determina n. 45 del 12/03/2023» (p.1)       │
│  │                                                  │
│  🟡 Comunicazione avvio              [▼ espandi]   │
│  │  Nessuna menzione art. 7 — potrebbe essere in    │
│  │  atto separato non fornito                       │
│  │                                                  │
│  🟢 Coerenza firmatari               [▼ espandi]   │
│  🟢 GDPR                             [▼ espandi]   │
│                                                     │
│  [📥 Scarica HTML] [📥 Scarica JSON] [📥 PDF]      │
└─────────────────────────────────────────────────────┘
```

### 3.3 Dashboard comune

```
┌─────────────────────────────────────────────────────┐
│  📊 Comune di Agrigento (pop. 57.000)               │
│                                                     │
│  Red flags attive: 12  │  Ultimo aggiornamento: 2h  │
│  ─────────────────────────────────────────────────  │
│                                                     │
│  🔴 Frazionamento (3)                              │
│  │  • CIG ABC1234567 — 4 affidamenti sotto soglia  │
│  │    Totale: €180.000 in 45 gg [→ vedi atti]       │
│  │  • CIG DEF...                                    │
│  │                                                  │
│  🔴 Tempi anomali (5)                              │
│  │  • Bando "Manutenzione strade" — 8 gg (min: 15) │
│  │    [→ vedi atto sorgente]                        │
│  │                                                  │
│  🟡 Concentrazione affidamenti (1)                  │
│  │  • 2024: 85% affidamenti diretti (n=47/55)       │
│  │                                                  │
│  ─────────────────────────────────────────────────  │
│  📈 Trend (ultimi 12 mesi)                          │
│  │  [grafico a barre: red flags per mese]           │
│  │                                                  │
│  🏘️ Confronto con comuni simili (50-70K abitanti)  │
│  │  Agrigento: 12 flags │ Media pari: 6 flags       │
│  │                                                  │
│  ⚠️ Disclaimer...                                   │
└─────────────────────────────────────────────────────┘
```

---

## 4. Stack frontend

| Layer | Scelta | Motivazione |
|-------|--------|-------------|
| Framework | **React** (Next.js) o **Vue** (Nuxt) | SPA moderna, SSG per SEO, community ampia |
| UI Library | **Shadcn/ui** (React) o **Tailwind** | Leggero, accessibile, personalizzabile |
| Grafici | **Recharts** o **Chart.js** | Leggeri, ben integrati con React |
| Mappa | **Leaflet** + GeoJSON Sicilia | Open source, zero costi, offline-ready |
| Upload | **react-dropzone** | Drag&drop maturo |
| State | **TanStack Query** | Cache API, retry, loading states |
| Deploy | **S3 + CloudFront** | Statico, globale, ~$0 |

**Alternativa minimal:** Streamlit (già previsto) — più rapido per MVP, meno customizzabile.

**Raccomandazione:** Partire con Streamlit per validare il prodotto (2 settimane), poi migrare a React quando il design è stabile.

---

## 5. API Backend — endpoint

### Analisi on-demand

```
POST /api/analisi
  Body: multipart/form-data (file PDF)
  Response: { report_id, status: "processing" }

GET /api/analisi/{report_id}
  Response: { status: "completed", report: {...} }
```

### Dashboard

```
GET /api/comuni
  Response: [{ codice_istat, nome, n_flags, ultima_scansione }]

GET /api/comuni/{codice_istat}/flags
  Query: ?tipo=frazionamento&da=2024-01&a=2024-12
  Response: { flags: [...], trend: [...] }

GET /api/comuni/{codice_istat}/atti/{atto_id}
  Response: { metadati, url_fonte, flags_associati }

GET /api/confronto?comuni=082053,084004&metrica=flags_totali
  Response: { dati_confronto: [...] }
```

### Mappa

```
GET /api/mappa/sicilia
  Response: GeoJSON con proprietà { codice_istat, indice_rischio, n_flags }
```

---

## 6. Accessibilità e UX

| Requisito | Implementazione |
|-----------|----------------|
| WCAG 2.1 AA | Contrasti, aria-labels, keyboard navigation |
| Mobile responsive | Breakpoint a 768px, menu hamburger |
| Lingua | Italiano (UI) + inglese (API/code) |
| Performance | Lighthouse > 90, LCP < 2.5s |
| Offline | Service worker per cache mappa + ultimi report |
| Feedback | Skeleton loader durante analisi, toast su errori |

---

## 7. Autenticazione e accesso

| Livello | Accesso | Auth |
|---------|---------|------|
| **Pubblico** | Dashboard aggregata, mappa, confronti | Nessuna |
| **Base** | Analisi fascicolo (max 5/giorno), download report | Opzionale (rate limit per IP) |
| **Registrato** | Analisi illimitate, storico personale, alert | Cognito (email/Google) |
| **PA** | Self-audit, vista pre-pubblicazione | Cognito + dominio @comune.*.it |
| **Admin** | Gestione spider, soglie, utenti | Cognito + gruppo admin |

---

## 8. Notifiche e alert

| Evento | Canale | Destinatario |
|--------|--------|-------------|
| Nuove red flag 🔴 per un comune "seguito" | Email / push | Utente registrato |
| Spider fallito > 24h | Email | Admin |
| Nuovo atto analizzato con anomalie | In-app | Utente che segue il comune |
| Report settimanale | Email digest | Utenti registrati |

---

## 9. Roadmap implementativa del frontend

### Fase 1 — MVP Streamlit (2 settimane)
- Upload PDF → report
- Lista comuni → red flags
- Deploy su Streamlit Cloud (gratis)
- **Obiettivo:** Validare il prodotto con 5-10 utenti pilota

### Fase 2 — React SPA (4-6 settimane)
- Redesign completo con componenti custom
- Mappa Sicilia interattiva
- Deploy su S3 + CloudFront
- **Obiettivo:** Prodotto presentabile a stakeholder

### Fase 3 — Funzionalità avanzate (ongoing)
- Self-audit PA
- Sistema di notifiche
- API pubblica per integrazioni (giornalisti, ricercatori)
- Embedding widget per testate locali
- **Obiettivo:** Crescita organica, community

---

## 10. Metriche prodotto (da tracciare)

| Metrica | Strumento | Target MVP |
|---------|-----------|-----------|
| Analisi effettuate / settimana | CloudWatch custom metric | > 50 |
| Utenti unici / mese | CloudFront logs + analytics | > 200 |
| Tempo medio su dashboard | Frontend analytics | > 2 min |
| Report scaricati | S3 access logs | > 30/settimana |
| Comuni "seguiti" da utenti | DB | > 20 |
| Bounce rate | Analytics | < 60% |

---

---

## 11. Come costruire il tool — implementazione concreta

### 11.1 Architettura applicativa

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (SPA)                            │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │  Home    │  │ Analisi  │  │Dashboard │  │   Mappa      │   │
│  │ +Upload  │  │ Report   │  │ Comune   │  │  Sicilia     │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘   │
│       └──────────────┴──────────────┴───────────────┘           │
│                           │ API calls (REST)                     │
└───────────────────────────┼─────────────────────────────────────┘
                            ▼
┌───────────────────────────────────────────────────────────────┐
│                     BACKEND (FastAPI)                           │
│                                                                │
│  /api/analisi      → upload PDF, lancia analisi, ritorna report│
│  /api/comuni       → lista comuni con conteggio red flags      │
│  /api/comuni/{id}  → dettaglio flags + atti per un comune      │
│  /api/mappa        → GeoJSON con indici aggregati              │
│  /api/report/{id}  → download report HTML/JSON/PDF             │
│                                                                │
│  Workers: Celery/SQS per analisi async (OCR pesante)          │
└───────────────────────┬───────────────────────────────────────┘
                        ▼
┌───────────────────────────────────────────────────────────────┐
│              DATABASE (PostgreSQL)                              │
│  enti | atti | entita_estratte | check_esiti | red_flags       │
└───────────────────────────────────────────────────────────────┘
```

### 11.2 Struttura del progetto frontend

```
talia-web/
├── public/
│   ├── sicilia.geojson          # Confini comunali Sicilia (ISTAT)
│   └── favicon.ico
├── src/
│   ├── app/
│   │   ├── layout.tsx           # Shell: navbar + sidebar + disclaimer footer
│   │   ├── page.tsx             # Home: upload + CTA dashboard
│   │   ├── analisi/
│   │   │   ├── page.tsx         # Upload PDF + progress
│   │   │   └── [id]/page.tsx   # Report interattivo di un fascicolo
│   │   ├── dashboard/
│   │   │   ├── page.tsx         # Lista comuni + filtri + mappa overview
│   │   │   └── [codice]/page.tsx # Dettaglio red flags di un comune
│   │   ├── mappa/
│   │   │   └── page.tsx         # Mappa coropletica full-screen
│   │   └── info/
│   │       └── page.tsx         # Chi siamo, metodologia, disclaimer legale
│   ├── components/
│   │   ├── UploadZone.tsx       # Drag & drop PDF
│   │   ├── ReportCard.tsx       # Singolo check con semaforo + espandi
│   │   ├── FlagTable.tsx        # Tabella red flags con sort/filter
│   │   ├── MapSicilia.tsx       # Leaflet + GeoJSON colorato
│   │   ├── TrendChart.tsx       # Recharts: trend mensile flags
│   │   ├── ComparePeers.tsx     # Confronto comuni simili
│   │   ├── Disclaimer.tsx       # Banner ⚠️ sempre visibile
│   │   └── Navbar.tsx           # Navigazione principale
│   ├── lib/
│   │   ├── api.ts              # Client API (fetch wrapper + types)
│   │   └── types.ts            # TypeScript types per Report, Flag, Comune
│   └── styles/
│       └── globals.css          # Tailwind + custom
├── next.config.js
├── tailwind.config.js
├── tsconfig.json
└── package.json
```

### 11.3 Pagine e navigazione

```
┌─────────────────────────────────────────────────┐
│  🔍 TALIA    [Home] [Analisi] [Dashboard] [Mappa] [Info]    │
├─────────────────────────────────────────────────┤
│                                                   │
│  Route: /                                         │
│  → Hero + Upload zone + link dashboard            │
│                                                   │
│  Route: /analisi                                  │
│  → Upload PDF → spinner → redirect a /analisi/123 │
│                                                   │
│  Route: /analisi/[id]                             │
│  → Report interattivo (semafori espandibili)      │
│  → Download buttons (HTML, JSON, PDF)             │
│                                                   │
│  Route: /dashboard                                │
│  → Ricerca comune + filtri (provincia, pop.)      │
│  → Lista card: nome, n° flags, ultima scansione   │
│  → Mini-mappa nell'header                         │
│                                                   │
│  Route: /dashboard/[codice_istat]                 │
│  → Dettaglio: flags attive, tabella atti, trend   │
│  → Drill-down: flag → atti → URL sorgente        │
│  → Confronto con comuni della stessa fascia       │
│                                                   │
│  Route: /mappa                                    │
│  → Mappa full-screen, click su comune → popup     │
│  → Legenda: colore = n° flags / gravità           │
│                                                   │
│  Route: /info                                     │
│  → Metodologia, disclaimer, team, licenza         │
│                                                   │
├─────────────────────────────────────────────────┤
│  ⚠️ Le segnalazioni sono anomalie da verificare  │
│  non accertamenti.  [Avvertenze legali]           │
└─────────────────────────────────────────────────┘
```

### 11.4 Backend — FastAPI (struttura)

```python
# backend/main.py
from fastapi import FastAPI, UploadFile
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="TALIA API", version="0.1.0")

# CORS per il frontend
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])

# --- Analisi on-demand ---
@app.post("/api/analisi")
async def crea_analisi(files: list[UploadFile]):
    """Upload PDF, lancia analisi asincrona, ritorna report_id."""
    # 1. Salva PDF su S3/disco
    # 2. Lancia task async (Celery o background task)
    # 3. Ritorna { report_id, status: "processing" }

@app.get("/api/analisi/{report_id}")
async def get_report(report_id: str):
    """Ritorna lo stato/risultato dell'analisi."""
    # Se completata: { status: "completed", report: {...} }
    # Se in corso: { status: "processing", progress: 60 }

# --- Dashboard ---
@app.get("/api/comuni")
async def lista_comuni(provincia: str = None, min_pop: int = None):
    """Lista comuni con conteggio red flags e ultima scansione."""

@app.get("/api/comuni/{codice_istat}")
async def dettaglio_comune(codice_istat: str):
    """Red flags attive, trend, atti recenti per un comune."""

@app.get("/api/comuni/{codice_istat}/flags")
async def flags_comune(codice_istat: str, tipo: str = None):
    """Lista flags filtrabili per tipo, con atti collegati."""

@app.get("/api/comuni/{codice_istat}/atti")
async def atti_comune(codice_istat: str, page: int = 1):
    """Atti raccolti per un comune, paginati."""

# --- Mappa ---
@app.get("/api/mappa")
async def mappa_sicilia():
    """GeoJSON con proprietà aggregate per comune."""

# --- Download ---
@app.get("/api/report/{report_id}/download")
async def download_report(report_id: str, formato: str = "html"):
    """Scarica report in HTML, JSON o PDF."""
```

### 11.5 Componenti chiave del frontend

#### Upload Zone (cuore dell'interazione)
```tsx
// Componente UploadZone — drag & drop + progress
function UploadZone() {
  // 1. Drag & drop o click per selezionare PDF
  // 2. Mostra lista file selezionati con preview nome
  // 3. Bottone "Analizza" → POST /api/analisi
  // 4. Polling su GET /api/analisi/{id} ogni 2 sec
  // 5. Quando status = "completed" → redirect a /analisi/{id}
  //
  // UX: progress bar con fasi ("Estrazione testo...", "Analisi entità...", "Checklist...")
}
```

#### Report interattivo (il prodotto visibile)
```tsx
// Componente ReportView — il report che l'utente vede
function ReportView({ report }) {
  // Header: disclaimer + metadata atti
  // Riepilogo: 🟢 2  🟡 1  🔴 2  ⚪ 2
  // Lista check: ognuno è un accordion
  //   - Chiuso: emoji + titolo + stato
  //   - Aperto: spiegazione + citazioni evidenziate + riferimenti normativi
  // Footer: download buttons + timestamp
}
```

#### Mappa Sicilia (impatto visivo)
```tsx
// Componente MapSicilia — Leaflet + GeoJSON
function MapSicilia({ dati }) {
  // 1. Carica GeoJSON confini comunali (ISTAT)
  // 2. Colora ogni comune in base a n° red flags:
  //    0 flags → verde, 1-3 → giallo, 4-10 → arancione, 10+ → rosso
  // 3. Hover: tooltip con nome comune + n° flags
  // 4. Click: popup con mini-riepilogo + link a /dashboard/{codice}
  // 5. Legenda in basso a destra
}
```

### 11.6 Flusso utente completo — scenario tipo

```
1. Cittadino arriva su talia.it
   └→ Vede hero + upload zone + "Esplora dashboard"

2a. PERCORSO ANALISI:
    └→ Trascina 2 PDF (indizione + annullamento)
    └→ Vede progress: "Estrazione testo... ✓" → "Analisi entità... ✓" → "Checklist..."
    └→ Report appare: 2 🔴, 1 🟡, 2 🟢
    └→ Espande check 🔴 "Termini": vede "14 mesi > 12 mesi" + citazione evidenziata
    └→ Scarica HTML per condividere

2b. PERCORSO DASHBOARD:
    └→ Clicca "Esplora dashboard"
    └→ Vede mappa Sicilia colorata
    └→ Clicca su Agrigento (rosso)
    └→ Vede: 12 red flags attive, trend in crescita, tabella atti
    └→ Clicca su flag "Frazionamento"
    └→ Vede: 4 affidamenti sotto soglia, totale €180K, CIG linkati
    └→ Clicca su URL fonte → va all'albo pretorio del comune
```

### 11.7 Piano implementativo step-by-step

#### Step 1 — Backend FastAPI (1 settimana)

```bash
# Struttura
backend/
├── main.py              # App FastAPI
├── routers/
│   ├── analisi.py       # Endpoints analisi
│   ├── comuni.py        # Endpoints dashboard
│   └── mappa.py         # Endpoint GeoJSON
├── services/
│   ├── analisi_service.py  # Chiama il motore TALIA esistente
│   └── query_service.py    # Query al DB per dashboard
├── requirements.txt     # fastapi, uvicorn, python-multipart
└── Dockerfile
```

Cosa fa: wrappa il motore TALIA esistente (`analizza_pdf`, `esegui_tutti`) dietro API REST. Non riscrive niente — espone ciò che già funziona.

#### Step 2 — Frontend MVP (2 settimane)

```bash
npx create-next-app@latest talia-web --typescript --tailwind
cd talia-web
npm install leaflet react-leaflet recharts react-dropzone
```

Priorità pagine:
1. Home + Upload (giorno 1-3)
2. Report view (giorno 4-7)
3. Dashboard lista + dettaglio (giorno 8-11)
4. Mappa (giorno 12-14)

#### Step 3 — Deploy (3 giorni)

```
Frontend: Vercel (gratis) o S3+CloudFront
Backend: AWS Lambda (via Mangum) o ECS Fargate
DB: RDS PostgreSQL free tier
```

#### Step 4 — Polish (1 settimana)
- Responsive mobile
- Loading states / skeleton
- Error handling + toast
- SEO meta tags
- Analytics (Plausible, privacy-friendly)

### 11.8 Tecnologie raccomandate

| Layer | Scelta consigliata | Alternativa rapida | Note |
|-------|-------------------|-------------------|------|
| Frontend framework | **Next.js 14** (App Router) | Streamlit | Next = prodotto serio; Streamlit = MVP in 2 gg |
| Styling | **Tailwind CSS + shadcn/ui** | Chakra UI | Componenti accessibili pronti |
| Mappa | **React-Leaflet** + GeoJSON ISTAT | Mapbox (a pagamento) | Leaflet è gratis e sufficiente |
| Grafici | **Recharts** | Chart.js | API dichiarativa, leggero |
| Upload | **react-dropzone** | input nativo | UX molto migliore |
| State/fetch | **TanStack Query** | SWR | Cache, retry, loading states gratis |
| Backend | **FastAPI** | Flask | Async nativo, OpenAPI auto-generata, typing |
| Task async | **Celery + Redis** o **SQS** | BackgroundTasks FastAPI | Per OCR pesante serve un worker |
| Auth (futuro) | **NextAuth.js** + Cognito | Auth0 | Gratis per volumi bassi |

### 11.9 GeoJSON Sicilia — dove prenderlo

```bash
# Confini comunali ISTAT (fonte ufficiale, gratis)
# Download: https://www.istat.it/it/archivio/222527
# Formato: shapefile → convertire in GeoJSON con ogr2ogr o mapshaper.org
# Filtrare per COD_REG = 19 (Sicilia)
# Risultato: ~391 poligoni, ~2 MB ottimizzato

# Oppure già pronto:
# https://github.com/openpolis/geojson-italy (repo community)
```

### 11.10 Approccio in 2 fasi: MVP rapido → prodotto completo

#### Fase 1: Streamlit (2-3 giorni, per validare subito)

```python
# src/talia/modulo3_dashboard/app.py
import streamlit as st
from talia.modulo1_fascicolo.analisi import analizza_pdf

st.set_page_config(page_title="TALIA", page_icon="🔍", layout="wide")
st.warning("⚠️ Le segnalazioni sono anomalie da verificare, non accertamenti.")

tab1, tab2 = st.tabs(["📄 Analisi Fascicolo", "📊 Dashboard"])

with tab1:
    files = st.file_uploader("Carica i PDF del fascicolo", type="pdf", accept_multiple_files=True)
    if files and st.button("Analizza"):
        # salva temp, analizza, mostra report
        report = analizza_pdf([...])
        for esito in report.esiti:
            with st.expander(f"{esito.stato.emoji} {esito.titolo}"):
                st.write(esito.spiegazione)
                for cit in esito.citazioni:
                    st.caption(f"«{cit.testo}»")

with tab2:
    # query DB, mostra tabella comuni + flags
    st.dataframe(...)
```

Deploy: `streamlit run app.py` → Streamlit Cloud (gratis, 1 click).

**Questo basta per la prima demo.** Poi si migra a Next.js quando serve di più.

#### Fase 2: Next.js + FastAPI (prodotto reale)

Quando Streamlit diventa limitante (customizzazione, performance, UX), si migra al frontend React con backend FastAPI come descritto sopra.

---

## 12. Monetizzazione (opzionale, lungo termine)

Il progetto è AGPL → open source. Ma può autosostenersi:

| Modello | Target | Prezzo indicativo |
|---------|--------|-------------------|
| **Freemium** | Cittadini: gratis; PA: self-audit a pagamento | €50-200/mese per ente |
| **SaaS PA** | Funzionari che vogliono pre-check | €99/mese per comune |
| **Consulenza** | Training PA su trasparenza | €500/giornata |
| **Grant/sponsor** | Fondazioni, civic tech, UE | €10-50K/anno |
| **Dati aggregati** | Ricercatori, università | API premium per bulk data |

**Nota:** La monetizzazione non è prioritaria ora. Il valore civico viene prima. Ma è bene sapere che il modello è sostenibile.
