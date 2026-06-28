# TAL-44 — Red flag: revoca/annullamento in catena procedimento

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🔤 NLP + ⚖️ LEX
- **Priorità:** P2
- **Stato:** Done
- **Branch:** `feat/TAL-30-dashboard-mvp`

## 🎯 Obiettivo

Rilevare automaticamente i procedimenti che hanno subìto una **revoca o annullamento
in autotutela**, calcolando il tempo trascorso dall'avvio e tracciando l'intera catena.

## 📚 Contesto

Revoca e annullamento in autotutela (artt. 21-quinquies e 21-nonies L. 241/1990) sono
legittimi ma richiedono motivazione rafforzata. Rilevarli automaticamente consente:
- di segnalare procedimenti potenzialmente anomali (es. revoca dopo 30 giorni senza motivazione pubblica);
- di tenere traccia di un ente che revoca sistematicamente le proprie gare.

**Disclaimer obbligatorio:** segnalazione da verificare, non accertamento.

## ✅ Task

- [x] `RevocaInCatenaRilevata` dataclass (procedimento_id, ente_id, cig, oggetto, stato_finale, data_avvio, data_revoca, giorni_elapsed, metodo_individuazione, atti)
- [x] `rileva_revoche_in_catena(conn)` — filtra procedimenti con `stato_finale IN ('revocato','annullato')` che hanno almeno un atto `ruolo=avvio`
- [x] Calcolo `giorni_elapsed` tra data_avvio e data_revoca
- [x] Integrato in `runner.esegui_tutti()` — chiamato dopo `ricostruisci_catene`
- [x] Salvato in DB come `tipo_flag='revoca_in_catena'`, severità `alta`
- [x] 6 test (revoca da CIG, annullamento, no-flag senza avvio, no-flag aggiudicazione, tabella assente, giorni_elapsed)

## 🧪 Criteri di accettazione

- [x] `rileva_revoche_in_catena` richiede avvio + revoca per generare flag (non solo revoca)
- [x] Procedimento aggiudicato regolarmente → nessun flag
- [x] `giorni_elapsed` corretto (test: 30 giorni)
- [x] Se tabella `procedimenti` assente → lista vuota (no crash)
- [x] Descrizione del flag include metodo di individuazione della catena

## 🔗 Dipendenze

TAL-42 ✅, TAL-43 ✅, TAL-23 ✅ (runner).

## 📝 Note implementative

- File: `src/talia/modulo2_scraping/red_flags/catena_revoca.py`
- `esegui_tutti` chiama `ricostruisci_catene(conn)` prima di tutti i red flag
  → le catene vengono sempre aggiornate prima di cercare le revoche.
- Prossimo passo (⚖️ LEX): validare la soglia "revoca sospetta" — quanti giorni
  tra avvio e revoca rendono l'atto anomalo? Attualmente tutti i revocati vengono
  segnalati; in futuro si potrebbe filtrare per giorni_elapsed < soglia.
