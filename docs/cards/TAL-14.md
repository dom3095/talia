# TAL-14 — Check 7: data breach GDPR non notificato

- **Epica:** E1 — Motore + Modulo 1
- **Ruolo:** ⚖️ LEX + 🔤 NLP
- **Priorità:** P1
- **Stato:** Review
- **Branch:** `feat/TAL-1-modulo1-prototipo`

## 🎯 Obiettivo

Rilevare il caso in cui un atto di autotutela descrive la divulgazione di dati personali
(es. bozza di graduatoria trapelata, atti interni riservati diffusi) senza menzionare
la notifica al Garante prevista dall'art. 33 GDPR entro 72 ore.

## 📚 Contesto

Emerso durante la validazione TAL-12 sul primo fascicolo reale (revoca selezione interna,
comune AG). L'atto descrive la presunta fuga della bozza di graduatoria come motivazione
della revoca — un evento che configura un potenziale data breach ai sensi dell'art. 4(12)
GDPR. L'atto non menziona né notifica al Garante né avvio di un procedimento interno di
accertamento della violazione.

Ulteriore red flag connesso: il Segretario Generale firmatario dell'atto è anche DPO del
comune → potenziale conflitto di interessi (art. 38(6) GDPR). Questo secondo aspetto
richiede dati esterni (check-8, dipende da TAL-25 scraping organigrammi).

## ✅ Task

- [x] `engine/checklist/check7_gdpr.py`: check deterministico
  - rileva `divulgazione/fuga + graduatoria/dati personali` (finestra 400 char)
  - 🔴 se breach descritto senza notifica Garante
  - 🟢 se notifica Garante menzionata
  - ⚪ NON_APPLICABILE se nessun breach descritto
- [x] Registrato in `checklist/__init__.py`
- [x] Test `tests/test_check7_gdpr.py` (5 casi: divulgazione/fuga positivi, assente, rosso, verde, N/A)

## 🧪 Criteri di accettazione

- [x] Sul fascicolo reale 1: rileva 🔴 (divulgazione graduatoria senza notifica Garante)
- [x] Testo senza eventi di divulgazione → NON_APPLICABILE (non produce falsi positivi)
- [x] Ogni esito 🔴 include citazione testuale dall'atto
- [x] Test passano (`pytest`)

## 🔗 Dipendenze

TAL-12 (validazione), TAL-13 (attori, per futuro check-8 DPO conflict).
Alimenta il futuro **TAL-25** (scraping organigrammi/DPO per check-8).

## 📝 Limiti noti

- L'assenza di menzione non prova l'omissione (la notifica può essere in atto separato).
- Pattern `_RE_DIVULGAZIONE` potrebbe non coprire circonlocuzioni inusuali → ampliare con
  nuovi fascicoli durante TAL-12.
- Check-8 (DPO = Segretario → conflitto) richede fonte esterna: rimandato a TAL-25.
