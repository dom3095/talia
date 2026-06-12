# 04 — Checklist Modulo 1: caso revoca/annullamento

[← Home](00-home.md)

Checklist per il caso d'uso prioritario: **revoca/annullamento** di concorsi e gare. Ogni check produce
verde/giallo/rosso con citazione testuale e riferimento normativo.

| # | Check | Metodo | Red flag se… |
|---|-------|--------|--------------|
| 1 | Base giuridica dichiarata | regex su "21-quinquies" / "21-nonies" (L. 241/90) | assente, o istituto incoerente con la motivazione (revoca ≠ annullamento) |
| 2 | Termini dell'autotutela | estrazione date atto originario / atto di annullamento | annullamento d'ufficio oltre **12 mesi** dall'atto |
| 3 | Qualità della motivazione | LLM: specifica vs boilerplate; densità; requisiti giurisprudenziali (interesse pubblico concreto e attuale, comparazione con affidamenti dei privati) | motivazione generica, di poche righe, mero "ripristino di legalità" |
| 4 | Violazione autodichiarata | LLM/NER: estrazione e classificazione dell'illegittimità dichiarata nell'atto | — (non è red flag: è dato prezioso per le statistiche) |
| 5 | Comunicazione avvio procedimento (art. 7 L. 241) | ricerca menzione nell'atto | assente nei confronti dei partecipanti |
| 6 | Coerenza firmatari | confronto firmatari indizione vs annullamento | stesso dirigente che si auto-annulla a ridosso della graduatoria |
| 7 | Follow-up | collegamento con atti successivi (scraping) | ribandito con requisiti modificati in modo mirato; riaffidamento a soggetto diverso dopo revoca |

## Note implementative

- **Check 1, 2, 5, 6** → deterministici (regex + estrazione date/firmatari). Prioritari, facili da testare.
- **Check 3** → unico che richiede LLM. Da fare per ultimo, solo sui flaggati.
- **Check 4** → estrazione/classificazione, alimenta statistiche, **non** è una red flag.
- **Check 7** → dipende dal Modulo 2 (scraping). Inizialmente stub.

## Distinzione fondamentale: revoca ≠ annullamento

- **Revoca** (art. 21-*quinquies* L. 241/90): per sopravvenuti motivi di opportunità, *ex nunc*.
- **Annullamento d'ufficio** (art. 21-*nonies*): per illegittimità originaria, *ex tunc*, entro termine ragionevole (≤ 12 mesi per l'autotutela su provvedimenti attributivi di vantaggi).

Usare l'istituto sbagliato nella motivazione = incoerenza → red flag check 1.

## Output del report

Per ogni check: stato (🟢🟡🔴), citazione testuale con offset, riferimento normativo, una riga di
spiegazione, disclaimer finale.

[→ 05 Red flags batch](05-red-flags-batch.md)