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
    salva_atti,
    scarica_atti,
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
