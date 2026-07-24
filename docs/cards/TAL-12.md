# TAL-12 — Validazione su 10 fascicoli reali

- **Epica:** E1 — Motore + Modulo 1
- **Ruolo:** ⚖️ LEX
- **Priorità:** P1
- **Stato:** In Progress (1/10 fascicoli validati da LEX; altri 8 preparati con report
  automatico il 2026-07-21, in attesa di lettura — vedi sezione sotto)
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
- 🟡 check 3 (LLM, TAL-11, girato 2026-07-21) — la motivazione è narrativamente specifica
  (segnalazione del Sindaco su una fuga di notizie concorsuali) ma tratta come accertata una
  "**presunta** divulgazione" senza descrivere alcuna verifica autonoma del Segretario
  Generale prima di agire: carenza di istruttoria, osservazione emersa discutendo il caso con
  Dom e ora un criterio esplicito del check ([dettagli in TAL-11](TAL-11.md)). Prima del fix
  il check dava 🟢, mancando il problema — falso negativo corretto in corso di sviluppo, non
  ancora ri-verificato da ⚖️ LEX.

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

## 📦 Fascicoli 2-9 — preparati, in attesa di lettura ⚖️ LEX (2026-07-21)

`scripts/prepara_fascicoli_candidati.py` (nuovo, TAL-48/TAL-12): combina
`procedimenti_da_riapertura()` + `procedimenti_critici()` (esclusi i duplicati — una
catena già coperta da una riapertura non è anche selezionata come "critica" a sé), scarica
i PDF, li copia in `data/samples/<id>/` e lancia `talia analizza` per generare il report
automatico. Selezionati 9 candidati diversificati per ente — tutti risultati riaperture
(sono più narrabili: due bandi collegati). Locale, mai committato (vedi `.gitignore`:
`data/samples/[0-9]*/` ora ignora anche `report.*`/`fonte.json`, non solo i PDF — gap
chiuso in questa sessione, questi file contengono dati reali estratti dai PDF).

| Cartella | Ente | Rif. (red_flag/proc) | Report | Esito automatico |
|---|---|---|---|---|
| `data/samples/3/` | (ente 3) | riapertura 475 | ✅ | 0🟢 0🟡 2🔴 3 n/a |
| `data/samples/6/` | (ente 5) | riapertura 499 (Ragusa 11306) | ✅ | 0🟢 1🟡 2🔴 2 n/a |
| `data/samples/7/` | Palma di Montechiaro | riapertura 472 (proc. 692→703) | ✅ | 0🟢 0🟡 2🔴 3 n/a |
| `data/samples/8/` | (ente 10) | riapertura 517 | ✅ | 0🟢 0🟡 2🔴 3 n/a |
| `data/samples/9/` | (ente 11) | riapertura 477 | ✅ | 0🟢 0🟡 2🔴 3 n/a (52 PDF) |
| `data/samples/10/` | (ente 13) | riapertura 509 | ✅ | 0🟢 0🟡 2🔴 3 n/a |
| `data/samples/11/` | (ente 17) | riapertura 496 | ⚠️ nessuno | 63 PDF, OCR troppo lento (>15 min su un solo documento scansionato) — da rilanciare in background più a lungo, o scartare il candidato |
| `data/samples/12/` | Comune di Giarre | riapertura 491 | ✅ | 0🟢 1🟡 2🔴 2 n/a |
| `data/samples/13/` | San Giovanni la Punta | riapertura 476 | ✅ | 0🟢 0🟡 2🔴 3 n/a |

**Da fare per ciascuno (non automatizzato):** lettura umana ⚖️ LEX, confronto con l'esito
di TALIA, tabella falsi positivi/negativi, `talia.md`/wiki se emergono pattern nuovi.
`report.md`/`report.json` in ciascuna cartella per la lettura rapida.

**Anomalia riscontrata, non spiegata:** durante questa sessione `data/samples/2/`
(2 PDF preesistenti, non tracciati da nessuna card — materiale di test isolato di metà
giugno) è sparito dal filesystem. Nessun comando eseguito in sessione lo cancella
(verificato: nessun `rm`/`rmtree`/`unlink` nel codice toccato); causa non identificata.
Non erano dati sensibili noti (un PIAO e una determina generici), ma segnalato per
trasparenza.
