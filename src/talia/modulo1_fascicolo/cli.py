"""CLI del Modulo 1: `talia analizza ...`.

Esempi:
    talia analizza fascicolo/                 # PDF e/o .txt in una cartella
    talia analizza indizione.pdf revoca.pdf   # file espliciti
    talia analizza caso.txt --formato html --out report.html
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..engine.models import FonteTesto, TestoAtto
from ..engine.pdf_text import da_pagine
from .analisi import analizza_testi
from .report import Report

_ESTENSIONI = {".pdf", ".txt"}
# Carattere di avanzamento pagina: nei .txt separa le pagine logiche.
_FORM_FEED = "\f"


def main(argv: list[str] | None = None) -> int:
    parser = _crea_parser()
    args = parser.parse_args(argv)
    if args.comando == "analizza":
        return _comando_analizza(args)
    parser.print_help()
    return 1


def _crea_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="talia", description="TALIA — analisi atti PA.")
    sub = parser.add_subparsers(dest="comando")

    analizza = sub.add_parser("analizza", help="Analizza un fascicolo (Modulo 1).")
    analizza.add_argument(
        "percorsi",
        nargs="+",
        help="File (.pdf/.txt) o cartelle contenenti il fascicolo.",
    )
    analizza.add_argument(
        "--formato",
        choices=("testo", "md", "json", "html"),
        default="testo",
        help="Formato di output (default: testo).",
    )
    analizza.add_argument(
        "--out",
        type=Path,
        help="File di destinazione; se omesso scrive su stdout.",
    )
    analizza.add_argument(
        "--llm",
        action="store_true",
        help="Abilita il check 3 (qualità motivazione, TAL-11): richiede un LLM "
        "locale raggiungibile via Ollama (ollama serve) sui fascicoli già flaggati.",
    )
    return parser


def _comando_analizza(args: argparse.Namespace) -> int:
    file = _raccogli_file(args.percorsi)
    if not file:
        print("Nessun file .pdf/.txt trovato nei percorsi indicati.", file=sys.stderr)
        return 1

    try:
        testi = [_carica_testo(f) for f in file]
    except RuntimeError as exc:  # es. extra [pdf] non installati
        print(f"Errore: {exc}", file=sys.stderr)
        return 2

    report = analizza_testi(testi, valuta_llm=args.llm)
    contenuto = _rendi(report, args.formato)

    if args.out:
        args.out.write_text(contenuto, encoding="utf-8")
        print(f"Report scritto in {args.out}")
    else:
        print(contenuto)
    return 0


def _raccogli_file(percorsi: list[str]) -> list[Path]:
    file: list[Path] = []
    for grezzo in percorsi:
        p = Path(grezzo)
        if p.is_dir():
            file.extend(sorted(f for f in p.iterdir() if f.suffix.lower() in _ESTENSIONI))
        elif p.suffix.lower() in _ESTENSIONI:
            file.append(p)
    return file


def _carica_testo(percorso: Path) -> TestoAtto:
    if percorso.suffix.lower() == ".pdf":
        # Import locale: estrai_testo richiede gli extra [pdf]. Si importa qui per
        # non penalizzare l'uso su soli .txt.
        from ..engine.pdf_text import estrai_testo

        return estrai_testo(percorso)
    testo = percorso.read_text(encoding="utf-8")
    pagine = testo.split(_FORM_FEED) if _FORM_FEED in testo else [testo]
    return da_pagine(
        pagine,
        fonte=FonteTesto.NATIVO,
        percorso=percorso.name,
    )


def _rendi(report: Report, formato: str) -> str:
    if formato == "json":
        return report.to_json()
    if formato == "html":
        return report.to_html()
    if formato == "md":
        return report.to_markdown()
    return report.to_markdown()  # "testo" = markdown leggibile a terminale


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
