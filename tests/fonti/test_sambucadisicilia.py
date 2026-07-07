"""Test offline per lo spider Sambuca di Sicilia (Halley HSPromila, TAL-49).

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
from talia.modulo2_scraping.fonti.sambucadisicilia import (
    CODICE_ISTAT,
    FONTE_SCRAPER,
    _parse_pagina,
    salva_atti,
)

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
    assert len(_parse_pagina(_HTML_PAGINA)) == 2


def test_parse_pagina_primo_atto():
    a = _parse_pagina(_HTML_PAGINA)[0]
    assert a.ente_codice_istat == CODICE_ISTAT
    assert a.tipo == "determina"
    assert a.numero == "1134"
    assert "LIQUIDAZIONE FATTURA" in a.oggetto
    assert a.cig == "A12345678B"
    assert a.data_pub == "2026-07-07"
    assert a.data_scadenza == "2026-07-22"
    assert a.fonte_scraper == FONTE_SCRAPER
    assert a.url_fonte.endswith("#2951")


def test_parse_pagina_secondo_atto_tipo_avviso():
    a = _parse_pagina(_HTML_PAGINA)[1]
    assert a.tipo == "avviso"
    assert a.cig is None


def test_parse_pagina_url_fonte_univoco_per_riga():
    atti = _parse_pagina(_HTML_PAGINA)
    assert atti[0].url_fonte != atti[1].url_fonte


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
    upsert_ente(
        conn,
        EnteMetadato(denominazione="Comune di Sambuca di Sicilia", codice_istat=CODICE_ISTAT),
    )
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
