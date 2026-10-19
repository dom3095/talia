"""Fase Amministrazione Trasparente del run notturno (TAL-62). Nessuna rete."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from talia.modulo2_scraping.db import (
    AttoMetadato,
    EnteMetadato,
    connetti,
    inizializza_db,
    inserisci_atto,
    upsert_ente,
)
from talia.modulo2_scraping.fonti import jcitygov
from talia.modulo2_scraping.registry import EntryRegistro

_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def rs():
    spec = importlib.util.spec_from_file_location(
        "run_scrapers_trasparenza_test", _ROOT / "scripts" / "run_scrapers.py"
    )
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _entry(slug, istat):
    return EntryRegistro(
        slug=slug,
        denominazione=f"Comune di {slug}",
        codice_istat=istat,
        modulo="jcitygov",
        piattaforma_tecnica="jCityGov/Liferay",
        base_url=f"https://{slug}.example.it",
    )


def _atto(istat, n, fonte):
    return AttoMetadato(
        ente_codice_istat=istat,
        tipo="bando",
        url_fonte=f"https://x.example.it/-/papca/display/{n}",
        fonte_scraper=fonte,
        data_accesso="2026-10-19T03:30:00",
    )


def test_fase_trasparenza_dedup_e_comune_rotto(rs, monkeypatch):
    conn = connetti(":memory:")
    inizializza_db(conn)
    for istat in ("088001", "088009"):
        upsert_ente(conn, EnteMetadato(denominazione=istat, codice_istat=istat))
    # Atto già raccolto dall'Albo Pretorio: in AT ha lo stesso URL.
    inserisci_atto(conn, _atto("088009", 1, "jcitygov"))

    def _finto(base_url, codice_istat, **_kwargs):
        if "acate" in base_url:
            raise TimeoutError("The read operation timed out")
        yield _atto(codice_istat, 1, "jcitygov_trasparenza")
        yield _atto(codice_istat, 2, "jcitygov_trasparenza")

    monkeypatch.setattr(jcitygov, "scarica_atti_trasparenza", _finto)

    tot = rs.esegui_trasparenza(conn, [_entry("acate", "088001"), _entry("ragusa", "088009")])

    assert tot == {"comuni": 2, "letti": 2, "nuovi": 1, "errori": 1}
    assert conn.execute("SELECT COUNT(*) FROM atti").fetchone()[0] == 2
    # L'atto d'albo ora ha anche la fonte AT, senza una riga doppia in `atti`.
    fonti = conn.execute(
        "SELECT fonte_scraper FROM atti_fonti WHERE url_fonte LIKE '%/1' ORDER BY 1"
    ).fetchall()
    assert [f[0] for f in fonti] == ["jcitygov", "jcitygov_trasparenza"]
