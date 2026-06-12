"""Test TAL-3: costruzione di TestoAtto e mapping testo→pagina."""

from talia.engine.models import FonteTesto
from talia.engine.pdf_text import _fonte_complessiva, da_pagine, da_testo


def test_da_pagine_offset_e_pagine():
    atto = da_pagine(["prima pagina", "seconda pagina"])
    assert len(atto.pagine) == 2
    # La prima pagina inizia a 0; la seconda dopo testo + separatore.
    assert atto.pagine[0].offset_inizio == 0
    assert atto.pagine[0].offset_fine == len("prima pagina")
    # Il testo della pagina coincide con la fetta di testo agli offset dichiarati.
    p2 = atto.pagine[1]
    assert atto.testo[p2.offset_inizio:p2.offset_fine] == "seconda pagina"


def test_pagina_per_offset():
    atto = da_pagine(["aaa", "bbb"])
    assert atto.pagina_per_offset(0) == 1
    assert atto.pagina_per_offset(atto.pagine[1].offset_inizio) == 2
    # Offset oltre il testo → nessuna pagina.
    assert atto.pagina_per_offset(10_000) is None


def test_estratto_compatta_spazi():
    atto = da_testo("Il   testo\ncon   spazi")
    estratto = atto.estratto(0, 2, contesto=100)
    assert "  " not in estratto
    assert "Il testo con spazi" == estratto


def test_fonte_complessiva():
    assert _fonte_complessiva([]) == FonteTesto.NATIVO
    assert _fonte_complessiva([FonteTesto.NATIVO]) == FonteTesto.NATIVO
    assert _fonte_complessiva([FonteTesto.OCR]) == FonteTesto.OCR
    assert _fonte_complessiva([FonteTesto.NATIVO, FonteTesto.OCR]) == FonteTesto.MISTO
