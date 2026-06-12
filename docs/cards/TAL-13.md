# TAL-13 — Estrazione attori nominati e procedimenti (regex + NER)

- **Epica:** E1 — Motore + Modulo 1
- **Ruolo:** 🔤 NLP
- **Priorità:** P1
- **Stato:** Review
- **Branch:** `feat/TAL-1-modulo1-prototipo`

## 🎯 Obiettivo
Estrarre da ogni atto gli **attori nominati** (persona + ruolo istituzionale: Sindaco, Segretario
Generale, RUP, Responsabile del Procedimento…) e i **procedimenti/atti citati** (determinazioni,
delibere, note protocollo, avvisi, con numero/anno/data), per costruire il grafo del fascicolo.
Un livello **NER spaCy opzionale** scopre entità che le regex non coprono (pattern discovery).

## 📚 Contesto
Estende TAL-5. Serve al check 6 (ruoli oltre ai nomi), al futuro check 7 (follow-up: catena di
atti) e alle statistiche del Modulo 2/3. Nato dalla validazione TAL-12: il fascicolo reale contiene
attori con ruoli multipli (stesso Segretario = RPCT = Responsabile del Procedimento) e una catena
di atti citati (det. 35/2025 → nota prot. → det. revoca).

## ✅ Task
- [x] `engine/attori.py`: estrazione deterministica attori (ruolo→nome, con offset/pagina)
- [x] Estrazione riferimenti ad atti: tipo, numero/anno, data, con offset
- [x] Script `scripts/estrai_attori.py`: report per fascicolo (attori, procedimenti, ricorrenze)
- [x] Livello NER spaCy opzionale (`[nlp]`): PER/ORG non coperte dalle regex → pattern discovery
- [x] Test deterministici (senza spaCy) con casi positivi e negativi

## 🧪 Criteri di accettazione
- [x] Sul fascicolo reale 1: trova Segretario Generale, Responsabile del Procedimento, Sindaco
- [x] Trova la catena det. originaria → nota prot. → det. revoca con numeri e date
- [x] Lo script gira anche senza spaCy (degrada con messaggio chiaro)
- [x] Nomi = dato personale: output solo locale/interno, mai committato
- [x] Test passano (`pytest`)

## 🔗 Dipendenze
TAL-3, TAL-5. Alimenta TAL-9 (ruoli) e il futuro check 7.

## 📝 Note
Determinismo prima: le regex coprono i pattern noti; spaCy serve a *scoprirne* di nuovi da
promuovere poi a regole. Modello: `it_core_news_lg` se disponibile, fallback md/sm.

## 📦 Consuntivo (12/06/2026)

Implementato `engine/attori.py` (`estrai_attori`, `estrai_riferimenti_atti`) + script
`scripts/estrai_attori.py`. Sul fascicolo reale 1:
- attori ricostruiti su tutti gli atti: Segretario Generale, Responsabile del Procedimento,
  Presidente, Responsabile; ruoli senza nome (Sindaco, RPCT) registrati come anonimi;
- catena del procedimento ricostruita: det. 35/2025 → delibere Giunta → nota prot.
  18443/2026 → det. di revoca n. 16, con ricorrenze cross-atto;
- firma digitale "NOME COGNOME / Provider" ora estratta (pattern maiuscolo pieno con
  stoplist intestazioni).

**Esito NER (it_core_news_sm):** molto rumoroso sul lessico giuridico ("Determinazione"
come PER, "OGGETTO" come ORG) anche dopo il filtro anti-rumore; il livello deterministico
lo supera nettamente su questi documenti. Da riprovare con `it_core_news_lg` (~560MB) prima
di promuovere il NER nel motore: per ora resta solo strumento di discovery nello script.
