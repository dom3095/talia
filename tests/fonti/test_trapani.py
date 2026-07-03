"""Test offline per lo spider Trapani e-pal.it (TAL-B6).

Nessuna chiamata di rete — tutte le fixture sono inline nel file.
"""

from __future__ import annotations

import io
import logging
from datetime import date

import pytest

from talia.modulo2_scraping.db import (
    EnteMetadato,
    connetti,
    conta_atti,
    inizializza_db,
    upsert_ente,
)
from talia.modulo2_scraping.fonti.trapani import (
    _MARGINE_FUTURO_GIORNI,
    CODICE_ISTAT,
    FONTE_SCRAPER,
    _intervallo_default,
    _next_page_url,
    _parse_page,
    salva_atti,
    scarica_atti,
)

# ---------------------------------------------------------------------------
# HTML di test (struttura reale e-pal.it Trapani)
# ---------------------------------------------------------------------------

_HTML_PAGINA_1 = """
<html><body>
<div class="row risultati-ricerca">
  <div class="col-sm-12">
    <ul class="pagination">
      <li class="active"><span>1</span></li>
      <li><a href="/AlboOnline/ricercaAlbo?dataPubblicazioneDal=2026-01-01&dataPubblicazioneAl=2026-12-31&page=2" class="step">2</a></li>
      <li><a href="/AlboOnline/ricercaAlbo?dataPubblicazioneDal=2026-01-01&dataPubblicazioneAl=2026-12-31&page=3" class="step">3</a></li>
    </ul>
  </div>
  <div class="ricerca">
    <div class="container">
      Trovati 293 documenti
      <div class="panel panel-primary">
        <div class="panel-heading titolo-albo" tabindex="0">
          Registrazione Albo n.   3810/2026
          <div class="">Oggetto:  ISTITUZIONE DIVIETO DI SOSTA CON RIMOZIONE FORZATA.</div>
        </div>
        <div class="panel-body" tabindex="0">
          <div class="col-sm-12">Documento in Pubblicazione dal 19/06/2026 &nbsp;al 04/07/2026</div>
          <div class="testata-etichetta">Tipo pubblicazione: </div>
          <div class="testata-dati col-sm-9">REGISTRO DELLE DETERMINE</div>
        </div>
      </div>
      <div class="panel panel-primary">
        <div class="panel-heading titolo-albo" tabindex="0">
          Registrazione Albo n.   3809/2026
          <div class="">Oggetto:  AUTORIZZAZIONE LAVORI VIA CARRARA. CIG A98765432C</div>
        </div>
        <div class="panel-body" tabindex="0">
          <div class="col-sm-12">Documento in Pubblicazione dal 18/06/2026 &nbsp;al 03/07/2026</div>
          <div class="testata-etichetta">Tipo pubblicazione: </div>
          <div class="testata-dati col-sm-9">ORDINANZA DIRIGENZIALE</div>
        </div>
      </div>
    </div>
  </div>
</div>
</body></html>
"""

_HTML_PAGINA_2 = """
<html><body>
<ul class="pagination">
  <li><a href="/AlboOnline/ricercaAlbo?dataPubblicazioneDal=2026-01-01&dataPubblicazioneAl=2026-12-31&page=1" class="step">1</a></li>
  <li class="active"><span>2</span></li>
</ul>
<div class="panel panel-primary">
  <div class="panel-heading titolo-albo" tabindex="0">
    Registrazione Albo n.   3800/2026
    <div class="">Oggetto:  DELIBERA ACQUISTO FORNITURE.</div>
  </div>
  <div class="panel-body" tabindex="0">
    <div class="col-sm-12">Documento in Pubblicazione dal 15/06/2026 &nbsp;al 30/06/2026</div>
    <div class="testata-etichetta">Tipo pubblicazione: </div>
    <div class="testata-dati col-sm-9">DELIBERA DI GIUNTA</div>
  </div>
</div>
</body></html>
"""

_HTML_VUOTO = "<html><body><div class='risultati-ricerca'></div></body></html>"


# ---------------------------------------------------------------------------
# Fixtures pytest
# ---------------------------------------------------------------------------


@pytest.fixture
def db():
    conn = connetti(":memory:")
    inizializza_db(conn)
    upsert_ente(
        conn,
        EnteMetadato(
            denominazione="Comune di Trapani",
            codice_istat=CODICE_ISTAT,
            provincia="TP",
        ),
    )
    return conn


# ---------------------------------------------------------------------------
# Test _parse_page
# ---------------------------------------------------------------------------


def test_parse_page_conta_atti():
    atti = _parse_page(_HTML_PAGINA_1)
    assert len(atti) == 2


def test_parse_page_numero():
    atti = _parse_page(_HTML_PAGINA_1)
    assert atti[0].numero == "3810/2026"


def test_parse_page_oggetto():
    atti = _parse_page(_HTML_PAGINA_1)
    assert "DIVIETO DI SOSTA" in (atti[0].oggetto or "")


def test_parse_page_tipo():
    atti = _parse_page(_HTML_PAGINA_1)
    assert "registro" in atti[0].tipo


def test_parse_page_data_atto():
    atti = _parse_page(_HTML_PAGINA_1)
    assert atti[0].data_atto == "2026-06-19"


def test_parse_page_data_scadenza():
    atti = _parse_page(_HTML_PAGINA_1)
    assert atti[0].data_scadenza == "2026-07-04"


def test_parse_page_url_sintetica():
    atti = _parse_page(_HTML_PAGINA_1)
    url = atti[0].url_fonte
    assert "servizi-trapani.e-pal.it" in url
    assert "3810" in url
    assert "2026" in url


def test_parse_page_fonte_scraper():
    atti = _parse_page(_HTML_PAGINA_1)
    assert atti[0].fonte_scraper == FONTE_SCRAPER


def test_parse_page_ente_istat():
    atti = _parse_page(_HTML_PAGINA_1)
    assert atti[0].ente_codice_istat == CODICE_ISTAT


def test_parse_page_cig_estratto():
    atti = _parse_page(_HTML_PAGINA_1)
    assert atti[1].cig == "A98765432C"


def test_parse_page_cig_assente():
    atti = _parse_page(_HTML_PAGINA_1)
    assert atti[0].cig is None


def test_parse_page_secondo_atto():
    atti = _parse_page(_HTML_PAGINA_1)
    assert atti[1].numero == "3809/2026"
    assert "ordinanza" in atti[1].tipo


def test_parse_page_vuota():
    assert _parse_page(_HTML_VUOTO) == []


# ---------------------------------------------------------------------------
# Test _next_page_url
# ---------------------------------------------------------------------------


def test_next_page_url_trova_pagina_2():
    url = _next_page_url(_HTML_PAGINA_1, current_page=1)
    assert url is not None
    assert "page=2" in url
    assert "servizi-trapani.e-pal.it" in url


def test_next_page_url_non_trova_oltre_ultima():
    url = _next_page_url(_HTML_PAGINA_2, current_page=2)
    assert url is None


def test_next_page_url_pagina_vuota():
    assert _next_page_url(_HTML_VUOTO, current_page=1) is None


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
# Test intervallo date di default (fix BUG-4)
# ---------------------------------------------------------------------------


def test_intervallo_default_dal_primo_gennaio():
    dal, _ = _intervallo_default(date(2026, 7, 3))
    assert dal == "2026-01-01"


def test_intervallo_default_al_nel_futuro():
    """Il server esclude gli atti ancora in pubblicazione se al=oggi (BUG-4):
    'al' deve cadere abbastanza avanti da coprire le finestre di pubblicazione."""
    oggi = date(2026, 7, 3)
    _, al = _intervallo_default(oggi)
    assert date.fromisoformat(al) > oggi
    assert (date.fromisoformat(al) - oggi).days == _MARGINE_FUTURO_GIORNI


def test_scarica_atti_warning_su_zero_atti(monkeypatch, caplog):
    """Se la pagina 1 non produce atti, va loggato un WARNING esplicito
    (fallimento silenzioso a 0 atti — fragilità comune degli scraper)."""

    class _FintaRisposta(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=0: _FintaRisposta(_HTML_VUOTO.encode()),
    )
    with caplog.at_level(logging.WARNING):
        atti = list(scarica_atti())
    assert atti == []
    assert any("0 atti" in r.message for r in caplog.records)
