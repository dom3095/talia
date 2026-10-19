# TAL-40 — README pubblico + contributing

- **Epica:** E4 — Scale-up & community
- **Ruolo:** 🧭 TL
- **Priorità:** P3
- **Stato:** Review
- **Branch:** `docs/TAL-40-readme-community`

## 🎯 Obiettivo
Rendere il progetto accogliente per la community civic tech: README, contributing, licenza, codice di condotta.

## 📚 Contesto
Crescita via open source ([roadmap tappa 5](../wiki/08-roadmap.md)): OpenPolis, onData, tesi universitarie.

## ✅ Task
- [x] `README.md` pubblico: cos'è TALIA, screenshot/report d'esempio, come si installa/usa
- [x] `CONTRIBUTING.md`: flusso branch/PR, come prendere una card dalla board
- [x] `LICENSE` open source (AGPL-3.0-or-later, già in `LICENSE` e `pyproject.toml`)
- [x] `CODE_OF_CONDUCT.md`
- [x] Issue template che richiamano le card/epiche
- [x] Sezione "avvertenze legali" sintetica e ben visibile

## 🧪 Criteri di accettazione
- [ ] Un nuovo contributor capisce in 5 minuti cos'è e come contribuire
- [x] Licenza scelta e applicata
- [x] Disclaimer/posizionamento chiari nel README

## 🔗 Dipendenze
Idealmente dopo un prototipo dimostrabile (TAL-12).

## 📝 Note
Scelta licenza non banale per un tool civico: valutare copyleft (AGPL) per tenere aperte le derivazioni. Discutere col team.

## 🔬 Tentativi

### 2026-10-19 — Tentativo 1
**Approccio:** README riscritto per chi arriva da fuori (cosa fa, stato dei tre
moduli, prova in 5 minuti sul fascicolo d'esempio, come contribuire), più
`CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1 per
riferimento + due regole proprie: niente accuse, niente dati personali) e tre
template di issue (segnalazione sbagliata, comune/scraper, proposta).
**Esito:** ✅
**Appreso:** il README precedente era fermo allo Sprint 1 (check 3 "previsto",
Python 3.11 mentre `pyproject` richiede 3.12, nessuna menzione dei Moduli 2-3).
La copertura dichiarata altrove (83%) non corrisponde al registro attuale:
ricalcolata dal registro + `data/comuni_sicilia.csv` → 258 comuni, 81,0%.
Il criterio "un nuovo contributor capisce in 5 minuti" resta da verificare con
una persona vera.
