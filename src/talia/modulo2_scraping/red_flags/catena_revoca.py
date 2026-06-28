"""Red flag: revoca/annullamento in catena procedimento — TAL-44.

Rileva procedimenti con almeno un atto di avvio e uno di revoca/annullamento.
Richiede che `ricostruisci_catene` sia già stato eseguito (catene nel DB).

Disclaimer: segnalazione da verificare, non accertamento.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import date


@dataclass
class RevocaInCatenaRilevata:
    """Procedimento revocato o annullato, con la sua catena di atti."""

    procedimento_id: int
    ente_id: int
    cig: str | None
    oggetto: str | None
    stato_finale: str        # 'revocato' | 'annullato'
    data_avvio: str | None
    data_revoca: str | None
    giorni_elapsed: int | None
    metodo_individuazione: str | None
    atti: list[dict] = field(default_factory=list)
    # ogni dict: {id, url_fonte, ruolo_in_catena, data_atto, oggetto}


def rileva_revoche_in_catena(conn: sqlite3.Connection) -> list[RevocaInCatenaRilevata]:
    """Trova tutti i procedimenti revocati/annullati nel DB.

    Presuppone che `ricostruisci_catene` sia già stato eseguito e che
    la tabella `procedimenti` esista (creata da `_evolvi_schema`).
    """
    try:
        procedimenti = conn.execute(
            """
            SELECT p.id, p.ente_id, p.cig, p.oggetto, p.stato_finale,
                   p.data_avvio, p.data_chiusura, p.metodo_individuazione
            FROM   procedimenti p
            WHERE  p.stato_finale IN ('revocato', 'annullato')
            """
        ).fetchall()
    except Exception:
        # Tabella procedimenti non ancora creata: nessun flag.
        return []

    risultati: list[RevocaInCatenaRilevata] = []
    for p in procedimenti:
        atti = conn.execute(
            """
            SELECT id, url_fonte, ruolo_in_catena, data_atto, oggetto
            FROM   atti
            WHERE  procedimento_id = ?
            ORDER  BY data_atto ASC NULLS LAST
            """,
            (p["id"],),
        ).fetchall()

        # Verifica che ci sia davvero un atto di avvio (non solo la revoca)
        ruoli = {a["ruolo_in_catena"] for a in atti}
        if "avvio" not in ruoli:
            continue

        data_revoca = next(
            (a["data_atto"] for a in atti if a["ruolo_in_catena"] in ("revoca", "annullamento")),
            p["data_chiusura"],
        )

        giorni_elapsed = None
        if p["data_avvio"] and data_revoca:
            try:
                d0 = date.fromisoformat(p["data_avvio"][:10])
                d1 = date.fromisoformat(data_revoca[:10])
                giorni_elapsed = (d1 - d0).days
            except ValueError:
                pass

        risultati.append(RevocaInCatenaRilevata(
            procedimento_id=p["id"],
            ente_id=p["ente_id"],
            cig=p["cig"],
            oggetto=p["oggetto"],
            stato_finale=p["stato_finale"],
            data_avvio=p["data_avvio"],
            data_revoca=data_revoca,
            giorni_elapsed=giorni_elapsed,
            metodo_individuazione=p["metodo_individuazione"],
            atti=[
                {
                    "id": a["id"],
                    "url": a["url_fonte"],
                    "ruolo": a["ruolo_in_catena"],
                    "data": a["data_atto"],
                }
                for a in atti
            ],
        ))

    return risultati


__all__ = ["RevocaInCatenaRilevata", "rileva_revoche_in_catena"]
