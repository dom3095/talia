"""Test offline per lo spider generico Halley EG (TAL-49).

Piattaforma condivisa da Vittoria, Sciacca, Adrano, Barcellona Pozzo di Gotto.
Nessuna chiamata di rete — fixture ricalcano l'HTML reale (righe duplicate
desktop/mobile, come emesso dal portale).
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
from talia.modulo2_scraping.fonti.halley import (
    FONTE_SCRAPER,
    _parse_pagina,
    _parse_pagina_trasparenza,
    salva_atti,
    scarica_atti,
    scarica_atti_trasparenza,
    scopri_categorie_trasparenza,
)

_BASE = "https://trasparenza.comune.vittoria.rg.it"
_ISTAT = "088012"

_HTML_PAGINA = """
<table class="cms-table" id="table-albo">
<thead><tr>
  <th><div onclick="location.href='mc_p_ricerca.php?&pag=1'"
      title="ordina per numero pubblicazione">Numero pubblicazione</div></th>
</tr></thead>
<tbody>
<tr>
  <td class="hidden-xs" style="width:18%">
    <strong>Numero pubblicazione</strong>
    <div>3459</div>
    <br>
    <strong>Mittente</strong>
    <div>Comune di Vittoria  </div>
    <br>
    <strong>Tipo</strong>
    <div>DETERMINE SINDACALI</div>
  </td>
  <td class="hidden-xs" style="width:35%;">
    <strong>Oggetto</strong><br>
    <a href="/mc/mc_p_dettaglio.php?id_pubbl=35583" title="Fai click qui per andare al dettaglio">
      <div class="albo-colore">nomina di vice-Segretario comunale CIG A12345678B.</div>
    </a>
  </td>
  <td class="hidden-xs" style="width:13%;">
    <strong>Numero atto</strong>
    <div>21</div>
    <br>
    <strong>Data atto</strong>
    <div>07/07/2026</div>
  </td>
  <td class="hidden-xs" style="width:15%;">
    <strong>Registro generale</strong>
    <div><i>Non definito</i></div>
    <br>
    <strong>Data registro generale</strong>
    <div>07/07/2026</div>
  </td>
  <td class="hidden-xs" style="width:10%;">
    <strong>Data inizio</strong>
    <div>07/07/2026</div>
    <br>
    <strong>Data fine</strong>
    <div>22/07/2026</div>
  </td>
  <td class="hidden-xs" style="width:10%;text-align:center;">
    <strong>Documento</strong>
    <a href="#" onclick="window.open('mc_attachment.php?mc=48460');" title="Scarica documento">
      <span class="fa fa-file-text-o"></span>
    </a>
  </td>
  <td data-id="35583" class="visible-xs">
    <strong>Numero pubblicazione</strong>
    <div>3459</div>
    <strong>Tipo</strong>
    <div>Determine Sindacali</div>
  </td>
</tr>
<tr>
  <td class="hidden-xs" style="width:18%">
    <strong>Numero pubblicazione</strong>
    <div>3458</div>
    <br>
    <strong>Mittente</strong>
    <div>Comune di Vittoria  </div>
    <br>
    <strong>Tipo</strong>
    <div>AVVISO PUBBLICO</div>
  </td>
  <td class="hidden-xs" style="width:35%;">
    <strong>Oggetto</strong><br>
    <a href="/mc/mc_p_dettaglio.php?id_pubbl=35570" title="Fai click qui per andare al dettaglio">
      <div class="albo-colore">avviso di gara senza CIG.</div>
    </a>
  </td>
  <td class="hidden-xs" style="width:13%;">
    <strong>Numero atto</strong>
    <div><i>Non definito</i></div>
    <br>
    <strong>Data atto</strong>
    <div>06/07/2026</div>
  </td>
  <td class="hidden-xs" style="width:15%;">
    <strong>Registro generale</strong>
    <div><i>Non definito</i></div>
    <br>
    <strong>Data registro generale</strong>
    <div>06/07/2026</div>
  </td>
  <td class="hidden-xs" style="width:10%;">
    <strong>Data inizio</strong>
    <div>06/07/2026</div>
    <br>
    <strong>Data fine</strong>
    <div>21/07/2026</div>
  </td>
  <td class="hidden-xs" style="width:10%;text-align:center;">
    <strong>Documento</strong>
  </td>
</tr>
</tbody>
</table>
"""

_HTML_SENZA_ATTI = (
    "<table><thead><tr><th>Numero pubblicazione</th></tr></thead><tbody></tbody></table>"
)


# ---------------------------------------------------------------------------
# Test _parse_pagina
# ---------------------------------------------------------------------------


def test_parse_pagina_conta_atti():
    atti = _parse_pagina(_HTML_PAGINA, _BASE, _ISTAT)
    assert len(atti) == 2


def test_parse_pagina_ignora_riga_header():
    """L'header contiene 'Numero pubblicazione' in testo semplice (link ordinamento),
    senza <strong>: non deve essere scambiato per una riga atto."""
    atti = _parse_pagina(_HTML_PAGINA, _BASE, _ISTAT)
    assert all(a.numero != "" for a in atti)


def test_parse_pagina_primo_atto():
    a = _parse_pagina(_HTML_PAGINA, _BASE, _ISTAT)[0]
    assert a.ente_codice_istat == _ISTAT
    assert a.tipo == "determine sindacali"
    assert a.numero == "21"
    assert a.oggetto == "nomina di vice-Segretario comunale CIG A12345678B."
    assert a.data_atto == "2026-07-07"
    assert a.data_scadenza == "2026-07-22"
    assert a.cig == "A12345678B"
    assert "35583" in a.url_fonte
    assert a.url_fonte.startswith(_BASE)
    assert a.fonte_scraper == FONTE_SCRAPER


def test_parse_pagina_numero_non_definito_diventa_none():
    a = _parse_pagina(_HTML_PAGINA, _BASE, _ISTAT)[1]
    assert a.numero is None
    assert a.cig is None


def test_parse_pagina_html_vuoto():
    assert _parse_pagina(_HTML_SENZA_ATTI, _BASE, _ISTAT) == []


def test_parse_pagina_html_totalmente_vuoto():
    assert _parse_pagina("", _BASE, _ISTAT) == []


# ---------------------------------------------------------------------------
# Test salva_atti
# ---------------------------------------------------------------------------


def _db():
    conn = connetti(":memory:")
    inizializza_db(conn)
    upsert_ente(
        conn,
        EnteMetadato(denominazione="Comune di Vittoria", codice_istat=_ISTAT, provincia="RG"),
    )
    return conn


def _atti_campione():
    return _parse_pagina(_HTML_PAGINA, _BASE, _ISTAT)


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
# Test retry su timeout/connessione rifiutata (host condiviso, 2026-08-05)
# ---------------------------------------------------------------------------

_HTML_PAGINA_VUOTA = '<table class="cms-table" id="table-albo"><tbody></tbody></table>'


class _RispostaFinta:
    def __init__(self, html: str):
        self._html = html.encode("utf-8")

    def read(self):
        return self._html

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_scarica_atti_riprova_dopo_un_timeout(monkeypatch):
    chiamate = {"n": 0}

    def _urlopen_finto(req, timeout=20, context=None):
        chiamate["n"] += 1
        if chiamate["n"] == 1:
            raise TimeoutError("simulato")
        if "pag=1" in req.full_url:
            return _RispostaFinta(_HTML_PAGINA_VUOTA)
        return _RispostaFinta(_HTML_PAGINA)

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_finto)
    monkeypatch.setattr("time.sleep", lambda _s: None)
    atti = list(scarica_atti(_BASE, _ISTAT))
    assert len(atti) == 2
    assert chiamate["n"] == 3


def test_scarica_atti_rilancia_dopo_retry_esaurito(monkeypatch):
    def _urlopen_finto(*_args, **_kwargs):
        raise TimeoutError("simulato")

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_finto)
    try:
        list(scarica_atti(_BASE, _ISTAT, _retry=0))
        raise AssertionError("doveva sollevare TimeoutError")
    except TimeoutError:
        pass


# ---------------------------------------------------------------------------
# Amministrazione Trasparente (TAL-62)
#
# Applicazione separata (Zend Framework, /zf/index.php/trasparenza/...):
# HTML completamente diverso dall'Albo Pretorio, fixture ricalcate su quello
# reale (Aci Bonaccorsi, verificato dal vivo 2026-08-16).
# ---------------------------------------------------------------------------

_HTML_MENU_TRASPARENZA = (
    "<li id='halley-menu-item-346'>"
    "<a href='/zf/index.php/trasparenza/index/index/categoria/184' target='_self'>"
    "Bandi di concorso</a></li>"
    "<li id='halley-menu-item-347'>"
    "<a href='/zf/index.php/trasparenza/index/index/categoria/185' target='_self'>"
    "Bandi di gara e contratti</a></li>"
)

_DOC_PATH = "/zf/index.php/trasparenza/index/visualizza-documento-generico/categoria/184"

_HTML_PAGINA_TRASPARENZA = f"""
<table>
<tbody>
<tr data-href="{_DOC_PATH}/documento/1149" data-target='_blank'>
  <td class=" break-all">
    <a href="{_DOC_PATH}/documento/1149" target='_blank' class="prevent-default">
      Schema di Contratto - Assunzione CIG A1B2C3D4E5 personale tecnico. (259.92 KB)
    </a>
    <div class="small" style="margin-top:10px;">
      Inserita il 22/12/2025
    </div>
    <div class="small">
      Modificata il 22/12/2025
    </div>
  </td>
</tr>
<tr data-href="{_DOC_PATH}/documento/1148" data-target='_blank'>
  <td class=" break-all">
    <a href="{_DOC_PATH}/documento/1148" target='_blank' class="prevent-default">
      DETERMINA - Chiusura procedimento selezione comparativa. (1.13 MB)
    </a>
    <div class="small" style="margin-top:10px;">
      Inserita il 19/12/2025
    </div>
  </td>
</tr>
</tbody>
</table>
<a href="/zf/index.php/trasparenza/index/index/categoria/184/page/2">Successiva &rsaquo;</a>
"""

_HTML_PAGINA_TRASPARENZA_2 = f"""
<table><tbody>
<tr data-href="{_DOC_PATH}/documento/900" data-target='_blank'>
  <td class=" break-all">
    <a href="{_DOC_PATH}/documento/900" target='_blank' class="prevent-default">
      BANDO DI CONCORSO PUBBLICO PER ESAMI. (500 KB)
    </a>
    <div class="small">Inserita il 10/01/2020</div>
  </td>
</tr>
</tbody></table>
"""

_HTML_PAGINA_TRASPARENZA_VUOTA = "<table><tbody></tbody></table>"

_BASE_TRASPARENZA = "https://servizi.comune.acibonaccorsi.ct.it"
_ISTAT_TRASPARENZA = "087001"


def test_scopri_categorie_trasparenza(monkeypatch):
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *a, **k: _RispostaFinta(_HTML_MENU_TRASPARENZA)
    )
    categorie = scopri_categorie_trasparenza(_BASE_TRASPARENZA)
    assert categorie == {
        "Bandi di concorso": "184",
        "Bandi di gara e contratti": "185",
    }


def test_scopri_categorie_trasparenza_pagina_assente(monkeypatch):
    def _urlopen_finto(*_a, **_k):
        raise urllib.error.URLError("simulato")

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_finto)
    assert scopri_categorie_trasparenza(_BASE_TRASPARENZA) == {}


def test_parse_pagina_trasparenza_conta_atti():
    atti = _parse_pagina_trasparenza(
        _HTML_PAGINA_TRASPARENZA, _BASE_TRASPARENZA, _ISTAT_TRASPARENZA, "Bandi di concorso"
    )
    assert len(atti) == 2


def test_parse_pagina_trasparenza_primo_atto():
    atti = _parse_pagina_trasparenza(
        _HTML_PAGINA_TRASPARENZA, _BASE_TRASPARENZA, _ISTAT_TRASPARENZA, "Bandi di concorso"
    )
    a = atti[0]
    assert a.ente_codice_istat == _ISTAT_TRASPARENZA
    assert a.tipo == "bandi di concorso"
    assert a.fonte_scraper == "halley_trasparenza"
    assert a.oggetto == "Schema di Contratto - Assunzione CIG A1B2C3D4E5 personale tecnico."
    assert "(259.92 KB)" not in a.oggetto
    assert a.cig == "A1B2C3D4E5"
    assert a.data_pub == "2025-12-22"
    assert a.url_fonte == (
        f"{_BASE_TRASPARENZA}/zf/index.php/trasparenza/index/"
        "visualizza-documento-generico/categoria/184/documento/1149"
    )
    # A differenza dell'Albo Pretorio, qui non c'è data di scadenza.
    assert a.data_scadenza is None


def test_parse_pagina_trasparenza_html_vuoto():
    assert (
        _parse_pagina_trasparenza(
            _HTML_PAGINA_TRASPARENZA_VUOTA, _BASE_TRASPARENZA, _ISTAT_TRASPARENZA, "x"
        )
        == []
    )


def test_scarica_atti_trasparenza_categoria_singola(monkeypatch):
    def _urlopen_finto(req, timeout=20, context=None):
        url = req.full_url
        if "index/index" in url and "categoria" not in url:
            return _RispostaFinta(_HTML_MENU_TRASPARENZA)
        return _RispostaFinta(_HTML_PAGINA_TRASPARENZA_VUOTA)

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_finto)
    atti = list(
        scarica_atti_trasparenza(
            _BASE_TRASPARENZA,
            _ISTAT_TRASPARENZA,
            categorie=["Bandi di gara e contratti"],
        )
    )
    assert atti == []  # categoria trovata (185) ma pagina vuota: nessun crash


def test_scarica_atti_trasparenza_categoria_non_trovata_non_crasha(monkeypatch):
    monkeypatch.setattr(
        urllib.request, "urlopen", lambda *a, **k: _RispostaFinta(_HTML_MENU_TRASPARENZA)
    )
    atti = list(
        scarica_atti_trasparenza(
            _BASE_TRASPARENZA, _ISTAT_TRASPARENZA, categorie=["Categoria Inesistente"]
        )
    )
    assert atti == []


def test_scarica_atti_trasparenza_segue_paginazione(monkeypatch):
    def _urlopen_finto(req, timeout=20, context=None):
        url = req.full_url
        if "categoria/184/page/2" in url:
            return _RispostaFinta(_HTML_PAGINA_TRASPARENZA_2)
        if "categoria/184" in url:
            return _RispostaFinta(_HTML_PAGINA_TRASPARENZA)
        return _RispostaFinta(_HTML_MENU_TRASPARENZA)

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_finto)
    atti = list(
        scarica_atti_trasparenza(
            _BASE_TRASPARENZA, _ISTAT_TRASPARENZA, categorie=["Bandi di concorso"]
        )
    )
    # 2 dalla prima pagina + 1 dalla seconda (raggiunta via "Successiva")
    assert len(atti) == 3
    assert atti[-1].oggetto == "BANDO DI CONCORSO PUBBLICO PER ESAMI."


def test_scarica_atti_trasparenza_rispetta_max_pagine(monkeypatch):
    def _urlopen_finto(req, timeout=20, context=None):
        url = req.full_url
        if "categoria/184/page/2" in url:
            return _RispostaFinta(_HTML_PAGINA_TRASPARENZA_2)
        if "categoria/184" in url:
            return _RispostaFinta(_HTML_PAGINA_TRASPARENZA)
        return _RispostaFinta(_HTML_MENU_TRASPARENZA)

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_finto)
    atti = list(
        scarica_atti_trasparenza(
            _BASE_TRASPARENZA,
            _ISTAT_TRASPARENZA,
            categorie=["Bandi di concorso"],
            max_pagine_per_categoria=1,
        )
    )
    # Si ferma dopo la prima pagina anche se "Successiva" è presente.
    assert len(atti) == 2
