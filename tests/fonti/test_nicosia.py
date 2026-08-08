"""Test offline per lo spider Nicosia (WordPress "Developers Italia", 2026-08-06).

Nessuna chiamata di rete — tutte le fixture sono inline nel file, ricalcate
sulla struttura HTML reale osservata (tema "Developers Italia" per PA).
"""

from __future__ import annotations

import urllib.error
import urllib.request

from talia.modulo2_scraping.db import (
    connetti,
    conta_atti,
    inizializza_db,
)
from talia.modulo2_scraping.fonti.nicosia import (
    CODICE_ISTAT,
    FONTE_SCRAPER,
    _parse_dettaglio,
    _parse_lista,
    prepara_ente,
    salva_atti,
    scarica_atti,
)

_U = "https://comune.nicosia.en.it"

_HTML_LISTA = f"""
<div class="row">
<div class="col-md-6 col-xl-4">
  <div class="card-wrapper">
    <div class="card no-after rounded">
      <div class="card-body">
        <a class="text-decoration-none" href="{_U}/documento_pubblico/ordinanza-dirigenziale-n-4-2026/">
          <h3 class="card-title h4">Ordinanza Dirigenziale n.4/2026</h3>
        </a>
        <p class="text-secondary mb-0">Chiusura temporanea al transito veicolare.</p>
      </div>
    </div>
  </div>
</div>
<div class="col-md-6 col-xl-4">
  <div class="card-wrapper">
    <div class="card no-after rounded">
      <div class="card-body">
        <a class="text-decoration-none" href="{_U}/documento_pubblico/revisione-liste-elettorali/">
          <h3 class="card-title h4">Revisione dinamica liste elettorali</h3>
        </a>
        <p class="text-secondary mb-0">Avviso pubblico.</p>
      </div>
    </div>
  </div>
</div>
</div>
"""

_HTML_LISTA_VUOTA = '<div class="row"></div>'

_HTML_DETTAGLIO = """
<html><head><title>Ordinanza Dirigenziale n.4/2026 &#8211; Comune di Nicosia</title></head>
<body>
<section id="descrizione">
<h4>Descrizione</h4>
<div class="richtext-wrapper lora">
    <div class="dettaglio">
<div class="infodato larghezza_100x100">CIG A12345678B - Chiusura temporanea SP 133.</div>
</div>
</div>
</section>
<article id="ultimo-aggiornamento" class="it-page-section mt-5">
    <h4 class="h6">Ultimo aggiornamento:
    <span class="h6 fw-normal">18/03/2026, 12:00</span>
    </h4>
</article>
</body></html>
"""

_HTML_DETTAGLIO_SENZA_DATA = """
<html><head><title>Documento senza data &#8211; Comune di Nicosia</title></head>
<body><p>Pagina priva della sezione "Ultimo aggiornamento".</p></body></html>
"""


# ---------------------------------------------------------------------------
# Test _parse_lista
# ---------------------------------------------------------------------------


def test_parse_lista_conta_voci():
    assert len(_parse_lista(_HTML_LISTA)) == 2


def test_parse_lista_url_e_titolo():
    voci = _parse_lista(_HTML_LISTA)
    assert voci[0][0] == f"{_U}/documento_pubblico/ordinanza-dirigenziale-n-4-2026/"
    assert voci[0][1] == "Ordinanza Dirigenziale n.4/2026"


def test_parse_lista_html_vuoto():
    assert _parse_lista(_HTML_LISTA_VUOTA) == []


# ---------------------------------------------------------------------------
# Test _parse_dettaglio
# ---------------------------------------------------------------------------


def test_parse_dettaglio_campi():
    url = f"{_U}/documento_pubblico/ordinanza-dirigenziale-n-4-2026/"
    a = _parse_dettaglio(_HTML_DETTAGLIO, url, CODICE_ISTAT)
    assert a is not None
    assert a.ente_codice_istat == CODICE_ISTAT
    assert a.tipo == "ordinanza"
    assert a.numero == "4"
    assert a.data_pub == "2026-03-18"
    assert "CIG A12345678B" in a.oggetto
    assert a.cig == "A12345678B"
    assert a.url_fonte == url
    assert a.fonte_scraper == FONTE_SCRAPER


def test_parse_dettaglio_pagina_corrotta_senza_data_ritorna_none():
    """Pagina senza la sezione "Ultimo aggiornamento": scartata, non un atto senza data."""
    url = f"{_U}/documento_pubblico/documento-senza-data/"
    assert _parse_dettaglio(_HTML_DETTAGLIO_SENZA_DATA, url, CODICE_ISTAT) is None


# ---------------------------------------------------------------------------
# Test salva_atti / prepara_ente
# ---------------------------------------------------------------------------


def _db():
    conn = connetti(":memory:")
    inizializza_db(conn)
    prepara_ente(conn)
    return conn


def _atti_campione():
    url = f"{_U}/documento_pubblico/ordinanza-dirigenziale-n-4-2026/"
    return [_parse_dettaglio(_HTML_DETTAGLIO, url, CODICE_ISTAT)]


def test_salva_atti_inseriti():
    esito = salva_atti(_atti_campione(), _db())
    assert esito["inseriti"] == 1
    assert esito["duplicati"] == 0


def test_salva_atti_idempotente():
    conn = _db()
    salva_atti(_atti_campione(), conn)
    esito2 = salva_atti(_atti_campione(), conn)
    assert esito2["inseriti"] == 0
    assert esito2["duplicati"] == 1


def test_salva_atti_nel_db():
    conn = _db()
    salva_atti(_atti_campione(), conn)
    assert conta_atti(conn) == 1


def test_salva_atti_lista_vuota():
    esito = salva_atti([], _db())
    assert esito["inseriti"] == 0


# ---------------------------------------------------------------------------
# Test scarica_atti (lista + dettaglio combinati, rete mockata)
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


def test_scarica_atti_combina_lista_e_dettaglio(monkeypatch):
    chiamate = []

    def _urlopen_finto(req, timeout=20):
        url = req.full_url
        chiamate.append(url)
        if url.endswith("/page/2/"):
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        if "documento-albo-pretorio" in url:
            return _RispostaFinta(_HTML_LISTA)
        return _RispostaFinta(_HTML_DETTAGLIO)

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_finto)
    atti = list(scarica_atti())
    assert len(atti) == 2
    # 1 fetch lista pagina 1 + 1 fetch lista pagina 2 (404) + 2 fetch dettaglio
    assert len(chiamate) == 4


def test_scarica_atti_nessuna_voce_non_solleva(monkeypatch):
    def _urlopen_finto(req, timeout=20):
        return _RispostaFinta(_HTML_LISTA_VUOTA)

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_finto)
    assert list(scarica_atti()) == []
