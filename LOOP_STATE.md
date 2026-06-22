# LOOP_STATE.md — Sprint 3: Scraping pilota & Red flags batch

## Stato corrente

```
current_step: B5
ultimo_aggiornamento: 2026-06-22
```

## Piano Sprint 3

Sprint 3 copre l'Epica E2 (Scraping pilota) e l'avvio dell'Epica E3 (Dashboard MVP).
Obiettivo: pipeline end-to-end **fetch → DB → red flags → dashboard** su dati reali Sicilia.

| # | Card | Titolo | Stato |
|---|------|--------|-------|
| B1 | TAL-21 | Schema DB atti + storage (SQLite, CRUD) | ✅ done |
| B2 | TAL-20 | Spider pilota albo pretorio (iCity) | ✅ done |
| B3 | TAL-22 | Pipeline ANAC open data (regione 19) | ✅ done |
| B4 | TAL-23 | Red flags batch deterministici | ✅ done |
| B5 | TAL-30 | Dashboard Streamlit MVP | ⏳ to_do |

---

## Dettaglio passi

### B1 — Schema DB atti + storage (TAL-21) ✅ done

**Obiettivo:** Creare `src/talia/modulo2_scraping/db.py` con schema SQLite,
dataclass `AttoMetadato` / `EnteMetadato`, e helper CRUD. Test in `tests/test_db.py`.

**File creati:**
- `src/talia/modulo2_scraping/db.py`
- `tests/test_db.py`

**Criteri di done:**
- [x] Tabelle: `enti`, `atti`, `entita_estratte`, `check_esiti`, `red_flags`
- [x] Ogni atto ha: ente, tipo, date, URL fonte, data accesso, hash SHA-256
- [x] Codice ISTAT ente
- [x] Upsert idempotente (nessun duplicato se re-run)
- [x] Indici su CIG, ente, data
- [x] Test CRUD base con SQLite in-memory

---

### B2 — Spider pilota albo pretorio iCity (TAL-20)

**Obiettivo:** Spider parametrizzato per il software **iCity/iPublic** (largamente
diffuso tra i comuni siciliani). Deve essere testabile offline con fixture HTML.

**File da creare:**
- `src/talia/modulo2_scraping/fonti/__init__.py`
- `src/talia/modulo2_scraping/fonti/icity.py` — spider + dataclass `AttoMetadato`
- `tests/fonti/__init__.py`
- `tests/fonti/fixtures/icity_lista.html` — HTML di esempio lista atti
- `tests/fonti/fixtures/icity_dettaglio.html` — HTML di esempio dettaglio atto
- `tests/fonti/test_icity.py` — test offline (no rete)

**Struttura spider (convezione modulo2):**
```python
@dataclass
class AttoMetadato: ...          # metadati di un singolo atto
def _parse_lista(html: str) -> list[dict]: ...    # estrae link dalla lista
def _parse_dettaglio(html: str, url: str) -> AttoMetadato: ...
def scarica_atti(base_url: str, ...) -> Iterator[AttoMetadato]: ...
def salva_atti(atti: Iterable[AttoMetadato], conn: sqlite3.Connection) -> int: ...
```

**Criteri di done:**
- [ ] `_parse_lista` e `_parse_dettaglio` funzionanti su fixture HTML realistiche
- [ ] `salva_atti` chiama `inserisci_atto` dal modulo `db`
- [ ] Rate limiting: rispetta `robots.txt` in produzione, skippabile in test
- [ ] Test offline: lista + dettaglio parsati correttamente, salvataggio in DB in-memory
- [ ] Nessun PDF committato

---

### B3 — Pipeline ANAC open data (TAL-22)

**Obiettivo:** Fetcher per open data ANAC/BDNCP filtrati per Sicilia (codice ISTAT regione 19).
Dataset CSV/JSON scaricabili senza API key.

**File da creare:**
- `src/talia/modulo2_scraping/fonti/anac.py`
- `tests/fonti/fixtures/anac_sample.csv` — campione sintetico
- `tests/fonti/test_anac.py`

**Criteri di done:**
- [ ] Scarica (o legge da file) CSV ANAC, filtra per CF/ISTAT regione 19
- [ ] Mappa campi → `AttoMetadato` (tipo='contratto_anac')
- [ ] Re-run incrementale (controlla hash/url prima di reinserire)
- [ ] Test con CSV sintetico (no rete)

---

### B4 — Red flags batch deterministici (TAL-23)

**Obiettivo:** Regole SQL/Python per frazionamento, concentrazione, tempi anomali.
Ogni regola: soglia documentata + lista atti/CIG sorgente.

**File da creare:**
- `src/talia/modulo2_scraping/red_flags/__init__.py`
- `src/talia/modulo2_scraping/red_flags/frazionamento.py`
- `src/talia/modulo2_scraping/red_flags/concentrazione.py`
- `src/talia/modulo2_scraping/red_flags/tempi_anomali.py`
- `src/talia/modulo2_scraping/red_flags/runner.py` — esegue tutte le regole
- `tests/red_flags/test_frazionamento.py`
- `tests/red_flags/test_concentrazione.py`
- `tests/red_flags/test_tempi_anomali.py`

**Criteri di done:**
- [ ] Ogni regola produce `list[RedFlag]` linkati agli atti sorgente
- [ ] Soglie come costanti con commento normativo
- [ ] Confronto tra pari (popolazione ± 30%)
- [ ] Test con DB sintetico (positivo + negativo per ogni regola)

---

### B5 — Dashboard Streamlit MVP (TAL-30)

**Obiettivo:** App Streamlit che legge dal DB, mostra red flags per comune con
drill-down agli atti sorgente. Disclaimer ben visibile.

**File da creare:**
- `src/talia/modulo3_dashboard/app.py`
- `src/talia/modulo3_dashboard/query.py` — helper query DB
- `tests/test_dashboard_query.py`

**Criteri di done:**
- [ ] App avviabile con `streamlit run src/talia/modulo3_dashboard/app.py`
- [ ] Vista per comune: red flags aggregate + tabella atti
- [ ] Drill-down: flag → atti/CIG → URL fonte
- [ ] Disclaimer visibile su ogni vista
- [ ] Anonimizzazione automatica per comuni con ≤ 5000 abitanti
- [ ] Test delle query (senza lanciare Streamlit)
