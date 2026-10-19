"""Test offline per lo spider generico Halley HSPromila (TAL-49).

Piattaforma condivisa da Sambuca di Sicilia e Santo Stefano Quisquina.
Nessuna chiamata di rete.
"""

from __future__ import annotations

import urllib.request

from talia.modulo2_scraping.db import (
    EnteMetadato,
    connetti,
    conta_atti,
    inizializza_db,
    upsert_ente,
)
from talia.modulo2_scraping.fonti.hspromila import (
    FONTE_SCRAPER,
    _parse_pagina,
    salva_atti,
    scarica_atti,
)

_URL = (
    "https://servizionline.hspromilaprod.hypersicapp.net/cmssambucadisicilia/"
    "portale/albopretorio/albopretorioconsultazione.aspx?P=400"
)
_ISTAT = "084034"

_HTML_PAGINA = """
<table>
<thead><tr>
  <th class="d-none" data-type="hidden"></th><th class="hidden" data-type="key"></th>
  <th class="hidden" data-type="date"></th><th class="hidden" data-type="number"></th>
  <th data-type="number">Numero registro</th><th data-type="string">Oggetto</th>
  <th data-type="string">Categoria</th><th data-type="string">Ente/ufficio</th>
  <th data-type="date">Data inizio pubblicazione</th>
  <th data-type="date">Data fine pubblicazione</th>
</tr></thead>
<tbody>
<tr class="">
  <td class="d-none"><input type="hidden" name="row_2951" /></td>
  <td class>2951</td>
  <td class>07/07/2026</td>
  <td class>800</td>
  <td class>1134</td>
  <td class>DETERMINA N.800 DEL 07/07/2026 - LIQUIDAZIONE FATTURA CIG A12345678B</td>
  <td class>Determine Dirigenziali</td>
  <td class>ATTI UFFICIO URBANISTICA</td>
  <td class>07/07/2026</td>
  <td class>22/07/2026</td>
</tr>
<tr class="">
  <td class="d-none"><input type="hidden" name="row_2950" /></td>
  <td class>2950</td>
  <td class>06/07/2026</td>
  <td class>799</td>
  <td class>1133</td>
  <td class>AVVISO PUBBLICO SENZA CIG</td>
  <td class>Avvisi</td>
  <td class>ATTI UFFICIO LAVORI PUBBLICI</td>
  <td class>06/07/2026</td>
  <td class>21/07/2026</td>
</tr>
</tbody>
</table>
"""

_HTML_SENZA_ATTI = "<table><thead><tr><th>Numero registro</th></tr></thead><tbody></tbody></table>"


# ---------------------------------------------------------------------------
# Test _parse_pagina
# ---------------------------------------------------------------------------


def test_parse_pagina_conta_atti():
    assert len(_parse_pagina(_HTML_PAGINA, _URL, _ISTAT)) == 2


def test_parse_pagina_primo_atto():
    a = _parse_pagina(_HTML_PAGINA, _URL, _ISTAT)[0]
    assert a.ente_codice_istat == _ISTAT
    assert a.tipo == "determina"
    assert a.numero == "1134"
    assert "LIQUIDAZIONE FATTURA" in a.oggetto
    assert a.cig == "A12345678B"
    assert a.data_pub == "2026-07-07"
    assert a.data_scadenza == "2026-07-22"
    assert a.fonte_scraper == FONTE_SCRAPER
    assert a.url_fonte.endswith("#2951")
    assert a.url_fonte.startswith(_URL)


def test_parse_pagina_secondo_atto_tipo_avviso():
    a = _parse_pagina(_HTML_PAGINA, _URL, _ISTAT)[1]
    assert a.tipo == "avviso"
    assert a.cig is None


def test_parse_pagina_url_fonte_univoco_per_riga():
    atti = _parse_pagina(_HTML_PAGINA, _URL, _ISTAT)
    assert atti[0].url_fonte != atti[1].url_fonte


def test_parse_pagina_html_vuoto():
    assert _parse_pagina(_HTML_SENZA_ATTI, _URL, _ISTAT) == []


def test_parse_pagina_stringa_vuota():
    assert _parse_pagina("", _URL, _ISTAT) == []


# ---------------------------------------------------------------------------
# Test salva_atti
# ---------------------------------------------------------------------------


def _db():
    conn = connetti(":memory:")
    inizializza_db(conn)
    upsert_ente(
        conn,
        EnteMetadato(denominazione="Comune di Sambuca di Sicilia", codice_istat=_ISTAT),
    )
    return conn


def _atti_campione():
    return _parse_pagina(_HTML_PAGINA, _URL, _ISTAT)


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


# ---------------------------------------------------------------------------
# Test retry su timeout (host condiviso, TAL-51/sweep 2026-07-26)
# ---------------------------------------------------------------------------


class _RispostaFinta:
    def __init__(self, html: str):
        self._html = html.encode("utf-8")

    def read(self):
        return self._html

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _OpenerFinto:
    """Sostituisce l'opener con cookie jar usato da `scarica_atti`.

    Dal 2026-08-19 (TAL-70) lo scraper non usa più `urllib.request.urlopen`
    diretto ma un opener con cookie jar, perché la postback di paginazione
    ASP.NET viene rifiutata senza il cookie di sessione della GET.
    """

    def __init__(self, apri):
        self._apri = apri

    def open(self, *args, **kwargs):
        return self._apri(*args, **kwargs)


def test_scarica_atti_riprova_dopo_un_timeout(monkeypatch):
    chiamate = {"n": 0}

    def _apri(*_args, **_kwargs):
        chiamate["n"] += 1
        if chiamate["n"] == 1:
            raise TimeoutError("simulato")
        return _RispostaFinta(_HTML_PAGINA)

    monkeypatch.setattr(urllib.request, "build_opener", lambda *_a: _OpenerFinto(_apri))
    monkeypatch.setattr("time.sleep", lambda _s: None)
    atti = list(scarica_atti(_URL, _ISTAT))
    assert len(atti) == 2
    assert chiamate["n"] == 2


def test_scarica_atti_rilancia_dopo_retry_esaurito(monkeypatch):
    def _apri(*_args, **_kwargs):
        raise TimeoutError("simulato")

    monkeypatch.setattr(urllib.request, "build_opener", lambda *_a: _OpenerFinto(_apri))
    try:
        list(scarica_atti(_URL, _ISTAT, _retry=0))
        raise AssertionError("doveva sollevare TimeoutError")
    except TimeoutError:
        pass


# ---------------------------------------------------------------------------
# Skin legacy `itemstyle` a 6 colonne + paginazione (TAL-70)
# ---------------------------------------------------------------------------

_HTML_LEGACY = """
<table>
<tr class="pagerstyle" align="right"><td>
  <span class='DG_PagerCellResults'>(Trovati 40 risultati)</span>
  <span class='DG_PagerCellPageTitle'>Pagina 1 di 4</span>
  <span class="DG_PagerCellPageNoAccess">1</span>
  <a class="DG_PagerCellPageLink"
     href="javascript:__doPostBack(&#39;ctl00$dg$ctl01$ctl01&#39;,&#39;&#39;)">2</a>
  <a class="DG_PagerCellPageLink"
     href="javascript:__doPostBack(&#39;ctl00$dg$ctl01$ctl02&#39;,&#39;&#39;)">3</a>
</td></tr>
<tr class="headerstyle"><td>NUMERO REGISTRO</td><td>OGGETTO</td></tr>
<tr class="itemstyle" onmouseover="x()">
  <td>581</td><td>TRASPORTO SCOLASTICO - AVVISO PUBBLICO</td><td>Avvisi</td>
  <td>UFFICIO SEGRETERIA</td><td>19/08/2026</td><td>01/09/2026</td>
</tr>
<tr class="alternatingitemstyle">
  <td>580</td><td>LIQUIDAZIONE FATTURA CIG A12345678B</td><td>Atti di Liquidazione</td>
  <td>ATTI UFFICIO TECNICO</td><td>17/08/2026</td><td>01/09/2026</td>
</tr>
</table>
<input type="hidden" name="__VIEWSTATE" value="abc" />
<input type="hidden" name="__EVENTTARGET" value="" />
"""


def test_parse_legacy_estrae_le_righe_itemstyle():
    """Regressione TAL-70: Floresta e Cianciana rispondevano 200 con la
    tabella piena, ma il parser cercava solo `<tr class="">`."""
    from talia.modulo2_scraping.fonti.hspromila import _parse_pagina

    atti = _parse_pagina(_HTML_LEGACY, "https://x/albo.aspx?P=400", "083022")
    assert len(atti) == 2
    a = atti[0]
    assert a.numero == "581"
    assert a.oggetto.startswith("TRASPORTO SCOLASTICO")
    assert a.tipo == "avviso"
    assert a.data_pub == "2026-08-19"
    assert a.data_scadenza == "2026-09-01"
    assert a.url_fonte.endswith("#581")


def test_parse_legacy_estrae_il_cig():
    from talia.modulo2_scraping.fonti.hspromila import _parse_pagina

    atti = _parse_pagina(_HTML_LEGACY, "https://x/albo.aspx?P=400", "083022")
    assert atti[1].cig == "A12345678B"


def test_url_fonte_univoco_per_atto_anche_in_legacy():
    """Senza frammento distinto, la UNIQUE(ente, url_fonte) scarterebbe tutti
    gli atti tranne il primo."""
    from talia.modulo2_scraping.fonti.hspromila import _parse_pagina

    atti = _parse_pagina(_HTML_LEGACY, "https://x/albo.aspx?P=400", "083022")
    assert len({a.url_fonte for a in atti}) == len(atti)


def test_link_pagine_mappa_numero_a_target():
    from talia.modulo2_scraping.fonti.hspromila import link_pagine

    assert link_pagine(_HTML_LEGACY) == {
        "2": "ctl00$dg$ctl01$ctl01",
        "3": "ctl00$dg$ctl01$ctl02",
    }


def test_link_pagine_assenti_su_skin_moderna():
    from talia.modulo2_scraping.fonti.hspromila import link_pagine

    assert link_pagine(_HTML_PAGINA) == {}


def test_campi_form_include_viewstate():
    from talia.modulo2_scraping.fonti.hspromila import campi_form

    campi = campi_form(_HTML_LEGACY)
    assert campi["__VIEWSTATE"] == "abc"
    assert "__EVENTTARGET" in campi


def test_skin_moderna_ha_la_precedenza():
    """Un tenant sulla skin corrente non deve passare dal parser legacy."""
    from talia.modulo2_scraping.fonti.hspromila import _parse_legacy, _parse_pagina

    assert _parse_pagina(_HTML_PAGINA, "https://x", "084001")
    assert _parse_legacy(_HTML_PAGINA, "https://x", "084001") == []
