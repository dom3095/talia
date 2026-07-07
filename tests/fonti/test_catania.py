"""Test offline per lo spider Catania URBI/Maggioli (TAL-49).

Nessuna chiamata di rete — fixture inline con la struttura reale del portale
(servizionline.comune.catania.it, dati anonimizzati).
"""

from __future__ import annotations

from talia.modulo2_scraping.db import connetti, conta_atti, inizializza_db
from talia.modulo2_scraping.fonti.catania import (
    CODICE_ISTAT,
    FONTE_SCRAPER,
    _parse_pagina,
    _tipo_da_tipologia,
    prepara_ente,
    salva_atti,
)


def _riga(id_pub: str, ente: str, tipologia: str, oggetto: str, reg: str) -> str:
    return f"""
 <tr>
  <td><span class="badge bg-success">In corso</span></td>
  <td>
Ente Mittente <strong>{ente}</strong>
<br>Tipologia Atto <strong>{tipologia}</strong>
<br><strong>{oggetto}</strong>
<br>in pubblicazione dal 07-07-2026 al 22-07-2026 (reg. {reg})
  </td>
  <td><button type="button"
   data-w3cbt-button-modale-url="ur1ME001.sto?StwEvent=91000302&IdMePubblica={id_pub}&x=1"
  >Pubblicazione</button></td>
 </tr>"""


_HTML_LISTA = (
    "<table><tr><th>Stato</th><th>Atti pubblicati</th><th>Visione</th></tr>"
    + _riga(
        "110044",
        "COMUNE DI CATANIA",
        "CATALOGO DEI DOCUMENTI/ORDINANZA CDS",
        "ORDINANZA DI PROVA CON CIG Z3A1B2C3D4. PROVVEDIMENTO TEMPORANEO.",
        "12040/2026",
    )
    + _riga(
        "110043",
        "COMUNE DI CATANIA",
        "DETERMINE DIRIGENZIALI",
        "DETERMINA DI PROVA SENZA CIG.",
        "12039/2026",
    )
    + _riga(
        "110042",
        "ALTRO ENTE DI PROVA",
        "CATALOGO DEI DOCUMENTI",
        "ATTO DI ALTRO ENTE OSPITATO SULL'ALBO.",
        "99/2026",
    )
    + "</table>"
)

_HTML_VUOTO = "<table><tr><th>Stato</th></tr></table>"

_HTML_CORROTTO = """
<table><tr><td>
 data-w3cbt-button-modale-url="ur1ME001.sto?IdMePubblica=110001"
 riga senza metadati né strong
</td></tr></table>
"""


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def test_parse_pagina_normale():
    atti, righe = _parse_pagina(_HTML_LISTA)
    assert righe == 3
    assert len(atti) == 2  # l'atto dell'altro ente è scartato
    a = atti[0]
    assert a.fonte_scraper == FONTE_SCRAPER
    assert a.ente_codice_istat == CODICE_ISTAT
    assert a.tipo == "ordinanza"
    assert a.numero == "12040/2026"
    assert a.data_pub == "2026-07-07"
    assert a.data_scadenza == "2026-07-22"
    assert a.cig == "Z3A1B2C3D4"
    assert "IdMePubblica=110044" in a.url_fonte
    assert atti[1].tipo == "determina"
    assert atti[1].cig is None


def test_parse_pagina_scarta_altri_enti():
    atti, _ = _parse_pagina(_HTML_LISTA)
    assert all("ALTRO ENTE" not in (a.oggetto or "") for a in atti)


def test_parse_pagina_zero_righe():
    atti, righe = _parse_pagina(_HTML_VUOTO)
    assert atti == [] and righe == 0


def test_parse_pagina_corrotta_non_solleva():
    """Riga con id ma senza metadati: conta come riga, non produce atti."""
    atti, righe = _parse_pagina(_HTML_CORROTTO)
    assert atti == [] and righe == 1


def test_tipo_da_tipologia():
    assert _tipo_da_tipologia("CATALOGO DEI DOCUMENTI/ORDINANZA CDS") == "ordinanza"
    assert _tipo_da_tipologia("DETERMINE DIRIGENZIALI") == "determina"
    assert _tipo_da_tipologia("BANDI DI GARA") == "bando"
    assert _tipo_da_tipologia("QUALCOSA DI IGNOTO") == "atto"


# ---------------------------------------------------------------------------
# Persistenza
# ---------------------------------------------------------------------------


def test_salva_atti_inserisce_e_deduplica(tmp_path):
    conn = connetti(tmp_path / "test.db")
    inizializza_db(conn)
    prepara_ente(conn)
    atti, _ = _parse_pagina(_HTML_LISTA)
    assert salva_atti(atti, conn) == {"inseriti": 2, "duplicati": 0}
    assert salva_atti(atti, conn) == {"inseriti": 0, "duplicati": 2}
    assert conta_atti(conn) == 2
