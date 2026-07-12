# TAL-52 — Deduplicazione atti tra scraper ridondanti sullo stesso comune

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🕷️ SCR
- **Priorità:** P3
- **Stato:** Backlog

## 🎯 Obiettivo

Evitare che un atto dello stesso comune, scaricato da due scraper diversi (piattaforme
diverse per lo stesso `codice_istat`), finisca duplicato in `atti` o produca red flags
raddoppiati.

## 📚 Contesto

Con TAL-50 (PR #12) `data/registro_scraper.csv` contiene deliberatamente due comuni
registrati su piattaforme diverse per ridondanza a costo zero (se una piattaforma cambia
HTML o va giù, l'altra continua a coprire il comune):

- **Campofelice di Roccella** (082017): `campofelicediroccella` (halley) + `campofeligerocchella` (jcitygov)
- **Partanna** (081015): `partanna` (halley) + `partanna_tp` (portalepa)

`registry.py::valida_registro` non blocca i duplicati di `codice_istat` tra slug diversi
(controlla solo slug duplicati) — comportamento voluto, non un bug.

Il rischio non è nella tabella `enti` (l'upsert su `codice_istat` collassa già le due righe
sullo stesso ente, vedi `HANDOFF.md`), ma in `atti`: se le due piattaforme espongono lo
stesso atto con `url_fonte` diverso (es. due CMS diversi che pubblicano lo stesso
provvedimento), oggi verrebbe inserito due volte (l'unicità è su `ente × url_fonte`, non
sul contenuto dell'atto) — con rischio di **red flags raddoppiati** per un comune che in
realtà non ha 2x l'attività di cui gli altri.

**Non ancora osservato in pratica** — è una card preventiva, non una correzione di un bug
riscontrato.

## ✅ Task

- [ ] Dopo qualche run reale su Campofelice di Roccella e Partanna, verificare se le due
      fonti espongono effettivamente atti sovrapposti (stesso numero/data/oggetto) o sono
      complementari (es. un CMS più aggiornato dell'altro, zero overlap)
- [ ] Se c'è overlap: definire una chiave di deduplicazione a livello di contenuto (es.
      `numero_atto` + `data_atto` + `ente_id`, non solo `url_fonte`) e decidere se tenerla
      come `UNIQUE` in DB o come step di dedup nel runner
- [ ] Se non c'è overlap: chiudere la card come "non serve", documentare in
      `docs/wiki/14-censimento-albi.md` perché le due fonti sono complementari

## ❓ Domande aperte

- [ ] La deduplicazione va fatta solo per questi 2 comuni noti o in modo generico per
      qualunque `codice_istat` con più righe attive nel registro? (da chiedere a Dom quando
      si affronta la card — impatta se la soluzione va in `registry.py`/`db.py` o resta
      locale ai 2 casi)

## 🔗 Dipendenze

TAL-50 (origine del caso), `src/talia/modulo2_scraping/db.py` (vincolo UNIQUE attuale su
`atti`), `src/talia/modulo2_scraping/registry.py`

## 📝 Note

Bassa priorità: costo di non farla è "qualche red flag doppio su 2 comuni su ~245", non
un rischio sistemico. Da rivalutare se in futuro si aggiungono altri comuni con doppia
registrazione intenzionale.
