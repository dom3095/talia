"""Dashboard TALIA — Modulo 3: vista aggregata per comune.

Legge esclusivamente dal DB (TAL-21). Non analizza, non scrive.

Avvio:
    streamlit run src/talia/modulo3_dashboard/app.py

Variabile d'ambiente opzionale:
    TALIA_DB — percorso al file SQLite (default: talia.db nella directory corrente)
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import streamlit as st

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
}

COLORI_SEVERITA = {
    "alta": "🔴",
    "media": "🟡",
    "bassa": "🟢",
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
# Componenti UI
# ---------------------------------------------------------------------------


def _mostra_disclaimer() -> None:
    st.warning(f"⚠️ {DISCLAIMER}", icon=None)


def _badge_severita(severita: str) -> str:
    return f"{COLORI_SEVERITA.get(severita, '⚪')} {severita.capitalize()}"


def _is_piccolo_comune(popolazione: int | None) -> bool:
    return popolazione is not None and popolazione < SOGLIA_PICCOLO_COMUNE


def _mostra_panoramica(conn: sqlite3.Connection) -> None:
    st.subheader("Panoramica comuni")

    rows = _carica_flags_per_ente(conn)
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
        st.dataframe(tabella, use_container_width=True)

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
        st.info(
            f"Questo comune ha meno di {SOGLIA_PICCOLO_COMUNE:,} abitanti. "
            "I dettagli nominativi degli atti non vengono mostrati per tutelare la privacy. "
            "Sono visualizzate solo le aggregazioni.",
            icon="🔒",
        )

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


def _mostra_comuni_virtuosi(conn: sqlite3.Connection) -> None:
    rows = _carica_flags_per_ente(conn)
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
            "TALIA è open source. "
            "Ogni segnalazione è da verificare con l'atto ufficiale linkato."
        )

    # --- Tabs principali ---
    tab_panoramica, tab_comune, tab_virtuosi = st.tabs(
        ["📊 Panoramica", "🔍 Dettaglio comune", "✅ Comuni virtuosi"]
    )

    with tab_panoramica:
        _mostra_panoramica(conn)

    with tab_comune:
        enti = _carica_enti(conn)
        if not enti:
            st.info("Nessun comune nel database.")
        else:
            opzioni = {r["denominazione"]: r for r in enti}
            scelta = st.selectbox("Seleziona un comune", list(opzioni.keys()))
            if scelta:
                r = opzioni[scelta]
                _mostra_dettaglio_comune(conn, r["id"], r["denominazione"], r["popolazione"])

    with tab_virtuosi:
        _mostra_comuni_virtuosi(conn)


if __name__ == "__main__":
    main()
