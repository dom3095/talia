# TAL-12 — Validazione su 10 fascicoli reali

- **Epica:** E1 — Motore + Modulo 1
- **Ruolo:** ⚖️ LEX
- **Priorità:** P1
- **Stato:** In Progress (1/10 fascicoli)
- **Branch:** `feat/TAL-1-modulo1-prototipo`

## 🎯 Obiettivo
Validare il prototipo Modulo 1 su **~10 fascicoli reali** (indizione + annullamento), misurando
falsi positivi/negativi e raffinando i check.

## 📚 Contesto
Chiusura della tappa 1 della [roadmap](../wiki/08-roadmap.md). È il test di realtà del prototipo.

## ✅ Task
- [ ] Raccogliere 10 fascicoli reali (anonimizzati per il repo, in `data/samples/`) — **1/10**
- [ ] Far girare il report su ciascuno — fatto sul fascicolo 1
- [ ] Confronto esito TALIA vs valutazione di un esperto ⚖️ LEX
- [ ] Tabella falsi positivi / falsi negativi per check
- [ ] Lista di raffinamenti per le regole (issue/card di follow-up)
- [ ] Documentare i risultati nella wiki

## 🧪 Criteri di accettazione
- [ ] Report generato per tutti e 10 i fascicoli senza crash
- [ ] Tasso di falsi positivi accettabile sui check deterministici (concordato col team)
- [ ] Nessun dato personale reale committato (campioni anonimizzati)
- [ ] Findings documentati + card di follow-up create

## 🔗 Dipendenze
TAL-10 (report), almeno TAL-6/TAL-7 (check minimi).

## 📝 Note
Una red flag è un invito a verificare: l'obiettivo non è "0 falsi positivi" ma rumore gestibile e
spiegazioni sempre corrette. Coinvolgere un giurista reale per il ground truth.

## 📦 Fascicolo 1 — revoca selezione interna, comune AG (12/06/2026)

4 PDF nativi (det. approvazione + bando + allegato contabile + det. di revoca in autotutela);
fonti pubbliche tracciate in `data/samples/1/sources.json`. **I PDF restano fuori dal repo**
(`.gitignore` esclude `*.pdf`: contengono nominativi reali).

**Esito finale (plausibile, da confermare con ⚖️ LEX):**
- 🔴 check 1 — la revoca cita solo un generico "Vista la L. 241/1990", mai il 21-quinquies.
- ⚪ check 2 — è una revoca, non un annullamento: correttamente non applicato.
- 🔴 check 5 — nessuna comunicazione di avvio; solo "pubblicazione sul sito vale notifica".
- 🟡 check 6 — stesso Segretario Generale firma approvazione e revoca.

**3 bug emersi e corretti (con test di regressione):**
1. Il boilerplate "si riserva di revocare" nei bandi li classificava come autotutela →
   classificazione a punteggio pesato (`punteggi_ruolo`), segnali forti vs deboli.
2. La selezione dell'atto in esame dipendeva dall'ordine alfabetico dei file → ora si
   sceglie il candidato col punteggio massimo.
3. "Pietro Amorosia" ≠ "Pietro Nicola Amorosia" per il check 6 (falso 🟢) → matching per
   sottoinsieme con ≥2 token comuni.

**Raffinamenti annotati per follow-up:** trattino opzionale in 21-quinquies/nonies (fatto);
firme digitali "NOME / Provider S.A." non estratte (ok per prudenza); date CCNL
("16.11.2022") rischiano di inquinare il check 2 sui fascicoli con annullamento.

## 📦 Candidati per i prossimi fascicoli (da TAL-48, 2026-07-20)

TAL-48 (integrazione pdf_download per le riaperture dopo revoca) ha scaricato PDF reali
di coppie bando-originale/bando-riaperto — materiale grezzo per i fascicoli 2-11, non
ancora passato dal report Modulo 1 né dalla validazione ⚖️ LEX:

- **Ragusa proc. 11306** (red_flag 499): lavori area verde, CIG — revocato 2022-07-27,
  riaperto 22 giorni dopo con oggetto quasi identico (Jaccard 0.86). PDF in
  `data/raw/pdf/comune_di_ragusa/11306/` (locale, gitignored).
- **Palma di Montechiaro proc. 692→703**: affidamento sorveglianza sanitaria annullato
  2023-11-20, re-affidato 2024-07-17 (Jaccard 0.76) — uno dei 3 casi noti già citati nel
  contesto di TAL-48. PDF in `data/raw/pdf/comune_di_palma_di_montechiaro/`.
- Altri 76 red flag `riapertura_dopo_revoca` disponibili in `talia.db` (query
  `SELECT * FROM red_flags WHERE tipo_flag='riapertura_dopo_revoca'`) per selezionarne
  altri via `python -m talia.modulo2_scraping.pdf_download --riaperture --limite N`.

Restano da fare per ciascuno (non automatizzato da TAL-48): far girare il report Modulo 1,
confronto con valutazione ⚖️ LEX, tabella falsi positivi/negativi.
