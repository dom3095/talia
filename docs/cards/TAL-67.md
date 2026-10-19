# TAL-67 — Dashboard: aggregati temporali per comune e provincia

- **Epica:** E3 — Dashboard
- **Ruolo:** 📊 FE
- **Priorità:** P1
- **Stato:** Review
- **Branch:** `feat/TAL-66-run-giornaliero-aggregati`

## 🎯 Obiettivo

Per ogni comune e per ogni provincia: volumi di atti aggregati per settimana,
mese, trimestre e semestre, più il dettaglio giornaliero dei documenti
ingeriti.

## 📚 Contesto

La tab 📈 Statistiche (TAL-30) mostra solo il presente: totali complessivi e
un trend giornaliero di ingestione a 7-90 giorni, senza filtri territoriali e
senza granularità superiori al giorno. Non risponde a "quanti atti ha
prodotto la provincia di Ragusa nel secondo trimestre".

## 📋 Spec

**Due assi temporali distinti, mai mescolati** — è il punto delicato della
card:

| Asse | Espressione | Risponde a |
|------|-------------|-----------|
| `atto` | `COALESCE(a.data_atto, a.data_pub)` | attività amministrativa del territorio |
| `ingestione` | `date(a.data_accesso)` | salute della pipeline di raccolta |

`COALESCE` e non `data_atto`: l'80% degli atti nel DB ha `data_atto` NULL
(molti scraper leggono solo la pagina-lista dell'albo, che espone la finestra
di pubblicazione). È la stessa trappola già costata un bug in TAL-48, dove il
codice funzionava sui test — le fixture hanno sempre `data_atto` valorizzato —
e restituiva zero righe sul DB reale. Per questo i test di questa card ne
includono uno esplicito con solo `data_pub`.

I due assi non sono intercambiabili e la UI lo dice: sull'asse di ingestione
un backfill storico concentra anni di atti in un giorno solo, e leggerlo come
attività del comune sarebbe un errore di interpretazione.

**Granularità:** giornaliera, settimanale, mensile, trimestrale, semestrale.
La settimana è ancorata al **lunedì** via `date(d,'weekday 0','-6 days')`
invece di `strftime('%W')`: l'etichetta è una data vera, ordinabile e senza
le ambiguità di numerazione a cavallo d'anno.

**Date non plausibili escluse:** sul DB reale esistono righe con anni
palesemente corrotti (`0202-06-16`, refuso nell'atto sorgente) che
sfonderebbero l'asse dei grafici. Il limite superiore non è "oggi" ma
oggi+90gg, perché `data_pub` è la data di *inizio* pubblicazione e alcuni albi
pubblicano con decorrenza futura — quelle non sono anomalie.

**Nessuna nuova dipendenza:** `st.bar_chart` accetta una lista di dict con
`x=`/`y=`, niente pandas esplicito (coerente con il resto di `app.py`).

## ✅ Task

- [x] `src/talia/modulo3_dashboard/aggregati.py` — funzioni pure, nessun
      import di Streamlit (testabili senza avviare l'app)
- [x] Tab 📅 Aggregati in `app.py`: selettori territorio/granularità/asse,
      serie con variazione sul periodo precedente, dettaglio giornaliero di
      ingestione con **gli zeri espliciti** (un giorno mancante nel grafico
      nasconde esattamente l'informazione che interessa: nessun run è girato),
      classifiche per provincia e per comune, stato degli scraper
- [x] 22 test in `tests/test_aggregati.py` + 4 in `tests/test_dashboard.py`
- [x] Verifica dal vivo con `AppTest.from_file` su `talia.db` reale: 0
      eccezioni

## 🔬 Tentativi

### 2026-08-18 — Tentativo 1
**Approccio:** verifica degli aggregati sul DB reale prima di considerarli
finiti.
**Esito:** ✅
**Appreso:** i numeri sono coerenti tra granularità (2026-T3 = 39.648 =
somma dei mesi luglio+agosto) e il grafico di ingestione giornaliera rende
visibile a colpo d'occhio il problema che TAL-66 risolve: **13 giorni
consecutivi a zero** dal 2026-08-07 al 2026-08-18. Il caso limite atteso
compare davvero anche sui dati veri: una settimana `2026-08-31` con 1 solo
atto, cioè una `data_pub` con decorrenza futura — confermando che tagliare le
date future a "oggi" sarebbe stato sbagliato.
