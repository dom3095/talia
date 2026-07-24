"""Prepara fascicoli candidati per TAL-12 a partire dalle catene "problematiche"
individuate da TAL-47/48: revocate/annullate (``procedimenti_critici``) e
riaperture (``procedimenti_da_riapertura``).

Per ciascun candidato, diversificato per ente:
  1. Scarica i PDF nella struttura canonica ``data/raw/pdf/<ente>/<id>/`` —
     riusa ``scarica_pdf_procedimento``/``scarica_pdf_riapertura`` di TAL-47/48
     (hash, meta.json, motivo_selezione.json/motivo_riapertura.json invariati).
  2. Copia i soli PDF (non i .bin di firma) in ``data/samples/<N>/`` — piatto,
     come si aspetta ``talia analizza`` — con un ``fonte.json`` che traccia la
     provenienza (procedimento/red flag, ente, criterio di selezione).
  3. Lancia ``talia analizza`` sulla cartella e salva ``report.md``.

Le catene con lo stesso `procedimento_id` di una riapertura non vengono anche
selezionate come "critiche" semplici (evita fascicoli duplicati per la stessa
vicenda).

Nessun dato viene MAI committato da qui: ``data/samples/`` resta locale (vedi
CLAUDE.md — mai PDF nominativi reali nel repo). Il "verde/giallo/rosso" del
report è un punto di partenza deterministico, non una valutazione legale: la
lettura umana (⚖️ LEX) resta il passo successivo, non automatizzato qui.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from talia.modulo1_fascicolo.analisi import analizza_testi  # noqa: E402
from talia.modulo1_fascicolo.cli import _carica_testo  # noqa: E402
from talia.modulo2_scraping.pdf_download import (  # noqa: E402
    _FONTI_SUPPORTATE,
    _diversifica_per_ente,
    procedimenti_critici,
    procedimenti_da_riapertura,
    scarica_pdf_procedimento,
    scarica_pdf_riapertura,
)

_SAMPLES_DIR = Path("data/samples")


def seleziona_candidati(
    conn: sqlite3.Connection, limite: int = 9, fonti: tuple[str, ...] = _FONTI_SUPPORTATE
) -> list[dict]:
    """Combina riaperture + catene critiche in una lista diversificata per ente.

    Ritorna dict ``{"tipo": "riapertura"|"critica", "id": ..., "ente_id": ...}``.
    Le riaperture hanno priorità (due bandi collegati sono più narrabili di una
    singola revoca) e la loro catena originale viene esclusa dai "critici"
    semplici per non duplicare la stessa vicenda in due fascicoli.
    """
    flag_ids = procedimenti_da_riapertura(conn, fonti=fonti, limite=None)
    riaperture: list[tuple[int, int]] = []
    id_catena_da_riapertura: set[int] = set()
    for flag_id in flag_ids:
        row = conn.execute(
            "SELECT ente_id, atti_cig FROM red_flags WHERE id = ?", (flag_id,)
        ).fetchone()
        if row is None:
            continue
        ente_id, atti_cig_raw = row
        try:
            dettaglio = json.loads(atti_cig_raw or "[]")
        except json.JSONDecodeError:
            dettaglio = []
        if dettaglio and dettaglio[0].get("id_catena_revocata") is not None:
            id_catena_da_riapertura.add(dettaglio[0]["id_catena_revocata"])
        riaperture.append((flag_id, ente_id))

    proc_ids = procedimenti_critici(conn, fonti=fonti, limite=None)
    critiche: list[tuple[int, int]] = []
    for proc_id in proc_ids:
        if proc_id in id_catena_da_riapertura:
            continue
        riga = conn.execute("SELECT ente_id FROM procedimenti WHERE id = ?", (proc_id,)).fetchone()
        if riga:
            critiche.append((proc_id, riga[0]))

    combinato = [{"tipo": "riapertura", "id": fid, "ente_id": eid} for fid, eid in riaperture] + [
        {"tipo": "critica", "id": pid, "ente_id": eid} for pid, eid in critiche
    ]
    righe = [(i, c["ente_id"]) for i, c in enumerate(combinato)]
    indici_scelti = _diversifica_per_ente(righe, limite)
    return [combinato[i] for i in indici_scelti]


def prossimo_id_libero() -> int:
    esistenti = [int(p.name) for p in _SAMPLES_DIR.iterdir() if p.is_dir() and p.name.isdigit()]
    return max(esistenti, default=0) + 1


def prepara_fascicolo(sample_id: int, downloaded: list[Path], provenienza: dict) -> Path:
    sample_dir = _SAMPLES_DIR / str(sample_id)
    sample_dir.mkdir(parents=True, exist_ok=True)
    n_copiati = 0
    for pdf in downloaded:
        if pdf.suffix.lower() != ".pdf":
            continue  # .bin (firme digitali): talia analizza legge solo .pdf/.txt
        target = sample_dir / pdf.name
        if not target.exists():
            shutil.copy2(pdf, target)
        n_copiati += 1
    (sample_dir / "fonte.json").write_text(
        json.dumps({**provenienza, "n_pdf": n_copiati}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return sample_dir


def genera_report(sample_dir: Path) -> dict:
    """Lancia il Modulo 1 sulla cartella e salva report.md + report.json."""
    file_pdf = sorted(sample_dir.glob("*.pdf"))
    if not file_pdf:
        return {"errore": "nessun PDF"}
    try:
        testi = [_carica_testo(f) for f in file_pdf]
        report = analizza_testi(testi)
    except Exception as e:
        return {"errore": str(e)}
    (sample_dir / "report.md").write_text(report.to_markdown(), encoding="utf-8")
    (sample_dir / "report.json").write_text(report.to_json(), encoding="utf-8")
    return report.conteggio


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="talia.db")
    parser.add_argument("--limite", type=int, default=9)
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    candidati = seleziona_candidati(conn, limite=args.limite)
    print(f"Candidati selezionati: {len(candidati)}")

    riepilogo = []
    for c in candidati:
        sample_id = prossimo_id_libero()
        try:
            if c["tipo"] == "riapertura":
                downloaded = scarica_pdf_riapertura(conn, c["id"])
                criterio = (
                    "riapertura_dopo_revoca (TAL-48): bando revocato/annullato "
                    "e poi ripubblicato"
                )
            else:
                downloaded = scarica_pdf_procedimento(conn, c["id"])
                criterio = "procedimento revocato/annullato (TAL-47)"
        except Exception as e:
            print(f"  [{c['tipo']}] id={c['id']}: errore download: {e}")
            continue

        if not downloaded:
            print(f"  [{c['tipo']}] id={c['id']}: 0 PDF scaricati, skip")
            continue

        provenienza = {
            "criterio_selezione": criterio,
            "tipo": c["tipo"],
            "id_selezione": c["id"],
            "ente_id": c["ente_id"],
            "disclaimer": "Segnalazione da verificare, non accertamento.",
        }
        sample_dir = prepara_fascicolo(sample_id, downloaded, provenienza)
        conteggio = genera_report(sample_dir)
        print(f"  data/samples/{sample_id}/  ← {c['tipo']} id={c['id']}  {conteggio}")
        riepilogo.append({"sample_id": sample_id, **c, "conteggio": conteggio})

    print("\n── RIEPILOGO ──")
    for r in riepilogo:
        print(f"  {r['sample_id']:>3}  {r['tipo']:10s}  {r['conteggio']}")

    conn.close()


if __name__ == "__main__":
    main()
