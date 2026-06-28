# TAL-43 — Engine catena: individuazione e collegamento procedimenti

- **Epica:** E1 — Motore + Modulo 1
- **Ruolo:** 🔤 NLP + 🧭 TL
- **Priorità:** P2
- **Stato:** Done
- **Branch:** `feat/TAL-30-dashboard-mvp`

## 🎯 Obiettivo

Implementare le tre strategie deterministiche per **individuare** quali atti
appartengono allo stesso procedimento e ricostruire la catena cronologica.

## 📚 Contesto

Il problema non è solo "raggruppa atti con lo stesso CIG" — il CIG spesso manca
o viene citato solo in alcuni atti. Bisogna individuare catene anche quando i link
sono impliciti (riferimento testuale, oggetto simile).

## ✅ Task

- [x] `classifica_ruolo(testo, tipo_atto)` — regex ordinati per priorità (revoca > annullamento > … > avvio)
- [x] `estrai_riferimenti(testo)` — CIG, CUP, numero_atto (regex deterministici)
- [x] **Strategia 1** `collega_per_cig(conn, cig)` — collegamento certo per CIG identico
- [x] **Strategia 2** `collega_per_riferimenti_incrociati(conn)` — legge CIG/numero_atto citati nel testo_estratto e collega al procedimento già noto
- [x] **Strategia 3** `collega_per_oggetto_simile(conn, ente_id)` — Jaccard trigrammi su oggetto normalizzato (soglia 0.35); catene marcate `metodo_individuazione = 'oggetto_simile_da_verificare'`
- [x] `ricostruisci_catene(conn, ente_id)` — orchestratore che applica le tre strategie in ordine
- [x] `costruisci_catena_da_testi(testi)` — versione in-memory per fascicoli M1 multi-PDF
- [x] 21 test (classifica_ruolo × 8 + estrai_riferimenti × 4 + DB × 9)

## 🧪 Criteri di accettazione

- [x] `classifica_ruolo("Si revoca il bando…")` → `"revoca"` (priorità revoca su avvio)
- [x] `collega_per_cig` idempotente (doppia esecuzione → stesso proc_id)
- [x] `costruisci_catena_da_testi` ordina cronologicamente e inferisce `stato_finale`
- [x] `collega_per_oggetto_simile` crea catena marcata "da_verificare" (richiede revisione)

## 🔗 Dipendenze

TAL-42 ✅, TAL-4 ✅ (CIG già estratti), TAL-21 ✅.

## 📝 Note implementative

- File: `src/talia/engine/catena.py`
- Priorità pattern ruolo: `revoca > annullamento > aggiudicazione > proroga > modifica > avvio`
  (un atto può citare sia "bando" sia "revoca" → deve vincere revoca)
- Strategia 3 (oggetto simile): trigrammi su oggetto normalizzato (lowercase, no stopword IT).
  Soglia 0.35 empirica — va calibrata su dati reali (TAL-12).
- `metodo_individuazione` in `procedimenti` traccia come è stata trovata la catena
  → permette filtrare in dashboard le catene "da verificare" vs. "certe".
