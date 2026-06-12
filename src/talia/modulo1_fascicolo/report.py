"""TAL-10 — Report del Modulo 1.

Aggrega gli esiti dei check in un `Report` e lo rende in tre formati:
- **testo/markdown**: per la CLI e i log;
- **JSON**: per integrazioni e per la dashboard (Modulo 3);
- **HTML statico**: vista user-facing, con disclaimer in evidenza.

Nessuna dipendenza esterna (budget zero): l'HTML è generato in puro Python con
escaping di sicurezza.
"""

from __future__ import annotations

import html
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime

from talia import DISCLAIMER

from ..engine.checklist import EsitoCheck
from ..engine.models import Citazione, Stato


@dataclass
class AttoMeta:
    """Metadati di un atto, per l'intestazione del report."""

    etichetta: str
    ruolo: str
    fonte: str
    pagine: int


@dataclass
class Report:
    """Esito complessivo dell'analisi di un fascicolo."""

    esiti: list[EsitoCheck]
    atti: list[AttoMeta] = field(default_factory=list)
    disclaimer: str = DISCLAIMER
    generato_il: datetime = field(default_factory=datetime.now)

    @property
    def conteggio(self) -> dict[str, int]:
        """Numero di esiti per stato (chiavi: valori di Stato)."""
        risultato = {stato.value: 0 for stato in Stato}
        for esito in self.esiti:
            risultato[esito.stato.value] += 1
        return risultato

    # --- serializzazione ----------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "generato_il": self.generato_il.isoformat(timespec="seconds"),
            "disclaimer": self.disclaimer,
            "atti": [asdict(a) for a in self.atti],
            "conteggio": self.conteggio,
            "esiti": [_esito_to_dict(e) for e in self.esiti],
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    # --- rese leggibili -----------------------------------------------------

    def to_markdown(self) -> str:
        righe = ["# Report TALIA — Analisi fascicolo", ""]
        if self.atti:
            righe.append("## Atti analizzati")
            for a in self.atti:
                righe.append(f"- **{a.etichetta}** — {a.ruolo} ({a.fonte}, {a.pagine} pagg.)")
            righe.append("")

        c = self.conteggio
        righe.append(
            f"**Esiti:** {Stato.VERDE.emoji} {c['verde']}  "
            f"{Stato.GIALLO.emoji} {c['giallo']}  "
            f"{Stato.ROSSO.emoji} {c['rosso']}  "
            f"{Stato.NON_APPLICABILE.emoji} {c['non_applicabile']}"
        )
        righe.append("")

        for esito in self.esiti:
            righe.append(f"## {esito.stato.emoji} {esito.titolo}")
            righe.append("")
            righe.append(esito.spiegazione)
            if esito.riferimenti_normativi:
                righe.append("")
                righe.append("_Riferimenti:_ " + "; ".join(esito.riferimenti_normativi))
            for cit in esito.citazioni:
                righe.append("")
                righe.append(f"> {_descr_citazione(cit)}")
            righe.append("")

        righe.append("---")
        righe.append(f"_{self.disclaimer}_")
        return "\n".join(righe)

    def to_html(self) -> str:
        return _render_html(self)


def _esito_to_dict(esito: EsitoCheck) -> dict:
    return {
        "id": esito.id,
        "titolo": esito.titolo,
        "stato": esito.stato.value,
        "spiegazione": esito.spiegazione,
        "riferimenti_normativi": list(esito.riferimenti_normativi),
        "citazioni": [asdict(c) for c in esito.citazioni],
    }


def _descr_citazione(cit: Citazione) -> str:
    pagina = f"p. {cit.pagina}, " if cit.pagina is not None else ""
    return f"«{cit.testo}» ({pagina}offset {cit.offset_inizio}–{cit.offset_fine})"


# ---------------------------------------------------------------------------
# Rendering HTML (puro Python, con escaping)
# ---------------------------------------------------------------------------

_COLORI = {
    "verde": "#1a7f37",
    "giallo": "#b08800",
    "rosso": "#b3261e",
    "non_applicabile": "#6e6e6e",
}


def _render_html(report: Report) -> str:
    def esc(s: str) -> str:
        return html.escape(str(s))

    parti: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="it"><head><meta charset="utf-8">',
        "<title>Report TALIA</title>",
        "<style>",
        "body{font-family:system-ui,sans-serif;max-width:820px;margin:2rem auto;"
        "padding:0 1rem;line-height:1.5;color:#1a1a1a}",
        ".disclaimer{background:#fff8e1;border:1px solid #e0c200;padding:1rem;"
        "border-radius:8px;margin:1rem 0}",
        ".check{border-left:4px solid #ccc;padding:.5rem 1rem;margin:1rem 0}",
        ".cit{background:#f5f5f5;border-radius:6px;padding:.5rem .75rem;margin:.5rem 0;"
        "font-size:.9rem;color:#333}",
        ".rif{font-size:.85rem;color:#555}",
        "</style></head><body>",
        "<h1>Report TALIA — Analisi fascicolo</h1>",
        f'<div class="disclaimer">⚠️ {esc(report.disclaimer)}</div>',
    ]

    if report.atti:
        parti.append("<h2>Atti analizzati</h2><ul>")
        for a in report.atti:
            parti.append(
                f"<li><strong>{esc(a.etichetta)}</strong> — {esc(a.ruolo)} "
                f"({esc(a.fonte)}, {a.pagine} pagg.)</li>"
            )
        parti.append("</ul>")

    for esito in report.esiti:
        colore = _COLORI[esito.stato.value]
        parti.append(f'<div class="check" style="border-left-color:{colore}">')
        parti.append(f"<h3>{esito.stato.emoji} {esc(esito.titolo)}</h3>")
        parti.append(f"<p>{esc(esito.spiegazione)}</p>")
        if esito.riferimenti_normativi:
            rif = "; ".join(esc(r) for r in esito.riferimenti_normativi)
            parti.append(f'<p class="rif">Riferimenti: {rif}</p>')
        for cit in esito.citazioni:
            parti.append(f'<div class="cit">{esc(_descr_citazione(cit))}</div>')
        parti.append("</div>")

    quando = esc(report.generato_il.isoformat(timespec="seconds"))
    parti.append(f"<hr><p><em>Generato il {quando}</em></p>")
    parti.append("</body></html>")
    return "\n".join(parti)
