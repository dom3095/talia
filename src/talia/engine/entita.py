"""TAL-4 — Estrazione entità deterministiche: date, importi, CIG, CUP.

Stadio 2 del motore. Regex per pattern rigidi del dominio amministrativo italiano.
Ogni entità conserva valore normalizzato, testo originale, offset e pagina, così
da essere sempre risalibile alla fonte (esplicabilità).

Le regex sono documentate inline con la motivazione e, dove rilevante, la fonte
del formato (es. specifiche ANAC per CIG/CUP).
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from .models import Entita, EntitaEstratte, TestoAtto, TipoEntita

# ---------------------------------------------------------------------------
# Date
# ---------------------------------------------------------------------------

# Mesi italiani → numero. Inclusi sia minuscolo che eventuale iniziale maiuscola
# (il match è case-insensitive, la chiave è in minuscolo).
_MESI = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}

# Data numerica: gg/mm/aaaa con separatore / - o . e anno a 4 cifre.
# Anno a 4 cifre per non confondere date con numeri di protocollo (es. 12/345).
_DATA_NUMERICA_RE = re.compile(
    r"\b(?P<g>0?[1-9]|[12]\d|3[01])[/\-.](?P<m>0?[1-9]|1[0-2])[/\-.](?P<a>\d{4})\b"
)

# Data testuale: "12 giugno 2026", "1° marzo 2024". L'indicatore ordinale (°/º)
# è opzionale.
_DATA_TESTUALE_RE = re.compile(
    r"\b(?P<g>0?[1-9]|[12]\d|3[01])[°º]?\s+(?P<mese>"
    + "|".join(_MESI)
    + r")\s+(?P<a>\d{4})\b",
    re.IGNORECASE,
)


def _entita(
    tipo: TipoEntita, valore: object, match: re.Match, atto: TestoAtto
) -> Entita:
    """Costruisce un'Entita da un match, agganciandola a offset e pagina."""
    return Entita(
        tipo=tipo,
        valore=valore,
        testo_originale=match.group(0),
        offset_inizio=match.start(),
        offset_fine=match.end(),
        pagina=atto.pagina_per_offset(match.start()),
    )


def estrai_date(atto: TestoAtto) -> list[Entita]:
    """Date in formato numerico e testuale, normalizzate a `datetime.date`.

    Le date di calendario non valide (es. 31/02) vengono scartate: quasi sempre
    sono falsi positivi (numeri di protocollo, codici).
    """
    trovate: list[Entita] = []

    for m in _DATA_NUMERICA_RE.finditer(atto.testo):
        valore = _data_valida(int(m["a"]), int(m["m"]), int(m["g"]))
        if valore is not None:
            trovate.append(_entita(TipoEntita.DATA, valore, m, atto))

    for m in _DATA_TESTUALE_RE.finditer(atto.testo):
        mese = _MESI[m["mese"].lower()]
        valore = _data_valida(int(m["a"]), mese, int(m["g"]))
        if valore is not None:
            trovate.append(_entita(TipoEntita.DATA, valore, m, atto))

    return trovate


def _data_valida(anno: int, mese: int, giorno: int) -> date | None:
    try:
        return date(anno, mese, giorno)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Importi in euro
# ---------------------------------------------------------------------------

# Numero in convenzione italiana: punto = separatore migliaia, virgola = decimali.
# - forma con migliaia: 1.234, 1.234.567 (gruppi di 3)
# - forma semplice: 500, 12345
# - decimali opzionali: ,56  ,5
_NUM_IT = r"(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{1,2})?"

# Un importo è qualificato dal simbolo/parola euro (prima o dopo il numero):
# evita di scambiare numeri qualsiasi per importi.
_IMPORTO_RE = re.compile(
    rf"(?:(?:€|\beuro\b)\s*(?P<pre>{_NUM_IT}))|(?:(?P<post>{_NUM_IT})\s*(?:€|\beuro\b))",
    re.IGNORECASE,
)


def estrai_importi(atto: TestoAtto) -> list[Entita]:
    """Importi in euro normalizzati a `Decimal`."""
    trovati: list[Entita] = []
    for m in _IMPORTO_RE.finditer(atto.testo):
        grezzo = m["pre"] or m["post"]
        valore = _normalizza_importo(grezzo)
        if valore is not None:
            trovati.append(_entita(TipoEntita.IMPORTO, valore, m, atto))
    return trovati


def _normalizza_importo(grezzo: str) -> Decimal | None:
    # Rimuove i separatori delle migliaia, converte la virgola decimale in punto.
    normalizzato = grezzo.replace(".", "").replace(",", ".")
    try:
        return Decimal(normalizzato)
    except InvalidOperation:
        return None


# ---------------------------------------------------------------------------
# CIG e CUP (codici ANAC)
# ---------------------------------------------------------------------------

# CIG (Codice Identificativo Gara, ANAC): 10 caratteri alfanumerici. Si richiede
# l'etichetta "CIG" nelle vicinanze per non confondere il codice con numeri di
# protocollo o altri token di 10 caratteri.
_CIG_RE = re.compile(r"\bCIG\b[\s:.\-n°]*([0-9A-Za-z]{10})\b", re.IGNORECASE)

# CUP (Codice Unico di Progetto): 15 caratteri alfanumerici, il primo è una
# lettera. Anche qui si pretende l'etichetta "CUP".
_CUP_RE = re.compile(r"\bCUP\b[\s:.\-n°]*([A-Za-z][0-9A-Za-z]{14})\b", re.IGNORECASE)


def estrai_cig(atto: TestoAtto) -> list[Entita]:
    """Codici CIG (10 alfanumerici) etichettati, normalizzati in maiuscolo."""
    trovati: list[Entita] = []
    for m in _CIG_RE.finditer(atto.testo):
        codice = m.group(1).upper()
        trovati.append(
            Entita(
                tipo=TipoEntita.CIG,
                valore=codice,
                testo_originale=m.group(0),
                offset_inizio=m.start(1),
                offset_fine=m.end(1),
                pagina=atto.pagina_per_offset(m.start(1)),
            )
        )
    return trovati


def estrai_cup(atto: TestoAtto) -> list[Entita]:
    """Codici CUP (15 alfanumerici, iniziale alfabetica) etichettati."""
    trovati: list[Entita] = []
    for m in _CUP_RE.finditer(atto.testo):
        codice = m.group(1).upper()
        trovati.append(
            Entita(
                tipo=TipoEntita.CUP,
                valore=codice,
                testo_originale=m.group(0),
                offset_inizio=m.start(1),
                offset_fine=m.end(1),
                pagina=atto.pagina_per_offset(m.start(1)),
            )
        )
    return trovati


# ---------------------------------------------------------------------------
# Orchestrazione
# ---------------------------------------------------------------------------


def estrai_entita(atto: TestoAtto) -> EntitaEstratte:
    """Estrae tutte le entità da un atto: base (TAL-4) + giuridiche (TAL-5).

    L'import di `firmatari` è locale per evitare cicli e tenere TAL-4 autonomo.
    """
    from .firmatari import estrai_firmatari, estrai_norme

    risultato = EntitaEstratte()
    risultato.aggiungi(*estrai_date(atto))
    risultato.aggiungi(*estrai_importi(atto))
    risultato.aggiungi(*estrai_cig(atto))
    risultato.aggiungi(*estrai_cup(atto))
    risultato.aggiungi(*estrai_norme(atto))
    risultato.aggiungi(*estrai_firmatari(atto))
    return risultato
