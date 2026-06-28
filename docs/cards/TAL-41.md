# TAL-41 — Modulo 0: Registro Attori (gerarchia comuni + società in house)

- **Epica:** E2 — Scraping pilota
- **Ruolo:** 🕷️ SCR + 🔤 NLP
- **Priorità:** P2
- **Stato:** Backlog
- **Dipende da:** TAL-13 (estrazione attori dai documenti), TAL-21 (schema DB)
- **Supera:** TAL-25 (organigrammi + DPO, assorbita qui)

## 🎯 Obiettivo

Costruire un **registro strutturato degli attori istituzionali** di ogni comune siciliano e delle
sue società in house, alimentato da fonti pubbliche ufficiali. Il registro consente di:

1. **Risolvere** i nomi estratti dai provvedimenti (TAL-13) in entità note (persona + ruolo + mandato).
2. **Contestualizzare** i red flag: "il firmatario era ancora in carica?", "il RUP e il Dirigente
   erano la stessa persona?", "la società in house era commissariata?".
3. **Costruire pattern** per comune nel tempo (es. stesso dirigente firma N affidamenti diretti).

## 📚 Contesto normativo e legalità

I dati raccolti sono **pubblici per obbligo di legge** e il loro riuso per finalità civiche è lecito:

| Dato | Norma | Fonte primaria |
|------|-------|----------------|
| Sindaco, giunta, consiglio | art. 14 D.Lgs. 33/2013 | sito comune → Amm. Trasparente |
| Segretario generale | art. 14 D.Lgs. 33/2013 | sito comune → Amm. Trasparente |
| Dirigenti + fasce retributive | art. 15 D.Lgs. 33/2013 | sito comune → Amm. Trasparente |
| DPO | art. 37-39 GDPR | sito comune + Garante |
| Organigramma | art. 13 D.Lgs. 33/2013 | sito comune → Amm. Trasparente |
| Società in house (CdA, presidente) | art. 22 D.Lgs. 33/2013 + D.Lgs. 175/2016 | ANAC + sito comune |
| Lista comuni + contatti istituzionali | — | IndicePA (IPA) — API pubblica JSON |

**Vincoli da rispettare:**
- Solo dati in capacità professionale (ruolo, mandato, firma atti). Nessun dato personale privato.
- Nessun output che suggerisca colpevolezza individuale. Il collegamento è "ha firmato l'atto",
  non "è responsabile dell'anomalia".
- Disclaimer su ogni vista pubblica.
- Dati nominativi solo per uso interno (mai committati nel repo).

## ✅ Task

### Schema DB
- [ ] Tabelle: `attori`, `mandati`, `ruoli`, `societa_inhouse`, `componenti_cda`
- [ ] Relazione `attori ↔ atti` (già presenti in DB da TAL-21): tabella ponte `attore_atto`
      con campo `tipo_presenza` (firmatario, proponente, citato, RUP…)

### Spider / raccolta dati
- [ ] `modulo0_attori/spiders/ipa_spider.py`: IndicePA API → lista comuni siciliani con URL
      sito istituzionale e contatti di riferimento
- [ ] `modulo0_attori/spiders/amm_trasparente_spider.py`: per ogni comune, scraping sezione
      "Organi di indirizzo politico" e "Personale → Dirigenti" dal sito comunale
- [ ] `modulo0_attori/spiders/anac_partecipate_spider.py`: registro ANAC società partecipate →
      CdA e presidente per ogni società in house siciliana

### Resolver
- [ ] `modulo0_attori/resolver.py`: dato un nome estratto da TAL-13, cerca nel registro con
      fuzzy match (gestione varianti: titoli, iniziali, inversione nome/cognome)
- [ ] Soglia di confidenza configurabile; i match incerti restano come "candidato" (non confermato)
- [ ] Script `scripts/risolvi_attori.py`: per un fascicolo, stampa attori estratti → candidati
      nel registro con score e fonte

### Test
- [ ] Test schema DB e CRUD
- [ ] Test resolver: match esatti, varianti con titoli, falsi positivi da evitare
- [ ] Test spider IPA con fixture JSON (offline)

## 🧪 Criteri di accettazione

- [ ] Dato un comune siciliano, il registro contiene Sindaco, Segretario Generale e almeno
      un Dirigente con relativo periodo di mandato.
- [ ] Il resolver, su un fascicolo reale già processato (TAL-12), risolve almeno il 50% degli
      attori estratti in un'entità del registro.
- [ ] I match con score < soglia sono marcati "candidato", non confermati.
- [ ] Nessun dato personale finisce nei file committati (fixture con nomi fittizi).
- [ ] Disclaimer presente in ogni output user-facing che esponga nomi.

## 🔗 Dipendenze e feed-forward

- **Alimenta:** TAL-9 (check coerenza firmatari, ora con incrocio registro), TAL-11 (LLM
  contesto arricchito), Modulo 3 dashboard (vista "attori per comune").
- **Supera TAL-25** (organigrammi + DPO da Amm. Trasparente): quella card viene chiusa e
  assorbita qui.

## 📝 Note architetturali

- Il registro è **append-only con versionamento del mandato** (da/a): un attore può avere
  più mandati nello stesso ruolo o ruoli diversi nel tempo.
- IndicePA è il punto di partenza obbligatorio: fornisce l'URL ufficiale del sito di ogni
  comune, da cui derivare il path `/amministrazione-trasparente/`.
- Il fuzzy match deve essere **conservativo**: meglio "non trovato" che un falso positivo che
  lega il nome sbagliato a un atto.
- Considerare Levenshtein o RapidFuzz per il matching; niente LLM per questa fase.
