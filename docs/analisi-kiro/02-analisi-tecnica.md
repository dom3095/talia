# 02 — Analisi Tecnica

> Criticità tecniche, refactoring, testing, performance, sicurezza.
> Branch: `analisi-kiro` | Data: 2026-06-28

---

## 1. Architettura del codice — punti di forza

Il codebase ha una struttura solida per un prototipo:

- **Separazione netta motore/moduli**: l'engine è puro (testo → entità → check), i moduli lo consumano senza accoppiamento
- **Esplicabilità built-in**: ogni `Entita` e `Citazione` porta offset+pagina, risalibile al documento
- **Zero dipendenze core**: il motore gira con la sola stdlib Python — deployment triviale
- **Check come plugin**: registry pattern (`registra(check)`) permette di aggiungere nuovi check senza toccare gli altri
- **Test coperti**: 164 test verdi, CI green

---

## 2. Criticità tecniche

### 2.1 Scalabilità del DB — SQLite non scala

**Problema:** SQLite è single-writer. Con scraping concorrente (più spider in parallelo, cron multipli) si avrà lock contention. Con 391 comuni × migliaia di atti/anno, il file DB crescerà a centinaia di MB.

**Impatto:** Blocca il passaggio a produzione.

**Soluzione:**
- Migrare a PostgreSQL (già previsto nel commento di `db.py`)
- Usare un ORM leggero (SQLAlchemy Core, non l'ORM full) per astrarre il dialetto
- Connection pooling per il Modulo 3 (dashboard con letture concorrenti)

### 2.2 Nessuna gestione errori di rete nel scraping

**Problema:** Gli spider (`icity.py`, `anac.py`) non hanno:
- Retry con backoff esponenziale
- Timeout configurabili
- Circuit breaker per fonti non disponibili
- Logging strutturato degli errori

**Impatto:** In produzione, un singolo timeout blocca la pipeline.

**Soluzione:**
- Wrapper HTTP con retry (tenacity o urllib3.Retry)
- Dead letter queue per atti non scaricabili
- Monitoring sugli errori di fetch

### 2.3 OCR non robusto

**Problema:** `pdf_text.py` fa:
1. Prova estrazione nativa (pdfplumber)
2. Se il testo è troppo corto → fallback OCR (Tesseract)

Ma non gestisce:
- PDF con rotazione pagine
- Scansioni a bassa risoluzione / multi-colonna
- PDF protetti da password
- Timeout per PDF enormi (centinaia di pagine)

**Impatto:** Sui fascicoli reali (scansioni di determine cartacee), l'OCR sarà il collo di bottiglia in qualità.

**Soluzione:**
- Pre-processing immagine (deskew, binarizzazione) prima di Tesseract
- Confidence score per pagina: se OCR quality < soglia → flag nel report
- Limite pagine configurabile (per evitare analisi di allegati irrilevanti)

### 2.4 Regex fragili per estrazione entità

**Problema:** Le regex di `entita.py` e `firmatari.py` sono calibrate su 2 fascicoli sintetici. Pattern problematici:

- **Date:** `_DATA_NUMERICA_RE` non distingue date da numeri di protocollo tipo "12/2024"
- **Importi:** formato italiano (punto=migliaia) vs formato OCR corrotto
- **Firmatari:** euristica su titoli onorifici fallisce se il testo OCR corrompe "Dott." in "Dott,"
- **CIG:** richiede label "CIG" nelle vicinanze — OK per il dominio, ma perde CIG citati senza etichetta

**Impatto:** False positives/negatives che inquinano la checklist.

**Soluzione:**
- Batteria di test su testi OCR reali (degradati)
- Fuzzy matching per titoli onorifici (distanza edit ≤ 1)
- Confidence score per entità estratte

### 2.5 Nessun caching / memoization

**Problema:** L'analisi di un fascicolo ri-esegue tutto ogni volta (estrazione, entità, check). Con PDF di 50+ pagine su un server, questo costa tempo CPU.

**Soluzione:**
- Cache hash-based: se l'SHA-256 del PDF è già nel DB, riusa le entità estratte
- Utile soprattutto nel Modulo 2 (ri-analisi periodiche)

### 2.6 Testing — copertura reale vs dichiarata

**Cosa c'è:**
- 164 test che passano
- Test unitari per ogni check
- Test end-to-end su fascicoli sintetici
- Test offline per spider (fixture HTML)

**Cosa manca:**
- **Integration test** con DB reale (non solo in-memory)
- **Test su testi OCR degradati** (il caso d'uso reale)
- **Property-based testing** per le regex (hypothesis)
- **Benchmark di performance** (tempo per fascicolo)
- **Test di regressione** su fascicoli reali catalogati
- **Mutation testing** per misurare la vera efficacia dei test

---

## 3. Debito tecnico

### 3.1 Python 3.14 — rischio compatibilità

`pyproject.toml` dichiara `requires-python = ">=3.14"`. Python 3.14 è appena rilasciato; molti ambienti cloud (Lambda, ECS) potrebbero non supportarlo ancora. Considerare abbassare a `>=3.11` (che è il minimo citato nella wiki).

### 3.2 Nessun logging strutturato

Il codebase usa `print` o niente. In produzione serve:
- Logging con livelli (DEBUG/INFO/WARNING/ERROR)
- Formato JSON per CloudWatch/ELK
- Correlation ID per tracciare un'analisi end-to-end
- Metriche (tempo per check, entità trovate per atto)

### 3.3 Nessuna configurazione centralizzata

Solo `.env.example` con 3 variabili. Serve un sistema di configurazione:
- Soglie dei check (oggi hardcoded: 365 giorni, 80% concentrazione, ecc.)
- Parametri spider (rate limit, timeout, user-agent)
- Parametri LLM (modello, endpoint, temperatura)
- Feature flags (abilitare/disabilitare check)

### 3.4 Nessun versionamento delle regole

Se una soglia cambia (es. il termine di autotutela passa da 12 a 18 mesi per una riforma), tutti gli esiti precedenti diventano incoerenti. Serve:
- Versione delle regole nel DB
- Ricalcolo esplicito quando una regola cambia
- Audit trail: "questo flag è stato generato con regola v1.2"

---

## 4. Sicurezza

| Aspetto | Stato | Rischio |
|---------|-------|---------|
| Input validation (PDF) | ⚠️ Nessuna | PDF malevoli possono crashare pdfplumber/Tesseract |
| SQL injection | ✅ Parametrizzato | Le query usano `?` placeholder |
| XSS nel report HTML | ✅ Escape con `html.escape()` | Corretto |
| Secrets management | ⚠️ Solo .env | No vault, no rotation |
| Rate limiting (scraping) | ⚠️ Parziale | Solo `robots.txt` check manuale |
| GDPR (dati nel DB) | ⚠️ Da completare | Anonimizzazione prevista ma non forzata |

**Azioni prioritarie:**
1. Validazione dimensione/tipo PDF prima del processing
2. Sandbox per Tesseract (ulimit/timeout)
3. Secret manager (AWS Secrets Manager) in cloud

---

## 5. Performance — proiezioni

| Operazione | Tempo attuale (stima) | Collo di bottiglia | Target |
|------------|----------------------|-------------------|--------|
| Analisi fascicolo 2 PDF nativi | ~1-2 sec | Regex + check | < 3 sec |
| Analisi fascicolo 2 PDF scansione | ~10-30 sec | OCR Tesseract | < 15 sec |
| Spider iCity (100 atti) | ~5-10 min | HTTP + parsing | < 3 min (parallelismo) |
| Red flags batch (1000 atti) | ~1-2 sec | SQL query | < 1 sec |
| Dashboard query | ~0.5 sec (SQLite) | I/O disco | < 200ms (PostgreSQL) |

---

## 6. Refactoring consigliati (priorità)

### Alta priorità
1. **Migrare DB a PostgreSQL** con migration tool (Alembic)
2. **Aggiungere logging strutturato** (structlog o logging stdlib con JSON formatter)
3. **Abbassare Python a 3.11+** per compatibilità cloud
4. **Configurazione centralizzata** (pydantic-settings o dynaconf)

### Media priorità
5. **Async spider** con aiohttp per parallelismo
6. **Pre-processing OCR** (deskew + binarizzazione)
7. **Cache hash-based** per entità già estratte
8. **Retry layer** per HTTP con backoff

### Bassa priorità
9. **Type checking** con mypy (già quasi tipato, serve il check in CI)
10. **Property-based testing** con hypothesis
11. **Benchmark suite** automatizzata
12. **Versionamento regole** nel DB

---

## 7. Dipendenze da introdurre (valutazione)

| Dipendenza | Scopo | Rischio | Alternativa |
|------------|-------|---------|-------------|
| `sqlalchemy[asyncio]` | Astrazione DB | Basso — standard de facto | SQL grezzo + adapter |
| `alembic` | Migrazioni schema | Basso | Script SQL manuali |
| `structlog` | Logging | Basso | stdlib `logging` |
| `tenacity` | Retry HTTP | Basso | Custom decorator |
| `pydantic-settings` | Configurazione | Basso | dataclass + env |
| `httpx` / `aiohttp` | HTTP async | Medio | requests (sync) |
| `streamlit` | Dashboard | Basso — già previsto | FastAPI + template |
| `sentence-transformers` | Embedding per RAG | Medio — pesante | API esterna |
| `ollama` | LLM locale | Basso | llama.cpp diretto |
