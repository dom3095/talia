# Contribuire a TALIA

Grazie per l'interesse. TALIA lavora su atti pubblici e produce segnalazioni
su amministrazioni identificabili: le regole qui sotto non sono burocrazia,
servono a non far danni a persone reali.

## Prima di tutto: le quattro regole

1. **Segnalare, non giudicare.** Nessun output dice che un illecito è avvenuto.
   Linguaggio condizionale ("da verificare", "anomalia rispetto a…"), sempre il
   link all'atto e la citazione testuale accanto al flag.
2. **Mai dati personali nel repo.** Niente PDF reali, niente `talia.db`,
   niente report generati su fascicoli veri. I campioni in `data/samples/`
   sono testi anonimizzati scritti a mano. Il `.gitignore` aiuta, non basta.
3. **Determinismo prima degli LLM**, e mai servizi a pagamento di default.
4. **Rispetto dei portali.** Scraper lenti (pausa tra richieste), User-Agent
   identificabile, nessun aggiramento di blocchi espliciti. Se un gestore
   chiede di fermarsi, ci si ferma.

Dettagli: [avvertenze legali](docs/wiki/09-avvertenze-legali.md).

## Come si lavora

Il lavoro è organizzato in **card** (`docs/cards/TAL-NN.md`) su una
[board](docs/cards/BOARD.md) kanban. Per prendere un lavoro:

1. Scegli una card in **To Do** (o apri una issue per proporne una).
2. Leggi `## 📋 Spec` e `## ❓ Domande aperte`: se ci sono domande non
   risolte, chiedile nella issue prima di scrivere codice.
3. Crea un branch `feat/TAL-NN-slug` o `fix/TAL-NN-slug` da `main`.
4. Apri una Pull Request. **Nessun commit diretto su `main`**, nemmeno per
   correzioni piccole.

Ogni card ha una sezione `## 🔬 Tentativi`: annota cosa hai provato, anche
quando non ha funzionato. È il modo in cui il progetto evita di ripercorrere
strade già battute.

## Ambiente di sviluppo

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e '.[all]'
pytest            # tutta la suite, senza rete
ruff check . && ruff format .
```

I test non devono mai fare richieste di rete: usano HTML e testi d'esempio
(fixture) e DB SQLite in memoria.

## Quando una PR è pronta

- [ ] `pytest` e `ruff check .` passano.
- [ ] Una regola nuova ha almeno un esempio positivo (da atto reale,
      anonimizzato) e uno negativo.
- [ ] Ogni red flag prodotto rimanda all'atto sorgente (URL, offset o citazione).
- [ ] Uno scraper nuovo ha almeno 3 test: caso normale, 0 atti, pagina
      corrotta. Logga un WARNING quando trova 0 atti.
- [ ] Prima di pubblicare una regola, misura sul DB reale **quanti** flag
      produce: una regola che segnala quasi tutti gli enti non è un indicatore
      (è successo, vedi [TAL-73](docs/cards/TAL-73.md)).
- [ ] Nessun dato personale reale nei file modificati.
- [ ] Commit in stile conventional commits, con la card: `feat(M2): … (TAL-NN)`.

## Contributi non di codice

Sono tra i più preziosi:

- **Validazione giuridica**: leggere i report del Modulo 1 su fascicoli reali
  e dire dove sbagliano ([TAL-12](docs/cards/TAL-12.md)).
- **Casi noti**: atti annullati dal TAR/CGA, comuni sciolti, inchieste
  giornalistiche, utili come casi di riferimento per tarare le soglie.
- **Nuovi albi**: segnalare la piattaforma di un comune non ancora coperto
  ([censimento](docs/wiki/14-censimento-albi.md)).

## Codice di condotta

Partecipando accetti il [codice di condotta](CODE_OF_CONDUCT.md).
