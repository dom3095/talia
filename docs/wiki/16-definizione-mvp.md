# 16 — Definizione di MVP: quando TALIA è "a terra"

[← Home](00-home.md)

> Scritta il 2026-10-19, su delega di Dom ("vorrei portare a terra il
> progetto"). Serve a sapere quando fermarsi: ogni criterio è misurabile, e
> ciò che non è qui è esplicitamente **dopo** l'MVP.

## L'MVP in una frase

Ogni notte TALIA raccoglie gli atti di oltre 250 comuni siciliani senza
perdere giorni. Calcola **solo** red flag che sa difendere, ciascuno con un link
vivo all'atto. Pubblica una **vista aggregata** con disclaimer, e offre il
Modulo 1 validato da un giurista su 10 fascicoli reali.

## Criteri, in ordine di dipendenza

### A. Raccolta affidabile (Modulo 2)

| Criterio | Come si misura | Stato 2026-10-19 |
|---|---|---|
| Nessun giorno senza run in 30 giorni | `SELECT date(avviato_a) FROM scraper_runs GROUP BY 1` senza buchi | ❌ buchi l'08/09 e il 03/10 (prima del tetto di TAL-72) |
| Run concluso prima del successivo | ora di fine nel log di `run_daily.sh` | ⏳ tetto di TAL-72 in `main` dal 19/10, primo run da misurare |
| Falliti cronici (8/8 run in una settimana) solo con causa documentata nel registro | query di TAL-75 | ⏳ #24 (403 PortalePA) + #25 (13 Halley SSL) |
| Copia del DB fuori dal disco, settimanale | file in `TALIA-backup/` | ⏳ #30 |
| Muti/stagnanti visibili ogni mattina nel report | `logs/ultimo_report.md` | ✅ muti (TAL-66), ⏳ stagnanti #29 |

### B. Red flag difendibili

| Criterio | Come si misura | Stato |
|---|---|---|
| Ogni regola attiva ha volumi misurati sul DB reale e un campione letto a mano | sezione in [wiki/05](05-red-flags-batch.md) | ⚠️ `frazionamento` e `concentrazione_diretti` erano indifendibili → #26 |
| Nessuna regola segnala la quasi totalità degli enti | quota di enti con ≥1 flag per regola | ⏳ dopo #26 |
| Ogni flag cita un link che funziona | campione di 30 flag, link aperti a mano | ❌ ~32% degli atti ha l'albo già scaduto; AT jCityGov (#28) e testo (#27) mitigano |

### C. Modulo 1 validato

| Criterio | Come si misura | Stato |
|---|---|---|
| 10 fascicoli reali letti da un ⚖️ giurista | [TAL-12](../cards/TAL-12.md) | ❌ 1/10; fascicoli 2-9 **già pronti con report**, serve solo la lettura |
| Tasso di falsi positivi per check, documentato | tabella in TAL-12 | ❌ dipende dal punto sopra |
| OCR provato su scansione | test automatico | ⏳ #31 |

**Questo è il collo di bottiglia dell'MVP, e non è un problema di codice:**
serve una persona con competenze di diritto amministrativo per qualche ora.

### D. Pubblicazione

| Criterio | Come si misura | Stato |
|---|---|---|
| Vista pubblica **aggregata** (per provincia/comune: conteggi, trend, flag per tipo), senza nominativi, con disclaimer | [checklist pre-pubblicazione](09-avvertenze-legali.md) tutta spuntata | ❌ la dashboard esiste ma è solo locale |
| Pubblicata gratis (Streamlit Community Cloud o HF Spaces) da uno **snapshot aggregato**, non dal DB intero | URL pubblico | ❌ |
| README e CONTRIBUTING per chi arriva da fuori | [TAL-40](../cards/TAL-40.md) | ⏳ #32 |

La pubblicazione richiede **un via libera esplicito di Dom**, per due motivi:
espone il progetto con il suo nome, e va fatta solo dopo B e C. Pubblicare
red flag non validati è il rischio che il principio n. 1 esiste per evitare.

## Ordine consigliato

1. Mergiare le PR aperte (#25 → #27 → #28 sono impilate; le altre sono
   indipendenti) e lasciar girare **una settimana** di run notturni.
2. Misurare A e B su quella settimana: durata, falliti, volumi dei flag,
   link vivi. Correggere ciò che emerge.
3. **In parallelo, C**: trovare il giurista e fargli leggere i fascicoli 2-9.
4. Costruire lo snapshot aggregato e la vista pubblica (D), passare la
   checklist di wiki 09, poi pubblicare.

## Fuori dall'MVP (deliberatamente)

- Riprogettazione di `concentrazione_diretti` ([TAL-76](../cards/TAL-76.md)).
- Amministrazione Trasparente di Halley e delle altre piattaforme.
- Testo e importi degli atti fuori da jCityGov; estrazione dell'importo
  dell'affidamento (riattiverebbe `frazionamento` sugli atti d'albo).
- Classificazione LLM nel run notturno.
- Messina e i ~130 comuni non coperti (copertura attuale: 258 comuni, 81%
  della popolazione).
- Registro attori (TAL-41), ground truth da sentenze (TAL-24), modulo DPO.
