"""Test della diagnosi dei red flag di frazionamento (TAL-73).

I flag sono prodotti dalla regola vera (`rileva_frazionamento` + salvataggio
del runner) su atti sintetici costruiti per ricadere ciascuno sotto una
ipotesi di falso positivo, più un caso che deve resistere a tutte.
"""

from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

import pytest

from talia.modulo2_scraping.db import (
    AttoMetadato,
    EnteMetadato,
    connetti,
    inizializza_db,
    inserisci_atto,
    salva_red_flag,
    upsert_ente,
)
from talia.modulo2_scraping.red_flags.diagnosi_frazionamento import (
    campiona,
    carica_flag,
    diagnostica,
    formatta_diagnosi,
    righe_csv,
)
from talia.modulo2_scraping.red_flags.frazionamento import rileva_frazionamento
from talia.modulo2_scraping.red_flags.runner import _salva_frazionamento

_ROOT = Path(__file__).resolve().parents[2]

_ENTI = {
    "eterogeneo": "000001",
    "cig_doppio": "000002",
    "misto": "000003",
    "omogeneo": "000004",
}


def _atto(ente, n, *, oggetto, importo, data, cig=None, fonte="halley", tipo_appalto=None):
    return AttoMetadato(
        ente_codice_istat=_ENTI[ente],
        tipo="contratto_anac" if fonte == "anac" else "determina",
        url_fonte=f"https://{ente}.example.it/{fonte}/{n}",
        fonte_scraper=fonte,
        data_accesso="2026-10-19T03:30:00",
        data_atto=data,
        oggetto=oggetto,
        importo_euro=importo,
        cig=cig,
        numero=str(n),
        metadati={"tipo_appalto": tipo_appalto} if tipo_appalto else {},
    )


@pytest.fixture()
def conn():
    c = connetti(":memory:")
    inizializza_db(c)
    for nome, istat in _ENTI.items():
        upsert_ente(c, EnteMetadato(denominazione=nome, codice_istat=istat))

    # Tre affidamenti SmartCIG senza nulla in comune: il rumore tipico.
    for n, ogg in enumerate(["cancelleria uffici", "manutenzione strade", "refezione scolastica"]):
        inserisci_atto(
            c,
            _atto("eterogeneo", n, oggetto=ogg, importo=60_000, data=f"2026-03-0{n + 1}",
                  cig=f"E00000000{n}", fonte="anac", tipo_appalto="SERVIZI"),
        )  # fmt: skip

    # La stessa gara contata due volte (contratto ANAC + determina d'albo).
    for n, (ogg, importo, data, cig, fonte) in enumerate(
        [
            ("pulizia immobili comunali sede", 60_000, "2026-03-01", "D000000001", "anac"),
            ("pulizia immobili comunali sede", 60_000, "2026-03-05", "D000000001", "halley"),
            ("pulizia immobili comunali palestra", 30_000, "2026-03-10", "D000000002", "halley"),
        ]
    ):
        inserisci_atto(
            c, _atto("cig_doppio", n, oggetto=ogg, importo=importo, data=data, cig=cig, fonte=fonte)
        )

    # Lavori e forniture nella stessa finestra.
    for n, (tipo, ogg) in enumerate(
        [("LAVORI", "rifacimento manto stradale via roma"),
         ("FORNITURE", "rifacimento manto stradale via roma"),
         ("LAVORI", "rifacimento manto stradale via roma")]
    ):  # fmt: skip
        inserisci_atto(
            c,
            _atto("misto", n, oggetto=ogg, importo=55_000, data=f"2026-04-0{n + 1}",
                  cig=f"M00000000{n}", fonte="anac", tipo_appalto=tipo),
        )  # fmt: skip

    # Il caso che una revisione umana vorrebbe vedere: stesso oggetto, spezzato.
    for n in range(3):
        inserisci_atto(
            c,
            _atto("omogeneo", n, oggetto="manutenzione verde pubblico villa comunale lotto",
                  importo=50_000, data=f"2026-05-0{n + 1}", cig=f"V00000000{n}"),
        )  # fmt: skip

    for rf in rileva_frazionamento(c):
        _salva_frazionamento(c, rf)
    return c


def _per_ente(flags):
    return {f.ente: f for f in flags}


def test_ogni_scenario_produce_un_flag(conn):
    assert set(_per_ente(carica_flag(conn))) == set(_ENTI)


def test_proprieta_dei_flag(conn):
    f = _per_ente(carica_flag(conn))
    assert f["eterogeneo"].strato == "solo_anac"
    assert f["eterogeneo"].gruppo_omogeneo_max < 3

    assert f["cig_doppio"].strato == "misto"
    assert f["cig_doppio"].cig_ripetuti
    assert f["cig_doppio"].totale_dedup_cig == 90_000

    assert f["misto"].tipi_appalto_misti

    omo = f["omogeneo"]
    assert omo.strato == "solo_albo"
    assert omo.gruppo_omogeneo_max == 3
    assert not (omo.cig_ripetuti or omo.tipi_appalto_misti)


def test_diagnosi_conta_le_ipotesi_e_i_superstiti(conn):
    d = diagnostica(carica_flag(conn))
    assert d.n_flag == 4
    conteggi = {k.split(" (")[0]: v for k, v in d.ipotesi.items()}
    assert conteggi["stesso CIG contato più volte"] == 1
    assert conteggi["tipi di appalto mescolati"] == 1
    assert conteggi["oggetti eterogenei"] == 1
    # Solo il caso omogeneo resiste a tutte le ipotesi.
    assert d.superstiti == 1


def test_flag_superato_e_contenuto(conn):
    """Finestra che si allunga a ogni run: il flag vecchio resta in tabella."""
    ente_id = conn.execute("SELECT id FROM enti WHERE codice_istat='000004'").fetchone()[0]
    ids = [
        r[0] for r in conn.execute("SELECT id FROM atti WHERE ente_id=? ORDER BY id", (ente_id,))
    ]
    salva_red_flag(
        conn, ente_id=ente_id, tipo_flag="frazionamento", severita="alta", descrizione="vecchio",
        atti_cig=[{"id": i} for i in ids[:2]], periodo_da="2026-05-01", periodo_a="2026-05-02",
    )  # fmt: skip
    d = diagnostica(carica_flag(conn))
    assert d.ipotesi["superato da un flag più recente con la stessa ancora"] == 1
    assert d.ipotesi["atti tutti contenuti in un altro flag dello stesso ente"] == 1


def test_campione_stratificato_e_riproducibile(conn):
    flags = carica_flag(conn)
    a = [f.id for f in campiona(flags, per_strato=1, seme=1)]
    b = [f.id for f in campiona(flags, per_strato=1, seme=1)]
    assert a == b
    assert len(a) == 3  # uno per strato


def test_righe_csv_da_compilare(conn):
    righe = righe_csv(carica_flag(conn))
    assert all(r["esito"] == "" for r in righe)
    assert any("https://" in r["atti"] for r in righe)


def test_formatta_diagnosi(conn):
    md = formatta_diagnosi(diagnostica(carica_flag(conn)))
    assert "Resistono a tutte le ipotesi: 1 flag" in md


def test_script_scrive_diagnosi_e_campione(conn, tmp_path, monkeypatch):
    db = tmp_path / "t.db"
    conn.execute(f"VACUUM INTO '{db}'")
    spec = importlib.util.spec_from_file_location(
        "diagnosi_frazionamento_script", _ROOT / "scripts" / "diagnosi_frazionamento.py"
    )
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    out = tmp_path / "out"
    monkeypatch.setattr(sys, "argv", ["x", "--db", str(db), "--output-dir", str(out)])

    assert modulo.main() == 0
    assert "Ipotesi di falso positivo" in (out / "diagnosi.md").read_text()
    with (out / "campione.csv").open() as fh:
        assert len(list(csv.DictReader(fh))) == 4
