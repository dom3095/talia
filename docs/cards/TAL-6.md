# TAL-6 — Check 1: base giuridica revoca/annullamento

- **Epica:** E1 — Motore + Modulo 1
- **Ruolo:** 🔤 NLP
- **Priorità:** P1
- **Stato:** Review
- **Branch:** `feat/TAL-1-modulo1-prototipo` (sviluppo congiunto Sprint 1)

## 🎯 Obiettivo
Check 1 della checklist: verifica presenza e coerenza della base giuridica dell'autotutela.

## 📚 Contesto
[wiki/04](../wiki/04-checklist-modulo1.md) check 1. Revoca (21-quinquies) ≠ annullamento (21-nonies) — vedi [glossario](../wiki/10-glossario.md).

## ✅ Task
- [x] Rilevare citazione di `21-quinquies` (revoca) e/o `21-nonies` (annullamento)
- [x] Classificare l'istituto dichiarato
- [x] Confronto con la motivazione: revoca = opportunità sopravvenuta; annullamento = illegittimità originaria
- [x] Esito 🟢 (base presente e coerente) / 🟡 (presente ma ambigua) / 🔴 (assente o incoerente)
- [x] Output con citazione testuale + offset + riferimento normativo

## 🧪 Criteri di accettazione
- [x] 🔴 se manca qualunque base giuridica
- [x] 🔴 se istituto incoerente con la motivazione (es. parla di illegittimità ma cita 21-quinquies)
- [x] Ogni esito porta la citazione testuale dell'atto
- [x] Test: caso coerente, caso assente, caso incoerente

## 🔗 Dipendenze
TAL-4, TAL-5.

## 📝 Note
La coerenza revoca/annullamento può richiedere un minimo di analisi semantica → per ora euristica deterministica su parole chiave; raffinamento LLM eventuale in TAL-11.
Validare i criteri con ⚖️ LEX.

## 📦 Consuntivo (12/06/2026)

Implementato in `engine/checklist/check1_base_giuridica.py`. Rileva 21-quinquies /
21-nonies; coerenza con la motivazione via euristica a parole spia (liste brevi e
prudenti). Esiti: 🔴 assente o incoerente, 🟡 ambiguo (entrambi citati) o motivazione non
riconducibile, 🟢 coerente. Ogni esito porta citazione con offset+pagina e riferimenti
normativi. Raffinamento LLM in TAL-11. **Da validare con ⚖️ LEX** le parole spia.
