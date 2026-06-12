# 07 — Fonti dati

[← Home](00-home.md)

Tutte le fonti sono **pubbliche e gratuite**.

| Fonte | Contenuto | Note |
|-------|-----------|------|
| Albi pretori dei 391 comuni siciliani | delibere, determine, bandi | pochi fornitori software → 4-5 scraper coprono gran parte della regione |
| Amministrazione Trasparente | struttura standardizzata per legge | ottima per scraping |
| ANAC / BDNCP | CIG, aggiudicazioni, varianti | filtrare per codice ISTAT regione 19 |
| GURS | Gazzetta Ufficiale Regione Siciliana | |
| UREGA | gare centralizzate | punto di osservazione unico |
| giustizia-amministrativa.it | sentenze TAR PA/CT e CGA | **ground truth**: atti effettivamente annullati |
| OpenCUP, OpenCoesione, SIOPE | parte finanziaria | |
| Liberi Consorzi / Città Metropolitane | atti ex province | spesso le meno trasparenti |

## Strategia di partenza

Non scrapare tutto subito. **Un solo software di albo pretorio** (il più diffuso tra i comuni siciliani)
o **una sola provincia**. Validare la pipeline, poi scalare.

> I 391 comuni usano pochi fornitori software per l'albo pretorio: 4-5 scraper ben fatti coprono gran parte
> della regione.

## Dataset etichettati "gratis" (ground truth)

- **Atti dei comuni sciolti per infiltrazione mafiosa** + **sentenze di annullamento** → esempi reali di "atti che hanno preceduto un problema accertato".
- Servono per **derivare indicatori statistici difendibili** e tarare le soglie dei red flag batch ([05](05-red-flags-batch.md)).

## Note etiche/tecniche sullo scraping

- Rispettare `robots.txt` e ritmi di richiesta sostenibili (rate limiting).
- Conservare l'**URL e la data di accesso** di ogni atto: serve all'esplicabilità.
- I PDF grezzi con dati nominativi **non vanno committati** nel repo.

[→ 08 Roadmap](08-roadmap.md)
