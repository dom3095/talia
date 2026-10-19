# TAL-77 — Testo degli atti jCityGov nuovi, estratto ogni notte

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🕷️ SCR + 🔤 NLP
- **Priorità:** P1
- **Stato:** Review
- **Branch:** `feat/TAL-77-testo-atti-jcitygov` (stacked su TAL-75)

## 🎯 Obiettivo
Che gli atti nuovi abbiano `testo_estratto`, preso mentre sono ancora
pubblicati sull'Albo. È la decisione n. 2 di [TAL-62](TAL-62.md)
("download/persistenza del testo"), delegata da Dom il 2026-10-19.

## 📋 Spec

### Il problema
`testo_estratto` è vuoto per **tutti** i 395.966 atti. Red flag, catene ed
estrazione del CIG lavorano sul solo `oggetto` della pagina-lista. Nessun atto
d'albo ha `importo_euro`, e per questo `frazionamento` produce 0 flag fuori da
SmartCIG ([TAL-73](TAL-73.md)). L'albo ritira l'atto dopo 15-30 giorni: il
testo o si prende ora o non si prende più.

### Decisione (e cosa si è scartato)
- **Incrementale, non backfill.** Solo atti con `data_accesso` negli ultimi
  20 giorni. Un backfill sui 101k atti jCityGov troverebbe gran parte dei link
  già morti e martellerebbe il fornitore.
- **Solo jCityGov per ora.** È l'unica piattaforma di cui sappiamo già leggere
  gli allegati (`pdf_download.trova_allegati`, TAL-47) ed è la più grande (~240
  atti nuovi/giorno, tutti sulla stessa infrastruttura). Halley (~580/giorno)
  è il passo successivo: richiede un parser degli allegati suo.
- **Solo testo nativo, niente OCR.** Tesseract su centinaia di scansioni
  allungherebbe il run di ore (TAL-72). Le scansioni restano con testo `''`.
- **Il PDF non si conserva.** Si salvano testo (max 200k caratteri) e
  `hash_sha256`; il file vive in una directory temporanea.
- **Minimizzazione:** solo determine, delibere, bandi, avvisi, contratti,
  affidamenti e liquidazioni. Esclusi matrimoni, notifiche e depositi del
  messo, anagrafe, permessi di costruire, ordinanze/ingiunzioni: testi con dati
  di privati che nessuna regola usa.
- **CIG dal testo solo se univoco** e solo se l'atto non ne ha già uno: un CIG
  sbagliato aggancerebbe l'atto al procedimento sbagliato (match esatto in
  `catena.py`, mai rimesso in discussione).
- **Importo: non ancora.** Una determina cita più importi (imponibile, IVA,
  totale, impegni precedenti): scegliere quello "dell'affidamento" è una regola
  da progettare e testare su atti veri, non un default. Card separata.

### Interfaccia
```bash
python scripts/run_scrapers.py ... --testo-atti 400   # 0 = disattivato (default CLI)
TALIA_TESTO_ATTI=0 ./scripts/run_daily.sh             # disattivare nel run notturno
```
`run_daily.sh` passa `--testo-atti 400`. Fase dopo lo scraping (e il ripasso),
prima dei red flag, sotto un tetto di 1800s; non fa mai fallire il run.

### Stato per atto
`testo_estratto IS NULL` = mai tentato · `''` = tentato senza risultato (non si
ritenta) · testo = estratto.

## ❓ Domande aperte
- [x] Persistere il testo? → Sì, incrementale, con i limiti sopra (decisione
      delegata da Dom, 2026-10-19).

## ✅ Task
- [x] `modulo2_scraping/testo_atti.py` + fase `--testo-atti` in `run_scrapers.py`
- [x] Test (`tests/test_testo_atti.py`, 14)
- [x] Prova dal vivo: 40 atti jCityGov reali (Ragusa, Scicli, Milazzo, Modica, Enna)
- [ ] Dopo una settimana di run: quota di atti con testo, durata della fase
- [ ] Card successive: parser allegati Halley; estrazione importo dell'affidamento

## 🔬 Tentativi

### 2026-10-19 — Tentativo 1
**Approccio:** riuso di `trova_allegati` + `scarica_pdf_allegato`, testo
nativo con `pdfplumber`.
**Esito:** ✅ — **35/40 atti con testo** (87%), ~2,5 s per atto (pausa di 1 s
tra richieste inclusa). 400 atti a notte ≈ 17 minuti.
**Appreso:** metà degli allegati sono **PDF firmati `.pdf.p7m`** (busta
CAdES, BER a lunghezza indefinita): il primo allegato spesso non è un PDF. Gli
stessi albi allegano quasi sempre anche la copia in chiaro subito dopo, quindi
basta provare i primi 3 allegati e prendere il primo con magic bytes `%PDF`,
senza decifrare la busta. Tra gli atti del campione c'erano pubblicazioni di
matrimonio e ordinanze-ingiunzione nominative: da qui il filtro sui tipi.

## 🔗 Dipendenze
TAL-47 (`pdf_download`), TAL-62 (decisione), TAL-72 (tetto di tempo), TAL-73
(importi per il frazionamento).
