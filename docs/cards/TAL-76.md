# TAL-76 — `concentrazione_diretti` segnala tutti gli enti: riprogettare la regola

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🔤 NLP + ⚖️ LEX
- **Priorità:** P2 (la regola è disattivata: non blocca nulla, ma manca un indicatore)
- **Stato:** To Do — regola **disattivata** nel runner (2026-10-19, PR TAL-73); da riprogettare
- **Branch:** —

## 🎯 Obiettivo
Un indicatore di concentrazione che misuri davvero il ricorso agli affidamenti
diretti (o allo stesso fornitore), invece di contare come "diretto" ogni atto
che non sia un bando.

## 📋 Spec

### Il problema (misurato su `talia.db`, 2026-10-19)
`red_flags/concentrazione.py` conta `tipo != 'bando'` come affidamento diretto.
Nel DB solo **208 atti** hanno tipo `bando`; tutto il resto (determine,
delibere, avvisi, ordinanze, liquidazioni) finisce tra i "diretti".

| Misura | Valore |
|---|---|
| flag in DB prima della disattivazione | 904 |
| enti-anno segnalati, senza SmartCIG | **510** |
| enti-anno con ≥10 atti d'albo (il minimo della regola) | **510** |

La regola segnala il 100% dei casi che può valutare: nessuna informazione, e la
descrizione del flag ("oltre l'80% di affidamenti diretti") non è vera.

### Decisione presa
Regola tolta dal run (`runner.REGOLE_DISATTIVATE`), flag esistenti cancellati
a ogni run. Il codice della regola resta, con i suoi test.

### Direzioni per la riprogettazione (da valutare con ⚖️ LEX)
- **Denominatore giusto:** solo atti che sono affidamenti (determine a
  contrarre / di affidamento), non tutto l'albo. Richiede di classificare il
  tipo di procedura dall'oggetto o dal testo.
- **SmartCIG:** il tracciato ANAC ha la modalità di scelta del contraente —
  verificare se è nel CSV mensile e persisterla nei `metadati`; darebbe un
  numeratore esatto (affidamento diretto vs procedura aperta) senza regex.
- **Confronto tra pari** (principio 3 di wiki 05): soglia relativa a comuni di
  taglia simile invece dell'80% assoluto.
- **Per fornitore** (il senso originale in wiki 05): richiede l'aggiudicatario,
  che oggi non persistiamo.

## ❓ Domande aperte
- [ ] Quale delle direzioni sopra (anche combinate)? Da decidere prima di
      implementare.

## 🔗 Dipendenze
TAL-23 (regola originale), TAL-73 (stessa misura sul frazionamento).
