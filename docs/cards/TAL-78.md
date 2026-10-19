# TAL-78 — Backup del DB fuori dal disco del Mac

- **Epica:** E2 — Scraping pilota
- **Ruolo:** ⚙️ OPS
- **Priorità:** P1
- **Stato:** Review
- **Branch:** `feat/TAL-78-backup-offsite`

## 🎯 Obiettivo
Che un guasto del disco del Mac non faccia perdere `talia.db`, l'unico asset
del progetto che non si può ricostruire (gli atti scaduti dall'albo non si
riscaricano). Segnalato in HANDOFF il 2026-08-18, punto 4.

## 📋 Spec
- `run_daily.sh`, dopo il backup locale: se l'ultima copia fuori disco ha più
  di 6 giorni, scrive `talia.db.AAAAMMGG.zst` (zstd -10) nella cartella
  `TALIA_BACKUP_OFFSITE_DIR`, di default iCloud Drive `TALIA-backup/` se
  esiste; ne tiene 4. `""` disattiva.
- Scrittura su `.tmp`, `zstd -t`, poi `mv`: niente file a metà sincronizzati.
- Se manca zstd o la scrittura fallisce lo dice nel log e prosegue: il backup
  fuori disco non deve mai impedire il run.

## ❓ Domande aperte
- [x] Destinazione? → iCloud Drive (decisione delegata da Dom, 2026-10-19):
      unica destinazione fuori disco già presente sul Mac, gratuita, 4 copie da
      ~60 MB stanno nel piano gratuito da 5 GB. Il DB contiene dati di atti
      pubblici con nomi: resta nell'account personale, non condiviso.

## 🔬 Tentativi

### 2026-10-19 — Tentativo 1
**Approccio:** misura della compressione sul backup reale, poi due run di
`run_daily.sh` su un DB di prova con cartelle temporanee.
**Esito:** ✅ — `talia.db` 1,1 GB → **60 MB** con `zstd -T0 -10` in 5,5 s. Primo
run: copia scritta; secondo: "meno di 7 giorni fa", saltata. Ripristino
verificato (`zstd -d` → `SELECT COUNT(*) FROM atti` corretto).
**Appreso:** la compressione è così buona (testo ripetitivo: oggetti, URL) che
il costo di tenerne più copie è trascurabile; il vincolo vero è non mandare in
sync un file incompleto.
