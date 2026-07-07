"""Test spider jCityGov — parsing HTML e costruzione url_fonte (TAL-30).

I test non fanno chiamate HTTP: usano HTML fixture sintetiche.
"""

from __future__ import annotations

from talia.modulo2_scraping.fonti.jcitygov import (
    _parse_date_cella,
    _parse_pagina,
    _parse_tipo,
    _url_dettaglio,
)

# ---------------------------------------------------------------------------
# HTML fixture minima di una pagina lista jCityGov
# ---------------------------------------------------------------------------

_HTML_LISTA = """
<table>
<thead><tr>
  <th>Tipo Atto</th><th><span>Anno e Numero Registro</span></th>
  <th>Oggetto</th><th>Periodo Pubblicazioneda - a</th><th>&nbsp;</th>
</tr></thead>
<tbody>
<tr class="master-detail-list-line master-detail-list-line-odd" data-id="4721119">
  <td class="categoria text">
    <span class="categoria_categoria">DETERMINE</span>
    <span class="categoria_separatore"> /</span>
    <span class="categoria_sottocategoria">DETERMINA DIRIGENZIALE</span>
  </td>
  <td class="annonumero number">2026/1031</td>
  <td class="oggetto text">AGGIUDICAZIONE APPALTO CIG: A1B2C3D4E5 SERVIZI VARI.</td>
  <td class="date">26/06/2026  31/12/2031</td>
  <td class="allegati">3</td>
</tr>
<tr class="master-detail-list-line master-detail-list-line-even" data-id="4720574">
  <td class="categoria text">
    <span class="categoria_categoria">DELIBERE</span>
    <span class="categoria_separatore"> /</span>
    <span class="categoria_sottocategoria">DELIBERA DI GIUNTA</span>
  </td>
  <td class="annonumero number">2026/42</td>
  <td class="oggetto text">APPROVAZIONE PIANO OPERATIVO.</td>
  <td class="date">01/06/2026  30/06/2026</td>
  <td class="allegati">1</td>
</tr>
</tbody>
</table>
"""

# Variante reale (es. Castel di Iudica): manca la colonna "Anno e Numero
# Registro" — le celle sono [tipo, oggetto, periodo]. Run 2026-07-07.
_HTML_LISTA_SENZA_NUMERO = """
<table>
<thead><tr>
  <th>Tipo Atto</th><th>Oggetto</th>
  <th>Periodo Pubblicazioneda - a</th><th>&nbsp;</th>
</tr></thead>
<tbody>
<tr class="master-detail-list-line master-detail-list-line-odd" data-id="5436021">
  <td class="categoria text">
    <span class="categoria_categoria">DETERMINE</span>
    <span class="categoria_separatore"> /</span>
    <span class="categoria_sottocategoria">DETERMINA CAPO SETTORE</span>
  </td>
  <td class="oggetto text">IRROGAZIONE SANZIONE DI PROVA ART. 7-BIS.</td>
  <td class="date">12/06/2026  31/12/2031</td>
  <td class="allegati">1</td>
</tr>
</tbody>
</table>
"""

_BASE = "https://caltanissetta.trasparenza-valutazione-merito.it"
_ISTAT = "085003"


# ---------------------------------------------------------------------------
# Test parsing tipo atto
# ---------------------------------------------------------------------------


def test_parse_tipo_con_sottocategoria():
    html = (
        '<span class="categoria_categoria">DETERMINE</span>'
        '<span class="categoria_separatore"> /</span>'
        '<span class="categoria_sottocategoria">DETERMINA DIRIGENZIALE</span>'
    )
    assert _parse_tipo(html) == "determine / determina dirigenziale"


def test_parse_tipo_fallback():
    assert _parse_tipo("<td>DELIBERA</td>") == "delibera"


# ---------------------------------------------------------------------------
# Test parsing date
# ---------------------------------------------------------------------------


def test_parse_date_cella_due_date():
    d1, d2 = _parse_date_cella("26/06/2026  31/12/2031")
    assert d1 == "2026-06-26"
    assert d2 == "2031-12-31"


def test_parse_date_cella_una_data():
    d1, d2 = _parse_date_cella("01/01/2025")
    assert d1 == "2025-01-01"
    assert d2 is None


def test_parse_date_cella_vuota():
    d1, d2 = _parse_date_cella("")
    assert d1 is None and d2 is None


# ---------------------------------------------------------------------------
# Test URL dettaglio
# ---------------------------------------------------------------------------


def test_url_dettaglio_contiene_id():
    url = _url_dettaglio(_BASE, "4721119")
    assert "4721119" in url
    assert _BASE in url
    assert "mostraDettaglio" in url


# ---------------------------------------------------------------------------
# Test parsing pagina completa
# ---------------------------------------------------------------------------


def test_parse_pagina_conta_atti():
    atti = _parse_pagina(_HTML_LISTA, _BASE, _ISTAT)
    assert len(atti) == 2


def test_parse_pagina_primo_atto():
    atti = _parse_pagina(_HTML_LISTA, _BASE, _ISTAT)
    a = atti[0]
    assert a.ente_codice_istat == _ISTAT
    assert a.numero == "1031"
    assert "aggiudicazione" in (a.oggetto or "").lower()
    assert a.cig == "A1B2C3D4E5"
    assert a.data_pub == "2026-06-26"
    assert a.data_scadenza == "2031-12-31"
    assert "4721119" in a.url_fonte
    assert a.fonte_scraper == "jcitygov"


def test_parse_pagina_secondo_atto():
    atti = _parse_pagina(_HTML_LISTA, _BASE, _ISTAT)
    a = atti[1]
    assert a.numero == "42"
    assert a.cig is None
    assert a.data_pub == "2026-06-01"


def test_parse_pagina_html_vuoto():
    assert _parse_pagina("", _BASE, _ISTAT) == []


def test_parse_pagina_layout_senza_colonna_numero():
    """Tenant senza colonna 'Anno e Numero Registro' (es. Castel di Iudica)."""
    atti = _parse_pagina(_HTML_LISTA_SENZA_NUMERO, _BASE, _ISTAT)
    assert len(atti) == 1
    a = atti[0]
    assert a.numero is None
    assert a.oggetto == "IRROGAZIONE SANZIONE DI PROVA ART. 7-BIS."
    assert a.data_pub == "2026-06-12"
    assert a.data_scadenza == "2031-12-31"
