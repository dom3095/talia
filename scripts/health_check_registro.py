"""Health-check del registro scraper (TAL-51): verifica raggiungibilità HTTP.

Un tentativo HEAD per ogni base_url del registro (fallback GET su 405/501),
timeout 8s, nessun retry pesante. Stdlib puro: urllib.request + ssl +
concurrent.futures. Verifica TUTTE le righe con base_url non vuoto, incluse
bloccato/pending — un fallimento su queste è atteso e non genera rumore
nell'exit code.

Uso:
    python scripts/health_check_registro.py
    python scripts/health_check_registro.py --summary /tmp/summary.md --json /tmp/report.json

Exit code: 0 se tutte le righe attivo/escluso_default rispondono; 1 se almeno
una fallisce (bloccato/pending non influenzano l'exit code).
"""

from __future__ import annotations

import argparse
import json
import ssl
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from talia.modulo2_scraping.registry import EntryRegistro, carica_registro  # noqa: E402

_TIMEOUT_S = 8
_MAX_WORKERS = 10
_USER_AGENT = "TALIA-healthcheck/1.0 (+https://github.com/, uso interno progetto civico)"
_STATI_CRITICI = ("attivo", "escluso_default")


@dataclass
class EsitoCheck:
    slug: str
    denominazione: str
    modulo: str
    base_url: str
    stato_registro: str
    ok: bool
    http_status: int | None
    errore: str | None
    durata_s: float


def _contesto_ssl(entry: EntryRegistro) -> ssl.SSLContext | None:
    if not entry.skip_ssl:
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _richiedi(url: str, metodo: str, ctx: ssl.SSLContext | None) -> int:
    req = urllib.request.Request(url, method=metodo, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=_TIMEOUT_S, context=ctx) as resp:
        return resp.status


def _verifica_url(entry: EntryRegistro) -> EsitoCheck:
    t0 = time.monotonic()
    ctx = _contesto_ssl(entry)
    try:
        status = _richiedi(entry.base_url, "HEAD", ctx)
        return EsitoCheck(
            entry.slug,
            entry.denominazione,
            entry.modulo,
            entry.base_url,
            entry.stato,
            True,
            status,
            None,
            time.monotonic() - t0,
        )
    except urllib.error.HTTPError as e:
        if e.code in (405, 501):
            try:
                status = _richiedi(entry.base_url, "GET", ctx)
                return EsitoCheck(
                    entry.slug,
                    entry.denominazione,
                    entry.modulo,
                    entry.base_url,
                    entry.stato,
                    True,
                    status,
                    None,
                    time.monotonic() - t0,
                )
            except Exception as e2:  # noqa: BLE001 — qualunque errore di rete è un fallimento del check
                return EsitoCheck(
                    entry.slug,
                    entry.denominazione,
                    entry.modulo,
                    entry.base_url,
                    entry.stato,
                    False,
                    None,
                    str(e2),
                    time.monotonic() - t0,
                )
        return EsitoCheck(
            entry.slug,
            entry.denominazione,
            entry.modulo,
            entry.base_url,
            entry.stato,
            False,
            e.code,
            str(e),
            time.monotonic() - t0,
        )
    except Exception as e:  # noqa: BLE001 — qualunque errore di rete è un fallimento del check
        return EsitoCheck(
            entry.slug,
            entry.denominazione,
            entry.modulo,
            entry.base_url,
            entry.stato,
            False,
            None,
            str(e),
            time.monotonic() - t0,
        )


def esegui_health_check(
    entries: list[EntryRegistro], max_workers: int = _MAX_WORKERS
) -> list[EsitoCheck]:
    """Verifica in parallelo ogni riga del registro con un base_url non vuoto."""
    da_verificare = [e for e in entries if e.base_url]
    risultati: list[EsitoCheck] = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_verifica_url, e): e for e in da_verificare}
        for fut in as_completed(futures):
            risultati.append(fut.result())
    risultati.sort(key=lambda r: r.slug)
    return risultati


def _falliti_critici(risultati: list[EsitoCheck]) -> list[EsitoCheck]:
    return [r for r in risultati if r.stato_registro in _STATI_CRITICI and not r.ok]


def _falliti_attesi(risultati: list[EsitoCheck]) -> list[EsitoCheck]:
    return [r for r in risultati if r.stato_registro not in _STATI_CRITICI and not r.ok]


def _exit_code(risultati: list[EsitoCheck]) -> int:
    return 1 if _falliti_critici(risultati) else 0


def _scrivi_summary_md(risultati: list[EsitoCheck], percorso: str) -> None:
    critici = _falliti_critici(risultati)
    attesi = _falliti_attesi(risultati)
    ok_count = sum(1 for r in risultati if r.ok)

    righe = [
        "# Health-check registro scraper",
        "",
        f"**{ok_count}/{len(risultati)} OK** — "
        f"{len(critici)} falliti inattesi, {len(attesi)} falliti attesi (bloccato/pending).",
        "",
    ]
    if critici:
        righe += [
            "## ⚠️ Falliti inattesi (attivo/escluso_default)",
            "",
            "| Comune | Modulo | URL | Errore |",
            "|---|---|---|---|",
        ]
        righe += [
            f"| {r.denominazione} | {r.modulo} | {r.base_url} | {r.errore or r.http_status} |"
            for r in critici
        ]
        righe.append("")
    else:
        righe.append("Nessun fallimento inatteso. ✅")
        righe.append("")
    if attesi:
        righe += [
            "## Falliti attesi (bloccato/pending, non azionabili)",
            "",
            "| Comune | Stato registro | Errore |",
            "|---|---|---|",
        ]
        righe += [
            f"| {r.denominazione} | {r.stato_registro} | {r.errore or r.http_status} |"
            for r in attesi
        ]
        righe.append("")

    Path(percorso).write_text("\n".join(righe), encoding="utf-8")


def _scrivi_json(risultati: list[EsitoCheck], percorso: str) -> None:
    Path(percorso).write_text(
        json.dumps([asdict(r) for r in risultati], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Health-check HTTP di tutti i base_url nel registro scraper TALIA."
    )
    p.add_argument(
        "--registro",
        default=None,
        metavar="FILE",
        help="Path al CSV (default: data/registro_scraper.csv)",
    )
    p.add_argument("--summary", default=None, metavar="FILE", help="Scrive un report Markdown")
    p.add_argument(
        "--json", default=None, metavar="FILE", dest="json_out", help="Scrive un report JSON"
    )
    p.add_argument("--max-workers", type=int, default=_MAX_WORKERS, dest="max_workers")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    entries = carica_registro(args.registro)
    risultati = esegui_health_check(entries, max_workers=args.max_workers)

    ok_count = sum(1 for r in risultati if r.ok)
    print(f"{ok_count}/{len(risultati)} OK")
    for r in risultati:
        if not r.ok:
            marker = "‼️ " if r.stato_registro in _STATI_CRITICI else "·  "
            print(f"  {marker}{r.slug:30s} [{r.stato_registro:16s}] {r.errore or r.http_status}")

    if args.summary:
        _scrivi_summary_md(risultati, args.summary)
    if args.json_out:
        _scrivi_json(risultati, args.json_out)

    return _exit_code(risultati)


if __name__ == "__main__":
    sys.exit(main())
