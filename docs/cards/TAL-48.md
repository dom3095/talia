# TAL-48 — Red flag: riapertura dopo revoca/annullamento (bando simile rilanciato)

- **Epica:** E2 — Fase 2 pipeline: PDF on-demand → analisi → red flags
- **Ruolo:** 🔤 NLP + ⚖️ LEX
- **Priorità:** P1
- **Stato:** To Do
- **Branch:** `feat/TAL-48-riapertura-dopo-revoca` (da creare dopo il merge di TAL-47)

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

- [ ] Soglia di similarità: 0.5 ha trovato i 3 casi veri, ma è calibrata su 27 catene.
      Confermare con ⚖️ LEX dopo il primo run completo.
- [ ] Il confronto testuale tra bando originale e bando rilanciato ("cosa è cambiato")
      è in scope qui o è una card separata (richiede PDF + estrazione testo)?

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
