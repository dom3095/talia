# TAL-6 — Check 1: base giuridica revoca/annullamento

- **Epica:** E1 — Motore + Modulo 1
- **Ruolo:** 🔤 NLP
- **Priorità:** P1
- **Stato:** To Do
- **Branch:** `feat/TAL-6-check1-base-giuridica`

## 🎯 Obiettivo
Check 1 della checklist: verifica presenza e coerenza della base giuridica dell'autotutela.

## 📚 Contesto
[wiki/04](../wiki/04-checklist-modulo1.md) check 1. Revoca (21-quinquies) ≠ annullamento (21-nonies) — vedi [glossario](../wiki/10-glossario.md).

## ✅ Task
- [ ] Rilevare citazione di `21-quinquies` (revoca) e/o `21-nonies` (annullamento)
- [ ] Classificare l'istituto dichiarato
- [ ] Confronto con la motivazione: revoca = opportunità sopravvenuta; annullamento = illegittimità originaria
- [ ] Esito 🟢 (base presente e coerente) / 🟡 (presente ma ambigua) / 🔴 (assente o incoerente)
- [ ] Output con citazione testuale + offset + riferimento normativo

## 🧪 Criteri di accettazione
- [ ] 🔴 se manca qualunque base giuridica
- [ ] 🔴 se istituto incoerente con la motivazione (es. parla di illegittimità ma cita 21-quinquies)
- [ ] Ogni esito porta la citazione testuale dell'atto
- [ ] Test: caso coerente, caso assente, caso incoerente

## 🔗 Dipendenze
TAL-4, TAL-5.

## 📝 Note
La coerenza revoca/annullamento può richiedere un minimo di analisi semantica → per ora euristica deterministica su parole chiave; raffinamento LLM eventuale in TAL-11.
Validare i criteri con ⚖️ LEX.
