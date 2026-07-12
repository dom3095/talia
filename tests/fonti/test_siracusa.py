"""Test offline per lo spider Siracusa portalepa PHP (TAL-B5).

Nessuna chiamata di rete — tutte le fixture sono inline nel file.
"""

from __future__ import annotations

import pytest

from talia.modulo2_scraping.db import (
    EnteMetadato,
    connetti,
    conta_atti,
    inizializza_db,
    upsert_ente,
)
from talia.modulo2_scraping.fonti.siracusa import (
    CODICE_ISTAT,
    FONTE_SCRAPER,
    _next_page_links,
    _parse_page,
    salva_atti,
)

# ---------------------------------------------------------------------------
# HTML di test (struttura reale portalepa Siracusa)
# ---------------------------------------------------------------------------

_CSRF = "abc123"

_HTML_PAGINA_1 = f"""
<html><body>
<table>
  <tr>
    <th>Numero progressivo</th>
    <th>Oggetto</th>
    <th>Atto</th>
    <th>Data affissione</th>
    <th>Fine Pubblicazione</th>
  </tr>
  <tr class="paginated_element">
    <td><a href='/openweb/albo/albo_dettagli.php?id=340282'>2026/0006060</a></td>
    <td>Manutenzione strade comunali</td>
    <td>Determina nr.100 del 01/06/2026</td>
    <td>01/06/2026</td>
    <td>16/06/2026</td>
  </tr>
  <tr class="paginated_element">
    <td><a href='/openweb/albo/albo_dettagli.php?id=340283'>2026/0006061</a></td>
    <td>Acquisto materiale informatico CIG A12345678B</td>
    <td>Determina nr.101 del 02/06/2026</td>
    <td>02/06/2026</td>
    <td>17/06/2026</td>
  </tr>
</table>
<a href='/openweb/albo/albo_pretorio.php?tabella_albo[page]=2&amp;tabella_albo[start]=16&amp;CSRF={_CSRF}'>Pag 2</a>
<a href='/openweb/albo/albo_pretorio.php?tabella_albo[page]=3&amp;tabella_albo[start]=32&amp;CSRF={_CSRF}'>Pag 3</a>
</body></html>
"""

_HTML_PAGINA_2 = f"""
<html><body>
<table>
  <tr class="paginated_element">
    <td><a href='/openweb/albo/albo_dettagli.php?id=340300'>2026/0006080</a></td>
    <td>Servizi sociali delibera</td>
    <td>Delibera nr.50 del 10/06/2026</td>
    <td>10/06/2026</td>
    <td>25/06/2026</td>
  </tr>
</table>
<a href='/openweb/albo/albo_pretorio.php?tabella_albo[page]=1&amp;tabella_albo[start]=0&amp;CSRF={_CSRF}'>Pag 1</a>
<a href='/openweb/albo/albo_pretorio.php?tabella_albo[page]=3&amp;tabella_albo[start]=32&amp;CSRF={_CSRF}'>Pag 3</a>
</body></html>
"""

_HTML_SENZA_ATTI = "<html><body><table></table></body></html>"


# ---------------------------------------------------------------------------
# Fixtures pytest
# ---------------------------------------------------------------------------


@pytest.fixture
def db():
    conn = connetti(":memory:")
    inizializza_db(conn)
    upsert_ente(conn, EnteMetadato(
        denominazione="Comune di Siracusa",
        codice_istat=CODICE_ISTAT,
        provincia="SR",
    ))
    return conn


# ---------------------------------------------------------------------------
# Test _parse_page
# ---------------------------------------------------------------------------


def test_parse_page_conta_atti():
    atti = _parse_page(_HTML_PAGINA_1)
    assert len(atti) == 2


def test_parse_page_numero():
    atti = _parse_page(_HTML_PAGINA_1)
    assert atti[0].numero == "2026/0006060"


def test_parse_page_oggetto():
    atti = _parse_page(_HTML_PAGINA_1)
    assert atti[0].oggetto == "Manutenzione strade comunali"


def test_parse_page_tipo():
    atti = _parse_page(_HTML_PAGINA_1)
    assert "determina" in atti[0].tipo


def test_parse_page_data_atto():
    atti = _parse_page(_HTML_PAGINA_1)
    assert atti[0].data_atto == "2026-06-01"


def test_parse_page_data_scadenza():
    atti = _parse_page(_HTML_PAGINA_1)
    assert atti[0].data_scadenza == "2026-06-16"


def test_parse_page_url_fonte():
    atti = _parse_page(_HTML_PAGINA_1)
    assert "340282" in atti[0].url_fonte
    assert atti[0].url_fonte.startswith("https://portalepa.comune.siracusa.it")


def test_parse_page_fonte_scraper():
    atti = _parse_page(_HTML_PAGINA_1)
    assert atti[0].fonte_scraper == FONTE_SCRAPER


def test_parse_page_ente_istat():
    atti = _parse_page(_HTML_PAGINA_1)
    assert atti[0].ente_codice_istat == CODICE_ISTAT


def test_parse_page_cig_estratto():
    atti = _parse_page(_HTML_PAGINA_1)
    assert atti[1].cig == "A12345678B"


def test_parse_page_cig_assente():
    atti = _parse_page(_HTML_PAGINA_1)
    assert atti[0].cig is None


def test_parse_page_vuota():
    assert _parse_page(_HTML_SENZA_ATTI) == []


# ---------------------------------------------------------------------------
# Test _next_page_links
# ---------------------------------------------------------------------------


def test_next_page_links_trova_pagine():
    links = _next_page_links(_HTML_PAGINA_1)
    assert 2 in links
    assert 3 in links


def test_next_page_links_url_valida():
    links = _next_page_links(_HTML_PAGINA_1)
    assert "portalepa.comune.siracusa.it" in links[2]
    assert _CSRF in links[2]


def test_next_page_links_pagina_senza_next():
    links = _next_page_links(_HTML_SENZA_ATTI)
    assert links == {}


# ---------------------------------------------------------------------------
# Test salva_atti
# ---------------------------------------------------------------------------


def _atti_campione():
    return _parse_page(_HTML_PAGINA_1)


def test_salva_atti_inseriti(db):
    esito = salva_atti(_atti_campione(), db)
    assert esito["inseriti"] == 2
    assert esito["duplicati"] == 0


def test_salva_atti_nel_db(db):
    salva_atti(_atti_campione(), db)
    assert conta_atti(db) == 2


def test_salva_atti_idempotente(db):
    salva_atti(_atti_campione(), db)
    esito2 = salva_atti(_atti_campione(), db)
    assert esito2["inseriti"] == 0
    assert esito2["duplicati"] == 2


def test_salva_atti_lista_vuota(db):
    esito = salva_atti([], db)
    assert esito["inseriti"] == 0


# ---------------------------------------------------------------------------
# Test parametrizzazione base_url
# ---------------------------------------------------------------------------


def test_parse_page_accetta_base_url_parametro():
    """Verifica che _parse_page accetti il parametro base_url."""
    base_url_custom = "http://test.example.com"
    atti = _parse_page(_HTML_PAGINA_1, base_url=base_url_custom)
    # Gli URL costruiti devono contenere il base_url custom
    assert len(atti) > 0
    assert all(base_url_custom in a.url_fonte for a in atti)
