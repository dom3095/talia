"""Test offline per lo spider generico URBI Cloud (TAL-49).

Piattaforma condivisa con Catania (`catania.py`, URBI self-hosted): stesso
meccanismo POST/stepper, parametrizzato per base_url/qs_base/ente_mittente.
Nessuna chiamata di rete.
"""

from __future__ import annotations

from talia.modulo2_scraping.db import (
    EnteMetadato,
    connetti,
    conta_atti,
    inizializza_db,
    upsert_ente,
)
from talia.modulo2_scraping.fonti.urbi import FONTE_SCRAPER, _parse_pagina, salva_atti

_BASE = "https://cloud.urbi.it/urbi/progs/urp/ur1ME001.sto"
_QS = "DB_NAME=wt00037115&w3cbt=S"
_ISTAT = "084017"
_ENTE = "COMUNE DI FAVARA"

_HTML_PAGINA = """
<table>
<tr>
  <td>
    Ente Mittente <strong>COMUNE DI FAVARA</strong>
    Tipologia Atto <strong>DETERMINA DIRIGENZIALE</strong>
    <br><strong>Liquidazione fattura CIG A12345678B.</strong><br>
    in pubblicazione dal 07-07-2026 al 22-07-2026 (reg. 87)
    <a href="?IdMePubblica=1001">dettaglio</a>
  </td>
</tr>
<tr>
  <td>
    Ente Mittente <strong>ALTRO ENTE</strong>
    Tipologia Atto <strong>DELIBERA</strong>
    <br><strong>Atto di un altro ente ospitato sullo stesso albo.</strong><br>
    in pubblicazione dal 01-07-2026 al 16-07-2026
    <a href="?IdMePubblica=1002">dettaglio</a>
  </td>
</tr>
<tr>
  <td>
    Ente Mittente <strong>COMUNE DI FAVARA</strong>
    Tipologia Atto <strong>ORDINANZA</strong>
    <br><strong>Ordinanza senza CIG.</strong><br>
    in pubblicazione dal 05-07-2026 al 20-07-2026
    <a href="?IdMePubblica=1003">dettaglio</a>
  </td>
</tr>
</table>
"""

_HTML_SENZA_ATTI = "<table></table>"


# ---------------------------------------------------------------------------
# Test _parse_pagina
# ---------------------------------------------------------------------------


def test_parse_pagina_filtra_per_ente_mittente():
    atti, righe = _parse_pagina(_HTML_PAGINA, _BASE, _QS, _ISTAT, _ENTE)
    assert righe == 3
    assert len(atti) == 2  # scarta "ALTRO ENTE"


def test_parse_pagina_primo_atto():
    atti, _ = _parse_pagina(_HTML_PAGINA, _BASE, _QS, _ISTAT, _ENTE)
    a = atti[0]
    assert a.ente_codice_istat == _ISTAT
    assert a.tipo == "determina"
    assert a.oggetto == "Liquidazione fattura CIG A12345678B."
    assert a.cig == "A12345678B"
    assert a.data_pub == "2026-07-07"
    assert a.data_scadenza == "2026-07-22"
    assert a.numero == "87"
    assert "1001" in a.url_fonte
    assert a.fonte_scraper == FONTE_SCRAPER


def test_parse_pagina_secondo_atto_senza_cig():
    atti, _ = _parse_pagina(_HTML_PAGINA, _BASE, _QS, _ISTAT, _ENTE)
    a = atti[1]
    assert a.tipo == "ordinanza"
    assert a.cig is None
    assert a.numero is None


def test_parse_pagina_case_insensitive_ente():
    atti, _ = _parse_pagina(_HTML_PAGINA, _BASE, _QS, _ISTAT, "comune di favara")
    assert len(atti) == 2


def test_parse_pagina_html_vuoto():
    atti, righe = _parse_pagina(_HTML_SENZA_ATTI, _BASE, _QS, _ISTAT, _ENTE)
    assert atti == []
    assert righe == 0


# ---------------------------------------------------------------------------
# Test salva_atti
# ---------------------------------------------------------------------------


def _db():
    conn = connetti(":memory:")
    inizializza_db(conn)
    upsert_ente(
        conn,
        EnteMetadato(denominazione="Comune di Favara", codice_istat=_ISTAT, provincia="AG"),
    )
    return conn


def _atti_campione():
    atti, _ = _parse_pagina(_HTML_PAGINA, _BASE, _QS, _ISTAT, _ENTE)
    return atti


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
