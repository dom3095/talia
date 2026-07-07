# 14 — Censimento albi pretori dei comuni siciliani (TAL-49)

Aggiornato: 2026-07-07. Fonte lista comuni: `data/comuni_sicilia.csv` (ISTAT × popolazione Wikipedia).

## Metodo

1. **Sweep deterministico** del pattern jCityGov `https://<slug>.trasparenza-valutazione-merito.it` su tutti i 391 comuni (GET, fingerprint Liferay nel body).
2. **Verifica** di ogni hit scaricando 10 atti reali con `fonti/jcitygov.py`: solo chi risponde con atti validi entra in `_JCITYGOV_COMUNI`.
3. Capoluoghi non jCityGov: scraper dedicati (vedi tabella in `CLAUDE.md`).

## Sintesi

- Comuni siciliani: **391** (5.001.690 abitanti)
- Hit sweep jCityGov: **68** → verificati e attivi: **60**
- Scraper dedicati: Palermo, Catania, Siracusa, Trapani, Agrigento (+ Messina bloccata)
- **Copertura: 65 comuni attivi ≈ 2.749.072 abitanti (55% della popolazione)**

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

## Hit jCityGov NON attivabili (portale presente, albo vuoto via API)

| Comune | Note |
|--------|------|
| Aragona | 0 atti dalla API albo |
| Condrò | 0 atti dalla API albo |
| Gaggi | 0 atti dalla API albo |
| Letojanni | 0 atti dalla API albo |
| Milazzo | 0 atti dalla API albo |
| Noto | 0 atti dalla API albo |
| Racalmuto | 0 atti dalla API albo |
| Ribera | 0 atti dalla API albo |

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
| Milazzo | ME | 32.146 |
| Partinico | PA | 31.401 |
| Avola | SR | 31.328 |
| Comiso | RG | 30.214 |
| Aci Catena | CT | 28.749 |
| Niscemi | CL | 27.975 |
| Misilmeri | PA | 27.570 |
| Termini Imerese | PA | 26.201 |
| Noto | SR | 23.704 |
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
