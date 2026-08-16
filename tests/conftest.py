"""Fixture condivise tra i test."""

from __future__ import annotations

import pytest


@pytest.fixture
def pdf_minimo():
    """Genera i byte di un PDF nativo valido e minimo, senza dipendenze esterne.

    Serve a testare l'estrazione PDF reale (`estrai_testo`, pdfplumber) senza
    committare PDF veri (contengono nominativi, vietato da CLAUDE.md) né
    aggiungere una libreria di scrittura PDF solo per i test — un PDF 1.4 a
    una pagina con xref corretta è sufficiente perché pdfplumber lo apra.
    """

    def _crea(testo: str) -> bytes:
        oggetti = [
            b"<</Type/Catalog/Pages 2 0 R>>",
            b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
            b"<</Type/Page/Parent 2 0 R/Resources<</Font<</F1 4 0 R>>>>"
            b"/MediaBox[0 0 612 792]/Contents 5 0 R>>",
            b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
        ]
        stream = f"BT /F1 18 Tf 72 700 Td ({testo}) Tj ET".encode("latin-1")
        oggetti.append(b"<</Length %d>>\nstream\n" % len(stream) + stream + b"\nendstream")

        out = bytearray(b"%PDF-1.4\n")
        offset_oggetti = []
        for i, oggetto in enumerate(oggetti, start=1):
            offset_oggetti.append(len(out))
            out += f"{i} 0 obj".encode() + b"\n" + oggetto + b"\nendobj\n"

        offset_xref = len(out)
        out += f"xref\n0 {len(oggetti) + 1}\n".encode()
        out += b"0000000000 65535 f \n"
        for offset in offset_oggetti:
            out += f"{offset:010d} 00000 n \n".encode()
        out += f"trailer<</Size {len(oggetti) + 1}/Root 1 0 R>>\n".encode()
        out += f"startxref\n{offset_xref}\n%%EOF".encode()
        return bytes(out)

    return _crea
