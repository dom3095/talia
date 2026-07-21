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
  ✅ **Implementati** in `src/talia/engine/checklist/` (vedi [11 — Implementazione](11-implementazione-motore.md)).
- **Check 3** → unico che richiede LLM. ✅ **Implementato** (TAL-11) in
  `src/talia/engine/checklist/check3_motivazione.py`. A differenza degli altri, **non** è
  registrato nel registry automatico (richiede sia gli esiti dei check precedenti sia una
  chiamata di rete al LLM locale): va abilitato esplicitamente con
  `analizza_testi(..., valuta_llm=True)` o `talia analizza ... --llm`. Disattivato di default.
- **Check 4** → estrazione/classificazione, alimenta statistiche, **non** è una red flag.
- **Check 7** → dipende dal Modulo 2 (scraping). Inizialmente stub.

### Stato implementazione (Sprint 1)

| Check | Modulo | Esiti possibili | Note |
|-------|--------|-----------------|------|
| 1 base giuridica | `check1_base_giuridica.py` | 🟢🟡🔴 | coerenza via parole spia, da validare con ⚖️ LEX |
| 2 termini 12 mesi | `check2_termini.py` | 🟢🟡🔴⚪ | solo annullamenti; date mancanti → 🟡, mai crash |
| 3 qualità motivazione | `check3_motivazione.py` | 🟢🟡🔴⚪ | LLM (qwen3:4b/Ollama) + RAG (BM25, `engine/rag.py`); solo se un altro check ha già flaggato; ⚪ altrimenti |
| 5 avvio art. 7 | `check5_avvio.py` | 🟢🔴 | assenza di menzione ≠ omissione provata |
| 6 firmatari | `check6_firmatari.py` | 🟢🟡⚪ | sovrapposizione → 🟡 conservativo |

## Distinzione fondamentale: revoca ≠ annullamento

- **Revoca** (art. 21-*quinquies* L. 241/90): per sopravvenuti motivi di opportunità, *ex nunc*.
- **Annullamento d'ufficio** (art. 21-*nonies*): per illegittimità originaria, *ex tunc*, entro termine ragionevole (≤ 12 mesi per l'autotutela su provvedimenti attributivi di vantaggi).

Usare l'istituto sbagliato nella motivazione = incoerenza → red flag check 1.

## Output del report

Per ogni check: stato (🟢🟡🔴), citazione testuale con offset, riferimento normativo, una riga di
spiegazione, disclaimer finale.

[→ 05 Red flags batch](05-red-flags-batch.md)