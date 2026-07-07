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
    (
        "barcellonapg",
        "https://servizi.comune.barcellonapozzodigotto.me.it/barcellona",
        "083005",
        "Comune di Barcellona Pozzo di Gotto",
    ),
]


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


def _make_halley_runner(entry):
    def _runner(conn, **kwargs):
        return _run_halley_comune(conn, *entry, **kwargs)

    return _runner


# Palermo (SISPI JSP) e Catania (HCL Domino NSF) non ancora implementati.

_SCRAPERS: dict[str, callable] = {
    "anac": _run_anac,
    "siracusa": _run_siracusa,
    "trapani": _run_trapani,
    "palermo": _run_palermo,
    "catania": _run_catania,
    "agrigento": _run_agrigento,
}
_SCRAPERS.update({entry[0]: _make_jcitygov_runner(entry) for entry in _JCITYGOV_COMUNI})
_SCRAPERS.update({entry[0]: _make_portalepa_runner(entry) for entry in _PORTALEPA_COMUNI})
_SCRAPERS.update({entry[0]: _make_halley_runner(entry) for entry in _HALLEY_COMUNI})

# Default: HTTP puro (veloci), Agrigento escluso (Playwright), ANAC escluso (400 MB)
_SCRAPERS_DEFAULT = (
    ["siracusa", "trapani", "palermo", "catania"]
    + [entry[0] for entry in _JCITYGOV_COMUNI]
    + [entry[0] for entry in _PORTALEPA_COMUNI]
    + [entry[0] for entry in _HALLEY_COMUNI]
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
