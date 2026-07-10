"""Test offline per lo spider Ribera (WordPress, TAL-49).

Nessuna chiamata di rete — tutte le fixture sono inline nel file.
"""

from __future__ import annotations

from talia.modulo2_scraping.db import (
    EnteMetadato,
    connetti,
    conta_atti,
    inizializza_db,
    upsert_ente,
)
from talia.modulo2_scraping.fonti.ribera import (
    CODICE_ISTAT,
    FONTE_SCRAPER,
    _parse_pagina,
    salva_atti,
)

_U = "https://www.comune.ribera.ag.it/atti-pubblici/albo-pretorio/?action=visatto&id="

_HTML_PAGINA = f"""
<table>
<thead><tr><th>Protocollo</th><th>Oggetto</th><th>Validità</th><th>Categoria</th><th>Settore</th></tr></thead>
<tbody>
<tr>
  <td><a href="{_U}4241">1643/2026</a></td>
  <td><a href="{_U}4241">n. 604 del 02.07.2026 - Impegno di spesa CIG A12345678B[...]</a></td>
  <td><a href="{_U}4241">07/07/2026<br />22/07/2026</a></td>
  <td><a href="{_U}4241">Determinazioni Dirigenziali</a></td>
  <td><a href="{_U}4241">I Settore - Affari Generali</a></td>
</tr>
<tr>
  <td><a href="{_U}4239">1641/2026</a></td>
  <td><a href="{_U}4239">Atto di pubblicazione di matrimonio.</a></td>
  <td><a href="{_U}4239">07/07/2026<br />15/07/2026</a></td>
  <td><a href="{_U}4239">Pubblicazioni Matrimoniali</a></td>
  <td><a href="{_U}4239">Stato Civile</a></td>
</tr>
</tbody>
</table>
"""

_HTML_SENZA_ATTI = "<table><thead><tr><th>Protocollo</th></tr></thead><tbody></tbody></table>"


# ---------------------------------------------------------------------------
# Test _parse_pagina
# ---------------------------------------------------------------------------


def test_parse_pagina_conta_atti():
    assert len(_parse_pagina(_HTML_PAGINA)) == 2


def test_parse_pagina_primo_atto():
    a = _parse_pagina(_HTML_PAGINA)[0]
    assert a.ente_codice_istat == CODICE_ISTAT
    assert a.tipo == "determina"
    assert a.numero == "1643/2026"
    assert "Impegno di spesa" in a.oggetto
    assert a.cig == "A12345678B"
    assert a.data_pub == "2026-07-07"
    assert a.data_scadenza == "2026-07-22"
    assert "id=4241" in a.url_fonte
    assert a.fonte_scraper == FONTE_SCRAPER


def test_parse_pagina_secondo_atto_tipo_fallback():
    a = _parse_pagina(_HTML_PAGINA)[1]
    assert a.tipo == "atto"  # "Pubblicazioni Matrimoniali" non matcha nessuna chiave nota
    assert a.cig is None
    assert a.data_scadenza == "2026-07-15"


def test_parse_pagina_html_vuoto():
    assert _parse_pagina(_HTML_SENZA_ATTI) == []


def test_parse_pagina_stringa_vuota():
    assert _parse_pagina("") == []


# ---------------------------------------------------------------------------
# Test salva_atti
# ---------------------------------------------------------------------------


def _db():
    conn = connetti(":memory:")
    inizializza_db(conn)
    upsert_ente(conn, EnteMetadato(denominazione="Comune di Ribera", codice_istat=CODICE_ISTAT))
    return conn


def _atti_campione():
    return _parse_pagina(_HTML_PAGINA)


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
# Test parametrizzazione base_url
# ---------------------------------------------------------------------------


def test_parse_pagina_accetta_base_url_parametro():
    """Verifica che _parse_pagina accetti il parametro base_url."""
    base_url_custom = "http://test.example.com"
    atti = _parse_pagina(_HTML_PAGINA, base_url=base_url_custom)
    # Gli URL costruiti devono contenere il base_url custom
    assert len(atti) > 0
    assert all(base_url_custom in a.url_fonte for a in atti)
