"""Test offline per lo spider generico "ServiziOnLine" ASP.NET/DevExpress (2026-08-06).

Nessuna chiamata di rete né Playwright — tutti i test usano _parse_html()
con HTML fixture inline che riproducono il DOM reso da Playwright (stessa
struttura di Agrigento, riusata su Pachino e Barrafranca).
"""

from __future__ import annotations

from talia.modulo2_scraping.db import (
    EnteMetadato,
    connetti,
    conta_atti,
    inizializza_db,
    upsert_ente,
)
from talia.modulo2_scraping.fonti.serviziolinealbo import (
    FONTE_SCRAPER,
    _parse_html,
    prepara_ente,
    salva_atti,
)

_BASE = "https://servizi.comune.pachino.sr.it"
_ISTAT = "089014"

# Pachino: titolo SENZA riferimento settoriale finale.
_HTML_PACHINO = f"""
<html><body>
<ul class="link-list">
  <li>
    <div class="list-item">
      <div class="it-right-zone">
        <a href="#" data-bs-toggle="collapse" data-bs-target="#collapse2094_2026"
           onclick="return getDettaglioScheda(this)">
          <span class="text text-custom p-1">
            2094/2026 del 06/08/2026 - Avviso Deposito Atti Nella Casa Del Comune
            <em>N.1 CARTELLA DI PAGAMENTO IN BUSTA CHIUSA E SIGILLATA CIG A12345678B</em>
          </span>
        </a>
        <span class="it-multiple">
          <a href="#" data-link="{_BASE}/ServiziOnLine/AlboPretorio/AlboPretorio?anno=2026&amp;numero=2094"
             aria-label="Copia Permalink della scheda"></a>
        </span>
      </div>
    </div>
  </li>
</ul>
</body></html>
"""

# Barrafranca: titolo CON riferimento settoriale finale (- NNNN/YYYY del DD/MM/YYYY).
_HTML_BARRAFRANCA = """
<html><body>
<ul class="link-list">
  <li>
    <div class="list-item">
      <div class="it-right-zone">
        <a href="#" data-bs-toggle="collapse" data-bs-target="#collapse1472_2026"
           onclick="return getDettaglioScheda(this)">
          <span class="text text-custom p-1">
            1472/2026 del 06/08/2026 - Ordinanza Sindacale - 2026/29 del 06/08/2026
            <em>Ulteriori provvedimenti per la sepoltura temporanea delle salme.</em>
          </span>
        </a>
        <span class="it-multiple">
          <a href="#" data-link="https://servizi.comune.barrafranca.en.it/ServiziOnLine/AlboPretorio/AlboPretorio?anno=2026&amp;numero=1472"
             aria-label="Copia Permalink della scheda"></a>
        </span>
      </div>
    </div>
  </li>
</ul>
</body></html>
"""

_HTML_VUOTO = "<html><body><ul class='link-list'></ul></body></html>"


def _db():
    conn = connetti(":memory:")
    inizializza_db(conn)
    upsert_ente(
        conn, EnteMetadato(denominazione="Comune di Pachino", codice_istat=_ISTAT, provincia="SR")
    )
    return conn


# ---------------------------------------------------------------------------
# Test _parse_html — titolo senza riferimento settoriale (Pachino)
# ---------------------------------------------------------------------------


def test_parse_html_conta_atti():
    assert len(_parse_html(_HTML_PACHINO, _ISTAT)) == 1


def test_parse_html_numero_e_data():
    a = _parse_html(_HTML_PACHINO, _ISTAT)[0]
    assert a.numero == "2094/2026"
    assert a.data_atto == "2026-08-06"


def test_parse_html_tipo_senza_settoriale():
    a = _parse_html(_HTML_PACHINO, _ISTAT)[0]
    assert a.tipo == "avviso"


def test_parse_html_oggetto_e_cig():
    a = _parse_html(_HTML_PACHINO, _ISTAT)[0]
    assert "CARTELLA DI PAGAMENTO" in a.oggetto
    assert a.cig == "A12345678B"


def test_parse_html_url_fonte():
    a = _parse_html(_HTML_PACHINO, _ISTAT)[0]
    assert "anno=2026" in a.url_fonte
    assert "numero=2094" in a.url_fonte


def test_parse_html_fonte_scraper_e_istat():
    a = _parse_html(_HTML_PACHINO, _ISTAT)[0]
    assert a.fonte_scraper == FONTE_SCRAPER
    assert a.ente_codice_istat == _ISTAT


def test_parse_html_vuoto():
    assert _parse_html(_HTML_VUOTO, _ISTAT) == []


def test_parse_html_no_duplicati():
    html_doppio = _HTML_PACHINO + _HTML_PACHINO
    assert len(_parse_html(html_doppio, _ISTAT)) == 1


# ---------------------------------------------------------------------------
# Test _parse_html — titolo CON riferimento settoriale finale (Barrafranca)
# ---------------------------------------------------------------------------


def test_parse_html_tipo_con_settoriale_non_lo_include():
    """Il riferimento settoriale finale ("- 2026/29 del 06/08/2026") non deve
    finire nel tipo estratto, altrimenti il fallback tipo="atto" scatterebbe sempre."""
    a = _parse_html(_HTML_BARRAFRANCA, "086004")[0]
    assert a.tipo == "ordinanza"


def test_parse_html_data_atto_con_settoriale():
    a = _parse_html(_HTML_BARRAFRANCA, "086004")[0]
    assert a.data_atto == "2026-08-06"


def test_parse_html_oggetto_con_settoriale():
    a = _parse_html(_HTML_BARRAFRANCA, "086004")[0]
    assert "sepoltura temporanea" in a.oggetto


# ---------------------------------------------------------------------------
# Test salva_atti / prepara_ente
# ---------------------------------------------------------------------------


def _atti_campione():
    return _parse_html(_HTML_PACHINO, _ISTAT)


def test_salva_atti_inseriti():
    esito = salva_atti(_atti_campione(), _db())
    assert esito["inseriti"] == 1
    assert esito["duplicati"] == 0


def test_salva_atti_nel_db():
    conn = _db()
    salva_atti(_atti_campione(), conn)
    assert conta_atti(conn) == 1


def test_salva_atti_idempotente():
    conn = _db()
    salva_atti(_atti_campione(), conn)
    esito2 = salva_atti(_atti_campione(), conn)
    assert esito2["inseriti"] == 0
    assert esito2["duplicati"] == 1


def test_salva_atti_lista_vuota():
    esito = salva_atti([], _db())
    assert esito["inseriti"] == 0


def test_prepara_ente():
    conn = connetti(":memory:")
    inizializza_db(conn)
    prepara_ente(conn, codice_istat="089014", denominazione="Comune di Pachino", provincia="SR")
    assert conn.execute("SELECT COUNT(*) FROM enti").fetchone()[0] == 1
