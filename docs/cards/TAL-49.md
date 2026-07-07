# TAL-49 — Censimento albi pretori e rollout scraper comuni siciliani

- **Epica:** E3 — Copertura territoriale
- **Ruolo:** 🕷️ SCR
- **Priorità:** P1
- **Stato:** In Progress
- **Branch:** `feat/E3-censimento-comuni-sicilia`

## 🎯 Obiettivo
Copertura scraper estesa oltre i capoluoghi: censimento piattaforma per tutti i 391 comuni siciliani (in ordine di popolazione) e attivazione degli scraper sulle piattaforme già supportate (jCityGov in primis).

## 📋 Spec

### Interfaccia
```text
data/comuni_sicilia.csv                # denominazione, provincia, codice_istat, popolazione (ordinato desc)
docs/wiki/14-censimento-albi.md        # tabella comune → URL albo → piattaforma → stato scraper
scripts/run_scrapers.py                # _JCITYGOV_COMUNI esteso; runner registrati dinamicamente
```

### Comportamento
1. Sweep deterministico del pattern `https://<slug>.trasparenza-valutazione-merito.it` (jCityGov) su tutti i comuni.
2. Ogni hit verificato con run reale a 2 pagine su DB isolato prima di entrare in `_JCITYGOV_COMUNI`.
3. Comuni non-jCityGov nella fascia alta di popolazione: esplorazione dedicata (agent economico) e classificazione piattaforma nella wiki.
4. Catania (URBI, HTTP puro) e Palermo (SISPI, Playwright) come scraper dedicati, card separate se non banali.

### Casi limite
- Slug non standard (es. `palmadimontechiaro` senza spazi, alias tipo Mojo/Moio) → verifica manuale, non inferire.
- Hit jCityGov con albo vuoto o portlet assente → il run di verifica a 2 pagine lo smaschera; non aggiungere al registro.
- Sito irraggiungibile → loggare in Tentativi e passare oltre, ritentare in coda.

## ❓ Domande aperte
- [ ] I nuovi comuni jCityGov verificati entrano subito nel default run o restano opt-in fino a conferma di Dom? (scelta provvisoria: entrano nel default; da confermare in review PR)

## 📚 Contesto
`CLAUDE.md` (tabella scraper, "Come aggiungere uno scraper"), `docs/wiki/13-scraper-status.md`.

## ✅ Task
- [x] Lista 391 comuni per popolazione (`data/comuni_sicilia.csv`)
- [x] Refactor registrazione dinamica runner jCityGov
- [ ] Sweep jCityGov completo + wiki censimento
- [ ] Verifica 2-pagine per ogni hit e aggiornamento `_JCITYGOV_COMUNI`
- [ ] Esplorazione Palermo (agent) → verdetto HTTP vs Playwright
- [ ] Scraper Catania (URBI) — bloccato: server giù il 2026-07-07
- [ ] Tabella scraper in CLAUDE.md + BOARD aggiornati

## 🧪 Criteri di accettazione
- [ ] Ogni comune aggiunto ha un run di verifica riuscito su DB isolato (atti > 0, url_fonte validi)
- [ ] Wiki censimento con URL e piattaforma per ogni comune classificato
- [ ] Test passano (`pytest`)
- [ ] DoD rispettata (vedi CLAUDE.md)

## 🔬 Tentativi

### 2026-07-07 — Tentativo 1
**Approccio:** Lista comuni: join ISTAT (Elenco comuni italiani, regione 19) × Wikipedia (popolazione).
**Esito:** ✅ 391/391 (3 alias risolti a mano: Calatafimi-Segesta, Mojo/Moio Alcantara, Tripi/Tripi-Abakainon).
**Appreso:** l'elenco ISTAT non ha la popolazione; Wikipedia sì ma con grafie leggermente diverse — serve normalizzazione + alias espliciti.

### 2026-07-07 — Tentativo 2
**Approccio:** Catania URBI: GET su `servizionline.comune.catania.it` (ur1ME001.sto, DB_NAME=wt00041571), già funzionante nelle esplorazioni di fine giugno.
**Esito:** ❌ server irraggiungibile (porte 443 e 80 chiuse, anche www.comune.catania.it giù).
**Appreso:** non è un blocco anti-bot: l'intera infrastruttura del Comune non risponde. Ritentare più tardi; lo scraper si può scrivere sull'HTML già osservato, ma senza validazione live non si dichiara "OK".

### 2026-07-07 — Tentativo 3
**Approccio:** Sweep GET del pattern `<slug>.trasparenza-valutazione-merito.it` su tutti i 391 comuni (0.3s delay, fingerprint Liferay nel body).
**Esito:** ⚠️ in corso — già >20 hit tra i comuni sopra i 18k abitanti (Marsala, Bagheria, Modica, Acireale, Mazara, Paternò, Misterbianco, Alcamo, …).
**Appreso:** il parco jCityGov in Sicilia è molto più ampio dei 4 comuni già in registro: è il moltiplicatore principale della copertura.

## 🔗 Dipendenze
—

## 📝 Note
Messina resta esclusa (BUG-5, FortiGate lato Comune). I run di verifica usano sempre `--db /tmp/... --no-red-flags`, mai `talia.db`.
