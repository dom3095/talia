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
    ("caltanissetta", _BASE.format("caltanissetta"), "085003", "Comune di Caltanissetta"),
    ("enna",          _BASE.format("enna"),          "086010", "Comune di Enna"),
    (
        "palma",
        "https://palmadimontechiaro.trasparenza-valutazione-merito.it",
        "084028",
        "Comune di Palma di Montechiaro",
    ),
    ("ragusa",        _BASE.format("ragusa"),        "088009", "Comune di Ragusa"),
]


def _run_jcitygov_comune(
    conn, nome, base_url, codice_istat, denominazione,
    max_pagine=10, no_stop=False, **_kwargs
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


def _run_caltanissetta(conn, **kwargs):
    return _run_jcitygov_comune(conn, *_JCITYGOV_COMUNI[0], **kwargs)


def _run_enna(conn, **kwargs):
    return _run_jcitygov_comune(conn, *_JCITYGOV_COMUNI[1], **kwargs)


def _run_palma(conn, **kwargs):
    return _run_jcitygov_comune(conn, *_JCITYGOV_COMUNI[2], **kwargs)


def _run_ragusa(conn, **kwargs):
    return _run_jcitygov_comune(conn, *_JCITYGOV_COMUNI[3], **kwargs)


# Palermo (SISPI JSP) e Catania (HCL Domino NSF) non ancora implementati.

_SCRAPERS: dict[str, callable] = {
    "anac": _run_anac,
    "siracusa": _run_siracusa,
    "trapani": _run_trapani,
    "agrigento": _run_agrigento,
    "caltanissetta": _run_caltanissetta,
    "enna": _run_enna,
    "palma": _run_palma,
    "ragusa": _run_ragusa,
}

# Default: HTTP puro (veloci), Agrigento escluso (Playwright), ANAC escluso (400 MB)
_SCRAPERS_DEFAULT = ["siracusa", "trapani", "caltanissetta", "enna", "palma", "ragusa"]


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
                conn, run_id,
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
        try:
            report = esegui_tutti(conn)
            print(
                f"  frazionamento:  {report.frazionamento}\n"
                f"  concentrazione: {report.concentrazione}\n"
                f"  tempi anomali:  {report.tempi_anomali}\n"
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
