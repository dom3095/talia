"""Test offline per lo spider iCity (TAL-20).

Nessuna chiamata di rete — tutte le fixture sono file HTML locali.
Nessun PDF committato.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from talia.modulo2_scraping.db import (
    AttoMetadato,
    EnteMetadato,
    connetti,
    inizializza_db,
    upsert_ente,
)
from talia.modulo2_scraping.fonti.icity import (
    FONTE_SCRAPER,
    _data_iso,
    _estrai_cig,
    _estrai_importo,
    _parse_dettaglio,
    _parse_lista,
    salva_atti,
    scarica_atti,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Fixtures pytest
# ---------------------------------------------------------------------------


@pytest.fixture()
def html_lista() -> str:
    return (FIXTURES / "icity_lista.html").read_text(encoding="utf-8")


@pytest.fixture()
def html_dettaglio() -> str:
    return (FIXTURES / "icity_dettaglio.html").read_text(encoding="utf-8")


@pytest.fixture()
def db():
    conn = connetti(":memory:")
    inizializza_db(conn)
    upsert_ente(
        conn,
        EnteMetadato(
            denominazione="Comune di Palermo",
            codice_istat="082053",
            provincia="PA",
        ),
    )
    return conn


# ---------------------------------------------------------------------------
# Utilità
# ---------------------------------------------------------------------------


def test_data_iso_formato_italiano() -> None:
    assert _data_iso("15/01/2024") == "2024-01-15"


def test_data_iso_giorno_singolo() -> None:
    assert _data_iso("01/06/2023") == "2023-06-01"


def test_data_iso_none() -> None:
    assert _data_iso(None) is None
    assert _data_iso("") is None


def test_data_iso_passthrough_iso() -> None:
    assert _data_iso("2024-01-15") == "2024-01-15"  # già ISO → pass-through


def test_data_iso_formato_invalido() -> None:
    assert _data_iso("not-a-date") is None


def test_estrai_cig_trovato() -> None:
    testo = "Affidamento servizi CIG A12345678B importo € 4.999,00"
    assert _estrai_cig(testo) == "A12345678B"


def test_estrai_cig_con_separatore() -> None:
    testo = "CIG: B98765432C — manutenzione strade"
    assert _estrai_cig(testo) == "B98765432C"


def test_estrai_cig_assente() -> None:
    assert _estrai_cig("Nessun cig qui") is None
    assert _estrai_cig(None) is None


def test_estrai_importo_trovato() -> None:
    assert _estrai_importo("importo € 4.999,00") == 4999.0


def test_estrai_importo_grande() -> None:
    assert _estrai_importo("base d'asta € 120.000,00") == 120000.0


def test_estrai_importo_assente() -> None:
    assert _estrai_importo("nessun importo") is None
    assert _estrai_importo(None) is None


# ---------------------------------------------------------------------------
# _parse_lista
# ---------------------------------------------------------------------------


def test_parse_lista_numero_righe(html_lista: str) -> None:
    base = "https://comune.palermo.it"
    righe = _parse_lista(html_lista, base)
    assert len(righe) == 3


def test_parse_lista_url_dettaglio(html_lista: str) -> None:
    righe = _parse_lista(html_lista, "https://comune.palermo.it")
    assert righe[0]["url_dettaglio"] == "https://comune.palermo.it/icity/albo/detail.do?id=11001"
    assert righe[1]["url_dettaglio"] == "https://comune.palermo.it/icity/albo/detail.do?id=11002"


def test_parse_lista_numero(html_lista: str) -> None:
    righe = _parse_lista(html_lista, "https://comune.palermo.it")
    assert righe[0]["numero"] == "2024-0001"


def test_parse_lista_tipo(html_lista: str) -> None:
    righe = _parse_lista(html_lista, "https://comune.palermo.it")
    assert righe[0]["tipo"] == "Determina"
    assert righe[1]["tipo"] == "Delibera"


def test_parse_lista_date_raw(html_lista: str) -> None:
    righe = _parse_lista(html_lista, "https://comune.palermo.it")
    assert righe[0]["data_pub_raw"] == "15/01/2024"
    assert righe[0]["data_scad_raw"] == "15/02/2024"


def test_parse_lista_oggetto_contiene_cig(html_lista: str) -> None:
    righe = _parse_lista(html_lista, "https://comune.palermo.it")
    assert "A12345678B" in (righe[0]["oggetto"] or "")


def test_parse_lista_html_vuoto() -> None:
    assert _parse_lista("<html><body></body></html>", "https://x.it") == []


# ---------------------------------------------------------------------------
# _parse_dettaglio
# ---------------------------------------------------------------------------


def test_parse_dettaglio_tipo(html_dettaglio: str) -> None:
    atto = _parse_dettaglio(html_dettaglio, "https://comune.palermo.it/icity/albo/detail.do?id=11001", "082053")
    assert atto.tipo == "determina"


def test_parse_dettaglio_numero(html_dettaglio: str) -> None:
    atto = _parse_dettaglio(html_dettaglio, "https://comune.palermo.it/icity/albo/detail.do?id=11001", "082053")
    assert atto.numero == "2024-0001"


def test_parse_dettaglio_date_iso(html_dettaglio: str) -> None:
    atto = _parse_dettaglio(html_dettaglio, "https://comune.palermo.it/icity/albo/detail.do?id=11001", "082053")
    assert atto.data_atto == "2024-01-12"
    assert atto.data_pub == "2024-01-15"
    assert atto.data_scadenza == "2024-02-15"


def test_parse_dettaglio_cig(html_dettaglio: str) -> None:
    atto = _parse_dettaglio(html_dettaglio, "https://comune.palermo.it/icity/albo/detail.do?id=11001", "082053")
    assert atto.cig == "A12345678B"


def test_parse_dettaglio_importo(html_dettaglio: str) -> None:
    atto = _parse_dettaglio(html_dettaglio, "https://comune.palermo.it/icity/albo/detail.do?id=11001", "082053")
    assert atto.importo_euro == 4999.0


def test_parse_dettaglio_url_pdf(html_dettaglio: str) -> None:
    atto = _parse_dettaglio(html_dettaglio, "https://comune.palermo.it/icity/albo/detail.do?id=11001", "082053")
    assert atto.url_pdf is not None
    assert "getDoc" in atto.url_pdf


def test_parse_dettaglio_fonte_scraper(html_dettaglio: str) -> None:
    atto = _parse_dettaglio(html_dettaglio, "https://comune.palermo.it/icity/albo/detail.do?id=11001", "082053")
    assert atto.fonte_scraper == FONTE_SCRAPER


def test_parse_dettaglio_url_fonte(html_dettaglio: str) -> None:
    url = "https://comune.palermo.it/icity/albo/detail.do?id=11001"
    atto = _parse_dettaglio(html_dettaglio, url, "082053")
    assert atto.url_fonte == url


def test_parse_dettaglio_ente(html_dettaglio: str) -> None:
    atto = _parse_dettaglio(html_dettaglio, "https://x.it/det", "082053")
    assert atto.ente_codice_istat == "082053"


# ---------------------------------------------------------------------------
# salva_atti
# ---------------------------------------------------------------------------


def test_salva_atti_inserimento(db, html_dettaglio: str) -> None:
    url = "https://comune.palermo.it/icity/albo/detail.do?id=11001"
    atto = _parse_dettaglio(html_dettaglio, url, "082053")
    esito = salva_atti([atto], db)
    assert esito["inseriti"] == 1
    assert esito["duplicati"] == 0


def test_salva_atti_idempotente(db, html_dettaglio: str) -> None:
    """Secondo salvataggio dello stesso atto (stessa url_fonte) → duplicato."""
    url = "https://comune.palermo.it/icity/albo/detail.do?id=11001"
    atto = _parse_dettaglio(html_dettaglio, url, "082053")
    salva_atti([atto], db)
    esito2 = salva_atti([atto], db)
    assert esito2["inseriti"] == 0
    assert esito2["duplicati"] == 1


def test_salva_atti_multipli(db, html_lista: str, html_dettaglio: str) -> None:
    atti = [
        _parse_dettaglio(html_dettaglio, f"https://comune.palermo.it/icity/albo/detail.do?id={i}", "082053")
        for i in (11001, 11002, 11003)
    ]
    esito = salva_atti(atti, db)
    assert esito["inseriti"] == 3


# ---------------------------------------------------------------------------
# scarica_atti (offline con _fetch_fn iniettato)
# ---------------------------------------------------------------------------


def test_scarica_atti_offline(db, html_lista: str, html_dettaglio: str) -> None:
    """Test end-to-end: lista → dettaglio → salvataggio, senza rete."""
    base = "https://comune.palermo.it/icity/albo"

    # Simula il fetch: lista solo alla pagina 1, dettaglio per ogni atto
    chiamate: list[str] = []

    def fetch_mock(url: str) -> str:
        chiamate.append(url)
        if "albo.do" in url:
            if "page=1" in url:
                return html_lista
            return "<html><body></body></html>"  # pagina vuota → stop
        return html_dettaglio  # ogni dettaglio restituisce lo stesso HTML

    atti_generati = list(
        scarica_atti(base, "082053", limit=3, delay=0, _fetch_fn=fetch_mock)
    )
    assert len(atti_generati) == 3
    # Verifica che tutti abbiano url_fonte valorizzato
    for atto in atti_generati:
        assert atto.url_fonte
        assert atto.fonte_scraper == FONTE_SCRAPER


def test_scarica_atti_rispetta_limit(db, html_lista: str, html_dettaglio: str) -> None:
    """Verifica che limit=1 restituisca al massimo 1 atto."""
    base = "https://comune.palermo.it/icity/albo"

    def fetch_mock(url: str) -> str:
        if "albo.do" in url:
            return html_lista
        return html_dettaglio

    atti = list(scarica_atti(base, "082053", limit=1, delay=0, _fetch_fn=fetch_mock))
    assert len(atti) == 1
