# TAL-45 — Dashboard M3: tab timeline procedimento

- **Epica:** E3 — Dashboard
- **Ruolo:** 📊 FE
- **Priorità:** P2
- **Stato:** Done
- **Branch:** `feat/TAL-30-dashboard-mvp`

## 🎯 Obiettivo

Aggiungere un tab **⛓️ Procedimenti** alla dashboard Streamlit che mostri la
timeline degli atti di ogni procedimento individuato per un comune.

## 📚 Contesto

Una catena "bando → revoca" visualizzata come timeline è molto più leggibile
di una lista di red flag astratti. L'utente può vedere in un colpo solo:
- quanti atti compongono il procedimento;
- il ruolo di ciascuno (avvio/modifica/revoca/…);
- il link all'atto ufficiale;
- se è stata individuata automaticamente o richiede verifica.

## ✅ Task

- [x] Costanti `ICONE_RUOLO` e `ETICHETTE_STATO_FINALE` per la UI
- [x] `_carica_procedimenti_per_ente(conn, ente_id)` — query con COUNT atti
- [x] `_carica_atti_procedimento(conn, proc_id)` — lista atti ordinata per data
- [x] `_mostra_procedimenti(conn)` — selectbox comune → expander per procedimento → timeline atti
- [x] Expander aperto automaticamente per i procedimenti revocati/annullati
- [x] Privacy piccoli comuni: oggetto anonimizzato, timeline non mostrata
- [x] Warning disclaimer su procedimenti revocati/annullati
- [x] Graceful degradation: se tabella `procedimenti` assente → messaggio "esegui batch"
- [x] Aggiunta etichetta `revoca_in_catena` in `ETICHETTE_TIPO_FLAG`

## 🧪 Criteri di accettazione

- [x] Tab visibile nella navigazione principale
- [x] Procedimento revocato → expander aperto + warning
- [x] Piccolo comune → oggetto anonimizzato
- [x] Se DB non ha la tabella procedimenti → no crash, messaggio informativo
- [ ] Test Streamlit — da aggiungere (TAL-45 aperto)

## 🔗 Dipendenze

TAL-42 ✅, TAL-43 ✅, TAL-30 ✅.

## 📝 Note implementative

- File: `src/talia/modulo3_dashboard/app.py`
- `_carica_procedimenti_per_ente` usa `LEFT JOIN atti` per contare gli atti collegati.
- Metodo di individuazione (`cig` vs `oggetto_simile_da_verificare`) mostrato in caption
  così l'utente sa quanto fidarsi del collegamento.
- Prossimi passi: grafico Gantt o timeline interattiva (Plotly) per catene lunghe.
