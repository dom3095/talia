"""Orchestratore scraper TALIA — esecuzione manuale (TAL-20/22/23).

Lancia i crawler disponibili in sequenza, salva nel DB e calcola i red flags.

Scrapers implementati:
  anac       — Dataset SmartCIG ANAC Sicilia (~400 MB CSV, HTTP)
  siracusa   — Albo pretorio Comune di Siracusa (HTTP)
  trapani    — Albo pretorio Comune di Trapani (HTTP)
  agrigento  — Albo pretorio Comune di Agrigento (Playwright/browser headless)

Uso tipico:
    python scripts/run_scrapers.py                               # tutti (escluso agrigento)
    python scripts/run_scrapers.py --scrapers siracusa trapani   # solo HTTP
    python scripts/run_scrapers.py --scrapers agrigento          # solo Agrigento
    python scripts/run_scrapers.py --scrapers anac --no-red-flags
    python scripts/run_scrapers.py --db /tmp/test.db --max-pagine 3
    TALIA_DB=prod.db python scripts/run_scrapers.py

Output: summary testuale su stdout; errori su stderr.
Il DB viene creato se non esiste. Ogni run è idempotente (UNIQUE su ente×url_fonte).
"""

from __future__ import annotations

import argparse
import sys
import time
import traceback
from pathlib import Path

# ---------------------------------------------------------------------------
# Setup path (funziona anche senza `pip install -e .`)
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from talia.modulo2_scraping.db import (  # noqa: E402
    connetti,
    inizia_run,
    inizializza_db,
    termina_run,
)
from talia.modulo2_scraping.red_flags.runner import esegui_tutti  # noqa: E402

# Quanti duplicati consecutivi senza un inserimento prima di fermare la paginazione.
# 20 = una pagina jCityGov intera — se è tutta già nota, abbiamo raggiunto il confine.
_STOP_CONSECUTIVI = 20

# ---------------------------------------------------------------------------
# Runner per ogni fonte
# ---------------------------------------------------------------------------


def _date_range(atti) -> tuple[str | None, str | None]:
    dates = [a.data_pub or a.data_atto for a in atti if a.data_pub or a.data_atto]
    return (min(dates) if dates else None, max(dates) if dates else None)


def _run_anac(conn, anac_file: str | None = None, **_kwargs) -> dict:
    from talia.modulo2_scraping.fonti.anac import carica_csv_anac, scarica_e_carica

    t0 = time.monotonic()
    if anac_file:
        print(f"  [ANAC] Carico da file locale: {anac_file}")
        with open(anac_file, encoding="utf-8", errors="replace") as f:
            contenuto = f.read()
        esito = carica_csv_anac(contenuto, conn)
    else:
        print("  [ANAC] Scarico CSV SmartCIG (~400 MB)… (pazienza)")
        esito = scarica_e_carica(conn)
    elapsed = time.monotonic() - t0
    print(f"  [ANAC] {esito} — {elapsed:.0f}s")
    esito["n_trovati"] = esito.get("inseriti", 0) + esito.get("duplicati", 0)
    return esito


def _run_siracusa(conn, max_pagine: int = 50, **_kwargs) -> dict:
    from talia.modulo2_scraping.fonti.siracusa import prepara_ente, salva_atti, scarica_atti

    prepara_ente(conn)
    print(f"  [Siracusa] Scarico albo pretorio (max {max_pagine} pagine)…")
    t0 = time.monotonic()
    atti = list(scarica_atti(max_pagine=max_pagine))
    esito = salva_atti(atti, conn)
    elapsed = time.monotonic() - t0
    print(f"  [Siracusa] {len(atti)} atti trovati → {esito} — {elapsed:.0f}s")
    esito["n_trovati"] = len(atti)
    esito["data_min"], esito["data_max"] = _date_range(atti)
    return esito


def _run_trapani(conn, max_pagine: int = 50, **_kwargs) -> dict:
    from talia.modulo2_scraping.fonti.trapani import prepara_ente, salva_atti, scarica_atti

    prepara_ente(conn)
    print(f"  [Trapani] Scarico albo pretorio (max {max_pagine} pagine)…")
    t0 = time.monotonic()
    atti = list(scarica_atti(max_pagine=max_pagine))
    esito = salva_atti(atti, conn)
    elapsed = time.monotonic() - t0
    print(f"  [Trapani] {len(atti)} atti trovati → {esito} — {elapsed:.0f}s")
    esito["n_trovati"] = len(atti)
    esito["data_min"], esito["data_max"] = _date_range(atti)
    return esito


def _run_palermo(conn, max_pagine: int = 50, **_kwargs) -> dict:
    from talia.modulo2_scraping.fonti.palermo import prepara_ente, salva_atti, scarica_atti

    prepara_ente(conn)
    print(f"  [Palermo] Scarico albo pretorio SISPI (max {max_pagine} pagine)…")
    t0 = time.monotonic()
    atti = list(scarica_atti(max_pagine=max_pagine))
    esito = salva_atti(atti, conn)
    elapsed = time.monotonic() - t0
    print(f"  [Palermo] {len(atti)} atti trovati → {esito} — {elapsed:.0f}s")
    esito["n_trovati"] = len(atti)
    esito["data_min"], esito["data_max"] = _date_range(atti)
    return esito


def _run_catania(conn, max_pagine: int = 100, **_kwargs) -> dict:
    from talia.modulo2_scraping.fonti.catania import prepara_ente, salva_atti, scarica_atti

    prepara_ente(conn)
    print(f"  [Catania] Scarico albo pretorio URBI (max {max_pagine} pagine)…")
    t0 = time.monotonic()
    atti = list(scarica_atti(max_pagine=max_pagine))
    esito = salva_atti(atti, conn)
    elapsed = time.monotonic() - t0
    print(f"  [Catania] {len(atti)} atti trovati → {esito} — {elapsed:.0f}s")
    esito["n_trovati"] = len(atti)
    esito["data_min"], esito["data_max"] = _date_range(atti)
    return esito


def _run_ribera(conn, max_pagine: int = 50, **_kwargs) -> dict:
    from talia.modulo2_scraping.fonti.ribera import prepara_ente, salva_atti, scarica_atti

    prepara_ente(conn)
    print(f"  [Ribera] Scarico albo pretorio WordPress (max {max_pagine} pagine)…")
    t0 = time.monotonic()
    atti = list(scarica_atti(max_pagine=max_pagine))
    esito = salva_atti(atti, conn)
    elapsed = time.monotonic() - t0
    print(f"  [Ribera] {len(atti)} atti trovati → {esito} — {elapsed:.0f}s")
    esito["n_trovati"] = len(atti)
    esito["data_min"], esito["data_max"] = _date_range(atti)
    return esito



def _run_agrigento(conn, max_pagine: int = 20, **_kwargs) -> dict:
    try:
        from talia.modulo2_scraping.fonti.agrigento import prepara_ente, salva_atti, scarica_atti
    except ImportError as exc:
        raise RuntimeError(
            "Agrigento richiede Playwright: pip install playwright && playwright install chromium"
        ) from exc

    prepara_ente(conn)
    print(f"  [Agrigento] Scarico albo pretorio con Playwright (max {max_pagine} pagine)…")
    t0 = time.monotonic()
    atti = list(scarica_atti(max_pagine=max_pagine))
    esito = salva_atti(atti, conn)
    elapsed = time.monotonic() - t0
    print(f"  [Agrigento] {len(atti)} atti trovati → {esito} — {elapsed:.0f}s")
    esito["n_trovati"] = len(atti)
    esito["data_min"], esito["data_max"] = _date_range(atti)
    return esito


# jCityGov (Liferay *.trasparenza-valutazione-merito.it)
# Messina esclusa: SSL self-signed cert — da risolvere separatamente.

_BASE = "https://{}.trasparenza-valutazione-merito.it"
_JCITYGOV_COMUNI = [
    # (nome_log, base_url, codice_istat, denominazione)
    ("caltanissetta", _BASE.format("caltanissetta"), "085004", "Comune di Caltanissetta"),
    ("enna", _BASE.format("enna"), "086009", "Comune di Enna"),
    (
        "palma",
        "https://palmadimontechiaro.trasparenza-valutazione-merito.it",
        "084027",
        "Comune di Palma di Montechiaro",
    ),
    ("ragusa", _BASE.format("ragusa"), "088009", "Comune di Ragusa"),
    # --- rollout E3 (TAL-49): hit sweep verificati con 10 atti reali ---
    ("marsala", _BASE.format("marsala"), "081011", "Comune di Marsala"),
    ("bagheria", _BASE.format("bagheria"), "082006", "Comune di Bagheria"),
    ("modica", _BASE.format("modica"), "088006", "Comune di Modica"),
    ("acireale", _BASE.format("acireale"), "087004", "Comune di Acireale"),
    ("mazaradelvallo", _BASE.format("mazaradelvallo"), "081012", "Comune di Mazara del Vallo"),
    ("paterno", _BASE.format("paterno"), "087033", "Comune di Paternò"),
    ("misterbianco", _BASE.format("misterbianco"), "087029", "Comune di Misterbianco"),
    ("alcamo", _BASE.format("alcamo"), "081001", "Comune di Alcamo"),
    ("licata", _BASE.format("licata"), "084021", "Comune di Licata"),
    ("augusta", _BASE.format("augusta"), "089001", "Comune di Augusta"),
    ("carini", _BASE.format("carini"), "082021", "Comune di Carini"),
    ("canicatti", _BASE.format("canicatti"), "084011", "Comune di Canicattì"),
    ("castelvetrano", _BASE.format("castelvetrano"), "081006", "Comune di Castelvetrano"),
    ("mascalucia", _BASE.format("mascalucia"), "087024", "Comune di Mascalucia"),
    ("giarre", _BASE.format("giarre"), "087017", "Comune di Giarre"),
    ("erice", _BASE.format("erice"), "081008", "Comune di Erice"),
    (
        "gravinadicatania",
        _BASE.format("gravinadicatania"),
        "087019",
        "Comune di Gravina di Catania",
    ),
    ("belpasso", _BASE.format("belpasso"), "087007", "Comune di Belpasso"),
    ("scicli", _BASE.format("scicli"), "088011", "Comune di Scicli"),
    ("lentini", _BASE.format("lentini"), "089011", "Comune di Lentini"),
    ("biancavilla", _BASE.format("biancavilla"), "087008", "Comune di Biancavilla"),
    (
        "sangiovannilapunta",
        _BASE.format("sangiovannilapunta"),
        "087041",
        "Comune di San Giovanni la Punta",
    ),
    ("tremestierietneo", _BASE.format("tremestierietneo"), "087051", "Comune di Tremestieri Etneo"),
    ("villabate", _BASE.format("villabate"), "082079", "Comune di Villabate"),
    ("acicastello", _BASE.format("acicastello"), "087002", "Comune di Aci Castello"),
    ("ispica", _BASE.format("ispica"), "088005", "Comune di Ispica"),
    ("riposto", _BASE.format("riposto"), "087039", "Comune di Riposto"),
    ("pedara", _BASE.format("pedara"), "087034", "Comune di Pedara"),
    ("cinisi", _BASE.format("cinisi"), "082031", "Comune di Cinisi"),
    ("valderice", _BASE.format("valderice"), "081022", "Comune di Valderice"),
    (
        "sangregoriodicatania",
        _BASE.format("sangregoriodicatania"),
        "087042",
        "Comune di San Gregorio di Catania",
    ),
    ("paceco", _BASE.format("paceco"), "081013", "Comune di Paceco"),
    ("taormina", _BASE.format("taormina"), "083097", "Comune di Taormina"),
    ("salemi", _BASE.format("salemi"), "081018", "Comune di Salemi"),
    ("ramacca", _BASE.format("ramacca"), "087037", "Comune di Ramacca"),
    (
        "santagatalibattiati",
        _BASE.format("santagatalibattiati"),
        "087045",
        "Comune di Sant'Agata li Battiati",
    ),
    ("troina", _BASE.format("troina"), "086018", "Comune di Troina"),
    ("acate", _BASE.format("acate"), "088001", "Comune di Acate"),
    (
        "santateresadiriva",
        _BASE.format("santateresadiriva"),
        "083089",
        "Comune di Santa Teresa di Riva",
    ),
    ("agira", _BASE.format("agira"), "086001", "Comune di Agira"),
    (
        "santamariadilicodia",
        _BASE.format("santamariadilicodia"),
        "087047",
        "Comune di Santa Maria di Licodia",
    ),
    ("nicolosi", _BASE.format("nicolosi"), "087031", "Comune di Nicolosi"),
    ("gangi", _BASE.format("gangi"), "082036", "Comune di Gangi"),
    ("rometta", _BASE.format("rometta"), "083076", "Comune di Rometta"),
    ("montelepre", _BASE.format("montelepre"), "082050", "Comune di Montelepre"),
    ("custonaci", _BASE.format("custonaci"), "081007", "Comune di Custonaci"),
    ("casteldiiudica", _BASE.format("casteldiiudica"), "087013", "Comune di Castel di Iudica"),
    ("sanvitolocapo", _BASE.format("sanvitolocapo"), "081020", "Comune di San Vito Lo Capo"),
    ("favignana", _BASE.format("favignana"), "081009", "Comune di Favignana"),
    ("busetopalizzolo", _BASE.format("busetopalizzolo"), "081002", "Comune di Buseto Palizzolo"),
    ("nissoria", _BASE.format("nissoria"), "086013", "Comune di Nissoria"),
    ("vita", _BASE.format("vita"), "081023", "Comune di Vita"),
    ("bompietro", _BASE.format("bompietro"), "082012", "Comune di Bompietro"),
    ("ustica", _BASE.format("ustica"), "082075", "Comune di Ustica"),
    ("blufi", _BASE.format("blufi"), "082082", "Comune di Blufi"),
    ("comitini", _BASE.format("comitini"), "084016", "Comune di Comitini"),
    # --- sbloccati 2026-07-07 (TAL-49): fallback "papca-ap/igrid" per tenant
    # dove il percorso standard "papca-g" ritorna 0 atti, vedi jcitygov.py ---
    ("milazzo", _BASE.format("milazzo"), "083049", "Comune di Milazzo"),
    ("aragona", _BASE.format("aragona"), "084003", "Comune di Aragona"),
    ("gaggi", _BASE.format("gaggi"), "083029", "Comune di Gaggi"),
    ("letojanni", _BASE.format("letojanni"), "083038", "Comune di Letojanni"),
    ("noto", _BASE.format("noto"), "089013", "Comune di Noto"),
    # Racalmuto: "Albo pretorio" vuoto ma "Storico atti" popolato (3384 atti).
    ("racalmuto", _BASE.format("racalmuto"), "084029", "Comune di Racalmuto"),
]


def _run_jcitygov_comune(
    conn, nome, base_url, codice_istat, denominazione, max_pagine=10, no_stop=False, **_kwargs
):
    from talia.modulo2_scraping.db import EnteMetadato, inserisci_atto, upsert_ente
    from talia.modulo2_scraping.fonti.jcitygov import scarica_atti

    upsert_ente(conn, EnteMetadato(denominazione=denominazione, codice_istat=codice_istat))
    limit = max_pagine * 20
    stop_label = " [backfill, stop disabilitato]" if no_stop else ""
    print(
        f"  [{nome.capitalize()}] Scarico albo pretorio jCityGov"
        f" (max {max_pagine} pagine){stop_label}…"
    )
    t0 = time.monotonic()

    inseriti = duplicati = consecutivi_dup = 0
    dates: list[str] = []
    for atto in scarica_atti(base_url, codice_istat, limit=limit):
        if inserisci_atto(conn, atto) is not None:
            inseriti += 1
            consecutivi_dup = 0
            if atto.data_pub:
                dates.append(atto.data_pub)
        else:
            duplicati += 1
            consecutivi_dup += 1
        if not no_stop and consecutivi_dup >= _STOP_CONSECUTIVI:
            break
    conn.commit()

    n_trovati = inseriti + duplicati
    elapsed = time.monotonic() - t0
    esito = {"inseriti": inseriti, "duplicati": duplicati}
    print(f"  [{nome.capitalize()}] {n_trovati} atti trovati → {esito} — {elapsed:.0f}s")
    esito["n_trovati"] = n_trovati
    esito["data_min"] = min(dates) if dates else None
    esito["data_max"] = max(dates) if dates else None
    return esito


def _make_jcitygov_runner(entry):
    def _runner(conn, **kwargs):
        return _run_jcitygov_comune(conn, *entry, **kwargs)

    return _runner


# portalepa PHP: stessa piattaforma di Siracusa, riusata da altri comuni
# sotto domini diversi (TAL-49). Partinico ha un layout colonne diverso
# ("_full"): non compatibile con questo modulo, vedi docs/wiki/14-censimento-albi.md.
_PORTALEPA_COMUNI = [
    # (nome_log, base_url, codice_istat, denominazione)
    ("gela", "https://portale.comune.gela.cl.it", "085007", "Comune di Gela"),
    ("monreale", "https://monreale.soluzionipa.it", "082049", "Comune di Monreale"),
    # --- sweep di dominio 2026-07-07 (TAL-49): pattern <slug>.soluzionipa.it e
    # portale(pa).comune.<slug>.<prov>.it, verificati con atti reali ciascuno.
    # Caltagirone era bloccata su jCityGov (WAF): raggiungibile qui invece. ---
    ("caltagirone", "https://caltagirone.soluzionipa.it", "087011", "Comune di Caltagirone"),
    (
        "villabate_portalepa",
        "https://villabate.soluzionipa.it",
        "082079",
        "Comune di Villabate",
    ),
    ("terrasini", "https://terrasini.soluzionipa.it", "082071", "Comune di Terrasini"),
    (
        "campobellodimazara",
        "https://servizi.comune.campobellodimazara.tp.it",
        "081004",
        "Comune di Campobello di Mazara",
    ),
    ("capaci", "https://capaci.soluzionipa.it", "082020", "Comune di Capaci"),
    ("misiliscemi", "https://misiliscemi.soluzionipa.it", "081025", "Comune di Misiliscemi"),
    (
        "isoladellefemmine",
        "https://servizi.comune.isoladellefemmine.pa.it",
        "082043",
        "Comune di Isola delle Femmine",
    ),
    (
        "lercarafriddi",
        "https://lercarafriddi.soluzionipa.it",
        "082045",
        "Comune di Lercara Friddi",
    ),
    ("grotte", "https://grotte.soluzionipa.it", "084018", "Comune di Grotte"),
    ("gibellina", "https://gibellina.soluzionipa.it", "081010", "Comune di Gibellina"),
    ("caronia", "https://caronia.soluzionipa.it", "083011", "Comune di Caronia"),
    (
        "santangelodibrolo",
        "https://santangelodibrolo.soluzionipa.it",
        "083088",
        "Comune di Sant'Angelo di Brolo",
    ),
    ("trappeto", "https://trappeto.soluzionipa.it", "082074", "Comune di Trappeto"),
    ("vicari", "https://vicari.soluzionipa.it", "082078", "Comune di Vicari"),
    ("aliminusa", "https://aliminusa.soluzionipa.it", "082003", "Comune di Aliminusa"),
    ("roccavaldina", "https://roccavaldina.soluzionipa.it", "083073", "Comune di Roccavaldina"),
]


def _run_portalepa_comune(
    conn, nome, base_url, codice_istat, denominazione, max_pagine=10, no_stop=False, **_kwargs
):
    from talia.modulo2_scraping.db import EnteMetadato, inserisci_atto, upsert_ente
    from talia.modulo2_scraping.fonti.portalepa import scarica_atti

    upsert_ente(conn, EnteMetadato(denominazione=denominazione, codice_istat=codice_istat))
    stop_label = " [backfill, stop disabilitato]" if no_stop else ""
    print(
        f"  [{nome.capitalize()}] Scarico albo pretorio portalepa"
        f" (max {max_pagine} pagine){stop_label}…"
    )
    t0 = time.monotonic()

    inseriti = duplicati = consecutivi_dup = 0
    dates: list[str] = []
    for atto in scarica_atti(base_url, codice_istat, max_pagine=max_pagine):
        if inserisci_atto(conn, atto) is not None:
            inseriti += 1
            consecutivi_dup = 0
            if atto.data_atto:
                dates.append(atto.data_atto)
        else:
            duplicati += 1
            consecutivi_dup += 1
        if not no_stop and consecutivi_dup >= _STOP_CONSECUTIVI:
            break
    conn.commit()

    n_trovati = inseriti + duplicati
    elapsed = time.monotonic() - t0
    esito = {"inseriti": inseriti, "duplicati": duplicati}
    print(f"  [{nome.capitalize()}] {n_trovati} atti trovati → {esito} — {elapsed:.0f}s")
    esito["n_trovati"] = n_trovati
    esito["data_min"] = min(dates) if dates else None
    esito["data_max"] = max(dates) if dates else None
    return esito


def _make_portalepa_runner(entry):
    def _runner(conn, **kwargs):
        return _run_portalepa_comune(conn, *entry, **kwargs)

    return _runner


# Halley EG (Halley Informatica): vendor diffuso tra più comuni siciliani
# sotto domini diversi (TAL-49). Paginazione stateless via ?pag=N.
_HALLEY_COMUNI = [
    # (nome_log, base_url, codice_istat, denominazione)
    ("vittoria", "https://trasparenza.comune.vittoria.rg.it", "088012", "Comune di Vittoria"),
    ("sciacca", "https://servizi.comune.sciacca.ag.it", "084041", "Comune di Sciacca"),
    ("adrano", "https://servizionline.comune.adrano.ct.it", "087006", "Comune di Adrano"),
    ("menfi", "https://servizi.comune.menfi.ag.it", "084023", "Comune di Menfi"),
    # skip_ssl: catena certificato incompleta lato server (cert valido, vedi _HALLEY_SKIP_SSL)
    ("siculiana", "https://trasparenza.comune.siculiana.ag.it", "084042", "Comune di Siculiana"),
    ("realmonte", "http://80.88.89.218/realmonte", "084032", "Comune di Realmonte"),
    (
        "barcellonapg",
        "https://servizi.comune.barcellonapozzodigotto.me.it/barcellona",
        "083005",
        "Comune di Barcellona Pozzo di Gotto",
    ),
    # --- sweep di dominio 2026-07-07 (TAL-49): pattern <prefisso>.comune.<slug>.<prov>.it,
    # verificati con atti reali ciascuno ---
    ("avola", "https://servizi.comune.avola.sr.it", "089002", "Comune di Avola"),
    ("misilmeri", "https://servizi.comune.misilmeri.pa.it", "082048", "Comune di Misilmeri"),
    (
        "piazzaarmerina",
        "https://servizi.comune.piazzaarmerina.en.it",
        "086014",
        "Comune di Piazza Armerina",
    ),
    (
        "sangiovannilapunta_halley",
        "https://servizi.comune.sangiovannilapunta.ct.it",
        "087041",
        "Comune di San Giovanni la Punta",
    ),
    ("pozzallo", "https://comune.pozzallo.rg.it", "088008", "Comune di Pozzallo"),
    ("scordia", "https://servizionline.comune.scordia.ct.it", "087049", "Comune di Scordia"),
    (
        "portoempedocle",
        "https://servizi.comune.portoempedocle.ag.it",
        "084028",
        "Comune di Porto Empedocle",
    ),
    ("melilli", "https://servizi.comune.melilli.sr.it", "089012", "Comune di Melilli"),
    (
        "santagatadimilitello",
        "https://servizi.comune.santagatadimilitello.me.it",
        "083084",
        "Comune di Sant'Agata di Militello",
    ),
    ("mazzarino", "https://servizi.comune.mazzarino.cl.it", "085009", "Comune di Mazzarino"),
    ("lipari", "https://servizi.comune.lipari.me.it", "083041", "Comune di Lipari"),
    ("randazzo", "https://servizionline.comune.randazzo.ct.it", "087038", "Comune di Randazzo"),
    ("mussomeli", "https://servizi.comune.mussomeli.cl.it", "085012", "Comune di Mussomeli"),
    ("partanna", "https://servizi.comune.partanna.tp.it", "081015", "Comune di Partanna"),
    (
        "trecastagni",
        "https://trasparenza.comune.trecastagni.ct.it",
        "087050",
        "Comune di Trecastagni",
    ),
    ("castelbuono", "https://servizi.comune.castelbuono.pa.it", "082022", "Comune di Castelbuono"),
    ("sortino", "https://servizi.comune.sortino.sr.it", "089019", "Comune di Sortino"),
    (
        "sangiuseppejato",
        "https://servizi.comune.sangiuseppejato.pa.it",
        "082064",
        "Comune di San Giuseppe Jato",
    ),
    (
        "casteltermini",
        "https://trasparenza.comune.casteltermini.ag.it",
        "084012",
        "Comune di Casteltermini",
    ),
    (
        "santavenerina",
        "https://servizi.comune.santavenerina.ct.it",
        "087048",
        "Comune di Santa Venerina",
    ),
    (
        "racalmuto_halley",
        "https://trasparenza.comune.racalmuto.ag.it",
        "084029",
        "Comune di Racalmuto",
    ),
    ("viagrande", "https://trasparenza.comune.viagrande.ct.it", "087053", "Comune di Viagrande"),
    (
        "sangiovannigemini",
        "https://trasparenza.comune.sangiovannigemini.ag.it",
        "084036",
        "Comune di San Giovanni Gemini",
    ),
    ("sommatino", "https://servizionline.comune.sommatino.cl.it", "085019", "Comune di Sommatino"),
    (
        "gioiosamarea",
        "https://servizionline.comune.gioiosamarea.me.it",
        "083033",
        "Comune di Gioiosa Marea",
    ),
    (
        "campofelicediroccella",
        "https://servizi.comune.campofelicediroccella.pa.it",
        "082017",
        "Comune di Campofelice di Roccella",
    ),
    ("marineo", "https://servizi.comune.marineo.pa.it", "082046", "Comune di Marineo"),
    (
        "calatafimisegesta",
        "https://servizi.comune.calatafimisegesta.tp.it",
        "081003",
        "Comune di Calatafimi-Segesta",
    ),
    ("tortorici", "https://servizi.comune.tortorici.me.it", "083099", "Comune di Tortorici"),
    (
        "pacedelmela",
        "https://trasparenza.comune.pacedelmela.me.it",
        "083064",
        "Comune di Pace del Mela",
    ),
    ("cammarata", "https://trasparenza.comune.cammarata.ag.it", "084009", "Comune di Cammarata"),
    (
        "serradifalco",
        "https://servizi.comune.serradifalco.cl.it",
        "085018",
        "Comune di Serradifalco",
    ),
    (
        "lampedusaelinosa",
        "https://servizi.comune.lampedusaelinosa.ag.it",
        "084020",
        "Comune di Lampedusa e Linosa",
    ),
    ("brolo", "https://servizi.comune.brolo.me.it", "083007", "Comune di Brolo"),
    (
        "sancipirello",
        "https://servizi.comune.sancipirello.pa.it",
        "082063",
        "Comune di San Cipirello",
    ),
    ("cerda", "https://servizi.comune.cerda.pa.it", "082028", "Comune di Cerda"),
    ("villarosa", "https://servizionline.comune.villarosa.en.it", "086020", "Comune di Villarosa"),
    (
        "santaninfa",
        "https://servizionline.comune.santaninfa.tp.it",
        "081019",
        "Comune di Santa Ninfa",
    ),
    ("prizzi", "https://trasparenza.comune.prizzi.pa.it", "082060", "Comune di Prizzi"),
    (
        "santaluciadelmela",
        "https://servizi.comune.santaluciadelmela.me.it",
        "083086",
        "Comune di Santa Lucia del Mela",
    ),
    (
        "favignana_halley",
        "https://trasparenza.comune.favignana.tp.it",
        "081009",
        "Comune di Favignana",
    ),
    (
        "caltavuturo",
        "https://trasparenza.comune.caltavuturo.pa.it",
        "082015",
        "Comune di Caltavuturo",
    ),
    ("torretta", "https://comune.torretta.pa.it", "082072", "Comune di Torretta"),
    ("maletto", "https://servizi.comune.maletto.ct.it", "087022", "Comune di Maletto"),
    (
        "cattolicaeraclea",
        "https://trasparenza.comune.cattolicaeraclea.ag.it",
        "084014",
        "Comune di Cattolica Eraclea",
    ),
    ("piraino", "https://servizi.comune.piraino.me.it", "083068", "Comune di Piraino"),
    (
        "francavilladisicilia",
        "https://servizionline.comune.francavilladisicilia.me.it",
        "083025",
        "Comune di Francavilla di Sicilia",
    ),
    ("venetico", "https://trasparenza.comune.venetico.me.it", "083104", "Comune di Venetico"),
    ("ciminna", "https://servizi.comune.ciminna.pa.it", "082030", "Comune di Ciminna"),
    (
        "valledolmo",
        "https://servizi.comune.valledolmo.pa.it/valledolmo",
        "082076",
        "Comune di Valledolmo",
    ),
    ("villafrati", "https://trasparenza.comune.villafrati.pa.it", "082080", "Comune di Villafrati"),
    (
        "castellumberto",
        "https://servizi.comune.castellumberto.me.it",
        "083014",
        "Comune di Castell'Umberto",
    ),
    (
        "campofranco",
        "https://trasparenza.comune.campofranco.cl.it",
        "085005",
        "Comune di Campofranco",
    ),
    (
        "acibonaccorsi",
        "https://servizi.comune.acibonaccorsi.ct.it",
        "087001",
        "Comune di Aci Bonaccorsi",
    ),
    ("milena", "https://servizionline.comune.milena.cl.it", "085010", "Comune di Milena"),
    (
        "alessandriadellarocca",
        "https://trasparenza.comune.alessandriadellarocca.ag.it",
        "084002",
        "Comune di Alessandria della Rocca",
    ),
    (
        "sanpieropatti",
        "https://servizi.comune.sanpieropatti.me.it",
        "083081",
        "Comune di San Piero Patti",
    ),
    ("montevago", "https://servizi.comune.montevago.ag.it", "084025", "Comune di Montevago"),
    (
        "chiusasclafani",
        "https://servizionline.comune.chiusasclafani.pa.it",
        "082029",
        "Comune di Chiusa Sclafani",
    ),
    (
        "sanpierniceto",
        "https://servizi.comune.sanpierniceto.me.it",
        "083080",
        "Comune di San Pier Niceto",
    ),
    ("sancono", "https://servizi.comune.sancono.ct.it", "087040", "Comune di San Cono"),
    ("ferla", "https://servizi.comune.ferla.sr.it", "089008", "Comune di Ferla"),
    ("cesaro", "https://servizionline.comune.cesaro.me.it", "083017", "Comune di Cesarò"),
    ("camastra", "https://trasparenza.comune.camastra.ag.it", "084008", "Comune di Camastra"),
    (
        "ventimigliadisicilia",
        "https://servizionline.comune.ventimigliadisicilia.pa.it",
        "082077",
        "Comune di Ventimiglia di Sicilia",
    ),
    ("giuliana", "https://servizi.comune.giuliana.pa.it", "082039", "Comune di Giuliana"),
    ("baucina", "https://comune.baucina.pa.it", "082008", "Comune di Baucina"),
    (
        "marianopoli",
        "https://servizionline.comune.marianopoli.cl.it",
        "085008",
        "Comune di Marianopoli",
    ),
    (
        "sanmaurocastelverde",
        "https://servizionline.comune.sanmaurocastelverde.pa.it",
        "082065",
        "Comune di San Mauro Castelverde",
    ),
    ("salaparuta", "https://servizi.comune.salaparuta.tp.it", "081017", "Comune di Salaparuta"),
    ("montedoro", "https://servizionline.comune.montedoro.cl.it", "085011", "Comune di Montedoro"),
    (
        "montagnareale",
        "https://servizionline.comune.montagnareale.me.it",
        "083056",
        "Comune di Montagnareale",
    ),
    ("santalfio", "https://servizi.comune.santalfio.ct.it", "087046", "Comune di Sant'Alfio"),
    ("isnello", "https://servizi.comune.isnello.pa.it", "082042", "Comune di Isnello"),
    ("roccamena", "https://servizi.comune.roccamena.pa.it", "082061", "Comune di Roccamena"),
    (
        "poggioreale",
        "https://trasparenza.comune.poggioreale.tp.it",
        "081016",
        "Comune di Poggioreale",
    ),
    ("sutera", "https://servizionline.comune.sutera.cl.it", "085020", "Comune di Sutera"),
    (
        "santeodoro",
        "https://servizionline.comune.santeodoro.me.it",
        "083090",
        "Comune di San Teodoro",
    ),
    ("milo", "https://servizi.comune.milo.ct.it", "087026", "Comune di Milo"),
    (
        "cefaladiana",
        "https://servizionline.comune.cefaladiana.pa.it",
        "082026",
        "Comune di Cefalà Diana",
    ),
    (
        "santacristinagela",
        "https://servizi.comune.santacristinagela.pa.it",
        "082066",
        "Comune di Santa Cristina Gela",
    ),
    ("sperlinga", "https://servizi.comune.sperlinga.en.it", "086017", "Comune di Sperlinga"),
    (
        "roccellavaldemone",
        "https://servizionline.comune.roccellavaldemone.me.it",
        "083074",
        "Comune di Roccella Valdemone",
    ),
    (
        "bompensiere",
        "https://servizionline.comune.bompensiere.cl.it",
        "085002",
        "Comune di Bompensiere",
    ),
    ("condro", "https://servizi.comune.condro.me.it", "083018", "Comune di Condrò"),
    (
        "joppologiancaxio",
        "https://trasparenza.comune.joppologiancaxio.ag.it",
        "084019",
        "Comune di Joppolo Giancaxio",
    ),
]


# Comuni Halley con catena certificato incompleta lato server (cert valido,
# manca l'intermedio): non è un cert scaduto, richiede solo skip_ssl (TAL-49).
_HALLEY_SKIP_SSL = {"siculiana", "joppologiancaxio"}


def _run_halley_comune(
    conn, nome, base_url, codice_istat, denominazione, max_pagine=10, no_stop=False, **_kwargs
):
    from talia.modulo2_scraping.db import EnteMetadato, inserisci_atto, upsert_ente
    from talia.modulo2_scraping.fonti.halley import scarica_atti

    upsert_ente(conn, EnteMetadato(denominazione=denominazione, codice_istat=codice_istat))
    stop_label = " [backfill, stop disabilitato]" if no_stop else ""
    print(
        f"  [{nome.capitalize()}] Scarico albo pretorio Halley EG"
        f" (max {max_pagine} pagine){stop_label}…"
    )
    t0 = time.monotonic()

    inseriti = duplicati = consecutivi_dup = 0
    dates: list[str] = []
    skip_ssl = nome in _HALLEY_SKIP_SSL
    for atto in scarica_atti(base_url, codice_istat, max_pagine=max_pagine, skip_ssl=skip_ssl):
        if inserisci_atto(conn, atto) is not None:
            inseriti += 1
            consecutivi_dup = 0
            if atto.data_atto:
                dates.append(atto.data_atto)
        else:
            duplicati += 1
            consecutivi_dup += 1
        if not no_stop and consecutivi_dup >= _STOP_CONSECUTIVI:
            break
    conn.commit()

    n_trovati = inseriti + duplicati
    elapsed = time.monotonic() - t0
    esito = {"inseriti": inseriti, "duplicati": duplicati}
    print(f"  [{nome.capitalize()}] {n_trovati} atti trovati → {esito} — {elapsed:.0f}s")
    esito["n_trovati"] = n_trovati
    esito["data_min"] = min(dates) if dates else None
    esito["data_max"] = max(dates) if dates else None
    return esito


def _make_halley_runner(entry):
    def _runner(conn, **kwargs):
        return _run_halley_comune(conn, *entry, **kwargs)

    return _runner


# URBI Cloud (Maggioli): stessa piattaforma di Catania (`catania.py`), riusata
# da comuni ospitati su cloud.urbi.it con un DB_NAME diverso per tenant
# (Favara, Raffadali — TAL-49).
_URBI_COMUNI = [
    # (nome_log, base_url, qs_base, codice_istat, ente_mittente, denominazione)
    (
        "favara",
        "https://cloud.urbi.it/urbi/progs/urp/ur1ME001.sto",
        "DB_NAME=wt00037115&w3cbt=S",
        "084017",
        "COMUNE DI FAVARA",
        "Comune di Favara",
    ),
    (
        "raffadali",
        "https://cloud.urbi.it/urbi/progs/urp/ur1ME002.sto",
        "DB_NAME=n1201794&w3cbt=S",
        "084030",
        "COMUNE DI RAFFADALI",
        "Comune di Raffadali",
    ),
    (
        "ravanusa",
        "https://servizi.comune.ravanusa.ag.it/urbi/progs/urp/ur1ME001.sto",
        "DB_NAME=n1200698&w3cbt=S",
        "084031",
        "COMUNE DI RAVANUSA",
        "Comune di Ravanusa",
    ),
    (
        "campobellodilicata",
        "https://cloud.urbi.it/urbi/progs/urp/ur1ME001.sto",
        "DB_NAME=n200119&w3cbt=S",
        "084010",
        "COMUNE DI CAMPOBELLO DI LICATA",
        "Comune di Campobello di Licata",
    ),
    (
        "naro",
        "https://servizionline.comune.naro.ag.it/urbi/progs/urp/ur1ME002.sto",
        "DB_NAME=n200490&w3cbt=S",
        "084026",
        "COMUNE DI NARO",
        "Comune di Naro",
    ),
    (
        "santamargheritadibelice",
        "https://cloud.urbi.it/urbi/progs/urp/ur1ME002.sto",
        "DB_NAME=wt00033773&w3cbt=S",
        "084038",
        "COMUNE DI SANTA MARGHERITA DI BELICE",
        "Comune di Santa Margherita di Belice",
    ),
    (
        "sanbiagioplatani",
        "https://cloud.urbi.it/urbi/progs/urp/ur1ME001.sto",
        "DB_NAME=wt00035339&w3cbt=S",
        "084035",
        "COMUNE DI SAN BIAGIO PLATANI",
        "Comune di San Biagio Platani",
    ),
    (
        "villafrancasicula",
        "https://servizionline.comune.villafrancasicula.ag.it/urbi/progs/urp/ur1ME001.sto",
        "DB_NAME=wt00033035&w3cbt=S",
        "084043",
        "COMUNE DI VILLAFRANCA SICULA",
        "Comune di Villafranca Sicula",
    ),
]


def _run_urbi_comune(
    conn,
    nome,
    base_url,
    qs_base,
    codice_istat,
    ente_mittente,
    denominazione,
    max_pagine=50,
    no_stop=False,
    **_kwargs,
):
    from talia.modulo2_scraping.db import EnteMetadato, inserisci_atto, upsert_ente
    from talia.modulo2_scraping.fonti.urbi import scarica_atti

    upsert_ente(conn, EnteMetadato(denominazione=denominazione, codice_istat=codice_istat))
    stop_label = " [backfill, stop disabilitato]" if no_stop else ""
    print(
        f"  [{nome.capitalize()}] Scarico albo pretorio URBI Cloud"
        f" (max {max_pagine} pagine){stop_label}…"
    )
    t0 = time.monotonic()

    inseriti = duplicati = consecutivi_dup = 0
    dates: list[str] = []
    for atto in scarica_atti(base_url, qs_base, codice_istat, ente_mittente, max_pagine=max_pagine):
        if inserisci_atto(conn, atto) is not None:
            inseriti += 1
            consecutivi_dup = 0
            if atto.data_pub:
                dates.append(atto.data_pub)
        else:
            duplicati += 1
            consecutivi_dup += 1
        if not no_stop and consecutivi_dup >= _STOP_CONSECUTIVI:
            break
    conn.commit()

    n_trovati = inseriti + duplicati
    elapsed = time.monotonic() - t0
    esito = {"inseriti": inseriti, "duplicati": duplicati}
    print(f"  [{nome.capitalize()}] {n_trovati} atti trovati → {esito} — {elapsed:.0f}s")
    esito["n_trovati"] = n_trovati
    esito["data_min"] = min(dates) if dates else None
    esito["data_max"] = max(dates) if dates else None
    return esito


def _make_urbi_runner(entry):
    def _runner(conn, **kwargs):
        return _run_urbi_comune(conn, *entry, **kwargs)

    return _runner


# Halley HSPromila (ASP.NET): variante Halley diversa da quella "EG"
# (`halley.py`), riusata da Sambuca di Sicilia e Santo Stefano Quisquina
# (TAL-49). Nessuna paginazione nota: un solo blocco di atti per comune.
_HSPROMILA_COMUNI = [
    # (nome_log, url, codice_istat, denominazione)
    (
        "sambucadisicilia",
        "https://servizionline.hspromilaprod.hypersicapp.net/cmssambucadisicilia"
        "/portale/albopretorio/albopretorioconsultazione.aspx?P=400",
        "084034",
        "Comune di Sambuca di Sicilia",
    ),
    (
        "santostefanoquisquina",
        "https://servizionline.hspromilaprod.hypersicapp.net/cmsssquisquina"
        "/portale/albopretorio/albopretorioconsultazione.aspx?P=600",
        "084040",
        "Comune di Santo Stefano Quisquina",
    ),
    (
        "santaelisabetta",
        "https://servizionline.hspromilaprod.hypersicapp.net/cmsselisabetta"
        "/portale/albopretorio/albopretorioconsultazione.aspx?P=400",
        "084037",
        "Comune di Santa Elisabetta",
    ),
    (
        "montallegro",
        "https://servizionline.hspromilaprod.hypersicapp.net/cmsmontallegro"
        "/portale/albopretorio/albopretorioconsultazione.aspx?P=400",
        "084024",
        "Comune di Montallegro",
    ),
    (
        "luccasicula",
        "https://servizionline.hspromilaprod.hypersicapp.net/cmsluccasicula"
        "/portale/albopretorio/albopretorioconsultazione.aspx?P=400",
        "084022",
        "Comune di Lucca Sicula",
    ),
]


def _run_hspromila_comune(conn, nome, url, codice_istat, denominazione, **_kwargs) -> dict:
    from talia.modulo2_scraping.db import EnteMetadato, inserisci_atto, upsert_ente
    from talia.modulo2_scraping.fonti.hspromila import scarica_atti

    upsert_ente(conn, EnteMetadato(denominazione=denominazione, codice_istat=codice_istat))
    print(f"  [{nome.capitalize()}] Scarico albo pretorio Halley HSPromila…")
    t0 = time.monotonic()
    atti = list(scarica_atti(url, codice_istat))
    esito = {"inseriti": 0, "duplicati": 0}
    for atto in atti:
        if inserisci_atto(conn, atto) is not None:
            esito["inseriti"] += 1
        else:
            esito["duplicati"] += 1
    conn.commit()
    elapsed = time.monotonic() - t0
    print(f"  [{nome.capitalize()}] {len(atti)} atti trovati → {esito} — {elapsed:.0f}s")
    esito["n_trovati"] = len(atti)
    esito["data_min"], esito["data_max"] = _date_range(atti)
    return esito


def _make_hspromila_runner(entry):
    def _runner(conn, **kwargs):
        return _run_hspromila_comune(conn, *entry, **kwargs)

    return _runner


# Palermo (SISPI JSP) e Catania (HCL Domino NSF) non ancora implementati.

_SCRAPERS: dict[str, callable] = {
    "anac": _run_anac,
    "siracusa": _run_siracusa,
    "trapani": _run_trapani,
    "palermo": _run_palermo,
    "catania": _run_catania,
    "ribera": _run_ribera,
    "agrigento": _run_agrigento,
}
_SCRAPERS.update({entry[0]: _make_jcitygov_runner(entry) for entry in _JCITYGOV_COMUNI})
_SCRAPERS.update({entry[0]: _make_portalepa_runner(entry) for entry in _PORTALEPA_COMUNI})
_SCRAPERS.update({entry[0]: _make_halley_runner(entry) for entry in _HALLEY_COMUNI})
_SCRAPERS.update({entry[0]: _make_urbi_runner(entry) for entry in _URBI_COMUNI})
_SCRAPERS.update({entry[0]: _make_hspromila_runner(entry) for entry in _HSPROMILA_COMUNI})

# Default: HTTP puro (veloci), Agrigento escluso (Playwright), ANAC escluso (400 MB)
_SCRAPERS_DEFAULT = (
    ["siracusa", "trapani", "palermo", "catania", "ribera"]
    + [entry[0] for entry in _JCITYGOV_COMUNI]
    + [entry[0] for entry in _PORTALEPA_COMUNI]
    + [entry[0] for entry in _HALLEY_COMUNI]
    + [entry[0] for entry in _URBI_COMUNI]
    + [entry[0] for entry in _HSPROMILA_COMUNI]
)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Lancia gli scraper TALIA e calcola i red flags.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Scrapers disponibili:
  anac       Dataset SmartCIG ANAC Sicilia (~400 MB, HTTP)
  siracusa   Albo pretorio Siracusa (HTTP)
  trapani    Albo pretorio Trapani (HTTP)
  agrigento  Albo pretorio Agrigento (Playwright — browser headless)

Non inclusi nel default: agrigento (Playwright), iCity comuni (config mancante).

Esempi:
  python scripts/run_scrapers.py
  python scripts/run_scrapers.py --scrapers siracusa trapani --max-pagine 5
  python scripts/run_scrapers.py --scrapers anac --no-red-flags
  python scripts/run_scrapers.py --scrapers siracusa trapani agrigento
  TALIA_DB=prod.db python scripts/run_scrapers.py
        """,
    )
    p.add_argument(
        "--db",
        default=None,
        help="Percorso DB SQLite (default: $TALIA_DB o talia.db)",
    )
    p.add_argument(
        "--scrapers",
        nargs="+",
        choices=list(_SCRAPERS),
        default=_SCRAPERS_DEFAULT,
        metavar="SCRAPER",
        help=f"Scrapers da eseguire (default: {' '.join(_SCRAPERS_DEFAULT)})",
    )
    p.add_argument(
        "--max-pagine",
        type=int,
        default=50,
        dest="max_pagine",
        help="Pagine massime per gli albi pretori (default: 50)",
    )
    p.add_argument(
        "--no-red-flags",
        action="store_true",
        dest="no_red_flags",
        help="Salta il calcolo dei red flags batch",
    )
    p.add_argument(
        "--anac-file",
        default=None,
        dest="anac_file",
        metavar="FILE",
        help=(
            "Carica il CSV SmartCIG da file locale invece di scaricarlo"
            " (utile se il WAF ANAC blocca il download automatico)"
        ),
    )
    p.add_argument(
        "--no-stop",
        action="store_true",
        dest="no_stop",
        help=(
            "Disabilita lo stop-on-known"
            " (backfill storico: scarica tutte le pagine anche se già in DB)"
        ),
    )
    p.add_argument(
        "--llm-modello",
        default=None,
        dest="llm_modello",
        metavar="MODELLO",
        help=(
            "Modello Ollama per classificare i procedimenti non classificati dalle regex"
            " (es. 'llama3.2'). Richiede Ollama attivo su localhost:11434."
            " Default: skip (solo classificazione deterministica)."
        ),
    )
    p.add_argument(
        "--llm-limite",
        type=int,
        default=200,
        dest="llm_limite",
        metavar="N",
        help="Numero massimo di procedimenti da passare all'LLM per run (default: 200).",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    args = _parse_args()

    import os

    db_path = args.db or os.environ.get("TALIA_DB", "talia.db")
    print(f"DB: {db_path}")

    conn = connetti(db_path)
    inizializza_db(conn)

    risultati: dict[str, dict | str] = {}
    errori = 0

    for nome in args.scrapers:
        fn = _SCRAPERS[nome]
        print(f"\n── {nome.upper()} ──")
        run_id = inizia_run(conn, nome)
        try:
            esito = fn(
                conn,
                max_pagine=args.max_pagine,
                anac_file=args.anac_file,
                no_stop=args.no_stop,
            )
            risultati[nome] = esito
            termina_run(
                conn,
                run_id,
                n_trovati=esito.get("n_trovati", 0),
                n_inseriti=esito.get("inseriti", 0),
                n_duplicati=esito.get("duplicati", 0),
                data_min=esito.get("data_min"),
                data_max=esito.get("data_max"),
            )
        except Exception:
            msg = traceback.format_exc()
            print(f"  ERRORE:\n{msg}", file=sys.stderr)
            termina_run(conn, run_id, n_trovati=0, n_inseriti=0, n_duplicati=0, errore=msg[:500])
            risultati[nome] = "ERRORE"
            errori += 1

    if not args.no_red_flags:
        print("\n── RED FLAGS ──")
        if args.llm_modello:
            print(
                f"  [LLM] Classificazione procedimenti sconosciuto con '{args.llm_modello}'"
                f" (max {args.llm_limite})…"
            )
        try:
            report = esegui_tutti(
                conn,
                modello_llm=args.llm_modello,
                llm_limite=args.llm_limite,
            )
            print(
                f"  frazionamento:  {report.frazionamento}\n"
                f"  concentrazione: {report.concentrazione}\n"
                f"  tempi anomali:  {report.tempi_anomali}\n"
                f"  revoche catena: {report.revoche_catena}\n"
                f"  totale flag:    {report.totale_flag}"
            )
        except Exception:
            print(traceback.format_exc(), file=sys.stderr)
            errori += 1

    print("\n── SUMMARY ──")
    for nome, esito in risultati.items():
        if isinstance(esito, dict):
            ins = esito.get("inseriti", 0)
            dup = esito.get("duplicati", 0)
            d0 = esito.get("data_min") or "?"
            d1 = esito.get("data_max") or "?"
            print(f"  {nome:15s}  +{ins:>4} ins  {dup:>4} dup  {d0} → {d1}")
        else:
            print(f"  {nome:15s}  {esito}")

    print("\n── COPERTURA DB ──")
    rows = conn.execute(
        """SELECT e.denominazione,
                  MIN(COALESCE(a.data_pub, a.data_atto)),
                  MAX(COALESCE(a.data_pub, a.data_atto)),
                  COUNT(*)
           FROM atti a JOIN enti e ON a.ente_id = e.id
           GROUP BY e.id ORDER BY e.denominazione"""
    ).fetchall()
    for r in rows:
        print(f"  {r[0]:<28s}  {r[3]:>5} atti  {r[1] or '?':>10} → {r[2] or '?'}")

    n_atti = conn.execute("SELECT COUNT(*) FROM atti").fetchone()[0]
    n_enti = conn.execute("SELECT COUNT(*) FROM enti").fetchone()[0]
    n_flags = conn.execute("SELECT COUNT(*) FROM red_flags").fetchone()[0]
    print(f"\n  DB: {n_enti} enti | {n_atti} atti | {n_flags} red flags")

    conn.close()
    return 1 if errori else 0


if __name__ == "__main__":
    sys.exit(main())
