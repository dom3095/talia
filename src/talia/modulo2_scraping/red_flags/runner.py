"""Runner: esegue tutte le regole batch e salva i risultati nel DB (TAL-23).

Uso tipico:
    conn = connetti("talia.db")
    inizializza_db(conn)
    report = esegui_tutti(conn)
    print(report)

Output:
    dict con chiavi 'frazionamento', 'concentrazione', 'tempi_anomali',
    ognuna con {'n_rilevati': int, 'n_salvati': int}.

Disclaimer: i flag prodotti sono segnalazioni da verificare, non accertamenti.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from talia.engine.catena import ricostruisci_catene
from talia.modulo2_scraping.db import salva_red_flag

from .catena_revoca import RevocaInCatenaRilevata, rileva_revoche_in_catena
from .concentrazione import ConcentrazioneRilevata, rileva_concentrazione
from .frazionamento import FrazionamentoRilevato, rileva_frazionamento
from .tempi_anomali import TempoAnomalioRilevato, rileva_tempi_anomali

# ---------------------------------------------------------------------------
# Mapping → DB
# ---------------------------------------------------------------------------


def _salva_revoca_in_catena(conn: sqlite3.Connection, rc: RevocaInCatenaRilevata) -> int:
    oggetto = rc.oggetto or "n/d"
    giorni = f" dopo {rc.giorni_elapsed} giorni" if rc.giorni_elapsed is not None else ""
    descrizione = (
        f"Procedimento {rc.stato_finale}{giorni}: {oggetto}. "
        f"Avvio: {rc.data_avvio or 'n/d'} — "
        f"{rc.stato_finale.capitalize()}: {rc.data_revoca or 'n/d'}. "
        f"Catena individuata via: {rc.metodo_individuazione or 'n/d'}."
    )
    return salva_red_flag(
        conn,
        ente_id=rc.ente_id,
        tipo_flag="revoca_in_catena",
        severita="alta",
        descrizione=descrizione,
        atti_cig=[
            {"id": a["id"], "url": a["url"], "ruolo": a["ruolo"], "data": a["data"]}
            for a in rc.atti
        ],
        periodo_da=rc.data_avvio,
        periodo_a=rc.data_revoca,
    )


def _salva_frazionamento(conn: sqlite3.Connection, rf: FrazionamentoRilevato) -> int:
    descrizione = (
        f"Potenziale frazionamento: {rf.n_atti} affidamenti sotto soglia "
        f"({rf.periodo_da} – {rf.periodo_a}), totale {rf.totale_euro:,.0f} EUR, "
        f"ciascuno < 140.000 EUR (art. 50 D.lgs. 36/2023)."
    )
    return salva_red_flag(
        conn,
        ente_id=rf.ente_id,
        tipo_flag="frazionamento",
        severita="alta",
        descrizione=descrizione,
        atti_cig=[
            {"id": a["id"], "url": a["url_fonte"], "importo": a["importo_euro"]}
            for a in rf.atti
        ],
        periodo_da=rf.periodo_da,
        periodo_a=rf.periodo_a,
    )


def _salva_concentrazione(conn: sqlite3.Connection, rc: ConcentrazioneRilevata) -> int:
    descrizione = (
        f"Eccessiva concentrazione affidamenti diretti: {rc.n_diretti}/{rc.n_totale} "
        f"({rc.quota_diretti * 100:.0f}%) non a gara nell'anno {rc.anno}. "
        f"Soglia: 80% (principio concorrenza art. 49 D.lgs. 36/2023)."
    )
    return salva_red_flag(
        conn,
        ente_id=rc.ente_id,
        tipo_flag="concentrazione_diretti",
        severita="media",
        descrizione=descrizione,
        atti_cig=[
            {"id": a["id"], "url": a["url_fonte"], "tipo": a["tipo"]}
            for a in rc.atti_campione
        ],
        periodo_da=f"{rc.anno}-01-01",
        periodo_a=f"{rc.anno}-12-31",
    )


def _salva_tempo_anomalo(conn: sqlite3.Connection, ta: TempoAnomalioRilevato) -> int:
    descrizione = (
        f"Finestra di pubblicazione bando troppo breve: {ta.giorni_pubblicazione} giorni "
        f"(soglia: {ta.soglia_applicata} giorni, art. 71 D.lgs. 36/2023). "
        f"Bando: {ta.oggetto or 'n/d'}."
    )
    return salva_red_flag(
        conn,
        ente_id=ta.ente_id,
        tipo_flag="tempo_pubblicazione_breve",
        severita="alta",
        descrizione=descrizione,
        atti_cig=[{"id": ta.atto_id, "url": ta.url_fonte, "giorni": ta.giorni_pubblicazione}],
        periodo_da=ta.data_pub,
        periodo_a=ta.data_scadenza,
    )


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------


@dataclass
class RapportoRunner:
    frazionamento: dict
    concentrazione: dict
    tempi_anomali: dict
    revoche_catena: dict

    @property
    def totale_flag(self) -> int:
        return (
            self.frazionamento["n_salvati"]
            + self.concentrazione["n_salvati"]
            + self.tempi_anomali["n_salvati"]
            + self.revoche_catena["n_salvati"]
        )


def esegui_tutti(conn: sqlite3.Connection) -> RapportoRunner:
    """Esegue tutte le regole di rilevamento e salva i flag nel DB.

    Args:
        conn: connessione SQLite con il DB già inizializzato (tabella ``red_flags``).

    Returns:
        ``RapportoRunner`` con i contatori per regola.
    """
    # --- Catene di eventi (prerequisito per revoche_catena) ---
    ricostruisci_catene(conn)

    # --- Frazionamento ---
    frazi = rileva_frazionamento(conn)
    n_frazi_salvati = sum(1 for rf in frazi if _salva_frazionamento(conn, rf) > 0)

    # --- Concentrazione ---
    conc = rileva_concentrazione(conn)
    n_conc_salvati = sum(1 for rc in conc if _salva_concentrazione(conn, rc) > 0)

    # --- Tempi anomali ---
    tempi = rileva_tempi_anomali(conn)
    n_tempi_salvati = sum(1 for ta in tempi if _salva_tempo_anomalo(conn, ta) > 0)

    # --- Revoche in catena ---
    revoche = rileva_revoche_in_catena(conn)
    n_revoche_salvati = sum(1 for rc in revoche if _salva_revoca_in_catena(conn, rc) > 0)

    return RapportoRunner(
        frazionamento={"n_rilevati": len(frazi), "n_salvati": n_frazi_salvati},
        concentrazione={"n_rilevati": len(conc), "n_salvati": n_conc_salvati},
        tempi_anomali={"n_rilevati": len(tempi), "n_salvati": n_tempi_salvati},
        revoche_catena={"n_rilevati": len(revoche), "n_salvati": n_revoche_salvati},
    )
