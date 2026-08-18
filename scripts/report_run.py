#!/usr/bin/env python3
"""Riepilogo dello stato degli scraper — usato dal run giornaliero (TAL-66).

Stampa un riepilogo Markdown e ritorna un exit code che il wrapper del cron
usa per decidere se notificare:

    0  nessun problema
    1  ci sono scraper falliti / muti / fermi
    2  errore nell'esecuzione del report stesso (DB assente, ecc.)

Uso:
    python scripts/report_run.py                      # su $TALIA_DB o talia.db
    python scripts/report_run.py --db /tmp/test.db
    python scripts/report_run.py --output logs/report.md
    python scripts/report_run.py --giorni-stale 7
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from talia.modulo2_scraping.db import connetti  # noqa: E402
from talia.modulo2_scraping.registry import (  # noqa: E402
    carica_registro,
    entries_default,
)
from talia.modulo2_scraping.run_report import (  # noqa: E402
    GIORNI_STALE_DEFAULT,
    formatta_markdown,
    riepiloga,
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--db", default=None, help="Percorso DB SQLite (default: $TALIA_DB o talia.db)")
    p.add_argument("--output", default=None, help="Scrive il riepilogo anche su file")
    p.add_argument(
        "--giorni-stale",
        type=int,
        default=GIORNI_STALE_DEFAULT,
        dest="giorni_stale",
        help=f"Giorni oltre i quali uno scraper è 'fermo' (default: {GIORNI_STALE_DEFAULT})",
    )
    p.add_argument(
        "--no-registro",
        action="store_true",
        dest="no_registro",
        help="Non confrontare con il registro (salta la sezione 'mai eseguiti')",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    db_path = args.db or os.environ.get("TALIA_DB", "talia.db")
    if not Path(db_path).exists():
        print(f"DB non trovato: {db_path}", file=sys.stderr)
        return 2

    attesi = None
    if not args.no_registro:
        try:
            attesi = entries_default(carica_registro())
        except Exception as exc:  # registro malformato: il report resta utile lo stesso
            print(f"Attenzione: registro non caricato ({exc})", file=sys.stderr)

    conn = connetti(db_path)
    try:
        riepilogo = riepiloga(conn, scraper_attesi=attesi, giorni_stale=args.giorni_stale)
    finally:
        conn.close()

    testo = formatta_markdown(riepilogo, giorni_stale=args.giorni_stale)
    print(testo)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(testo, encoding="utf-8")

    return 1 if riepilogo.ha_problemi else 0


if __name__ == "__main__":
    sys.exit(main())
