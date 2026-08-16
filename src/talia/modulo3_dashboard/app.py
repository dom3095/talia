"""Dashboard TALIA — Modulo 3: vista aggregata per comune.

Legge esclusivamente dal DB (TAL-21), tranne: la tab mappa, che incrocia anche
i confini comunali e l'elenco di riferimento dei comuni siciliani (file
statici in `data/`, indispensabili per mostrare anche i comuni mai censiti
da nessuno scraper — assenti dal DB per definizione); e la tab "Analisi
fascicolo" (TAL-60), un front-end opzionale per il Modulo 1 che analizza i
file caricati dall'utente in locale, senza persistenza né scrittura sul DB.
Per il resto, non scrive mai.

Avvio:
    streamlit run src/talia/modulo3_dashboard/app.py

Variabile d'ambiente opzionale:
    TALIA_DB — percorso al file SQLite (default: talia.db nella directory corrente)
"""

from __future__ import annotations

import csv
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import pydeck as pdk
import streamlit as st

if TYPE_CHECKING:
    from talia.modulo1_fascicolo.report import Report

# ---------------------------------------------------------------------------
# Costanti
# ---------------------------------------------------------------------------

DISCLAIMER = (
    "**Segnalazioni da verificare, non accertamenti.** "
    "Gli indicatori mostrati sono ricavati automaticamente da atti pubblici "
    "tramite regole deterministiche. Nessuna segnalazione implica responsabilità "
    "penale o amministrativa. Ogni dato è linkato alla fonte ufficiale."
)

SOGLIA_PICCOLO_COMUNE = 5_000  # abitanti

ETICHETTE_TIPO_FLAG = {
    "frazionamento": "Frazionamento artificioso",
    "concentrazione_diretti": "Concentrazione affidamenti diretti",
    "tempo_pubblicazione_breve": "Finestra pubblicazione breve",
    "revoca_in_catena": "Revoca/annullamento in catena",
}

ICONE_RUOLO = {
    "avvio": "🟢",
    "modifica": "🔵",
    "proroga": "🔵",
    "aggiudicazione": "✅",
    "revoca": "🔴",
    "annullamento": "🔴",
    "altro": "⚪",
}

ETICHETTE_STATO_FINALE = {
    "in_corso": "In corso",
    "revocato": "Revocato",
    "annullato": "Annullato",
    "aggiudicato": "Aggiudicato",
    "sconosciuto": "Sconosciuto",
    "da_verificare": "Da verificare",
}

# Default "🔵" per gli stati non elencati (in_corso, sconosciuto, da_verificare).
ICONE_STATO_FINALE = {
    "revocato": "🔴",
    "annullato": "🔴",
    "aggiudicato": "✅",
}

COLORI_SEVERITA = {
    "alta": "🔴",
    "media": "🟡",
    "bassa": "🟢",
}

RADICE_REPO = Path(__file__).resolve().parents[3]
GEOJSON_COMUNI_PATH = RADICE_REPO / "data" / "comuni_sicilia_confini.geojson"
COMUNI_SICILIA_CSV_PATH = RADICE_REPO / "data" / "comuni_sicilia.csv"

# Stati "coperti" a fini di mappa/statistiche: uno scraper esiste e funziona,
# anche se escluso dal run automatico di default (es. Agrigento, Playwright lento).
STATI_COPERTI = frozenset({"attivo", "escluso_default"})

STATO_COLORI_MAPPA = {
    "attivo": [46, 139, 87, 200],
    "escluso_default": [46, 139, 87, 200],
    "pending": [245, 166, 35, 200],
    "bloccato": [178, 34, 34, 200],
    "non_censito": [190, 190, 190, 140],
}

STATO_ETICHETTE_MAPPA = {
    "attivo": "Coperto",
    "escluso_default": "Coperto (escluso dal run automatico)",
    "pending": "In verifica (pending)",
    "bloccato": "Bloccato",
    "non_censito": "Non censito",
}

# ---------------------------------------------------------------------------
# Accesso al DB
# ---------------------------------------------------------------------------


@st.cache_resource(show_spinner="Connessione al database…")
def _get_conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _carica_enti(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, denominazione, codice_istat, provincia, popolazione"
        " FROM enti ORDER BY denominazione"
    ).fetchall()


def _carica_flags_per_ente(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Aggrega i red flags per ente: conta per tipo e severità."""
    return conn.execute(
        """
        SELECT
            e.id            AS ente_id,
            e.denominazione,
            e.codice_istat,
            e.popolazione,
            e.provincia,
            COUNT(rf.id)    AS n_flags,
            SUM(CASE WHEN rf.severita = 'alta'  THEN 1 ELSE 0 END) AS n_alta,
            SUM(CASE WHEN rf.severita = 'media' THEN 1 ELSE 0 END) AS n_media,
            SUM(CASE WHEN rf.severita = 'bassa' THEN 1 ELSE 0 END) AS n_bassa
        FROM enti e
        LEFT JOIN red_flags rf ON rf.ente_id = e.id
        GROUP BY e.id
        ORDER BY n_flags DESC, e.denominazione
        """
    ).fetchall()


def _carica_flags_detail(conn: sqlite3.Connection, ente_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT rf.id, rf.tipo_flag, rf.severita, rf.descrizione,
               rf.atti_cig, rf.data_rilevazione, rf.periodo_da, rf.periodo_a
        FROM red_flags rf
        WHERE rf.ente_id = ?
        ORDER BY rf.data_rilevazione DESC
        """,
        (ente_id,),
    ).fetchall()


def _carica_statistiche_generali(conn: sqlite3.Connection) -> dict:
    tot_atti = conn.execute("SELECT COUNT(*) FROM atti").fetchone()[0]
    tot_enti_con_atti = conn.execute("SELECT COUNT(DISTINCT ente_id) FROM atti").fetchone()[0]
    atti_7g = conn.execute(
        "SELECT COUNT(*) FROM atti WHERE data_accesso >= date('now', '-7 days')"
    ).fetchone()[0]
    atti_30g = conn.execute(
        "SELECT COUNT(*) FROM atti WHERE data_accesso >= date('now', '-30 days')"
    ).fetchone()[0]
    tot_red_flags = conn.execute("SELECT COUNT(*) FROM red_flags").fetchone()[0]
    return {
        "tot_atti": tot_atti,
        "tot_enti_con_atti": tot_enti_con_atti,
        "atti_7g": atti_7g,
        "atti_30g": atti_30g,
        "tot_red_flags": tot_red_flags,
    }


def _carica_atti_per_giorno(conn: sqlite3.Connection, giorni: int = 30) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT date(data_accesso) AS giorno, COUNT(*) AS n
        FROM atti
        WHERE data_accesso >= date('now', ?)
        GROUP BY giorno
        ORDER BY giorno
        """,
        (f"-{giorni} days",),
    ).fetchall()


def _carica_atti_per_provincia(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT COALESCE(e.provincia, 'n/d') AS provincia, COUNT(a.id) AS n
        FROM atti a JOIN enti e ON a.ente_id = e.id
        GROUP BY provincia
        ORDER BY n DESC
        """
    ).fetchall()


def _carica_atti_per_tipo(conn: sqlite3.Connection, limite: int = 12) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT tipo, COUNT(*) AS n FROM atti GROUP BY tipo ORDER BY n DESC LIMIT ?",
        (limite,),
    ).fetchall()


def _carica_atti_per_fonte(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT fonte_scraper, COUNT(*) AS n FROM atti GROUP BY fonte_scraper ORDER BY n DESC"
    ).fetchall()


def _carica_atti_da_ids(conn: sqlite3.Connection, ids: list[int]) -> dict[int, sqlite3.Row]:
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT id, url_fonte, cig, oggetto, importo_euro, data_atto"
        f" FROM atti WHERE id IN ({placeholders})",
        ids,
    ).fetchall()
    return {r["id"]: r for r in rows}


# ---------------------------------------------------------------------------
# Mappa di copertura: confini comunali + registro CSV, non solo DB.
#
# Eccezione all'unica fonte-DB del modulo: i confini geografici e l'elenco
# completo dei 391 comuni siciliani (compresi quelli mai censiti da nessuno
# scraper, quindi assenti da `enti`) non possono venire dal DB per
# definizione. Lo stato di copertura per comune resta letto da
# `enti.stato_scraper`, sincronizzato dal registro ad ogni run.
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner="Carico i confini comunali…")
def _carica_geojson_comuni(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data(show_spinner=False)
def _carica_popolazione_sicilia(path: str) -> dict[str, int]:
    """Popolazione per codice ISTAT, per tutti i comuni siciliani (rif. statico)."""
    popolazione: dict[str, int] = {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                popolazione[row["codice_istat"]] = int(row["popolazione"])
            except (KeyError, ValueError):
                continue
    return popolazione


def _carica_stato_scraper_per_comune(conn: sqlite3.Connection) -> dict[str, dict]:
    rows = conn.execute(
        """
        SELECT e.codice_istat, e.stato_scraper, e.modulo,
               COUNT(a.id) AS n_atti
        FROM enti e
        LEFT JOIN atti a ON a.ente_id = e.id
        GROUP BY e.id
        """
    ).fetchall()
    return {r["codice_istat"]: dict(r) for r in rows}


def _costruisci_geojson_copertura(geojson: dict, stato_per_comune: dict[str, dict]) -> dict:
    """Ricostruisce il GeoJSON aggiungendo colore/etichetta/n_atti per feature.

    Non muta l'oggetto originale (che è cachato da Streamlit e riusato tra i run).
    """
    features = []
    for feat in geojson["features"]:
        codice = feat["properties"].get("com_istat_code")
        info = stato_per_comune.get(codice)
        stato = info["stato_scraper"] if info else "non_censito"
        n_atti = info["n_atti"] if info else 0
        proprieta = dict(feat["properties"])
        proprieta.update(
            fill_color=STATO_COLORI_MAPPA.get(stato, STATO_COLORI_MAPPA["non_censito"]),
            stato_label=STATO_ETICHETTE_MAPPA.get(stato, stato),
            n_atti=n_atti,
        )
        features.append({**feat, "properties": proprieta})
    return {"type": "FeatureCollection", "features": features}


def _calcola_copertura_popolazione(
    geojson: dict, stato_per_comune: dict[str, dict], popolazione_per_comune: dict[str, int]
) -> dict:
    tot_comuni = len(geojson["features"])
    tot_popolazione = 0
    coperti_comuni = 0
    coperti_popolazione = 0
    per_stato: dict[str, int] = {}

    for feat in geojson["features"]:
        codice = feat["properties"].get("com_istat_code")
        info = stato_per_comune.get(codice)
        stato = info["stato_scraper"] if info else "non_censito"
        pop = popolazione_per_comune.get(codice, 0)

        per_stato[stato] = per_stato.get(stato, 0) + 1
        tot_popolazione += pop
        if stato in STATI_COPERTI:
            coperti_comuni += 1
            coperti_popolazione += pop

    return {
        "tot_comuni": tot_comuni,
        "tot_popolazione": tot_popolazione,
        "coperti_comuni": coperti_comuni,
        "coperti_popolazione": coperti_popolazione,
        "per_stato": per_stato,
    }


# ---------------------------------------------------------------------------
# Componenti UI
# ---------------------------------------------------------------------------


def _mostra_disclaimer() -> None:
    st.warning(f"⚠️ {DISCLAIMER}", icon=None)


def _badge_severita(severita: str) -> str:
    return f"{COLORI_SEVERITA.get(severita, '⚪')} {severita.capitalize()}"


def _is_piccolo_comune(popolazione: int | None) -> bool:
    return popolazione is not None and popolazione < SOGLIA_PICCOLO_COMUNE


def _avviso_privacy_piccolo_comune(cosa_nascosta: str) -> None:
    """Banner privacy per i piccoli comuni: `cosa_nascosta` non viene mostrata.

    Estratto da due copie quasi identiche (`_mostra_dettaglio_comune`,
    `_mostra_procedimenti` — code review 2026-08-08) con testo/soglia già
    divergenti tra loro: un solo punto da aggiornare per la soglia o il testo
    del disclaimer, rilevante perché è proprio il meccanismo di tutela
    privacy nei piccoli comuni richiesto da CLAUDE.md.
    """
    st.info(
        f"Questo comune ha meno di {SOGLIA_PICCOLO_COMUNE:,} abitanti: {cosa_nascosta} "
        "non vengono mostrati per tutelare la privacy. Sono visualizzate solo le "
        "aggregazioni.",
        icon="🔒",
    )


def _mostra_panoramica(rows: list[sqlite3.Row]) -> None:
    st.subheader("Panoramica comuni")

    if not rows:
        st.info("Nessun dato disponibile nel database.")
        return

    virtuosi = [r for r in rows if r["n_flags"] == 0]
    con_flags = [r for r in rows if r["n_flags"] > 0]

    if con_flags:
        st.markdown("#### Comuni con segnalazioni")
        tabella = []
        for r in con_flags:
            nome = r["denominazione"]
            if _is_piccolo_comune(r["popolazione"]):
                nome = f"{nome} *(< {SOGLIA_PICCOLO_COMUNE:,} ab.)*"
            tabella.append(
                {
                    "Comune": nome,
                    "Provincia": r["provincia"] or "—",
                    "Popolazione": r["popolazione"] or "n/d",
                    "🔴 Alta": r["n_alta"],
                    "🟡 Media": r["n_media"],
                    "🟢 Bassa": r["n_bassa"],
                    "Totale flag": r["n_flags"],
                }
            )
        st.dataframe(tabella, width="stretch")

    if virtuosi:
        with st.expander(f"✅ Comuni senza segnalazioni ({len(virtuosi)})", expanded=False):
            st.markdown(
                "I seguenti comuni non presentano attualmente alcun indicatore di anomalia "
                "nel periodo analizzato."
            )
            for r in virtuosi:
                prov = f" ({r['provincia']})" if r["provincia"] else ""
                st.markdown(f"- **{r['denominazione']}**{prov}")


def _mostra_dettaglio_comune(
    conn: sqlite3.Connection, ente_id: int, denominazione: str, popolazione: int | None
) -> None:
    piccolo = _is_piccolo_comune(popolazione)

    flags = _carica_flags_detail(conn, ente_id)

    if not flags:
        st.success(f"✅ **{denominazione}** non presenta segnalazioni nel periodo analizzato.")
        return

    label_pop = f" *(< {SOGLIA_PICCOLO_COMUNE:,} ab. — drill-down anonimizzato)*" if piccolo else ""
    st.subheader(f"Segnalazioni per {denominazione}{label_pop}")

    if piccolo:
        _avviso_privacy_piccolo_comune("i dettagli nominativi degli atti")

    for flag in flags:
        tipo_label = ETICHETTE_TIPO_FLAG.get(flag["tipo_flag"], flag["tipo_flag"])
        badge = _badge_severita(flag["severita"])
        periodo = ""
        if flag["periodo_da"] and flag["periodo_a"]:
            periodo = f" | Periodo: {flag['periodo_da']} – {flag['periodo_a']}"

        with st.expander(f"{badge} — {tipo_label}{periodo}", expanded=False):
            st.markdown(f"**Descrizione:** {flag['descrizione']}")
            st.caption(f"Rilevato il: {flag['data_rilevazione'][:10]}")

            if piccolo:
                st.markdown("*Dettaglio atti non disponibile per piccoli comuni (privacy).*")
                continue

            atti_cig: list[dict] = json.loads(flag["atti_cig"] or "[]")
            if not atti_cig:
                continue

            ids = [a["id"] for a in atti_cig if "id" in a]
            atti_map = _carica_atti_da_ids(conn, ids)

            st.markdown("**Atti di riferimento:**")
            for entry in atti_cig:
                atto_id = entry.get("id")
                url = entry.get("url", "")
                atto = atti_map.get(atto_id)

                oggetto = atto["oggetto"] if atto and atto["oggetto"] else "n/d"
                cig = atto["cig"] if atto and atto["cig"] else entry.get("cig", "—")
                importo = atto["importo_euro"] if atto and atto["importo_euro"] else None
                data = atto["data_atto"] if atto and atto["data_atto"] else "—"

                dettagli = []
                if cig and cig != "—":
                    dettagli.append(f"CIG: `{cig}`")
                if importo is not None:
                    dettagli.append(f"Importo: {importo:,.2f} EUR")
                if "giorni" in entry:
                    dettagli.append(f"Giorni pubblicazione: {entry['giorni']}")
                dettagli.append(f"Data: {data}")

                dettagli_str = " | ".join(dettagli)

                if url:
                    st.markdown(f"- [{oggetto}]({url}) — {dettagli_str}")
                else:
                    st.markdown(f"- {oggetto} — {dettagli_str}")


def _carica_procedimenti_per_ente(conn: sqlite3.Connection, ente_id: int) -> list[sqlite3.Row]:
    try:
        return conn.execute(
            """
            SELECT p.id, p.tipo, p.cig, p.oggetto, p.data_avvio, p.data_chiusura,
                   p.stato_finale, p.metodo_individuazione,
                   COUNT(a.id) AS n_atti
            FROM   procedimenti p
            LEFT   JOIN atti a ON a.procedimento_id = p.id
            WHERE  p.ente_id = ?
            GROUP  BY p.id
            ORDER  BY p.data_avvio DESC NULLS LAST
            """,
            (ente_id,),
        ).fetchall()
    except Exception:
        return []


def _carica_atti_procedimento(conn: sqlite3.Connection, procedimento_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT id, tipo, numero, oggetto, data_atto, url_fonte,
               ruolo_in_catena, cig, importo_euro
        FROM   atti
        WHERE  procedimento_id = ?
        ORDER  BY data_atto ASC NULLS LAST
        """,
        (procedimento_id,),
    ).fetchall()


def _mostra_procedimenti(conn: sqlite3.Connection, enti: list[sqlite3.Row]) -> None:
    st.subheader("Catene di eventi per comune")
    st.markdown(
        "Un **procedimento** raggruppa gli atti amministrativi collegati "
        "(bando → modifiche → revoca/aggiudicazione). "
        "Le catene individuate via similarità oggetto richiedono verifica manuale."
    )

    if not enti:
        st.info("Nessun comune nel database.")
        return

    opzioni = {r["denominazione"]: r for r in enti}
    scelta = st.selectbox("Seleziona un comune", list(opzioni.keys()), key="proc_comune")
    if not scelta:
        return

    r = opzioni[scelta]
    procedimenti = _carica_procedimenti_per_ente(conn, r["id"])

    if not procedimenti:
        st.info(
            "Nessun procedimento individuato per questo comune. "
            "Esegui prima il batch di ricostruzione catene."
        )
        return

    piccolo = _is_piccolo_comune(r["popolazione"])
    if piccolo:
        _avviso_privacy_piccolo_comune("i dettagli nominativi")

    for proc in procedimenti:
        stato = proc["stato_finale"] or "sconosciuto"
        etichetta_stato = ETICHETTE_STATO_FINALE.get(stato, stato)
        icona_stato = ICONE_STATO_FINALE.get(stato, "🔵")
        metodo = proc["metodo_individuazione"] or "n/d"
        cig_label = f" | CIG: `{proc['cig']}`" if proc["cig"] else ""
        periodo = ""
        if proc["data_avvio"]:
            periodo = f" | {proc['data_avvio'][:10]}"
            if proc["data_chiusura"]:
                periodo += f" → {proc['data_chiusura'][:10]}"

        titolo = f"{icona_stato} {etichetta_stato}{cig_label}{periodo} — {proc['n_atti']} atti"

        with st.expander(titolo, expanded=(stato in ("revocato", "annullato"))):
            oggetto = proc["oggetto"] or "n/d"
            st.markdown(f"**Oggetto:** {oggetto if not piccolo else '*(anonimizzato)*'}")
            st.caption(f"Metodo individuazione: {metodo}")

            if piccolo:
                st.markdown("*Timeline atti non disponibile per piccoli comuni (privacy).*")
                continue

            atti = _carica_atti_procedimento(conn, proc["id"])
            if not atti:
                st.markdown("*Nessun atto collegato.*")
                continue

            st.markdown("**Timeline:**")
            for atto in atti:
                ruolo = atto["ruolo_in_catena"] or "altro"
                icona = ICONE_RUOLO.get(ruolo, "⚪")
                data = atto["data_atto"][:10] if atto["data_atto"] else "data n/d"
                desc = atto["oggetto"] or atto["tipo"] or "n/d"
                url = atto["url_fonte"]
                link = f"[{desc}]({url})" if url else desc
                importo = f" — {atto['importo_euro']:,.0f} EUR" if atto["importo_euro"] else ""
                st.markdown(f"- {icona} **{data}** `{ruolo}` {link}{importo}")

            if stato in ("revocato", "annullato"):
                st.warning(
                    "⚠️ Procedimento terminato con revoca/annullamento. "
                    "Segnalazione da verificare con l'atto ufficiale.",
                    icon=None,
                )


def _mostra_comuni_virtuosi(rows: list[sqlite3.Row]) -> None:
    virtuosi = [r for r in rows if r["n_flags"] == 0]

    st.subheader("Comuni virtuosi")
    st.markdown(
        "I comuni elencati non presentano alcun indicatore di anomalia nel periodo analizzato. "
        "La dashboard non è una gogna: la trasparenza include il riconoscimento"
        " delle buone pratiche."
    )

    if not virtuosi:
        st.info("Nessun comune senza segnalazioni (o nessun dato nel database).")
        return

    cols = st.columns(3)
    for i, r in enumerate(virtuosi):
        prov = f", {r['provincia']}" if r["provincia"] else ""
        cols[i % 3].success(f"✅ {r['denominazione']}{prov}")


def _mostra_statistiche(conn: sqlite3.Connection) -> None:
    st.subheader("Statistiche di ingestione")

    stats = _carica_statistiche_generali(conn)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Atti totali", f"{stats['tot_atti']:,}")
    col2.metric("Comuni con atti", stats["tot_enti_con_atti"])
    col3.metric("Atti ultimi 7 giorni", f"{stats['atti_7g']:,}")
    col4.metric("Atti ultimi 30 giorni", f"{stats['atti_30g']:,}")

    st.markdown("#### Atti ingeriti per giorno")
    giorni = st.slider("Finestra temporale (giorni)", min_value=7, max_value=90, value=30, step=1)
    trend = _carica_atti_per_giorno(conn, giorni)
    if trend:
        st.bar_chart({r["giorno"]: r["n"] for r in trend})
    else:
        st.info(f"Nessun atto ingerito negli ultimi {giorni} giorni.")

    col_prov, col_tipo = st.columns(2)
    with col_prov:
        st.markdown("#### Atti per provincia")
        per_provincia = _carica_atti_per_provincia(conn)
        if per_provincia:
            st.dataframe(
                [{"Provincia": r["provincia"], "Atti": r["n"]} for r in per_provincia],
                width="stretch",
                hide_index=True,
            )

    with col_tipo:
        st.markdown("#### Atti per tipo (top 12)")
        per_tipo = _carica_atti_per_tipo(conn)
        if per_tipo:
            st.dataframe(
                [{"Tipo": r["tipo"], "Atti": r["n"]} for r in per_tipo],
                width="stretch",
                hide_index=True,
            )

    st.markdown("#### Atti per piattaforma scraper")
    per_fonte = _carica_atti_per_fonte(conn)
    if per_fonte:
        st.dataframe(
            [{"Scraper": r["fonte_scraper"], "Atti": r["n"]} for r in per_fonte],
            width="stretch",
            hide_index=True,
        )

    st.caption(f"Red flags totali nel database: {stats['tot_red_flags']:,}")


def _mostra_mappa(conn: sqlite3.Connection) -> None:
    st.subheader("Copertura scraper — comuni siciliani")
    st.markdown(
        "Colore per stato dello scraper nel registro. Il perimetro colorato indica solo "
        "se TALIA raccoglie atti da quel comune, non la qualità o completezza dei dati."
    )

    if not GEOJSON_COMUNI_PATH.exists():
        st.warning(f"File dei confini comunali non trovato: `{GEOJSON_COMUNI_PATH}`")
        return

    geojson = _carica_geojson_comuni(str(GEOJSON_COMUNI_PATH))
    stato_per_comune = _carica_stato_scraper_per_comune(conn)
    popolazione_per_comune = _carica_popolazione_sicilia(str(COMUNI_SICILIA_CSV_PATH))
    copertura = _calcola_copertura_popolazione(geojson, stato_per_comune, popolazione_per_comune)

    perc_comuni = 100 * copertura["coperti_comuni"] / copertura["tot_comuni"]
    perc_pop = (
        100 * copertura["coperti_popolazione"] / copertura["tot_popolazione"]
        if copertura["tot_popolazione"]
        else 0
    )
    col1, col2, col3, col4 = st.columns(4)
    col1.metric(
        "🟢 Comuni coperti",
        copertura["coperti_comuni"],
        f"{perc_comuni:.0f}% del totale",
    )
    col2.metric("🟠 In verifica", copertura["per_stato"].get("pending", 0))
    col3.metric("🔴 Bloccati", copertura["per_stato"].get("bloccato", 0))
    col4.metric(
        "Popolazione coperta",
        f"{perc_pop:.0f}%",
        f"{copertura['coperti_popolazione']:,} / {copertura['tot_popolazione']:,} ab.",
    )

    geojson_colorato = _costruisci_geojson_copertura(geojson, stato_per_comune)
    layer = pdk.Layer(
        "GeoJsonLayer",
        data=geojson_colorato,
        get_fill_color="properties.fill_color",
        get_line_color=[90, 90, 90],
        line_width_min_pixels=0.5,
        pickable=True,
        auto_highlight=True,
    )
    view_state = pdk.ViewState(latitude=37.6, longitude=14.15, zoom=6.6, pitch=0)
    deck = pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        map_provider="carto",
        map_style="light",
        tooltip={"text": "{name}\nStato: {stato_label}\nAtti raccolti: {n_atti}"},
    )
    st.pydeck_chart(deck, width="stretch")

    st.caption(
        "🟢 Coperto (scraper attivo) · 🟠 In verifica (pending) · "
        "🔴 Bloccato (problema noto, vedi CLAUDE.md) · ⚪ Non censito (nessuno scraper)"
    )


# ---------------------------------------------------------------------------
# Tab "Analisi fascicolo" (Modulo 1, TAL-60)
# ---------------------------------------------------------------------------
#
# Unica tab che *analizza* invece di leggere solo dal DB (vedi eccezione nel
# docstring di modulo). Nessuna scrittura né persistenza: i file caricati
# vivono in una directory temporanea cancellata subito dopo l'estrazione del
# testo (principio 4 CLAUDE.md — i fascicoli reali contengono nominativi).
# Riusa `analizza_testi`, lo stesso motore della CLI `talia analizza`: questa
# tab è un front-end alternativo, non una reimplementazione (TAL-10 aveva
# scartato Streamlit per il *formato del report*, che resta HTML/JSON a zero
# dipendenze; qui Streamlit è già una dipendenza del Modulo 3, quindi il
# ragionamento "zero deps" non si applica a un front-end interattivo opzionale).

_ESTENSIONI_ANALISI = {".pdf", ".txt"}
_FORM_FEED_ANALISI = "\f"


def _analizza_file_caricati(
    documenti: list[tuple[str, bytes, str | None]], *, valuta_llm: bool
) -> Report:
    """Estrae il testo dai documenti caricati e produce il `Report` del Modulo 1.

    Isolata da qualunque widget Streamlit (prende nome+bytes+descrizione, non
    `UploadedFile`) per essere testabile senza `AppTest`. La descrizione
    (TAL-60) sono le osservazioni scritte dall'utente per quel documento nel
    box di upload: passate a `analizza_testi` per concorrere alla
    classificazione del ruolo e comparire nel report.
    """
    from talia.engine.models import FonteTesto
    from talia.engine.pdf_text import da_pagine, estrai_testo
    from talia.modulo1_fascicolo.analisi import analizza_testi

    testi = []
    descrizioni: list[str | None] = []
    with tempfile.TemporaryDirectory() as tmp:
        for nome, contenuto, descrizione in documenti:
            suffisso = Path(nome).suffix.lower()
            if suffisso == ".pdf":
                percorso = Path(tmp) / nome
                percorso.write_bytes(contenuto)
                testi.append(estrai_testo(percorso))
            else:  # .txt, unico altro tipo ammesso dal file_uploader
                testo = contenuto.decode("utf-8")
                pagine = testo.split(_FORM_FEED_ANALISI) if _FORM_FEED_ANALISI in testo else [testo]
                testi.append(da_pagine(pagine, fonte=FonteTesto.NATIVO, percorso=nome))
            descrizioni.append(descrizione or None)

    return analizza_testi(testi, descrizioni=descrizioni, valuta_llm=valuta_llm)


def _mostra_report_fascicolo(report: Report) -> None:
    from talia.modulo1_fascicolo.report import descrivi_citazione

    c = report.conteggio
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🟢 Verde", c["verde"])
    col2.metric("🟡 Giallo", c["giallo"])
    col3.metric("🔴 Rosso", c["rosso"])
    col4.metric("⚪ N/A", c["non_applicabile"])

    if report.atti:
        st.markdown("**Atti analizzati:**")
        for a in report.atti:
            riga = f"- **{a.etichetta}** — {a.ruolo}"
            if a.descrizione:
                riga += f" — _{a.descrizione}_"
            st.markdown(riga)

    for esito in report.esiti:
        aperto_default = esito.stato.value in ("giallo", "rosso")
        with st.expander(f"{esito.stato.emoji} {esito.titolo}", expanded=aperto_default):
            st.markdown(esito.spiegazione)
            if esito.riferimenti_normativi:
                st.caption("Riferimenti: " + "; ".join(esito.riferimenti_normativi))
            for cit in esito.citazioni:
                st.markdown(f"> {descrivi_citazione(cit)}")

    st.download_button(
        "⬇️ Scarica report (HTML)",
        data=report.to_html(),
        file_name="report_talia.html",
        mime="text/html",
    )
    st.caption(f"⚠️ {report.disclaimer}")


def _raccogli_box_fascicolo() -> list[tuple]:
    """Renderizza la catena di box "allega file + descrizione" (TAL-60).

    Un box per documento: appena si carica il file nel box N, compare il box
    N+1 (vuoto), così si compone un fascicolo da 1 a N atti senza un bottone
    "+" esplicito. Le chiavi dei widget sono stabili per indice (`tal60_file_
    {i}`/`tal60_desc_{i}`): Streamlit conserva il loro valore in
    `st.session_state` tra un rerun e l'altro, quindi al giro successivo si sa
    già quanti box mostrare senza dover ricalcolare nulla di esplicito.
    """
    documenti = []
    i = 0
    while True:
        with st.container(border=True):
            st.caption(f"Documento {i + 1}")
            col_file, col_desc = st.columns([2, 3])
            file = col_file.file_uploader(
                "Allega file",
                type=["pdf", "txt"],
                key=f"tal60_file_{i}",
                label_visibility="collapsed",
            )
            descrizione = col_desc.text_input(
                "Descrizione/osservazioni",
                key=f"tal60_desc_{i}",
                placeholder='Descrizione/osservazioni (opzionale) — es. "bando originario", '
                '"revoca in autotutela"…',
                label_visibility="collapsed",
            )
        if file is None:
            break
        documenti.append((file, descrizione))
        i += 1
    return documenti


def _mostra_analisi_fascicolo() -> None:
    st.subheader("Analizza un fascicolo")
    st.caption(
        "Allega gli atti di un fascicolo uno alla volta (indizione, bando, "
        "revoca/annullamento…) per ricostruire la catena: dopo ogni file compare il box "
        "successivo. PDF nativi o scansionati, oppure .txt. La descrizione è facoltativa "
        "ma aiuta a classificare correttamente il ruolo di ogni atto quando il testo da "
        "solo è ambiguo. L'analisi gira in locale — i file caricati non vengono salvati "
        "né inviati altrove."
    )

    documenti = _raccogli_box_fascicolo()

    usa_llm = st.checkbox(
        "Includi check 3 — qualità motivazione (LLM)",
        value=False,
        help="Richiede Ollama in esecuzione in locale (`ollama serve`). Più lento (minuti).",
    )

    if documenti and st.button("Analizza", type="primary"):
        with st.spinner("Analisi in corso…"):
            try:
                report = _analizza_file_caricati(
                    [(f.name, f.getvalue(), d) for f, d in documenti], valuta_llm=usa_llm
                )
            except Exception as exc:  # estrazione PDF/LLM: mostrato, non un crash dell'app
                st.error(f"Errore durante l'analisi: {exc}")
                st.session_state.pop("report_modulo1", None)
            else:
                st.session_state["report_modulo1"] = report

    report = st.session_state.get("report_modulo1")
    if report is not None:
        st.divider()
        _mostra_report_fascicolo(report)
    elif not documenti:
        st.info("Allega almeno un documento per avviare l'analisi.")


# ---------------------------------------------------------------------------
# App principale
# ---------------------------------------------------------------------------


def main() -> None:
    st.set_page_config(
        page_title="TALIA — Trasparenza Atti Locali",
        page_icon="🏛️",
        layout="wide",
        menu_items={"About": "TALIA è un progetto civico open source. Nessun dato implica accuse."},
    )

    st.title("🏛️ TALIA — Trasparenza Atti Locali")
    _mostra_disclaimer()

    # --- Sidebar: configurazione DB ---
    with st.sidebar:
        st.header("Configurazione")
        default_db = os.environ.get("TALIA_DB", "talia.db")
        db_path = st.text_input("Percorso database SQLite", value=default_db)

        if not Path(db_path).exists():
            st.error(f"Database non trovato: `{db_path}`")
            st.stop()

        conn = _get_conn(db_path)

        st.divider()
        st.caption(
            "TALIA è open source. Ogni segnalazione è da verificare con l'atto ufficiale linkato."
        )

    # --- Tabs principali ---
    (
        tab_analisi,
        tab_panoramica,
        tab_comune,
        tab_procedimenti,
        tab_virtuosi,
        tab_statistiche,
        tab_mappa,
    ) = st.tabs(
        [
            "📁 Analisi fascicolo",
            "📊 Panoramica",
            "🔍 Dettaglio comune",
            "⛓️ Procedimenti",
            "✅ Comuni virtuosi",
            "📈 Statistiche",
            "🗺️ Mappa copertura",
        ]
    )

    with tab_analisi:
        _mostra_analisi_fascicolo()

    # Caricate una volta e condivise tra i tab che ne hanno bisogno (code
    # review 2026-08-08): _carica_enti/_carica_flags_per_ente venivano prima
    # richiamate indipendentemente da due tab ciascuna, riemettendo la stessa
    # query ad ogni rerun di Streamlit (lo script gira per intero ad ogni
    # interazione con un widget qualsiasi).
    enti = _carica_enti(conn)
    flags_per_ente = _carica_flags_per_ente(conn)

    with tab_panoramica:
        _mostra_panoramica(flags_per_ente)

    with tab_comune:
        if not enti:
            st.info("Nessun comune nel database.")
        else:
            opzioni = {r["denominazione"]: r for r in enti}
            scelta = st.selectbox("Seleziona un comune", list(opzioni.keys()))
            if scelta:
                r = opzioni[scelta]
                _mostra_dettaglio_comune(conn, r["id"], r["denominazione"], r["popolazione"])

    with tab_procedimenti:
        _mostra_procedimenti(conn, enti)

    with tab_virtuosi:
        _mostra_comuni_virtuosi(flags_per_ente)

    with tab_statistiche:
        _mostra_statistiche(conn)

    with tab_mappa:
        _mostra_mappa(conn)


if __name__ == "__main__":
    main()
