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
- Piattaforma **portalepa** (stessa di Siracusa, generalizzata in `portalepa.py`): **18 comuni**, di cui 16 trovati con sweep di dominio il 2026-07-07 (vedi sotto)
- Piattaforma **Halley EG** (generica in `halley.py`): **92 comuni**, di cui 85 trovati con sweep di dominio il 2026-07-07 + Menfi/Siculiana/Realmonte (provincia di Agrigento, 2026-07-08)
- Piattaforma **URBI Cloud** (generica in `urbi.py`, stesso motore di Catania): **6 comuni** (Favara, Raffadali, Ravanusa, Campobello di Licata, Naro, Santa Margherita di Belice — provincia di Agrigento, 2026-07-08)
- Piattaforma **Halley HSPromila** (ASP.NET, generica in `hspromila.py`): **2 comuni** (Sambuca di Sicilia, Santo Stefano Quisquina)
- Scraper dedicato **Ribera** (WordPress, `ribera.py`)
- **Copertura: 186 comuni attivi ≈ 3.631.325 abitanti (72,6% della popolazione)**

### Completamento provincia di Agrigento (2026-07-08)

Su richiesta di Dom, censiti i 12 comuni più popolosi tra i 25 non ancora coperti della provincia di Agrigento, a gruppi di 3 (ricognizione haiku + validazione diretta). Riepilogo piattaforme: 6 **URBI Cloud** (stesso motore di Catania, generalizzato in `urbi.py`: base_url/DB_NAME/ente_mittente parametrici), 3 **Halley EG** (Menfi, Siculiana, Realmonte — già coperti da `halley.py`), 2 **Halley HSPromila** (ASP.NET, `hypersicapp.net`, piattaforma nuova generalizzata in `hspromila.py`), 1 **WordPress** (Ribera, `ribera.py`).

Note tecniche rilevanti:
- **Siculiana**: certificato TLS valido ma con catena incompleta lato server (non un cert scaduto) → aggiunto `skip_ssl` opzionale a `halley.py`, stesso pattern già usato in `jcitygov.py` per Messina.
- **Bug scoperto e corretto**: la prima versione di `hspromila.py`/`ribera.py`-style per piattaforme senza link di dettaglio per atto rischia di riusare lo stesso `url_fonte` per tutti gli atti — la dedup DB `(ente_id, url_fonte)` scarterebbe silenziosamente tutti tranne il primo. Fix: frammento `#<id_riga>` per renderlo univoco.
- **Falsi allarmi "serve Playwright"**: 2 comuni su 12 (Ravanusa, Santo Stefano Quisquina) sono stati erroneamente segnalati come richiedenti Playwright dagli agenti di ricognizione; verificati a mano, funzionano entrambi in HTTP puro.

Dettagli completi in `docs/cards/TAL-49.md`, Tentativi 13-16.

### Sweep di dominio Halley EG (2026-07-07)

A differenza di jCityGov, Halley non ha un pattern di dominio unico: i 4 tenant noti (Vittoria, Sciacca, Adrano, Barcellona P.G.) usavano sottodomini diversi (`trasparenza.`, `servizi.`, `servizionline.`) sullo stesso schema `comune.<slug>.<prov>.it`. Sweep programmatico su tutti i 391 comuni non ancora coperti, provando i sottodomini noti + path `/mc/mc_p_ricerca.php`, fingerprint su `"table-albo"` + `"Halley"` nel body: **85 nuovi hit**, tutti verificati con atti reali (0 vuoti, 0 errori dopo retry). Aggiunti tutti a `_HALLEY_COMUNI`.

Due comuni risultati anche su Halley erano già registrati su jCityGov con lo stesso codice ISTAT (**Racalmuto**, **Favignana**) o path diverso (**San Giovanni la Punta**): rinominati con suffisso `_halley` per evitare collisioni di chiave nello scraper registry — stesso ente, due fonti indipendenti (`upsert_ente` è idempotente sullo stesso `codice_istat`).

### Sweep di dominio portalepa (2026-07-07)

Stesso approccio applicato a portalepa: pattern `<slug>.soluzionipa.it` e `portale(pa).comune.<slug>.<prov>.it/openweb/albo/albo_pretorio.php`, fingerprint su `"paginated_element"`. **16 nuovi hit** (oltre a Gela/Monreale già noti e Siracusa/Partinico già gestiti), tutti verificati con atti reali: Terrasini, Campobello di Mazara, Capaci, Misiliscemi, Isola delle Femmine, Lercara Friddi, Grotte, Gibellina, Caronia, Sant'Angelo di Brolo, Trappeto, Vicari, Aliminusa, Roccavaldina, **Villabate** (già su jCityGov, rinominato `villabate_portalepa`) e — risultato più interessante — **Caltagirone**: bloccata su jCityGov (WAF + cert scaduto), ma raggiungibile via portalepa. Rimane fuori solo **Messina** tra i capoluoghi bloccati.

Script degli sweep non committati nel repo (one-off in scratchpad); pattern riutilizzabile in futuro per altri vendor.

### Fix 2026-07-07 — tenant jCityGov con percorso "papca-ap" alternativo

6 degli 8 comuni nella tabella "Hit jCityGov NON attivabili" sotto in realtà avevano l'albo raggiungibile, ma su un'istanza portlet diversa (`/web/trasparenza/papca-ap/-/papca/igrid/<id>` invece di `/web/trasparenza/papca-g`), scoperta dalla pagina menu `/web/trasparenza/albo-pretorio` (blocco `data-mainurl`). Questa pagina espone in realtà **due** risorse per tenant: "Albo pretorio" (corrente) e "Storico atti" (archivio), con `igrid` diversi. `jcitygov.py::scarica_atti` ora rileva "0 risultati" sul percorso standard e prova in sequenza le risorse alternative, fermandosi alla prima non vuota. Sbloccati: **Milazzo** (32.146 ab.), **Aragona**, **Gaggi**, **Letojanni**, **Noto** (23.704 ab.) via "Albo pretorio"; **Racalmuto** (8.345 ab., 3.384 atti storici 2022) via "Storico atti". Restano genuinamente a 0 atti su entrambe le risorse: **Condrò, Ribera**.

### Implementate 2026-07-07 — portalepa generalizzato + Halley EG

Ricognizione su 10 comuni non-jCityGov (Gela, Vittoria, Barcellona P.G., Sciacca, Caltagirone, Monreale, Adrano, Favara, Milazzo, Partinico) aveva segnalato "SoluzioniPA" come vendor nuovo per Gela/Monreale/Partinico. **Verifica diretta**: Gela e Monreale usano in realtà l'**identica piattaforma di Siracusa** (`portalepa`, path `/openweb/albo/albo_pretorio.php`, righe `<tr class="paginated_element">`) — il modulo `siracusa.py` è stato generalizzato in `portalepa.py` (base_url + codice_istat parametrici) e riusato senza nuovo lavoro di piattaforma. **Partinico** ha invece un layout colonne diverso (variante `_full`, no data_scadenza separata): non compatibile con `portalepa.py`, resta da fare un mapping dedicato.

**Halley EG** confermato vendor genuinamente nuovo: implementato `halley.py` (generico, paginazione stateless via querystring `?pag=N`, nessuna sessione richiesta) per Vittoria, Sciacca, Adrano, Barcellona Pozzo di Gotto.

Restano da implementare:
- **Partinico** (31k ab.): portalepa variante `_full`, mapping colonne diverso da confermare

### Completamento provincia di Agrigento (2026-07-08)

**Favara** (33k ab.) e **Raffadali** (13k ab.) sono entrambi **URBI Cloud** (`cloud.urbi.it`, stesso meccanismo di Catania) — generalizzato `catania.py` in `urbi.py` parametrico. **Ribera** (19k ab., segnata sopra come "0 atti anche sul percorso alternativo" su jCityGov) in realtà non usa affatto jCityGov: l'albo vero è su **WordPress** del sito istituzionale (`comune.ribera.ag.it`, tema "design-comuni-wordpress-theme") — nuovo scraper dedicato `ribera.py`. Dettagli in `docs/cards/TAL-49.md`, Tentativo 13.

**Caltagirone** ✅ sbloccata il 2026-07-07 tramite sweep portalepa (vedi sotto): era bloccata solo su jCityGov, raggiungibile su `caltagirone.soluzionipa.it`.

Dettagli completi in `docs/cards/TAL-49.md`, Tentativi 8-10.

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

Da ricontrollare periodicamente: potrebbe esporre l'albo su altro portale o attivarlo in futuro
(come già successo per Racalmuto → "Storico atti" jCityGov, e per Ribera → WordPress).

## Prossimi comuni da censire (non jCityGov, per popolazione)

| Comune | Prov | Popolazione |
|--------|------|------------:|
| Partinico | PA | 31.401 |
| Comiso | RG | 30.214 |
| Aci Catena | CT | 28.749 |
| Niscemi | CL | 27.975 |
| Termini Imerese | PA | 26.201 |
| San Cataldo | CL | 23.424 |
| Floridia | SR | 22.685 |
| Pachino | SR | 22.068 |
| Rosolini | SR | 21.526 |
| Bronte | CT | 19.234 |
| Carlentini | SR | 17.958 |
| Aci Sant'Antonio | CT | 17.270 |
| Palagonia | CT | 16.540 |

Per questi serve individuare la piattaforma (URBI, Halley, portalepa, e-pal, siti custom…): stessa procedura di TAL-49, esplorazione + scraper riusabile per famiglia di piattaforma.
