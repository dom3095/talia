# TAL-48 — Red flag: riapertura dopo revoca/annullamento (bando simile rilanciato)

- **Epica:** E2 — Fase 2 pipeline: PDF on-demand → analisi → red flags
- **Ruolo:** 🔤 NLP + ⚖️ LEX
- **Priorità:** P1
- **Stato:** Done
- **Branch:** `feat/TAL-48-pdf-riaperture` (il vecchio `feat/TAL-48-riapertura-dopo-revoca`
  era rimasto indietro rispetto a `main` dopo il merge del Tentativo 1 via PR #9 — branch
  nuovo per questo giro, ripartito da `main` aggiornato)

## 🎯 Obiettivo

Rilevare quando, dopo la revoca/annullamento di un procedimento, lo stesso ente
pubblica un atto con oggetto simile o identico (bando/selezione/affidamento
rilanciato). È un pattern da verificare: la re-indizione con criteri ritoccati
può essere fisiologica, ma è anche il meccanismo tipico del bando "su misura".

## 📚 Contesto

Idea dell'utente (2026-07-06), verificata empiricamente sul DB durante TAL-47.
Casi reali trovati con similarità Jaccard ≥ 0.5 sui token dell'oggetto:

- **Palma proc. 656**: bando assegnazione 10 lotti ZES annullato 2023-12-14 →
  stesso bando ripubblicato 2026-05-18 (atto 3400).
- **Ragusa proc. 1079**: determina a contrattare revocata → riadottata identica
  18 giorni dopo (atto 2961, sim 1.00).
- **Palma proc. 692**: affidamento sorveglianza sanitaria annullato 2023-11-20 →
  re-affidato 2024-07-17 (proc. 703, sim 0.74).

**Falso positivo istruttivo:** Enna proc. 924 matcha 6 atti "COSTO PERSONALE — TRIM."
— atti periodici trimestrali, non una riapertura. Serve una guardia anti-periodicità.

## 📋 Spec

- Nuovo check batch `red_flags/riapertura_revoca.py` (stesso stile di `catena_revoca.py`):
  - input: catene con `stato_finale IN ('revocato','annullato')` e data di chiusura nota;
  - cerca atti dello stesso ente con `data > data_revoca` e oggetto simile
    (Jaccard su token, stopword del dominio escluse);
  - produce una riga in `red_flags` (`tipo_flag = 'riapertura_dopo_revoca'`) con
    riferimenti a entrambi gli atti (originale + riapertura) e la similarità;
  - **guardia anti-periodicità**: se gli atti simili sono ≥ 3 distribuiti nel tempo
    (routine amministrativa ricorrente), non flaggare;
  - **guardia copertura**: come TAL-47, nessun segnale fuori dalla finestra di
    copertura del DB per l'ente.
- Registrare nel runner (`red_flags/runner.py`).
- La riapertura diventa criterio di download aggiuntivo per `pdf_download`
  (scaricare i PDF di ENTRAMBI i bandi per il futuro confronto "cosa è cambiato").
- Test con i casi reali sopra (anonimizzati) + caso periodico Enna come negativo.

## ❓ Domande aperte

- [x] Soglia di similarità: 0.5 ha trovato i 3 casi veri, ma è calibrata su 27 catene.
      Confermare con ⚖️ LEX dopo il primo run completo.
      **Risposta (Dom, 2026-07-20):** confermata 0.5 per questo giro. Da ricalibrare dopo
      aver visto i PDF reali scaricati (prossimo punto), non alla cieca ora.
- [x] Il confronto testuale tra bando originale e bando rilanciato ("cosa è cambiato")
      è in scope qui o è una card separata (richiede PDF + estrazione testo)?
      **Risposta (Dom, 2026-07-20):** card separata. Questo giro di TAL-48 si limita al
      download dei PDF di entrambi i bandi (originale + riapertura); il confronto
      testuale richiede prima l'estrazione testo (pipeline non ancora generalizzata
      oltre jCityGov) — va aperta una card di follow-up quando serve.

## 🔗 Dipendenze

TAL-43/46 (engine catena), TAL-47 (download PDF per il confronto futuro).

## 🔬 Tentativi

### 2026-07-06 — Tentativo 0 (esplorativo, in sessione TAL-47)
**Approccio:** query esplorativa: per ogni catena revocata con data nota, cercare atti
dello stesso ente successivi alla revoca con Jaccard ≥ 0.5 sull'oggetto.
**Esito:** ⚠️ parziale — 3 casi veri (Palma 656 e 692, Ragusa 1079) + 1 famiglia di
falsi positivi (Enna 924, atti trimestrali periodici).
**Appreso:** il segnale esiste ed è rilevabile senza PDF; serve guardia anti-periodicità;
la catena Enna 924 è essa stessa mal ricostruita (fuzzy) — le guardie di TAL-46/47
(metodo + copertura) vanno riusate qui.

### 2026-07-10 — Tentativo 1 (implementazione MVP)
**Approccio:** modulo `riapertura_revoca.py` con:
- `rileva_riapertura_dopo_revoca(conn, soglia_similarita=0.5)`: query procedimenti
  revocati/annullati, ricerca atti dello stesso ente con oggetto simile
- Tokenizzazione con stopword del dominio (regex `\b\w+\b`, escludendo < 3 char)
- Similarità Jaccard su token normalizzati
- Guardia anti-periodicità: ≥ 3 atti simili nel tempo → skip
- Integrazione runner: `_salva_riapertura_dopo_revoca()`, nuovo campo RapportoRunner
- 12 test (tokenizzazione, Jaccard, 4 casi reali + edge case)
**Esito:** ✅ 320 test verdi (312 base + 8 suite).
**Appreso:** guardia anti-periodicità funziona (test Enna esclude correttamente);
Jaccard 0.5 è una buona soglia empirica (non calibrata su full DB, ancora da confermare
con LEX post-run completo). La similarità è deterministicamente calcolabile senza PDF.
Prossimo step: integrazione con pdf_download per scaricare i PDF di entrambi i bandi
(richiede test su fascicolo Palma reale, se PR #8 passa).

### 2026-07-20 — Tentativo 2 (bugfix su DB reale + integrazione pdf_download)

**Approccio:** prima di integrare il download, verifica su `talia.db` reale (238 enti,
104.812 atti, run scraper completo dello stesso giorno): `rileva_riapertura_dopo_revoca`
restituiva **0 risultati**, nonostante 449 catene revocate/annullate disponibili.

**Causa:** `data_atto` è **NULL per il 100% degli atti jCityGov** (79.462 atti, la
piattaforma dominante — inclusi tutti e 3 i casi reali documentati sopra). Il modulo
filtrava sia il gate di chiusura (`p.data_chiusura IS NOT NULL`, derivato da `data_atto`
in `engine/catena.py`) sia la ricerca dei candidati (`data_atto > data_chiusura_rev`) su
quel campo — sempre `NULL` su jCityGov, quindi sempre escluso. I 12 test esistenti non
l'avevano mai preso perché le fixture impostano `data_atto` a mano in ogni riga.

**Esito:** ✅ fix mirato in `riapertura_revoca.py` (non tocca l'engine catena condiviso,
per contenere il rischio): gate di chiusura ricalcolato direttamente dagli atti con
`ruolo_in_catena IN ('revoca','annullamento')` via `MAX(COALESCE(data_atto, data_pub))`,
stessa `COALESCE` nella ricerca dei candidati post-revoca. Da 0 → **78 riaperture rilevate**
su tutto il DB (446/449 catene ora superano il gate, prima solo 54). 1 nuovo test di
regressione (fixture con `data_atto` NULL, replica lo scenario jCityGov reale).

**Nota collaterale osservata (non un bug da correggere ora):** con la guardia
anti-periodicità applicata sul DB pieno, 2 dei 3 casi noti (Palma 656, Ragusa 1079)
non compaiono più nei risultati finali — probabilmente perché la guardia conta ≥3 match
"ovunque nel tempo" senza escludere la coppia revoca/riapertura stessa dal conteggio, e con
più dati è più facile raggiungere quella soglia per coincidenza. Solo Palma 692 resta tra
i 78. Utile per la ricalibrazione futura della soglia (domanda aperta già risposta:
rimandata a dopo aver visto i PDF reali).

**Integrazione `pdf_download.py` (TAL-47):**
- `_scarica_pdf_atti()`: estratto il loop di download condiviso da `scarica_pdf_procedimento`
  (nessun comportamento cambiato, solo refactor per riuso).
- `scarica_pdf_atto()`: nuovo, scarica gli allegati di un atto singolo senza catena — serve
  per l'atto di riapertura quando l'engine non lo ha ancora agganciato a un proprio
  procedimento (query per `procedimento_id` non lo troverebbe).
- `procedimenti_da_riapertura()` + `_diversifica_per_ente()` (estratto da
  `procedimenti_critici` per riuso): selezione diversificata per comune dei red flag
  `riapertura_dopo_revoca` su fonti supportate (jCityGov).
- `scarica_pdf_riapertura()`: orchestratore — scarica la catena originale (con il suo
  `motivo_selezione.json` esistente), poi la riapertura (catena propria se ne ha una,
  altrimenti il solo atto), poi un nuovo `motivo_riapertura.json` che spiega il
  collegamento (per esplicabilità, principio non negoziabile del progetto).
- CLI: nuovo flag `--riaperture` in `pdf_download.py main()`.
- 6 nuovi test (atto singolo, selezione fonti, riapertura con/senza catena propria,
  flag inesistente).

**Validazione end-to-end su `talia.db` reale:** popolati i 78 red flag, scaricate 3
riaperture reali con `--riaperture --limite 3` — inclusa **Palma proc. 692→703** (uno dei
3 casi noti documentati sopra: "affidamento sorveglianza sanitaria annullato → re-affidato",
confermato dal vivo) e **Ragusa proc. 11306** (metodo `cig`, alta confidenza). PDF reali
in `data/raw/pdf/` (gitignored), `motivo_riapertura.json` corretto in entrambi i casi.

**Trovato e sistemato anche:** `run_scrapers.py` calcolava `riapertura_dopo_revoca` nel
report red flags ma non lo stampava mai nel blocco `── RED FLAGS ──` — aggiunta la riga
mancante.

**Esito:** ✅ 480 test verdi (erano 473), lint pulito. **Appreso:** un modulo può avere
test verdi al 100% e comunque produrre zero output reale se le fixture non replicano un
dettaglio strutturale della fonte dati dominante (qui: quale campo data è popolato) — vale
la pena, per i moduli di analisi, un controllo di sanità su un campione di DB reale prima
di considerarli "finiti", non solo la suite unitaria.

**Prossimo passo (non bloccante, fuori scope qui):** integrazione di `--riaperture` nel
flusso di default di `run_scrapers.py` (oggi resta un comando CLI separato, come già era
`procedimenti_critici` prima di questa card); confronto testuale PDF originale vs
riapertura (card separata, richiede estrazione testo generalizzata oltre jCityGov);
ricalibrazione soglia Jaccard con i PDF reali ora scaricabili.
