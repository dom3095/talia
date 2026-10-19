# HANDOFF.md — Stato corrente

> Aggiornato: 2026-10-19 (sera). `main` = `cc9af66` (PR #24). Storico delle
> sessioni fino a oggi: [`docs/handoff/archivio_sessioni_2026.md`](docs/handoff/archivio_sessioni_2026.md).
> Obiettivo concordato: **portare a terra il progetto**, criteri in
> [wiki/16 — Definizione di MVP](docs/wiki/16-definizione-mvp.md).

## PR aperte (da mergiare, il merge lo fa Dom)

| PR | Card | Cosa | Base |
|---|---|---|---|
| #25 | TAL-75 | `skip_ssl` per 13 Halley con certificato rotto (13/13 verificati dal vivo) + **ripasso** a fine run dei falliti per timeout/reset (`--budget-ripasso`, 3600s) | `main` |
| #27 | TAL-77 | **testo degli atti jCityGov nuovi** ogni notte (`--testo-atti 400`): solo testo nativo, solo tipi utili, PDF non conservato; 35/40 dal vivo | **#25** |
| #28 | TAL-62 | **Amministrazione Trasparente jCityGov nel run** (`--trasparenza`), categorie per prefisso; Halley AT fuori per scelta | **#27** |
| #26 | TAL-73, TAL-76 | `frazionamento` senza SmartCIG (12.892 flag → 0) + ricalcolo completo; `concentrazione_diretti` disattivata (510/510 enti-anno) | `main` |
| #29 | TAL-69 | sezione 🥶 **stagnanti** nel report, soglia relativa al comune | `main` |
| #30 | TAL-78 | copia settimanale del DB **su iCloud Drive** (zstd, 1,1 GB → 60 MB) | `main` |
| #31 | TAL-3 | test OCR su scansione sintetica, TAL-3 chiusa | `main` |
| #32 | TAL-40 | README pubblico, CONTRIBUTING, codice di condotta, issue template | `main` |
| questa | — | HANDOFF/BOARD riordinati, wiki 16 MVP, card mergiate in Done, decisione TAL-64 | `main` |

**Ordine:** #25 → #27 → #28 sono impilate (stesso punto di `run_scrapers.main()`);
le altre sono indipendenti. Possibili conflitti minori solo su `CLAUDE.md` e
`docs/wiki/15-run-automatico.md`, toccati da #25, #27, #28 e #30.

## Decisioni prese il 2026-10-19 (delegate da Dom)

- **TAL-73**: SmartCIG escluso dal frazionamento invece di tarare la soglia.
  Nessun atto d'albo ha `importo_euro`, quindi oggi la regola produce 0 flag.
- **TAL-76**: `concentrazione_diretti` tolta dal run finché non viene riprogettata.
- **TAL-62**: AT jCityGov sì, Halley no (doppioni senza CIG/numero).
  Testo: incrementale e solo jCityGov (TAL-77).
- **TAL-64**: la fase 1 additiva (`atti_fonti` affianca `atti`) è l'assetto
  stabile. Le colonne per-fonte non si spostano finché non serve.
- **TAL-69**: soglia `max(14, 3 × intervallo tipico)`, mai nell'exit code.
- **TAL-78**: backup fuori disco su iCloud Drive (`TALIA_BACKUP_OFFSITE_DIR` per cambiarlo).

## Stato DB e run (`talia.db`, 1,1 GB)

- 395.966 atti (176.827 SmartCIG), 13.990 red flag di cui 12.892
  `frazionamento` e 904 `concentrazione_diretti`, che spariranno al primo run dopo #26.
- `atti_fonti` **non esiste ancora** in `talia.db`: la crea il primo run con
  il codice di #22, cioè stanotte.
- Run del 19/10: 211/266 OK; 55 falliti, di cui 25 per il 403 PortalePA (corretto
  in #24, mergiata dopo l'avvio del run) e 13 per i certificati Halley (#25).

## Domattina (primo run con #20-#24 in `main`)

```bash
cat logs/ultimo_report.md
python - <<'EOF'
import sqlite3; c = sqlite3.connect("file:talia.db?mode=ro", uri=True)
print(c.execute("SELECT (SELECT COUNT(*) FROM atti_fonti) = (SELECT COUNT(*) FROM atti)").fetchone())
print(c.execute("""SELECT scraper_id, errore FROM scraper_runs
  WHERE date(avviato_a) = date('now') AND errore LIKE '%403%'""").fetchall())   # atteso: []
print(c.execute("""SELECT scraper_id, round((julianday(completato_a)-julianday(avviato_a))*1440)
  FROM scraper_runs WHERE date(avviato_a) = date('now') ORDER BY 2 DESC LIMIT 5""").fetchall())
EOF
```

Attesi: `atti_fonti` allineata ad `atti`, nessun 403 sui 24 PortalePA, nessuno
scraper oltre i 20 minuti, run finito ben prima delle 03:30 successive.

## Prossimi passi, in ordine

1. Merge delle PR, poi **una settimana di run** senza toccare nulla di grosso.
2. Misurare i criteri A e B di [wiki/16](docs/wiki/16-definizione-mvp.md):
   durata, falliti, volumi dei red flag, quota di atti con testo (TAL-77),
   nuovi atti da AT (TAL-62), link vivi su un campione di flag.
3. **TAL-12**: è il collo di bottiglia dell'MVP. I fascicoli 2-9 sono pronti
   con report automatico in `data/samples/<n>/`; serve solo un giurista che li legga.
4. Vista pubblica aggregata (criterio D): solo dopo 2 e 3, con un via libera esplicito.

## Cose da sapere

- `sqlite3 -readonly talia.db` a volte fallisce con "unable to open database
  file": è il DB in WAL senza `-shm`. Usare `sqlite3.connect("file:talia.db?mode=ro", uri=True)`.
- `CLAUDE.md` cita `docs/handoff/epica_E2.md`, che non è mai esistito; la
  cartella `docs/handoff/` contiene ora solo l'archivio.
- `jcitygov.py` e `pdf_download.py` usano un User-Agent da Chrome, non
  identificabile, a differenza di PortalePA (TAL-74). Da allineare con cautela:
  cambiarlo su 74 comuni senza misura rischia un blocco come quello di settembre.
- Branch locali: cancellati i 14 con PR mergiata e punta identica alla PR;
  restano `feat/sprint3-unified`, `fix/BUG-4-trapani-regex` e `rebased/TAL-*`,
  senza PR, più tre con commit dopo il merge (`feat/TAL-48-riapertura-dopo-revoca`,
  `feat/TAL-72-tetto-tempo-scraper`, `fix/TAL-74-portalepa-user-agent`). Lo stash
  superato di TAL-72 è stato eliminato (recuperabile come `0bb2a86` finché git non fa pulizia).
