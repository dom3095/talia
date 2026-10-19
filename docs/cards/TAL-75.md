# TAL-75 — Fallimenti cronici residui: certificati Halley e ripasso dei transitori

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🕷️ SCR + ⚙️ OPS
- **Priorità:** P1
- **Stato:** Review
- **Branch:** `fix/TAL-75-halley-ssl-cronici`

## 🎯 Obiettivo
Riportare a zero i fallimenti *cronici* del run notturno che non dipendono dal
WAF PortalePA (TAL-74), e far recuperare nello stesso run gli scraper falliti
per una notte di rete instabile.

## 📋 Spec

### Comportamento
1. **Certificati:** gli scraper Halley con `CERTIFICATE_VERIFY_FAILED` in tutti
   i run della settimana 12-19/10 ricevono `skip_ssl=true` nel registro, come
   già fatto per Siculiana/Joppolo/San Giuseppe Jato. Sola lettura di dati
   pubblici: il rischio di un MITM è accettabile e coerente con la prassi.
2. **Ripasso:** a fine loop, gli scraper falliti con errore *transitorio*
   (timeout, handshake, connessione chiusa/resettata, risposta troncata,
   DNS/rete) vengono ritentati una volta, entro un budget complessivo
   (`--budget-ripasso`, default 3600s, `0` = disattivato). Il nuovo tentativo
   scrive la sua riga in `scraper_runs`; il report legge l'ultima.

### Casi limite
- Certificato non valido e HTTP 4xx/5xx → **non** si ritentano (si
  ripresenterebbero identici).
- Il traceback di un errore di certificato contiene `timeout=30` → conta solo
  la riga dell'eccezione (`sintesi_errore`).
- Notte con DNS giù per tutto il run → si ritentano tutti, ma falliscono in
  pochi secondi ciascuno; il budget evita comunque che il ripasso allunghi il
  run di ore in caso di timeout diffusi (il guasto di TAL-72).
- Un recupero al ripasso non conta come errore del run (exit code 0).

## ❓ Domande aperte
- [x] `skip_ssl` anche per certificati **scaduti**, non solo catena
      incompleta? → Sì (decisione delegata da Dom, 2026-10-19): sono dati
      pubblici in sola lettura, e il gestore del portale non è raggiungibile.

## ✅ Task
- [x] Diagnosi su `scraper_runs` (ultimi 8 run per scraper)
- [x] `skip_ssl=true` per 13 scraper Halley, verificato dal vivo
- [x] `run_report.e_transitorio()` + `ripassa_transitori()` in `run_scrapers.py`
- [x] Test (`tests/test_ripasso.py`, 16)
- [ ] Dopo il primo run notturno: i 13 non falliscono più; contare i recuperi
      al ripasso (`SELECT scraper_id, COUNT(*) FROM scraper_runs WHERE
      date(avviato_a)=date('now') GROUP BY 1 HAVING COUNT(*)>1`)

## 🧪 Criteri di accettazione
- [x] 13/13 scraper tornano atti dal vivo
- [x] Test passano (`pytest`)
- [ ] Al run notturno: falliti cronici (8/8 nell'ultima settimana) solo quelli
      con causa nota e documentata

## 🔬 Tentativi

### 2026-10-19 — Tentativo 1
**Approccio:** ultimo run di ogni scraper fallito + quota di fallimenti negli
ultimi 7 giorni.
**Esito:** ✅
**Appreso:** dei 55 falliti del 19/10 solo due famiglie sono croniche (8/8):
i 25 PortalePA in 403 (TAL-74, già corretto) e **13 Halley con certificato
rotto** (4 scaduti: Pace del Mela, Racalmuto, Santa Cristina Gela, Tortorici;
9 con catena incompleta: Calatafimi-Segesta, Casteltermini, Cattolica Eraclea,
Condrò, Fiumefreddo, Giuliana, Maletto, Sperlinga, Venetico). Gli altri sono
intermittenti e cadono negli stessi giorni (15/10, 19/10): Catania fallisce
3/8 per timeout ma di norma finisce in 2 minuti, Palermo e Trapani 2/8. È la
rete di quella notte, non i portali.

Verificato dal vivo con `skip_ssl`, 1 pagina ciascuno: **13/13** tornano atti
(7-35 per pagina).

Nota operativa: il CSV del registro ha righe con virgole non quotate nelle note;
riscriverlo con `csv.DictWriter` le altera. Le 13 righe sono state modificate
una per una.

## 🔗 Dipendenze
TAL-72 (tetto di tempo, report per causa), TAL-74 (403 PortalePA).
