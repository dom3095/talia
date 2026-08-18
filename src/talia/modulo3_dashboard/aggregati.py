"""Aggregati temporali per la dashboard (TAL-67).

Funzioni pure di query: nessun import di Streamlit, così sono testabili
senza avviare l'app. La dashboard le usa per la tab "📅 Aggregati".

Due assi temporali distinti, che rispondono a domande diverse e **non vanno
confusi**:

* ``asse="atto"`` — quando l'atto è stato prodotto/pubblicato dal comune.
  Usa ``COALESCE(data_atto, data_pub)``: l'80% degli atti nel DB ha
  ``data_atto`` NULL perché molti scraper leggono solo la pagina-lista
  dell'albo, che espone la finestra di pubblicazione (vedi CLAUDE.md).
  Serve a leggere l'attività amministrativa del territorio.
* ``asse="ingestione"`` — quando TALIA ha raccolto l'atto (``data_accesso``).
  Serve a leggere la salute della pipeline di scraping, non il territorio:
  un backfill storico produce un picco enorme in un giorno solo.

Le date fuori intervallo plausibile sono escluse da entrambe le serie: sul DB
reale esistono poche righe con anni palesemente corrotti (es. ``0202-06-16``,
refuso nell'atto sorgente) che altrimenti sfondano l'asse dei grafici.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

#: Granularità disponibili → etichetta leggibile per i selettori della UI.
GRANULARITA: dict[str, str] = {
    "giornaliera": "Giornaliera",
    "settimanale": "Settimanale",
    "mensile": "Mensile",
    "trimestrale": "Trimestrale",
    "semestrale": "Semestrale",
}

#: Assi temporali disponibili → etichetta leggibile.
ASSI: dict[str, str] = {
    "atto": "Data dell'atto (COALESCE data_atto/data_pub)",
    "ingestione": "Data di ingestione in TALIA (data_accesso)",
}

# Espressione SQL della data per ciascun asse. `data_accesso` è un timestamp
# ISO completo (con fuso), quindi va troncato a giorno.
_ESPR_ASSE: dict[str, str] = {
    "atto": "COALESCE(a.data_atto, a.data_pub)",
    "ingestione": "date(a.data_accesso)",
}

# Finestra di date considerate valide. Il limite superiore non è "oggi": la
# `data_pub` è la data di *inizio pubblicazione* e alcuni albi pubblicano atti
# con decorrenza nei giorni successivi — non sono errori.
DATA_MIN_VALIDA = "2000-01-01"
GIORNI_FUTURO_AMMESSI = 90


@dataclass(frozen=True)
class PuntoSerie:
    """Un periodo della serie temporale."""

    periodo: str  # etichetta leggibile, es. "2026-08", "2026-T3"
    inizio: str  # data ISO di inizio periodo (chiave di ordinamento)
    n_atti: int
    n_enti: int


@dataclass(frozen=True)
class RigaTerritorio:
    """Aggregato di un territorio (comune o provincia) su un intervallo."""

    nome: str
    n_atti: int
    n_enti: int
    primo: str | None
    ultimo: str | None


# ---------------------------------------------------------------------------
# Espressioni SQL per granularità
# ---------------------------------------------------------------------------


def _espressioni_periodo(granularita: str, d: str) -> tuple[str, str]:
    """Ritorna ``(etichetta_sql, inizio_sql)`` per la granularità richiesta.

    ``d`` è l'espressione SQL che produce una data ``YYYY-MM-DD``.

    La settimana è ancorata al **lunedì** (``weekday 0`` porta alla domenica
    successiva o al giorno stesso se è domenica; ``-6 days`` risale al lunedì),
    invece che a ``strftime('%W')`` — così l'etichetta è una data vera,
    ordinabile e senza le ambiguità di numerazione a cavallo d'anno.
    """
    mese = f"CAST(strftime('%m', {d}) AS INTEGER)"
    anno = f"strftime('%Y', {d})"
    if granularita == "giornaliera":
        return d, d
    if granularita == "settimanale":
        lunedi = f"date({d}, 'weekday 0', '-6 days')"
        return lunedi, lunedi
    if granularita == "mensile":
        return f"strftime('%Y-%m', {d})", f"strftime('%Y-%m-01', {d})"
    if granularita == "trimestrale":
        trim = f"(({mese} + 2) / 3)"
        etichetta = f"{anno} || '-T' || {trim}"
        inizio = f"{anno} || '-' || printf('%02d', {trim} * 3 - 2) || '-01'"
        return etichetta, inizio
    if granularita == "semestrale":
        sem = f"(({mese} + 5) / 6)"
        etichetta = f"{anno} || '-S' || {sem}"
        inizio = f"{anno} || '-' || printf('%02d', {sem} * 6 - 5) || '-01'"
        return etichetta, inizio
    raise ValueError(f"Granularità sconosciuta: {granularita!r} (attese: {sorted(GRANULARITA)})")


def _espressione_data(asse: str) -> str:
    try:
        return _ESPR_ASSE[asse]
    except KeyError:
        raise ValueError(f"Asse sconosciuto: {asse!r} (attesi: {sorted(ASSI)})") from None


def _filtri_territorio(
    provincia: str | None, ente_id: int | None
) -> tuple[list[str], list[object]]:
    dove: list[str] = []
    parametri: list[object] = []
    if provincia:
        dove.append("e.provincia = ?")
        parametri.append(provincia)
    if ente_id is not None:
        dove.append("a.ente_id = ?")
        parametri.append(ente_id)
    return dove, parametri


def _clausola_validita(d: str) -> str:
    return (
        f"{d} IS NOT NULL AND {d} >= '{DATA_MIN_VALIDA}'"
        f" AND {d} <= date('now', '+{GIORNI_FUTURO_AMMESSI} days')"
    )


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


def serie_temporale(
    conn: sqlite3.Connection,
    *,
    granularita: str = "mensile",
    asse: str = "atto",
    provincia: str | None = None,
    ente_id: int | None = None,
    da: str | None = None,
    a: str | None = None,
) -> list[PuntoSerie]:
    """Serie di atti aggregati per periodo, filtrabile per provincia o comune.

    ``da``/``a`` sono date ISO inclusive sull'asse scelto.
    """
    d = _espressione_data(asse)
    etichetta, inizio = _espressioni_periodo(granularita, d)

    dove = [_clausola_validita(d)]
    parametri: list[object] = []
    filtri, par_filtri = _filtri_territorio(provincia, ente_id)
    dove += filtri
    parametri += par_filtri
    if da:
        dove.append(f"{d} >= ?")
        parametri.append(da)
    if a:
        dove.append(f"{d} <= ?")
        parametri.append(a)

    righe = conn.execute(
        f"""
        SELECT {etichetta} AS periodo,
               {inizio}    AS inizio,
               COUNT(*)              AS n_atti,
               COUNT(DISTINCT a.ente_id) AS n_enti
        FROM atti a JOIN enti e ON a.ente_id = e.id
        WHERE {" AND ".join(dove)}
        GROUP BY periodo, inizio
        ORDER BY inizio
        """,
        parametri,
    ).fetchall()
    return [
        PuntoSerie(
            periodo=r["periodo"],
            inizio=r["inizio"],
            n_atti=r["n_atti"],
            n_enti=r["n_enti"],
        )
        for r in righe
    ]


def aggregati_per_provincia(
    conn: sqlite3.Connection,
    *,
    asse: str = "atto",
    da: str | None = None,
    a: str | None = None,
) -> list[RigaTerritorio]:
    """Totali per provincia sull'intervallo richiesto."""
    return _aggregati_territorio(
        conn,
        raggruppa_per="COALESCE(e.provincia, 'n/d')",
        asse=asse,
        da=da,
        a=a,
        provincia=None,
    )


def aggregati_per_comune(
    conn: sqlite3.Connection,
    *,
    asse: str = "atto",
    provincia: str | None = None,
    da: str | None = None,
    a: str | None = None,
    limite: int | None = None,
) -> list[RigaTerritorio]:
    """Totali per comune sull'intervallo richiesto, opzionalmente di una provincia."""
    righe = _aggregati_territorio(
        conn,
        raggruppa_per="e.denominazione",
        asse=asse,
        da=da,
        a=a,
        provincia=provincia,
    )
    return righe[:limite] if limite else righe


def _aggregati_territorio(
    conn: sqlite3.Connection,
    *,
    raggruppa_per: str,
    asse: str,
    da: str | None,
    a: str | None,
    provincia: str | None,
) -> list[RigaTerritorio]:
    d = _espressione_data(asse)
    dove = [_clausola_validita(d)]
    parametri: list[object] = []
    filtri, par_filtri = _filtri_territorio(provincia, None)
    dove += filtri
    parametri += par_filtri
    if da:
        dove.append(f"{d} >= ?")
        parametri.append(da)
    if a:
        dove.append(f"{d} <= ?")
        parametri.append(a)

    righe = conn.execute(
        f"""
        SELECT {raggruppa_per} AS nome,
               COUNT(*)                  AS n_atti,
               COUNT(DISTINCT a.ente_id) AS n_enti,
               MIN({d})                  AS primo,
               MAX({d})                  AS ultimo
        FROM atti a JOIN enti e ON a.ente_id = e.id
        WHERE {" AND ".join(dove)}
        GROUP BY nome
        ORDER BY n_atti DESC, nome
        """,
        parametri,
    ).fetchall()
    return [
        RigaTerritorio(
            nome=r["nome"],
            n_atti=r["n_atti"],
            n_enti=r["n_enti"],
            primo=r["primo"],
            ultimo=r["ultimo"],
        )
        for r in righe
    ]


def ingestione_giornaliera(
    conn: sqlite3.Connection,
    *,
    giorni: int = 30,
    provincia: str | None = None,
    ente_id: int | None = None,
) -> list[PuntoSerie]:
    """Documenti ingeriti per giorno, con i giorni a zero esplicitati.

    I giorni senza ingestione sono restituiti con ``n_atti=0`` invece di essere
    omessi: un buco nella serie è esattamente l'informazione che interessa
    (nessun run è girato quel giorno), e un grafico che salta i giorni vuoti lo
    nasconde.
    """
    dove = ["date(a.data_accesso) >= date('now', ?)"]
    parametri: list[object] = [f"-{giorni - 1} days"]
    filtri, par_filtri = _filtri_territorio(provincia, ente_id)
    dove += filtri
    parametri += par_filtri

    righe = conn.execute(
        f"""
        SELECT date(a.data_accesso)     AS giorno,
               COUNT(*)                 AS n_atti,
               COUNT(DISTINCT a.ente_id) AS n_enti
        FROM atti a JOIN enti e ON a.ente_id = e.id
        WHERE {" AND ".join(dove)}
        GROUP BY giorno
        """,
        parametri,
    ).fetchall()
    per_giorno = {r["giorno"]: r for r in righe}

    inizio = conn.execute("SELECT date('now', ?)", (f"-{giorni - 1} days",)).fetchone()[0]
    asse_completo = [
        r[0]
        for r in conn.execute(
            """
            WITH RECURSIVE giorni(g) AS (
                SELECT ?
                UNION ALL
                SELECT date(g, '+1 day') FROM giorni WHERE g < date('now')
            )
            SELECT g FROM giorni
            """,
            (inizio,),
        ).fetchall()
    ]

    serie: list[PuntoSerie] = []
    for g in asse_completo:
        r = per_giorno.get(g)
        serie.append(
            PuntoSerie(
                periodo=g,
                inizio=g,
                n_atti=r["n_atti"] if r else 0,
                n_enti=r["n_enti"] if r else 0,
            )
        )
    return serie


def province_disponibili(conn: sqlite3.Connection) -> list[str]:
    """Province presenti in ``enti``, ordinate alfabeticamente."""
    return [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT provincia FROM enti"
            " WHERE provincia IS NOT NULL AND provincia <> ''"
            " ORDER BY provincia"
        ).fetchall()
    ]
