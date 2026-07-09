# 05 — Red flags batch (regole deterministiche, no LLM)

[← Home](00-home.md)

Regole che girano sui dati raccolti dallo scraping (Modulo 2). Tutte **deterministiche**: regex + SQL,
nessun LLM. Ognuna deve essere oggettiva, misurabile e linkata agli atti.

| Red flag | Descrizione | Segnale misurabile |
|----------|-------------|--------------------|
| **Frazionamento artificioso** | affidamenti diretti ripetuti sotto soglia | stesso oggetto/fornitore, importi appena sotto soglia, ravvicinati nel tempo |
| **Concentrazione** | stesso fornitore ricorrente | specialmente con lo stesso RUP; gare a offerente unico |
| **Tempi anomali** | finestre di pubblicazione bandi anormalmente brevi | durata pubblicazione < soglia di legge/mediana |
| **Catene di proroghe** | proroghe contrattuali ripetute | n. proroghe sullo stesso contratto |
| **Varianti gonfianti** | varianti che superano soglia | importo finale ≫ importo aggiudicato |
| **Revoche ricorrenti** | revoche seguite da riaffidamento | revoca + nuovo affidamento ravvicinato |
| **Riapertura dopo revoca** | bando rilanciato con oggetto simile dopo revoca/annullamento | similarità Jaccard ≥ 0.5 sull'oggetto, entro X mesi dalla revoca (esclude routine admin ricorrenti) |
| **Somma urgenza / emergenza** | uso sistematico per bypassare gare | frequenza affidamenti in urgenza (dissesto, rifiuti) |
| **Fondi a scadenza** | PNRR, PO-FESR | concentrazione di affidamenti diretti su questi fondi |
| **Trasparenza** | mancata/tardiva pubblicazione obbligatoria (D.lgs. 33/2013) | oggettiva e misurabile: presenza/ritardo pubblicazione |
| **Antimafia (Sicilia)** | imprese interdette che ricompaiono | altra ragione sociale o nei subappalti |

## Red flag da contenuto PDF (Fase 2 — richiede download)

I seguenti check **non sono rilevabili dai soli metadati** e richiedono l'analisi del testo dell'atto.
Vengono eseguiti solo sugli atti già flaggati dalla Fase 1.

| Check ID | Descrizione | Segnale |
|---|---|---|
| `revoca_motivazione_vaga` | Revoca in autotutela con motivazione generica, senza accertamento dei fatti | Assenza di riferimenti a: indagine interna, responsabile accertato, misure adottate |
| `gdpr_breach_non_notificato` | Violazione di dati personali in procedura concorsuale senza notifica al Garante | Revoca cita "divulgazione" o "violazione segretezza" ma nessun atto separato di notifica ex art. 33 GDPR |
| `dpo_segretario_conflitto` | Il DPO è la stessa persona che firma/gestisce l'atto irregolare | Richiede dato esterno: ruolo DPO dell'ente. Check: firmatario atto = soggetto DPO registrato |
| `numero_atto_incoerente` | Riferimento a numero determinazione diverso tra oggetto e dispositivo | Es.: oggetto revoca cita "N. 33/2025", corpo e dispositivo citano "N. 35/2025" |
| `commissione_nominata_nel_bando` | Commissione esaminatrice nominata nell'atto di indizione anziché dopo scadenza domande | Anomalia procedurale: i candidati conoscono i commissari prima di presentare domanda |
| `attestazione_finanziaria_vuota` | Attestazione di copertura finanziaria firmata con tabella impegni/importi vuota | Attestazione formalmente valida ma senza dati economici concreti |

### Caso studio: Palma di Montechiaro — Det. SG 35/2025 + revoca (giugno 2026)

Fascicolo analizzato manualmente per validare l'approccio a due fasi:

- **Fase 1 (metadati):** keyword `REVOCA IN AUTOTUTELA` nell'oggetto della det. 16/2026 → flag immediato. Discrepanza rilevabile: la revoca cita "N. 33/2025" ma in DB l'atto di indizione è "N. 35/2025".
- **Fase 2 (PDF):** emersi 4 elementi invisibili dai metadati:
  1. Causa reale: bozza di graduatoria divulgata prima dell'ufficializzazione → potenziale **data breach GDPR** (art. 33 GDPR: notifica Garante entro 72h). La revoca non la menziona.
  2. Esistenza di una **seconda procedura parallela** (Cat. D, Istruttori → Funzionari) coinvolta nella stessa violazione ma non formalmente revocata.
  3. Il Segretario Generale è anche **RPCT e DPO** → conflitto: è il soggetto che dovrebbe notificare il breach ed è anche il firmatario degli atti irregolari.
  4. Attestazione di copertura finanziaria con tabella impegni/importi **vuota**.

> Segnalazioni da verificare, non accertamenti. Il fascicolo è disponibile in `data/samples/1/` (anonimizzato).

### Riapertura dopo revoca — TAL-48

Pattern rilevato empiricamente (Palma, Ragusa) e implementato in fase 1:

- **Contesto:** procedimento annullato/revocato; settimane o mesi dopo, lo **stesso ente** pubblica un **nuovo atto con oggetto molto simile** (similarità Jaccard ≥ 0.5 sui token normalizzati).
- **Interpretazione:** la re-indizione con criteri "aggiustati" (anziché affrontare i motivi della revoca) è un pattern che suggerisce possibile *bando su misura* rilanciato.
- **Guardia anti-periodicità:** se l'ente pubblica lo **stesso oggetto ≥3 volte nel tempo**, è routine amministrativa (es. report trimestrali), non una riapertura sospetta.
- **Casi reali:**
  - **Palma proc. 656:** bando assegnazione 10 lotti ZES annullato 2023-12-14 → bando ripubblicato 2026-05-18 (sim 0.74).
  - **Ragusa proc. 1079:** determina a contrattare revocata → riadottata identica 18 giorni dopo (sim 1.00).
- **Falso positivo noto:** Enna proc. 924 (atti trimestrali "COSTO PERSONALE — TRIM.") → escluso dalla guardia periodicità.

**Modulo:** `src/talia/modulo2_scraping/red_flags/riapertura_revoca.py`
- Algoritmo Jaccard su token normalizzati (stopword dominio esclusi, lunghezza ≥3 char)
- Prerequisito: tabella `procedimenti` da `ricostruisci_catene()`, connessione SQLite con `row_factory=sqlite3.Row`
- Severità: MEDIA (segnala per verifica, non accertamento)

## Principi di design delle regole

1. **Soglie esplicite e documentate** — ogni numero magico (12 mesi, soglie affidamento) ha fonte normativa citata nel codice.
2. **Falsi positivi attesi** — una red flag è un invito a verificare, non un verdetto. Tarare per non sommergere di rumore.
3. **Confronto tra pari** — anomalie misurate rispetto a comuni di taglia simile, non in assoluto.
4. **Tracciabilità** — ogni flag elenca gli atti/CIG che l'hanno generata.

## Ground truth per tarare le soglie

Atti dei comuni sciolti per infiltrazione mafiosa + sentenze di annullamento (TAR/CGA) →
esempi reali di "atti che hanno preceduto un problema accertato". Vedi [07 Fonti dati](07-fonti-dati.md).

[→ 06 Corpus normativo](06-corpus-normativo.md)