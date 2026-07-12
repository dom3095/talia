"""Test offline per lo spider Agrigento ASP.NET/DevExpress (TAL-B6).

Nessuna chiamata di rete né Playwright — tutti i test usano _parse_html()
con HTML fixture inline che riproducono il DOM reso da Playwright.
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
from talia.modulo2_scraping.fonti.agrigento import (
    CODICE_ISTAT,
    FONTE_SCRAPER,
    _parse_html,
    prepara_ente,
    salva_atti,
)

# ---------------------------------------------------------------------------
# HTML di test (struttura DOM reale dopo rendering Playwright)
# ---------------------------------------------------------------------------

_BASE = "http://servizionline.comune.agrigento.it"

_HTML_PAGINA = f"""
<html><body>
<ul class="link-list">
  <li>
    <div class="list-item">
      <div class="it-right-zone">
        <a href="#" data-bs-toggle="collapse" data-bs-target="#collapse2910_2026"
           onclick="return getDettaglioScheda(this)">
          <span class="text text-custom p-1">
            2910/2026 del 20/06/2026 - Determina Dirigenziale - 2026/1926 del 20/06/2026
            <em>Liquidazione contributo alla Parrocchia per servizi sociali. CIG BC0685F655</em>
          </span>
        </a>
        <span class="it-multiple">
          <a href="#" data-link="{_BASE}/ServiziOnLine/AlboPretorio/AlboPretorio?anno=2026&amp;numero=2910"
             aria-label="Copia Permalink della scheda"></a>
        </span>
      </div>
    </div>
  </li>
  <li>
    <div class="list-item">
      <div class="it-right-zone">
        <a href="#" data-bs-toggle="collapse" data-bs-target="#collapse2909_2026"
           onclick="return getDettaglioScheda(this)">
          <span class="text text-custom p-1">
            2909/2026 del 19/06/2026 - Delibera di Giunta - 2026/55 del 19/06/2026
            <em>Approvazione piano triennale opere pubbliche 2026-2028.</em>
          </span>
        </a>
        <span class="it-multiple">
          <a href="#" data-link="{_BASE}/ServiziOnLine/AlboPretorio/AlboPretorio?anno=2026&amp;numero=2909"
             aria-label="Copia Permalink della scheda"></a>
        </span>
      </div>
    </div>
  </li>
</ul>
</body></html>
"""

_HTML_VUOTO = "<html><body><ul class='link-list'></ul></body></html>"


# ---------------------------------------------------------------------------
# Fixtures pytest
# ---------------------------------------------------------------------------


@pytest.fixture
def db():
    conn = connetti(":memory:")
    inizializza_db(conn)
    upsert_ente(conn, EnteMetadato(
        denominazione="Comune di Agrigento",
        codice_istat=CODICE_ISTAT,
        provincia="AG",
    ))
    return conn


# ---------------------------------------------------------------------------
# Test _parse_html
# ---------------------------------------------------------------------------


def test_parse_html_conta_atti():
    atti = _parse_html(_HTML_PAGINA)
    assert len(atti) == 2


def test_parse_html_numero():
    atti = _parse_html(_HTML_PAGINA)
    assert atti[0].numero == "2910/2026"


def test_parse_html_tipo():
    atti = _parse_html(_HTML_PAGINA)
    assert "determina" in atti[0].tipo


def test_parse_html_oggetto():
    atti = _parse_html(_HTML_PAGINA)
    assert "Liquidazione" in (atti[0].oggetto or "")


def test_parse_html_data_atto():
    atti = _parse_html(_HTML_PAGINA)
    assert atti[0].data_atto == "2026-06-20"


def test_parse_html_url_fonte():
    atti = _parse_html(_HTML_PAGINA)
    assert "anno=2026" in atti[0].url_fonte
    assert "numero=2910" in atti[0].url_fonte


def test_parse_html_fonte_scraper():
    atti = _parse_html(_HTML_PAGINA)
    assert atti[0].fonte_scraper == FONTE_SCRAPER


def test_parse_html_ente_istat():
    atti = _parse_html(_HTML_PAGINA)
    assert atti[0].ente_codice_istat == CODICE_ISTAT


def test_parse_html_cig_estratto():
    atti = _parse_html(_HTML_PAGINA)
    assert atti[0].cig == "BC0685F655"


def test_parse_html_cig_assente():
    atti = _parse_html(_HTML_PAGINA)
    assert atti[1].cig is None


def test_parse_html_secondo_atto():
    atti = _parse_html(_HTML_PAGINA)
    assert atti[1].numero == "2909/2026"
    assert "delibera" in atti[1].tipo


def test_parse_html_vuoto():
    assert _parse_html(_HTML_VUOTO) == []


def test_parse_html_no_duplicati():
    # Stesso HTML ripetuto simula duplicati nel DOM DevExpress
    html_doppio = _HTML_PAGINA + _HTML_PAGINA
    atti = _parse_html(html_doppio)
    assert len(atti) == 2


# ---------------------------------------------------------------------------
# Test salva_atti
# ---------------------------------------------------------------------------


def _atti_campione():
    return _parse_html(_HTML_PAGINA)


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


def test_prepara_ente_accetta_base_url_parametro(db):
    """Verifica che prepara_ente accetti il parametro base_url."""
    # Dovrebbe non sollevare
    prepara_ente(
        db,
        base_url="http://test.example.com",
        codice_istat="999999",
        denominazione="Test Agrigento",
    )
