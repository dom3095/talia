"""Diagnosi e campione da etichettare dei red flag di frazionamento (TAL-73).

Sola lettura: apre il DB in modalità read-only, non tocca nulla.

Uso:
    python scripts/diagnosi_frazionamento.py                       # talia.db, 20 flag per strato
    python scripts/diagnosi_frazionamento.py --db talia.db --per-strato 30
    python scripts/diagnosi_frazionamento.py --output-dir reports/tal73

Produce in ``--output-dir`` (default ``reports/tal73``):
    diagnosi.md   — ipotesi di falso positivo strutturale, con conteggi
    campione.csv  — flag da etichettare a mano (colonne `esito`, `note`)

Per stimare il tasso di falsi positivi: compilare `esito` nel CSV con
``vero_segnale`` / ``falso_positivo`` / ``incerto`` e riportare i conteggi
per strato nella card TAL-73.
"""

from __future__ import annotations

import argparse
import csv
import os
import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from talia.modulo2_scraping.red_flags.diagnosi_frazionamento import (  # noqa: E402
    COLONNE_CSV,
    campiona,
    carica_flag,
    diagnostica,
    formatta_diagnosi,
    righe_csv,
)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--db", default=os.environ.get("TALIA_DB", "talia.db"))
    p.add_argument("--per-strato", type=int, default=20, dest="per_strato")
    p.add_argument("--seme", type=int, default=72, help="Seme del campionamento (riproducibile)")
    p.add_argument("--output-dir", default="reports/tal73", dest="output_dir")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    if not Path(args.db).exists():
        print(f"DB non trovato: {args.db}", file=sys.stderr)
        return 2
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row

    flags = carica_flag(conn)
    if not flags:
        print("Nessun red flag di frazionamento nel DB.")
        return 0

    testo = formatta_diagnosi(diagnostica(flags))
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "diagnosi.md").write_text(testo, encoding="utf-8")

    campione = campiona(flags, per_strato=args.per_strato, seme=args.seme)
    with (out / "campione.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLONNE_CSV)
        writer.writeheader()
        writer.writerows(righe_csv(campione))

    print(testo)
    print(f"Scritti {out / 'diagnosi.md'} e {out / 'campione.csv'} ({len(campione)} flag).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
