# 06 — Prospetto Economico

> Stime di revenue, scenari di monetizzazione, costi, proiezioni a 3 anni.
> Branch: `analisi-kiro` | Data: 2026-06-28

---

## 1. Premessa

TALIA è open source (AGPL-3.0): il codice resta un bene comune. La monetizzazione avviene tramite **servizi a valore aggiunto** sopra il motore open source — modello consolidato (Red Hat, Elastic, GitLab).

---

## 2. Mercato target

### 2.1 Dimensione del mercato

| Segmento | Numerica | Note |
|----------|----------|------|
| Comuni siciliani | 391 | Target iniziale |
| Comuni italiani | 7.904 | Espansione naturale (stesse norme) |
| Province / Città Metropolitane | 107 | Enti più grandi, budget maggiori |
| Regioni | 20 | Coordinamento e supervisione |
| RPCT (Responsabili Anticorruzione) | ~8.000 | 1 per ente, obbligatorio per legge |
| Testate giornalistiche locali | ~600 | Data journalism in crescita |
| Università con corsi diritto amm.vo | ~50 | Ricerca e didattica |

### 2.2 Perché il mercato è pronto

- **Obbligo normativo**: ogni PA deve avere un Piano Triennale Prevenzione Corruzione (PTPCT) e un RPCT. Oggi questi controlli sono manuali o inesistenti.
- **PNRR**: miliardi in affidamenti rapidi senza strumenti di monitoraggio automatico.
- **D.lgs. 36/2023**: nuovo Codice Appalti → PA in fase di adattamento, alto tasso di errori procedurali.
- **Pressione ANAC**: richiede monitoraggio ma non fornisce strumenti ai singoli comuni.
- **Zero competitor**: nessuno offre analisi automatica a livello di singolo atto comunale.

---

## 3. Modelli di revenue

### 3.1 SaaS per PA — Self-audit (revenue principale)

Il funzionario carica l'atto PRIMA di pubblicarlo → TALIA segnala errori → li corregge prima che diventino problemi.

| Piano | Target | Prezzo | Cosa include |
|-------|--------|--------|-------------|
| **Base** | Comuni < 15K abitanti | €79/mese | 50 analisi/mese, dashboard, alert |
| **Standard** | Comuni 15-50K | €149/mese | Analisi illimitate, API, storico |
| **Enterprise** | Comuni > 50K, Province | €299/mese | Multi-utente, report custom, SLA |
| **Regionale** | Regione / Prefettura | €999/mese | Vista aggregata tutti i comuni, benchmark |

### 3.2 API per giornalismo e ricerca

| Cliente tipo | Prezzo | Volume stimato |
|-------------|--------|----------------|
| Testata giornalistica | €500/mese | 5-10 clienti |
| Centro ricerca / università | €200/mese | 10-20 clienti |
| Associazione civic tech | €100/mese | 5-10 clienti |
| Accesso bulk dati (export) | €1.000 una tantum | 10-20/anno |

### 3.3 Consulenza e formazione

| Servizio | Prezzo unitario | Volume annuo stimato |
|----------|----------------|---------------------|
| Training RPCT (giornata in presenza/remoto) | €500-800 | 30-50 giornate |
| Audit personalizzato per ente | €2.000-5.000 | 15-25 enti |
| Setup + customizzazione | €3.000-10.000 | 5-15 enti |
| Report tematico commissionato | €5.000-15.000 | 5-10 report |

### 3.4 Grant e finanziamenti (non ricorrenti)

| Fonte | Importo | Probabilità | Tempistica |
|-------|---------|-------------|-----------|
| AWS Activate (credits) | €5-25K | Alta | 1-2 mesi |
| Google.org / Digital News Innovation | €20-50K | Media | 6 mesi |
| Bando EU Horizon / NGI | €50-200K | Media | 12 mesi |
| Fondazioni italiane (Cariplo, CompagniaSanPaolo) | €20-50K | Media-Alta | 6 mesi |
| PNRR Misura 1.2 (digitalizzazione PA) | €50-150K | Media | 6-12 mesi |
| ANAC / PCM collaborazione istituzionale | €30-100K | Media | 12 mesi |
| Premio civic tech (PA Digitale, ForumPA) | €5-20K | Media | annuale |

---

## 4. Proiezione finanziaria a 3 anni

### Scenario conservativo

| | Anno 1 | Anno 2 | Anno 3 |
|--|--------|--------|--------|
| **Comuni paganti** | 10 | 50 | 120 |
| **Revenue SaaS** | €12K | €72K | €172K |
| **API / giornalismo** | €0 | €18K | €48K |
| **Consulenza** | €10K | €40K | €80K |
| **Grant** | €15K | €30K | €20K |
| **Revenue totale** | **€37K** | **€160K** | **€320K** |
| Costi operativi | €15K | €90K | €180K |
| **Margine** | **€22K** | **€70K** | **€140K** |

### Scenario ottimistico

| | Anno 1 | Anno 2 | Anno 3 |
|--|--------|--------|--------|
| **Comuni paganti** | 30 | 200 | 500 |
| **Revenue SaaS** | €43K | €288K | €720K |
| **API / giornalismo** | €6K | €60K | €120K |
| **Consulenza** | €20K | €80K | €150K |
| **Grant** | €50K | €100K | €50K |
| **Revenue totale** | **€119K** | **€528K** | **€1.04M** |
| Costi operativi | €30K | €200K | €400K |
| **Margine** | **€89K** | **€328K** | **€640K** |

---

## 5. Struttura dei costi

### Anno 1 (fase prototipo → lancio)

| Voce | Conservativo | Ottimistico |
|------|-------------|-------------|
| AWS infrastruttura | €600 | €2.400 |
| Sviluppo (tempo proprio / volontario) | €0 | €0 |
| Dominio + servizi base | €200 | €500 |
| Legale (costituzione, contratti) | €3.000 | €5.000 |
| Marketing / eventi / conferenze | €1.000 | €5.000 |
| **Totale** | **€4.800** | **€12.900** |

### Anno 2-3 (crescita)

| Voce | Anno 2 | Anno 3 |
|------|--------|--------|
| AWS (scale up) | €3-5K | €8-15K |
| Team (1-2 dev, part/full time) | €40-80K | €80-160K |
| Commerciale / marketing | €10-20K | €20-40K |
| Legale / compliance | €5-10K | €10-15K |
| Infra / tool vari | €2-5K | €5-10K |
| **Totale** | **€60-120K** | **€123-240K** |

---

## 6. Break-even analysis

| Punto di pareggio | Formula | Risultato |
|-------------------|---------|-----------|
| Se solo io (costo €0) | 1 comune × €79 | €79/mese copre AWS |
| Se 1 dev stipendiato (€40K/anno) | €40K ÷ €149 × 12 | **23 comuni** |
| Se team 2 dev (€80K/anno) + ops | €100K ÷ €149 × 12 | **56 comuni** |
| Se team 3 persone + marketing | €180K ÷ €149 × 12 | **101 comuni** |

**Conclusione:** Con 50-100 comuni paganti il progetto è autosufficiente con un team piccolo. Su 391 comuni siciliani, il 25% di penetrazione (98 comuni) genera €175K/anno di margine netto.

---

## 7. Valore strategico (oltre la revenue diretta)

### Per chi ci lavora

| Beneficio | Valore stimato |
|-----------|---------------|
| Portfolio project AWS+AI+NLP completo | Equivale a 2-3 certificazioni (€5-10K di corsi) |
| Posizionamento come esperto civic tech | Inviti a conferenze, visibilità |
| Network PA / ANAC / università | Relazioni che aprono a consulenze e bandi |
| Pubblicazioni accademiche | 1-2 paper in 18 mesi → dottorato, assegni ricerca (€20-30K/anno) |
| Credibilità come data scientist | Progetto reale > 100 progetti su Kaggle |

### Come asset aziendale

| Scenario | Valutazione |
|----------|-------------|
| Acqui-hire (team acquisito per competenze) | €100-300K |
| Acquisizione tool (se 200+ comuni) | €500K-2M (5-10x revenue) |
| Licensing a grande player (ANAC, Deloitte, PwC) | €100-500K/anno |
| Spin-off in RegTech più ampia | Potenziale serie A €1-5M |

---

## 8. Rischi economici

| Rischio | Probabilità | Impatto | Mitigazione |
|---------|-------------|---------|-------------|
| PA lente a comprare (burocrazia acquisti) | Alta | Ritardo 6-12 mesi | Convenzioni CONSIP, MEPA |
| Competitor entra nel mercato | Bassa (barriere alte) | Medio | First mover + community |
| Cambio normativo riduce obblighi trasparenza | Molto bassa | Alto | Diversificare su compliance |
| Falsi positivi danneggiano reputazione | Media | Alto | Disclaimer + validazione LEX |
| Team si scioglie prima del product-market fit | Media | Alto | Grant per sostenere fase iniziale |

---

## 9. Timeline verso prima revenue

```
Mese 1-2:  MVP dashboard + deploy cloud (costo: €0-50 AWS)
              │
Mese 3:    Demo a 5 comuni pilota (gratis, per feedback)
              │
Mese 4:    Candidatura a 2-3 grant (AWS Activate + fondazione)
              │
Mese 5-6:  Primi 5-10 comuni paganti (€79-149/mese)
              │         Prima revenue: €400-1.500/mese
              │
Mese 7-9:  Espansione: 20-30 comuni + prima consulenza
              │         Revenue: €2-5K/mese
              │
Mese 10-12: 50+ comuni + API giornalismo + scale nazionale
                        Revenue: €5-15K/mese
```

---

## 10. Conclusione

| Metrica | Valore |
|---------|--------|
| **Investimento iniziale** | Quasi zero (tempo + competenze) |
| **Revenue anno 1 (realistica)** | €37-119K |
| **Revenue anno 3 (realistica)** | €320K-1M |
| **Break-even** | 23-56 comuni paganti |
| **Mercato indirizzabile** | 7.900+ comuni italiani = €14M/anno potenziali |
| **Downside** | Portfolio eccezionale + competenze acquisite |
| **Upside** | Business sostenibile con impatto sociale reale |

Il rapporto rischio/reward è tra i migliori possibili: l'investimento è quasi solo tempo, il downside è comunque positivo (competenze, portfolio, network), e l'upside è un business reale in un mercato senza concorrenza.
