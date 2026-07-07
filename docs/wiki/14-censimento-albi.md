# 14 — Censimento albi pretori dei comuni siciliani (TAL-49)

Aggiornato: 2026-07-07. Fonte lista comuni: `data/comuni_sicilia.csv` (ISTAT × popolazione Wikipedia).

## Metodo

1. **Sweep deterministico** del pattern jCityGov `https://<slug>.trasparenza-valutazione-merito.it` su tutti i 391 comuni (GET, fingerprint Liferay nel body).
2. **Verifica** di ogni hit scaricando 10 atti reali con `fonti/jcitygov.py`: solo chi risponde con atti validi entra in `_JCITYGOV_COMUNI`.
3. Capoluoghi non jCityGov: scraper dedicati (vedi tabella in `CLAUDE.md`).

## Sintesi

- Comuni siciliani: **391** (5.001.690 abitanti)
- Hit sweep jCityGov: **68** → verificati e attivi: **66** (60 rollout + Milazzo, Aragona, Gaggi, Letojanni, Noto, Racalmuto sbloccati il 2026-07-07, vedi sotto)
- Scraper dedicati: Palermo, Catania, Siracusa, Trapani, Agrigento (+ Messina bloccata)
- **Copertura: 71 comuni attivi ≈ 2.585.335 abitanti (51,7% della popolazione)**

### Fix 2026-07-07 — tenant jCityGov con percorso "papca-ap" alternativo

6 degli 8 comuni nella tabella "Hit jCityGov NON attivabili" sotto in realtà avevano l'albo raggiungibile, ma su un'istanza portlet diversa (`/web/trasparenza/papca-ap/-/papca/igrid/<id>` invece di `/web/trasparenza/papca-g`), scoperta dalla pagina menu `/web/trasparenza/albo-pretorio` (blocco `data-mainurl`). Questa pagina espone in realtà **due** risorse per tenant: "Albo pretorio" (corrente) e "Storico atti" (archivio), con `igrid` diversi. `jcitygov.py::scarica_atti` ora rileva "0 risultati" sul percorso standard e prova in sequenza le risorse alternative, fermandosi alla prima non vuota. Sbloccati: **Milazzo** (32.146 ab.), **Aragona**, **Gaggi**, **Letojanni**, **Noto** (23.704 ab.) via "Albo pretorio"; **Racalmuto** (8.345 ab., 3.384 atti storici 2022) via "Storico atti". Restano genuinamente a 0 atti su entrambe le risorse: **Condrò, Ribera**.

### Prossime famiglie di piattaforma individuate (ricognizione 2026-07-07, non ancora implementate)

Ricognizione su 10 comuni non-jCityGov (Gela, Vittoria, Barcellona P.G., Sciacca, Caltagirone, Monreale, Adrano, Favara, Milazzo, Partinico) ha rivelato 2 vendor diffusi tra più comuni siciliani, oltre a Caltagirone che è jCityGov ma bloccato (WAF + cert scaduto dal 2022, come Messina):

- **Halley EG** (HTTP puro, PHP, paginazione `?pag=N`): Vittoria (61k ab.), Sciacca (41k), Adrano (35k), Barcellona Pozzo di Gotto (42k) — candidato per uno scraper generico `halley.py`
- **SoluzioniPA** (`<slug>.soluzionipa.it/openweb/albo/`, HTTP puro salvo verifica): Monreale (38k), Gela (76k, dominio proprio ma stesso path), Partinico (31k, possibile rendering React lato client da verificare) — candidato per `soluzionipa.py` + eventuale sweep di dominio come per jCityGov
- **URBI Cloud** (Favara, 33k): dialetto diverso da Catania, form POST tradizionale invece di stepper StwEvent

Dettagli completi in `docs/cards/TAL-49.md`, Tentativo 8.

## Comuni jCityGov attivi (registro `_JCITYGOV_COMUNI`)

| Comune | Prov | Popolazione | URL albo |
|--------|------|------------:|----------|
| Marsala | TP | 80.218 | https://marsala.trasparenza-valutazione-merito.it |
| Ragusa | RG | 69.794 | https://ragusa.trasparenza-valutazione-merito.it |
| Caltanissetta | CL | 61.711 | https://caltanissetta.trasparenza-valutazione-merito.it |
| Bagheria | PA | 54.257 | https://bagheria.trasparenza-valutazione-merito.it |
| Modica | RG | 53.959 | https://modica.trasparenza-valutazione-merito.it |
| Acireale | CT | 51.456 | https://acireale.trasparenza-valutazione-merito.it |
| Mazara del Vallo | TP | 49.995 | https://mazaradelvallo.trasparenza-valutazione-merito.it |
| Paternò | CT | 47.870 | https://paterno.trasparenza-valutazione-merito.it |
| Misterbianco | CT | 47.356 | https://misterbianco.trasparenza-valutazione-merito.it |
| Alcamo | TP | 45.314 | https://alcamo.trasparenza-valutazione-merito.it |
| Licata | AG | 38.125 | https://licata.trasparenza-valutazione-merito.it |
| Augusta | SR | 36.169 | https://augusta.trasparenza-valutazione-merito.it |
| Carini | PA | 35.681 | https://carini.trasparenza-valutazione-merito.it |
| Canicattì | AG | 34.863 | https://canicatti.trasparenza-valutazione-merito.it |
| Castelvetrano | TP | 31.824 | https://castelvetrano.trasparenza-valutazione-merito.it |
| Mascalucia | CT | 29.984 | https://mascalucia.trasparenza-valutazione-merito.it |
| Giarre | CT | 28.114 | https://giarre.trasparenza-valutazione-merito.it |
| Erice | TP | 28.012 | https://erice.trasparenza-valutazione-merito.it |
| Enna | EN | 27.894 | https://enna.trasparenza-valutazione-merito.it |
| Gravina di Catania | CT | 26.543 | https://gravinadicatania.trasparenza-valutazione-merito.it |
| Belpasso | CT | 26.378 | https://belpasso.trasparenza-valutazione-merito.it |
| Scicli | RG | 25.922 | https://scicli.trasparenza-valutazione-merito.it |
| Lentini | SR | 24.484 | https://lentini.trasparenza-valutazione-merito.it |
| Biancavilla | CT | 23.703 | https://biancavilla.trasparenza-valutazione-merito.it |
| Palma di Montechiaro | AG | 23.643 | https://palmadimontechiaro.trasparenza-valutazione-merito.it |
| San Giovanni la Punta | CT | 22.049 | https://sangiovannilapunta.trasparenza-valutazione-merito.it |
| Tremestieri Etneo | CT | 21.032 | https://tremestierietneo.trasparenza-valutazione-merito.it |
| Villabate | PA | 19.819 | https://villabate.trasparenza-valutazione-merito.it |
| Aci Castello | CT | 18.122 | https://acicastello.trasparenza-valutazione-merito.it |
| Ispica | RG | 15.122 | https://ispica.trasparenza-valutazione-merito.it |
| Riposto | CT | 14.181 | https://riposto.trasparenza-valutazione-merito.it |
| Pedara | CT | 12.896 | https://pedara.trasparenza-valutazione-merito.it |
| Cinisi | PA | 12.031 | https://cinisi.trasparenza-valutazione-merito.it |
| Valderice | TP | 11.951 | https://valderice.trasparenza-valutazione-merito.it |
| San Gregorio di Catania | CT | 11.497 | https://sangregoriodicatania.trasparenza-valutazione-merito.it |
| Paceco | TP | 11.487 | https://paceco.trasparenza-valutazione-merito.it |
| Taormina | ME | 11.084 | https://taormina.trasparenza-valutazione-merito.it |
| Salemi | TP | 10.871 | https://salemi.trasparenza-valutazione-merito.it |
| Ramacca | CT | 10.775 | https://ramacca.trasparenza-valutazione-merito.it |
| Sant'Agata li Battiati | CT | 9.829 | https://santagatalibattiati.trasparenza-valutazione-merito.it |
| Troina | EN | 9.628 | https://troina.trasparenza-valutazione-merito.it |
| Acate | RG | 9.574 | https://acate.trasparenza-valutazione-merito.it |
| Santa Teresa di Riva | ME | 9.240 | https://santateresadiriva.trasparenza-valutazione-merito.it |
| Agira | EN | 8.484 | https://agira.trasparenza-valutazione-merito.it |
| Santa Maria di Licodia | CT | 7.322 | https://santamariadilicodia.trasparenza-valutazione-merito.it |
| Nicolosi | CT | 7.156 | https://nicolosi.trasparenza-valutazione-merito.it |
| Gangi | PA | 7.063 | https://gangi.trasparenza-valutazione-merito.it |
| Rometta | ME | 6.541 | https://rometta.trasparenza-valutazione-merito.it |
| Montelepre | PA | 6.421 | https://montelepre.trasparenza-valutazione-merito.it |
| Custonaci | TP | 5.392 | https://custonaci.trasparenza-valutazione-merito.it |
| Castel di Iudica | CT | 4.748 | https://casteldiiudica.trasparenza-valutazione-merito.it |
| San Vito Lo Capo | TP | 4.415 | https://sanvitolocapo.trasparenza-valutazione-merito.it |
| Favignana | TP | 4.185 | https://favignana.trasparenza-valutazione-merito.it |
| Buseto Palizzolo | TP | 3.031 | https://busetopalizzolo.trasparenza-valutazione-merito.it |
| Nissoria | EN | 2.969 | https://nissoria.trasparenza-valutazione-merito.it |
| Vita | TP | 2.139 | https://vita.trasparenza-valutazione-merito.it |
| Bompietro | PA | 1.474 | https://bompietro.trasparenza-valutazione-merito.it |
| Ustica | PA | 1.287 | https://ustica.trasparenza-valutazione-merito.it |
| Blufi | PA | 1.083 | https://blufi.trasparenza-valutazione-merito.it |
| Comitini | AG | 944 | https://comitini.trasparenza-valutazione-merito.it |
| Milazzo | ME | 32.146 | https://milazzo.trasparenza-valutazione-merito.it (percorso `papca-ap/igrid`, vedi fix 2026-07-07) |
| Aragona | AG | 9.493 | https://aragona.trasparenza-valutazione-merito.it (percorso `papca-ap/igrid`) |
| Noto | SR | 23.704 | https://noto.trasparenza-valutazione-merito.it (percorso `papca-ap/igrid`) |
| Gaggi | ME | 3.138 | https://gaggi.trasparenza-valutazione-merito.it (percorso `papca-ap/igrid`) |
| Letojanni | ME | 2.699 | https://letojanni.trasparenza-valutazione-merito.it (percorso `papca-ap/igrid`) |

## Hit jCityGov NON attivabili (portale presente, albo vuoto via API)

| Comune | Note |
|--------|------|
| Condrò | 0 atti anche sul percorso alternativo `papca-ap/igrid` |
| Racalmuto | 0 atti anche sul percorso alternativo `papca-ap/igrid` |
| Ribera | 0 atti anche sul percorso alternativo `papca-ap/igrid` |

Da ricontrollare periodicamente: potrebbero esporre l'albo su altro portale o attivarlo in futuro.

## Prossimi comuni da censire (non jCityGov, per popolazione)

| Comune | Prov | Popolazione |
|--------|------|------------:|
| Gela | CL | 75.668 |
| Vittoria | RG | 61.006 |
| Barcellona Pozzo di Gotto | ME | 41.632 |
| Sciacca | AG | 40.899 |
| Caltagirone | CT | 38.123 |
| Monreale | PA | 38.018 |
| Adrano | CT | 35.549 |
| Favara | AG | 32.972 |
| Partinico | PA | 31.401 |
| Avola | SR | 31.328 |
| Comiso | RG | 30.214 |
| Aci Catena | CT | 28.749 |
| Niscemi | CL | 27.975 |
| Misilmeri | PA | 27.570 |
| Termini Imerese | PA | 26.201 |
| San Cataldo | CL | 23.424 |
| Floridia | SR | 22.685 |
| Piazza Armerina | EN | 22.196 |
| Pachino | SR | 22.068 |
| Rosolini | SR | 21.526 |
| Ribera | AG | 19.302 |
| Bronte | CT | 19.234 |
| Pozzallo | RG | 18.929 |
| Carlentini | SR | 17.958 |
| Aci Sant'Antonio | CT | 17.270 |
| Scordia | CT | 17.185 |
| Porto Empedocle | AG | 16.841 |
| Palagonia | CT | 16.540 |

Per questi serve individuare la piattaforma (URBI, Halley, portalepa, e-pal, siti custom…): stessa procedura di TAL-49, esplorazione + scraper riusabile per famiglia di piattaforma.
