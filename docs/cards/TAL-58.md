# TAL-58 — Dashboard: query duplicate + pulizia minore

- **Epica:** E3 — Dashboard
- **Ruolo:** 📊 FE
- **Priorità:** P3
- **Stato:** Review
- **Branch:** `feat/TAL-53-nome-ruolo-graduatoria` (proseguito sullo stesso branch)

## 🎯 Obiettivo
Findings del `/code-review` multi-agente (2026-08-08) su `modulo3_dashboard/app.py`:
query duplicate tra tab diversi, avviso privacy per i piccoli comuni scritto a mano in
due punti (già divergenti), un ternario annidato dove il resto del file usa dict lookup,
una somma ricalcolata invece di riusare un valore già disponibile.

## 📋 Spec

### Comportamento
1. **`_carica_enti`/`_carica_flags_per_ente` caricate una sola volta in `main()`**,
   passate ai tab che ne hanno bisogno invece di essere richiamate indipendentemente da
   `_mostra_panoramica`/`_mostra_comuni_virtuosi` (stesso dato) e da `_mostra_procedimenti`
   (stesso dato di `tab_comune`). Streamlit riesegue l'intero script ad ogni interazione
   con un widget: prima ogni rerun riemetteva la stessa query 2 volte.
2. **`_avviso_privacy_piccolo_comune(cosa_nascosta)`** (nuovo helper): unifica il banner
   privacy per i piccoli comuni, scritto a mano in `_mostra_dettaglio_comune` e
   `_mostra_procedimenti` con soglia/testo già leggermente divergenti.
3. **`ICONE_STATO_FINALE`** (nuovo dict, accanto a `ETICHETTE_STATO_FINALE`): sostituisce
   il ternario annidato per l'icona di stato di un procedimento, coerente con lo stile
   dict-lookup già usato altrove nel file (`ICONE_RUOLO`, `ETICHETTE_STATO_FINALE`).
4. **Copertura mappa**: `col1.metric` ora usa `copertura["coperti_comuni"]` (già
   calcolato da `_calcola_copertura_popolazione`) invece di ricalcolare la somma
   `per_stato["attivo"] + per_stato["escluso_default"]`.

### Casi limite / scelte di scope
- **Non aggiunta `@st.cache_data` ai loader SQL** (finding separato, stesso agente).
  Le funzioni cache già presenti nel file (`_carica_geojson_comuni`,
  `_carica_popolazione_sicilia`) prendono un `path: str` come chiave — hashabile out of
  the box. I loader SQL prendono `conn: sqlite3.Connection`, non hashabile in modo
  affidabile da `st.cache_data` senza convenzioni aggiuntive (prefisso `_conn` per
  escluderlo dall'hash, TTL, gestione di un DB che cambia sotto lo stesso path). È un
  cambio più ampio e sensibile alla correttezza (dati stantii se non configurato bene),
  da proporre a parte — qui risolta solo la duplicazione di chiamata effettivamente
  presente (punto 1), che era il costo pratico segnalato.

## ❓ Domande aperte
_Nessuna._

## 📚 Contesto
Findings del `/code-review` (`main...HEAD`), angoli E (simplification) e F (efficiency).

## ✅ Task
- [x] `enti`/`flags_per_ente` caricati una volta in `main()`, passati ai tab
- [x] `_avviso_privacy_piccolo_comune()` condiviso, usato da entrambi i call site
- [x] `ICONE_STATO_FINALE` dict, sostituito il ternario annidato
- [x] `copertura["coperti_comuni"]` riusato invece di ricalcolare la somma

## 🧪 Criteri di accettazione
- [x] Nessuna regressione sui 17 test esistenti di `test_dashboard.py`
- [x] Verificato dal vivo (non solo staticamente): DB di test reale +
      `streamlit.testing.v1.AppTest` — script eseguito per intero, **0 eccezioni**
      (copre tutti i tab, incluse le funzioni con firma cambiata)
- [x] Test passano (`pytest`)
- [x] DoD rispettata (vedi CLAUDE.md)

## 🔗 Dipendenze
Nessuna.

## 📝 Note
Il retrofit di `@st.cache_data` sui loader SQL resta un finding aperto, non affrontato
qui per le ragioni in "Casi limite" — vedi report `/code-review` per il dettaglio.
