"""TAL-3 — Estrazione testo da PDF (nativo + OCR).

Stadio 1 del motore. Gestisce sia i PDF digitali (testo nativo) sia le scansioni
(immagini) tramite OCR Tesseract. Conserva il mapping testo→pagina richiesto per
l'esplicabilità delle citazioni.

Le dipendenze pesanti (`pdfplumber`, `pytesseract`) sono importate in modo lazy:
il core del motore (entità, checklist, report) resta utilizzabile e testabile
anche senza di esse, lavorando su `TestoAtto` costruiti da testo già disponibile
(`da_pagine` / `da_testo`).
"""

from __future__ import annotations

from pathlib import Path

from .models import FonteTesto, PaginaTesto, TestoAtto

# Separatore tra pagine nel testo concatenato. Un carattere singolo mantiene gli
# offset semplici da calcolare e da spiegare.
SEPARATORE_PAGINA = "\n"

# Sotto questa soglia di caratteri "utili" una pagina è considerata una scansione
# (PDF immagine) e si tenta l'OCR. Valore empirico: un atto reale ha centinaia di
# caratteri per pagina; una pagina quasi vuota di testo nativo è quasi sempre
# un'immagine.
SOGLIA_CARATTERI_NATIVI = 20

LINGUA_OCR_DEFAULT = "ita"


def da_pagine(
    pagine: list[str],
    *,
    fonte: FonteTesto = FonteTesto.NATIVO,
    percorso: str | None = None,
    metadati: dict[str, str] | None = None,
) -> TestoAtto:
    """Costruisce un `TestoAtto` da una lista di testi-pagina già disponibili.

    Non richiede dipendenze esterne: utile per i test e per gli atti forniti già
    come testo (es. campioni `.txt` anonimizzati in `data/samples/`).
    """
    parti: list[str] = []
    oggetti_pagina: list[PaginaTesto] = []
    offset = 0
    for i, testo_pagina in enumerate(pagine, start=1):
        inizio = offset
        fine = inizio + len(testo_pagina)
        oggetti_pagina.append(
            PaginaTesto(
                numero=i,
                testo=testo_pagina,
                offset_inizio=inizio,
                offset_fine=fine,
                fonte=fonte,
            )
        )
        parti.append(testo_pagina)
        # Il separatore occupa spazio negli offset ma non appartiene a nessuna
        # pagina: lo si salta avanzando l'offset.
        offset = fine + len(SEPARATORE_PAGINA)

    return TestoAtto(
        testo=SEPARATORE_PAGINA.join(parti),
        pagine=oggetti_pagina,
        fonte=fonte,
        percorso=percorso,
        metadati=metadati or {},
    )


def da_testo(testo: str, **kwargs) -> TestoAtto:
    """`TestoAtto` mono-pagina da una stringa. Comodità per test e snippet."""
    return da_pagine([testo], **kwargs)


def _ocr_pagina(pagina, lingua: str) -> str:
    """OCR di una singola pagina pdfplumber tramite Tesseract.

    Import lazy: solleva un errore chiaro se le dipendenze OCR mancano.
    """
    try:
        import pytesseract
    except ImportError as exc:  # pragma: no cover - dipende dall'ambiente
        raise RuntimeError(
            "OCR richiesto ma pytesseract non è installato. "
            "Installa gli extra: pip install -e '.[pdf]' e assicurati che "
            "Tesseract sia presente nel sistema (con la lingua 'ita')."
        ) from exc

    # Render della pagina a immagine e OCR. resolution=300 è un buon compromesso
    # qualità/velocità per documenti amministrativi scansionati.
    immagine = pagina.to_image(resolution=300).original
    return pytesseract.image_to_string(immagine, lang=lingua)


def estrai_testo(
    percorso: str | Path,
    *,
    lingua_ocr: str = LINGUA_OCR_DEFAULT,
    soglia_caratteri: int = SOGLIA_CARATTERI_NATIVI,
) -> TestoAtto:
    """Estrae il testo da un PDF, con fallback OCR per le pagine-immagine.

    Per ogni pagina: prova l'estrazione nativa; se il testo è troppo scarso
    (pagina probabilmente scansionata) ricorre all'OCR Tesseract in italiano.
    La fonte risultante è NATIVO, OCR o MISTO a seconda delle pagine.
    """
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover - dipende dall'ambiente
        raise RuntimeError(
            "Estrazione PDF richiesta ma pdfplumber non è installato. "
            "Installa gli extra: pip install -e '.[pdf]'."
        ) from exc

    percorso = Path(percorso)
    testi_pagina: list[str] = []
    fonti_pagina: list[FonteTesto] = []

    with pdfplumber.open(percorso) as pdf:
        for pagina in pdf.pages:
            testo_nativo = pagina.extract_text() or ""
            if len(testo_nativo.strip()) >= soglia_caratteri:
                testi_pagina.append(testo_nativo)
                fonti_pagina.append(FonteTesto.NATIVO)
            else:
                testo_ocr = _ocr_pagina(pagina, lingua_ocr)
                testi_pagina.append(testo_ocr)
                fonti_pagina.append(FonteTesto.OCR)

    fonte_complessiva = _fonte_complessiva(fonti_pagina)

    # Riutilizza da_pagine per il calcolo offset, poi riassegna la fonte per
    # pagina (da_pagine assume una fonte uniforme).
    atto = da_pagine(testi_pagina, fonte=fonte_complessiva, percorso=str(percorso))
    atto.pagine = [
        PaginaTesto(
            numero=p.numero,
            testo=p.testo,
            offset_inizio=p.offset_inizio,
            offset_fine=p.offset_fine,
            fonte=fonti_pagina[i],
        )
        for i, p in enumerate(atto.pagine)
    ]
    return atto


def _fonte_complessiva(fonti: list[FonteTesto]) -> FonteTesto:
    insieme = set(fonti)
    if not insieme or insieme == {FonteTesto.NATIVO}:
        return FonteTesto.NATIVO
    if insieme == {FonteTesto.OCR}:
        return FonteTesto.OCR
    return FonteTesto.MISTO
