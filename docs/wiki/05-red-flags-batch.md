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
| **Somma urgenza / emergenza** | uso sistematico per bypassare gare | frequenza affidamenti in urgenza (dissesto, rifiuti) |
| **Fondi a scadenza** | PNRR, PO-FESR | concentrazione di affidamenti diretti su questi fondi |
| **Trasparenza** | mancata/tardiva pubblicazione obbligatoria (D.lgs. 33/2013) | oggettiva e misurabile: presenza/ritardo pubblicazione |
| **Antimafia (Sicilia)** | imprese interdette che ricompaiono | altra ragione sociale o nei subappalti |

## Principi di design delle regole

1. **Soglie esplicite e documentate** — ogni numero magico (12 mesi, soglie affidamento) ha fonte normativa citata nel codice.
2. **Falsi positivi attesi** — una red flag è un invito a verificare, non un verdetto. Tarare per non sommergere di rumore.
3. **Confronto tra pari** — anomalie misurate rispetto a comuni di taglia simile, non in assoluto.
4. **Tracciabilità** — ogni flag elenca gli atti/CIG che l'hanno generata.

## Ground truth per tarare le soglie

Atti dei comuni sciolti per infiltrazione mafiosa + sentenze di annullamento (TAR/CGA) →
esempi reali di "atti che hanno preceduto un problema accertato". Vedi [07 Fonti dati](07-fonti-dati.md).

[→ 06 Corpus normativo](06-corpus-normativo.md)