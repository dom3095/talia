"""Test offline per lo spider generico "portalepa" PHP (TAL-49).

Piattaforma condivisa da Siracusa, Gela, Monreale — vedi siracusa.py per
il caso originale a comune singolo. Nessuna chiamata di rete.
"""

from __future__ import annotations

from talia.modulo2_scraping.db import (
    EnteMetadato,
    connetti,
    conta_atti,
    inizializza_db,
    upsert_ente,
)
from talia.modulo2_scraping.fonti.portalepa import (
    FONTE_SCRAPER,
    _next_page_links,
    _parse_page,
    salva_atti,
)

_BASE = "https://portale.comune.gela.cl.it"
_ISTAT = "085007"
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
<a href='/openweb/albo/albo_pretorio.php?tabella_albo[page]=2&amp;tabella_albo[start]=16&amp;\
CSRF={_CSRF}'>Pag 2</a>
<a href='/openweb/albo/albo_pretorio.php?tabella_albo[page]=3&amp;tabella_albo[start]=32&amp;\
CSRF={_CSRF}'>Pag 3</a>
</body></html>
"""

_HTML_SENZA_ATTI = "<html><body><table></table></body></html>"


# ---------------------------------------------------------------------------
# Test _parse_page
# ---------------------------------------------------------------------------


def test_parse_page_conta_atti():
    atti = _parse_page(_HTML_PAGINA_1, _BASE, _ISTAT)
    assert len(atti) == 2


def test_parse_page_numero():
    atti = _parse_page(_HTML_PAGINA_1, _BASE, _ISTAT)
    assert atti[0].numero == "2026/0006060"


def test_parse_page_oggetto():
    atti = _parse_page(_HTML_PAGINA_1, _BASE, _ISTAT)
    assert atti[0].oggetto == "Manutenzione strade comunali"


def test_parse_page_tipo():
    atti = _parse_page(_HTML_PAGINA_1, _BASE, _ISTAT)
    assert "determina" in atti[0].tipo


def test_parse_page_data_atto():
    atti = _parse_page(_HTML_PAGINA_1, _BASE, _ISTAT)
    assert atti[0].data_atto == "2026-06-01"


def test_parse_page_data_scadenza():
    atti = _parse_page(_HTML_PAGINA_1, _BASE, _ISTAT)
    assert atti[0].data_scadenza == "2026-06-16"


def test_parse_page_url_fonte():
    atti = _parse_page(_HTML_PAGINA_1, _BASE, _ISTAT)
    assert "340282" in atti[0].url_fonte
    assert atti[0].url_fonte.startswith(_BASE)


def test_parse_page_fonte_scraper():
    atti = _parse_page(_HTML_PAGINA_1, _BASE, _ISTAT)
    assert atti[0].fonte_scraper == FONTE_SCRAPER


def test_parse_page_ente_istat():
    atti = _parse_page(_HTML_PAGINA_1, _BASE, _ISTAT)
    assert atti[0].ente_codice_istat == _ISTAT


def test_parse_page_cig_estratto():
    atti = _parse_page(_HTML_PAGINA_1, _BASE, _ISTAT)
    assert atti[1].cig == "A12345678B"


def test_parse_page_cig_assente():
    atti = _parse_page(_HTML_PAGINA_1, _BASE, _ISTAT)
    assert atti[0].cig is None


def test_parse_page_vuota():
    assert _parse_page(_HTML_SENZA_ATTI, _BASE, _ISTAT) == []


# ---------------------------------------------------------------------------
# Test _next_page_links
# ---------------------------------------------------------------------------


def test_next_page_links_trova_pagine():
    links = _next_page_links(_HTML_PAGINA_1, _BASE)
    assert 2 in links
    assert 3 in links


def test_next_page_links_url_valida():
    links = _next_page_links(_HTML_PAGINA_1, _BASE)
    assert _BASE in links[2]
    assert _CSRF in links[2]


def test_next_page_links_pagina_senza_next():
    links = _next_page_links(_HTML_SENZA_ATTI, _BASE)
    assert links == {}


# ---------------------------------------------------------------------------
# Test salva_atti
# ---------------------------------------------------------------------------


def _db():
    conn = connetti(":memory:")
    inizializza_db(conn)
    upsert_ente(
        conn,
        EnteMetadato(denominazione="Comune di Gela", codice_istat=_ISTAT, provincia="CL"),
    )
    return conn


def _atti_campione():
    return _parse_page(_HTML_PAGINA_1, _BASE, _ISTAT)


def test_salva_atti_inseriti():
    esito = salva_atti(_atti_campione(), _db())
    assert esito["inseriti"] == 2
    assert esito["duplicati"] == 0


def test_salva_atti_nel_db():
    conn = _db()
    salva_atti(_atti_campione(), conn)
    assert conta_atti(conn) == 2


def test_salva_atti_idempotente():
    conn = _db()
    salva_atti(_atti_campione(), conn)
    esito2 = salva_atti(_atti_campione(), conn)
    assert esito2["inseriti"] == 0
    assert esito2["duplicati"] == 2


def test_salva_atti_lista_vuota():
    esito = salva_atti([], _db())
    assert esito["inseriti"] == 0
