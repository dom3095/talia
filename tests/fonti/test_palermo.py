"""Test offline per lo spider Palermo SISPI (TAL-49).

Nessuna chiamata di rete — fixture inline con la struttura reale del portale
(albopretorio.comune.palermo.it, dati anonimizzati).
"""

from __future__ import annotations

from talia.modulo2_scraping.db import connetti, conta_atti, inizializza_db
from talia.modulo2_scraping.fonti.palermo import (
    CODICE_ISTAT,
    FONTE_SCRAPER,
    _parse_categorie,
    _parse_hidden,
    _parse_pagina,
    _parse_paginazione,
    prepara_ente,
    salva_atti,
)

_URL_LISTA = (
    "https://albopretorio.comune.palermo.it/albopretorio/pu/"
    "push-tabella-delibere.do?nomeTabella=FO_SCEDELIBEREAP&AP=AP&TD=2010"
)

# Struttura reale: riga header (th), riga conteggio (colspan), righe dati con
# link tabella-modifica.do e 6 celle.
_HTML_LISTA = """
<html><body>
<form action="/albopretorio/dbmanager/tabella-filtro.do">
<input type='hidden' name='siglaStato' value='L'/>
<input type='hidden' name='row' value=''/>
<input type='hidden' name='chiave' value=''/>
<input type='hidden' name='provieneDa' value=''/>
</form>
<table>
 <tr><th><div class='title_no_sort'>N.ro</div></th><th>Numero</th></tr>
 <tr><td colspan='6'>N.ro righe 654</td></tr>
 <tr>
  <td class='row_head'><a href='/albopretorio/dbmanager/tabella-modifica.do?row=0'>
<span>1</span></a></td>
  <td style='text-align: right;'>9901</td>
  <td style='text-align: left;'>07/07/2026</td>
  <td style='text-align: left;'>DETERMINA DI PROVA CON CIG Z3A1B2C3D4 PER SERVIZIO DI TEST;</td>
  <td style='text-align: left;'>07/07/2026</td>
  <td style='text-align: left;'>22/07/2026</td>
 </tr>
 <tr>
  <td class='row_head'><a href='/albopretorio/dbmanager/tabella-modifica.do?row=1'>
<span>2</span></a></td>
  <td style='text-align: right;'>9893</td>
  <td style='text-align: left;'>06/07/2026</td>
  <td style='text-align: left;'>SECONDA DETERMINA DI PROVA SENZA CIG;</td>
  <td style='text-align: left;'>06/07/2026</td>
  <td style='text-align: left;'>21/07/2026</td>
 </tr>
</table>
<div>pagina 1 di 66</div>
</body></html>
"""

_HTML_VUOTO = """
<html><body>
<table>
 <tr><th><div class='title_no_sort'>N.ro</div></th></tr>
</table>
<div>Nessun record presente.</div>
</body></html>
"""

_HTML_CORROTTO = """
<html><body><table><tr>
 <td class='row_head'><a href='/albopretorio/dbmanager/tabella-modifica.do?row=0'>1</a></td>
 <td>9901</td>
</tr></table>
"""

_HTML_SERVIZI = """
<div class='card'>
 <h5 class='card-title text-black'>DELIBERE</h5>
 <button onclick="location.href='../jsp/home.jsp?modo=info&info=scelta_tipo_documento.jsp\
&AP=AP&TD=10&SERCOD=7060'">
  <span>Accedi</span></button>
</div>
<div class='card'>
 <h5 class='card-title text-black'>DETERMINAZIONI DIRIGENZIALI</h5>
 <button onclick="location.href='../jsp/home.jsp?modo=info&info=scelta_tipo_documento.jsp\
&AP=AP&TD=20&SERCOD=7070'">
  <span>Accedi</span></button>
</div>
"""


# ---------------------------------------------------------------------------
# Parsing lista
# ---------------------------------------------------------------------------


def test_parse_pagina_normale():
    atti = _parse_pagina(_HTML_LISTA, _URL_LISTA, "determina")
    assert len(atti) == 2
    a = atti[0]
    assert a.numero == "9901"
    assert a.tipo == "determina"
    assert a.fonte_scraper == FONTE_SCRAPER
    assert a.ente_codice_istat == CODICE_ISTAT
    assert a.data_atto == "2026-07-07"
    assert a.data_pub == "2026-07-07"
    assert a.data_scadenza == "2026-07-22"
    assert a.cig == "Z3A1B2C3D4"
    assert a.url_fonte == f"{_URL_LISTA}#prot-9901"
    assert atti[1].cig is None


def test_parse_pagina_scarta_header_e_conteggio():
    """Header (th) e riga 'N.ro righe' non devono produrre atti."""
    atti = _parse_pagina(_HTML_LISTA, _URL_LISTA, "determina")
    assert all(a.numero in {"9901", "9893"} for a in atti)


def test_parse_pagina_zero_atti():
    assert _parse_pagina(_HTML_VUOTO, _URL_LISTA, "determina") == []


def test_parse_pagina_corrotta_non_solleva():
    """Riga con celle mancanti: scartata senza eccezioni."""
    assert _parse_pagina(_HTML_CORROTTO, _URL_LISTA, "determina") == []


# ---------------------------------------------------------------------------
# Paginazione e form
# ---------------------------------------------------------------------------


def test_parse_paginazione():
    assert _parse_paginazione(_HTML_LISTA) == (1, 66)
    assert _parse_paginazione(_HTML_VUOTO) == (1, 1)


def test_parse_hidden():
    hidden = _parse_hidden(_HTML_LISTA)
    assert hidden == {"siglaStato": "L", "row": "", "chiave": "", "provieneDa": ""}


# ---------------------------------------------------------------------------
# Scoperta categorie
# ---------------------------------------------------------------------------


def test_parse_categorie():
    cats = _parse_categorie(_HTML_SERVIZI)
    url_delibere = (
        "../jsp/home.jsp?modo=info&info=scelta_tipo_documento.jsp&AP=AP&TD=10&SERCOD=7060"
    )
    assert ("DELIBERE", url_delibere) in cats
    assert len(cats) == 2


# ---------------------------------------------------------------------------
# Persistenza
# ---------------------------------------------------------------------------


def test_salva_atti_inserisce_e_deduplica(tmp_path):
    conn = connetti(tmp_path / "test.db")
    inizializza_db(conn)
    prepara_ente(conn)
    atti = _parse_pagina(_HTML_LISTA, _URL_LISTA, "determina")
    esito = salva_atti(atti, conn)
    assert esito == {"inseriti": 2, "duplicati": 0}
    esito2 = salva_atti(atti, conn)
    assert esito2 == {"inseriti": 0, "duplicati": 2}
    assert conta_atti(conn) == 2


# ---------------------------------------------------------------------------
# Test parametrizzazione base_url
# ---------------------------------------------------------------------------


def test_prepara_ente_accetta_base_url_parametro(tmp_path):
    """Verifica che prepara_ente accetti il parametro base_url."""
    conn = connetti(tmp_path / "test.db")
    inizializza_db(conn)
    # Dovrebbe non sollevare
    prepara_ente(
        conn,
        base_url="http://test.example.com",
        codice_istat="999999",
        denominazione="Test Comune",
    )
    # L'importante è che non sollevi TypeError per parametri inaspettati
