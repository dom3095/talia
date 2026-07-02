# 12 — Schema DB (Modulo 2)

[← Home](00-home.md)

Documentazione del database SQLite usato dal Modulo 2 (scraping) e dal Modulo 3
(dashboard). Implementato in `src/talia/modulo2_scraping/db.py` (TAL-21).

## Principi di progetto

- **SQLite in sviluppo** — nessun server da avviare, nessuna dipendenza esterna.
- **PostgreSQL in produzione** — lo schema usa solo feature standard SQL-92;
  le placeholder `?` di sqlite3 vanno sostituite con `%s` per psycopg2.
- **SQL grezzo** — nessun ORM (budget ≈ 0, dipendenze minime). Le query sono in
  costanti di stringa leggibili.
- **Idempotenza** — `inizializza_db()` usa `CREATE TABLE IF NOT EXISTS`; si può
  chiamare a ogni avvio.
- **Integrità referenziale** — `PRAGMA foreign_keys = ON`; le FK sono dichiarate
  esplicitamente.

## Tabelle

### `enti`

Comuni siciliani e altri enti.

| Colonna | Tipo | Note |
|---------|------|------|
| id | INTEGER PK | auto-increment |
| denominazione | TEXT | nome ufficiale |
| codice_istat | TEXT UNIQUE | 6 cifre, es. "082053" per Palermo |
| provincia | TEXT | sigla, es. "PA" |
| popolazione | INTEGER | per il confronto tra pari |
| sito_web | TEXT | URL istituzionale |

### `atti`

Atti amministrativi raccolti dallo scraping (albi pretori, ANAC, GURS, …).

| Colonna | Tipo | Note |
|---------|------|------|
| id | INTEGER PK | |
| ente_id | INTEGER FK→enti | |
| tipo | TEXT | 'determina', 'delibera', 'bando', … |
| numero | TEXT | numero/anno dell'atto |
| data_atto | TEXT | ISO 8601 |
| data_pub | TEXT | data pubblicazione albo |
| data_scadenza | TEXT | fine pubblicazione |
| data_accesso | TEXT | quando scaricato (esplicabilità) |
| url_fonte | TEXT | URL pagina sorgente **(obbligatorio)** |
| url_pdf | TEXT | URL del PDF grezzo |
| hash_sha256 | TEXT | integrità del file |
| cig | TEXT | Codice Identificativo Gara ANAC |
| oggetto | TEXT | titolo/oggetto |
| importo_euro | REAL | importo aggiudicato/previsto |
| testo_estratto | TEXT | full-text (mai il PDF grezzo) |
| fonte_scraper | TEXT | 'icity', 'anac', 'gurs', … |
| metadati | TEXT | JSON blob per campi extra |

**Chiave di unicità:** `(ente_id, url_fonte)` — un re-run non duplica.

Colonne aggiunte da `engine/catena._evolvi_schema` (lazy, idempotente — TAL-42/46):

| Colonna | Tipo | Note |
|---------|------|------|
| procedimento_id | INTEGER FK→procedimenti | catena di appartenenza |
| ruolo_in_catena | TEXT | avvio / aggiudicazione / liquidazione / revoca / annullamento / modifica / proroga / altro |
| numero_settoriale | TEXT | registro settoriale (es. "35/2025") — è il numero citato nei riferimenti incrociati; `numero` è il registro generale. Popolamento: follow-up TAL-46 |

### `procedimenti`

Catene di atti dello stesso procedimento (TAL-42/43/46). Creata lazy da
`engine/catena._evolvi_schema`.

| Colonna | Tipo | Note |
|---------|------|------|
| id | INTEGER PK | |
| ente_id | INTEGER FK→enti | |
| tipo | TEXT | 'gara', 'generico' |
| cig | TEXT | se individuato per CIG |
| oggetto | TEXT | oggetto rappresentativo |
| data_avvio / data_chiusura | TEXT | ISO 8601 |
| stato_finale | TEXT | in_corso / aggiudicato / concluso / revocato / annullato / sconosciuto |
| metodo_individuazione | TEXT | 'cig', 'contenimento_oggetto', 'oggetto_simile_da_verificare' (+suffisso '_llm') — le catene `…da_verificare` richiedono revisione umana |
| creato_a | TEXT | ISO 8601 |

### `entita_estratte`

Entità estratte dal testo di un atto (date, CIG, importi, firmatari, norme).
Popolata dal Modulo 1 (`engine/entita.py`).

| Colonna | Tipo | Note |
|---------|------|------|
| id | INTEGER PK | |
| atto_id | INTEGER FK→atti | CASCADE delete |
| tipo | TEXT | TipoEntita: data, importo, cig, cup, norma, firmatario |
| valore | TEXT | valore normalizzato serializzato |
| testo_originale | TEXT | testo grezzo come appare nel documento |
| offset_inizio | INTEGER | posizione nel testo concatenato |
| offset_fine | INTEGER | estremo escluso |
| pagina | INTEGER | 1-based, se nota |

### `check_esiti`

Risultati dei check della checklist Modulo 1 applicati a un atto.

| Colonna | Tipo | Note |
|---------|------|------|
| id | INTEGER PK | |
| atto_id | INTEGER FK→atti | CASCADE delete |
| check_id | TEXT | es. 'check1_base_giuridica' |
| stato | TEXT | 'verde', 'giallo', 'rosso', 'non_applicabile' |
| motivazione | TEXT | |
| citazioni | TEXT | JSON array di `{testo, pagina, offset_*}` |
| data_check | TEXT | ISO 8601 |

**Chiave di unicità:** `(atto_id, check_id)` — upsert al ri-esecuzione.

### `red_flags`

Flag batch aggregati per ente, prodotti dal Modulo 2 (TAL-23).

| Colonna | Tipo | Note |
|---------|------|------|
| id | INTEGER PK | |
| ente_id | INTEGER FK→enti | |
| tipo_flag | TEXT | 'frazionamento', 'concentrazione', … |
| severita | TEXT | 'bassa', 'media', 'alta' |
| descrizione | TEXT | testo leggibile |
| atti_cig | TEXT | JSON array di `{id?, cig?, url}` sorgente |
| data_rilevazione | TEXT | ISO 8601 |
| periodo_da | TEXT | inizio periodo analizzato |
| periodo_a | TEXT | fine periodo analizzato |

## Indici

| Indice | Scopo |
|--------|-------|
| `idx_atti_cig` | join CIG ↔ ANAC |
| `idx_atti_ente_data` | serie temporali per ente |
| `idx_atti_scraper` | filtrare per fonte |
| `idx_flags_ente_tipo` | dashboard per comune |
| `idx_check_atto` | esiti checklist per atto |

## Helper CRUD (`db.py`)

| Funzione | Descrizione |
|----------|-------------|
| `connetti(percorso)` | Apre/crea il DB; attiva FK e WAL |
| `inizializza_db(conn)` | Crea tabelle e indici (idempotente) |
| `upsert_ente(conn, EnteMetadato)` | Inserisce o aggiorna un ente |
| `inserisci_atto(conn, AttoMetadato)` | Inserisce se nuovo (ritorna id o None) |
| `conta_atti(conn, ente_id?)` | Conta atti nel DB |
| `atti_per_ente(conn, codice_istat)` | Lista atti di un ente |
| `salva_check_esito(conn, atto_id, …)` | Upsert esito check |
| `salva_red_flag(conn, ente_id, …)` | Inserisce un red flag |
| `red_flags_per_ente(conn, codice_istat)` | Lista red flag di un ente |

## Migrazione verso PostgreSQL

1. Sostituire `sqlite3.connect` con `psycopg2.connect` (o SQLAlchemy engine).
2. Cambiare `?` → `%s` nelle query parametrizzate.
3. Rimuovere i PRAGMA SQLite (`foreign_keys`, `journal_mode`).
4. `INTEGER PRIMARY KEY` → `SERIAL PRIMARY KEY` o `BIGSERIAL`.
5. `ON CONFLICT … DO UPDATE` (upsert) è già sintassi PostgreSQL-compatibile.

[→ 13 Spider iCity](13-spider-icity.md) *(prossimo passo)*
