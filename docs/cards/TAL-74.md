# TAL-74 — PortalePA/SoluzioniPA: 24 comuni bloccati dal filtro sull'User-Agent

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🕷️ SCR
- **Priorità:** P0 (ogni giorno senza run è copertura persa: gli albi espongono gli atti 15-30 giorni)
- **Stato:** Review — fix applicato e verificato dal vivo; resta aperta la richiesta al fornitore
- **Branch:** `fix/TAL-74-portalepa-user-agent` (da `main`, indipendente dalla catena #20-#23)

## 🎯 Obiettivo

Far tornare a produrre atti i 24 scraper PortalePA/SoluzioniPA (23 con
`portalepa.py`, 1 con `siracusa.py`) bloccati con HTTP 403 dal 2026-09-15, senza
mascherare l'identità del progetto, e chiedere al fornitore un'autorizzazione
esplicita.

## 📋 Spec

### Il problema

Audit di `scraper_runs` (2026-10-19): 24 scraper hanno fallito **tutti i giorni**
dell'ultima settimana con `HTTP Error 403: Forbidden`. Tutti hanno funzionato
fino al **2026-09-14** e hanno fallito per la prima volta il **2026-09-15**: un
solo evento, non 24 guasti. Sono tutti portali `*.soluzionipa.it` (più
`portalepa.comune.siracusa.it`, `portale.comune.gela.cl.it` e due
`servizi.comune.*`), cioè lo stesso fornitore.

### Causa, misurata

Non è l'IP né il client HTTP: è l'**User-Agent**. Stesso URL, stessa macchina:

| Richiesta a `caltagirone.soluzionipa.it/openweb/albo/albo_pretorio.php` | Esito |
|---|---|
| UA `TALIA-bot/0.1 (civic transparency; …)` — curl, IPv4 e IPv6, e urllib | **403** |
| UA predefinito di curl / urllib, o `Mozilla/5.0` | 200 |
| UA `Mozilla/5.0 (compatible; TALIA/0.1; +https://github.com/dom3095/talia)` | **200** |

Il filtro scatta con ogni probabilità sulla parola "bot". Ipotesi, non provata:
è una regola WAF aggiunta dal fornitore il 2026-09-15 (le intestazioni della
risposta non rivelano il prodotto). Altre piattaforme (jCityGov, Halley, URBI,
hspromila) usano lo stesso UA `TALIA-bot` e **non** sono bloccate: la modifica
riguarda solo PortalePA.

### Decisione (Dom, 2026-10-19): opzione 4

UA diverso **come misura temporanea dichiarata** + richiesta di autorizzazione
al fornitore. Si è scelta la variante che **mantiene l'identificazione**
(`Mozilla/5.0 (compatible; TALIA/0.1; +https://github.com/dom3095/talia)`, il
formato dei crawler dichiarati) invece di uno UA Chrome puro come in `anac.py`
(BUG-2): il gestore del portale che legge i log vede chi siamo e dove contattarci.

### Cosa NON si fa

- Non si cambia lo UA delle altre piattaforme: non sono bloccate e non c'è
  motivo di togliere la parola "bot" dove non serve.
- Non si prova a "indovinare" quali stringhe passino: una sola variante, quella
  che identifica il progetto.
- Se il fornitore rifiuta o chiede di fermarsi, **si ferma** lo scraping
  PortalePA e si documenta: l'accesso agli atti non vale la violazione di un
  divieto esplicito.

## ❓ Domande aperte

- [x] ~~Quale UA usare / come gestire il blocco?~~ → opzione 4, Dom 2026-10-19.
- [ ] Il fornitore risponde? (richiesta da inviare, testo qui sotto) — finché non
      risponde, lo UA resta misura temporanea.

## ✅ Task

- [x] Costante pubblica `USER_AGENT` in `fonti/portalepa.py`, importata da `fonti/siracusa.py`
- [x] 3 test: UA senza "bot" ma con riferimento al progetto; `siracusa` usa lo stesso;
      l'header arriva davvero nella richiesta
- [x] Verifica dal vivo di tutti e 24 gli scraper (1 pagina ciascuno, DB isolato): 24/24 OK
- [x] CLAUDE.md: fragilità "filtro WAF sull'UA"
- [ ] Inviare la richiesta al fornitore (testo sotto) — **Dom**
- [ ] Dopo il primo run notturno con la modifica: verificare in `scraper_runs` che i 24 non falliscano più

## 🔬 Tentativi

### 2026-10-19 — Tentativo 1
**Approccio:** confronto UA/client contro un portale bloccato; scelta della variante identificativa; run reale dei 24.
**Esito:** ✅
**Appreso:** il 403 era sull'UA (non sull'IP, come invece ipotizzava la decisione
Akamai di luglio per i runner GitHub). `Mozilla/5.0 (compatible; TALIA/0.1; +URL)`
passa e mantiene l'identificazione. Il backfill del buco 15/09→oggi **non** è
possibile in generale (gli albi espongono 15-30 giorni): si recupera solo ciò che
è ancora in pubblicazione, quindi il primo run con la modifica è il più importante.

## 📝 Bozza di richiesta al fornitore

*Scritta per: il supporto tecnico di SoluzioniPA (o i referenti dei singoli comuni
se non c'è un contatto centrale). Da completare con i recapiti prima dell'invio.*

> **Oggetto:** Richiesta di autorizzazione all'accesso automatizzato in lettura all'Albo Pretorio — progetto civico open source TALIA
>
> Buongiorno,
>
> mi chiamo [NOME], sviluppo **TALIA** (Trasparenza Atti Locali: Indicatori e Analisi,
> https://github.com/dom3095/talia), un progetto civico open source, senza scopo di
> lucro, che legge gli atti pubblicati negli Albi Pretori dei comuni siciliani per
> segnalare anomalie da verificare — mai accuse — sempre con rimando all'atto originale.
>
> I portali che utilizzano la vostra piattaforma (`*.soluzionipa.it` e le installazioni
> `portalepa`/`openweb`) vengono letti da noi **una volta a notte, intorno alle 03:30**,
> richiedendo soltanto le pagine pubbliche dell'Albo Pretorio (`/openweb/albo/albo_pretorio.php`
> e i dettagli collegati), senza autenticazione e in sequenza, mai in parallelo.
>
> Dal **15 settembre 2026** queste richieste ricevono risposta **HTTP 403** quando lo
> User-Agent contiene la parola "bot" (il nostro era `TALIA-bot/0.1`); la stessa richiesta
> con uno User-Agent diverso riceve 200. Presumiamo l'introduzione di un filtro sui crawler.
>
> Nel frattempo ci identifichiamo con
> `Mozilla/5.0 (compatible; TALIA/0.1; +https://github.com/dom3095/talia)`, in modo che
> nei vostri log sia riconoscibile chi siamo e dove scriverci.
>
> Vi chiediamo:
> 1. di **autorizzare esplicitamente** questo accesso (o indicarci lo User-Agent o l'indirizzo
>    che preferite vengano consentiti);
> 2. se esiste un **feed, un'API o un export** degli atti pubblicati da usare al posto della
>    lettura delle pagine;
> 3. se avete **limiti di frequenza** o fasce orarie da rispettare.
>
> Se preferite che l'accesso cessi, ci basta una vostra comunicazione e sospenderemo subito
> la lettura dei vostri portali.
>
> Grazie per l'attenzione,
> [NOME] — [EMAIL] — https://github.com/dom3095/talia
