"""Test TAL-3: costruzione di TestoAtto e mapping testo→pagina."""

import pytest

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


def test_estrai_testo_pdf_nativo(tmp_path, pdf_minimo):
    # Prima di questo test `estrai_testo` (il cuore di TAL-3: OCR (Tesseract) →
    # estrazione testo PDF) non era mai stata chiamata su un vero PDF in nessun
    # test — solo indirettamente via CLI su fixture .txt, che non passano da
    # pdfplumber. Un PDF reale non può essere committato (nominativi, vietato
    # da CLAUDE.md); questo PDF minimo (fixture `pdf_minimo`, senza dipendenze
    # esterne) copre almeno il ramo nativo, non quello OCR (gap noto, TAL-3).
    pytest.importorskip("pdfplumber", reason="extra 'pdf' non installato")
    from talia.engine.pdf_text import estrai_testo

    percorso = tmp_path / "atto.pdf"
    percorso.write_bytes(pdf_minimo("Determina di indizione concorso pubblico"))

    atto = estrai_testo(percorso)

    assert "Determina di indizione concorso pubblico" in atto.testo
    assert atto.fonte == FonteTesto.NATIVO


def _pdf_scansione(percorso, righe: list[str]) -> None:
    """PDF di sola immagine (nessun livello di testo), come una scansione.

    Generato al volo invece che committato: un PDF reale scansionato conterrebbe
    nominativi (vietato da CLAUDE.md), e un'immagine sintetica esercita lo
    stesso ramo di `estrai_testo` — pagina senza testo nativo → Tesseract.
    """
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("L", (1700, 2200), color=255)  # A4 a ~200 dpi
    disegno = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=56)
    for i, riga in enumerate(righe):
        disegno.text((150, 200 + i * 110), riga, fill=0, font=font)
    img.save(percorso, "PDF", resolution=200)


def test_estrai_testo_scansione_via_ocr(tmp_path):
    """Chiude il gap di TAL-3: il ramo OCR provato su un PDF vero, non solo su mock."""
    import shutil

    pytest.importorskip("pdfplumber", reason="extra 'pdf' non installato")
    pytest.importorskip("pytesseract", reason="extra 'ocr' non installato")
    pytest.importorskip("PIL", reason="Pillow non installato")
    if shutil.which("tesseract") is None:
        pytest.skip("binario tesseract non installato")
    from talia.engine.pdf_text import estrai_testo

    percorso = tmp_path / "scansione.pdf"
    _pdf_scansione(
        percorso,
        ["COMUNE DI ESEMPIO", "DETERMINAZIONE DIRIGENZIALE", "Revoca in autotutela del bando"],
    )

    atto = estrai_testo(percorso)

    assert atto.fonte == FonteTesto.OCR
    assert atto.pagine[0].fonte == FonteTesto.OCR
    testo = atto.testo.upper()
    for parola in ("COMUNE", "DETERMINAZIONE", "DIRIGENZIALE", "REVOCA", "AUTOTUTELA"):
        assert parola in testo
