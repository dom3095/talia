"""TAL-5 — Estrazione firmatari e norme citate.

Completa lo stadio 2 del motore con due estrazioni a supporto dei check:
- **norme citate**: alimentano l'esplicabilità (check 1 base giuridica) e le
  statistiche; include il riconoscimento di 21-quinquies / 21-nonies.
- **firmatari**: euristica deterministica basata su titoli onorifici e formule
  di sottoscrizione, usata dal check 6 (coerenza firmatari, TAL-9).

L'estrazione dei nomi è inevitabilmente euristica: serve sempre il disclaimer.
"""

from __future__ import annotations

import re

from .models import Entita, TestoAtto, TipoEntita

# ---------------------------------------------------------------------------
# Norme citate
# ---------------------------------------------------------------------------

# Numerali ordinali usati negli articoli di legge (art. 21-nonies, ecc.).
_SUFFISSI = (
    "bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies|undecies|duodecies"
)

# 1) Articolo con suffisso, anche senza prefisso "art." (es. "21-nonies").
_ART_SUFFISSO_RE = re.compile(
    rf"\b(?:art(?:icolo)?\.?\s*)?\d{{1,3}}\s*-\s*(?:{_SUFFISSI})\b", re.IGNORECASE
)

# 2) Articolo semplice: richiede la parola "art."/"articolo" per non agganciare
#    qualunque numero.
_ART_SEMPLICE_RE = re.compile(r"\bart(?:icolo)?\.?\s*\d{1,3}\b", re.IGNORECASE)

# 3) Riferimento a legge/decreto con numero/anno (D.lgs. 36/2023, L. 241/1990,
#    L.R. 12/2011, legge 190/2012, ...).
_LEGGE_RE = re.compile(
    r"\b(?:d\.?\s*lgs\.?|decreto\s+legislativo|d\.?\s*l\.?|l\.?\s*r\.?|legge|l\.)"
    r"\s*(?:n\.?\s*)?\d{1,4}\s*/\s*\d{2,4}\b",
    re.IGNORECASE,
)

_PATTERN_NORME = (_ART_SUFFISSO_RE, _ART_SEMPLICE_RE, _LEGGE_RE)


def estrai_norme(atto: TestoAtto) -> list[Entita]:
    """Riferimenti normativi citati nel testo (articoli e leggi/decreti).

    I duplicati e i match interamente contenuti in un altro (es. "art. 21"
    dentro "art. 21-nonies") vengono rimossi tenendo il più esteso.
    """
    grezzi: list[Entita] = []
    for pattern in _PATTERN_NORME:
        for m in pattern.finditer(atto.testo):
            grezzi.append(
                Entita(
                    tipo=TipoEntita.NORMA,
                    valore=_normalizza_norma(m.group(0)),
                    testo_originale=m.group(0),
                    offset_inizio=m.start(),
                    offset_fine=m.end(),
                    pagina=atto.pagina_per_offset(m.start()),
                )
            )
    return _rimuovi_contenuti(grezzi)


def _normalizza_norma(testo: str) -> str:
    return " ".join(testo.split())


def _rimuovi_contenuti(entita: list[Entita]) -> list[Entita]:
    """Elimina le entità il cui intervallo è contenuto in quello di un'altra."""
    # Ordina per ampiezza decrescente: i match più larghi "assorbono" i più piccoli.
    ordinate = sorted(entita, key=lambda e: e.offset_fine - e.offset_inizio, reverse=True)
    tenute: list[Entita] = []
    for e in ordinate:
        contenuta = any(
            t.offset_inizio <= e.offset_inizio and e.offset_fine <= t.offset_fine
            for t in tenute
        )
        if not contenuta:
            tenute.append(e)
    return sorted(tenute, key=lambda e: e.offset_inizio)


# ---------------------------------------------------------------------------
# Firmatari
# ---------------------------------------------------------------------------

# Titoli onorifici che tipicamente precedono il nome di un firmatario.
_TITOLI = r"Dott\.ssa|Dott\.|Dr\.|Ing\.|Avv\.|Arch\.|Geom\.|Rag\.|Prof\.|Sig\.ra|Sig\.|Cons\."

# Una parola di un nome proprio: iniziale maiuscola (anche accentata), resto
# lettere. Copre sia "Rossi" sia l'OCR in maiuscolo "ROSSI".
_PAROLA_NOME = r"[A-ZÀ-Ù][A-Za-zà-ùÀ-Ù']+"

# Nome = 2 o 3 parole proprie consecutive.
# Le parole del nome sono separate da spazi orizzontali: un newline chiude il
# nome (evita di agganciare l'inizio della riga successiva, es. "Il Segretario").
_NOME = rf"(?:{_PAROLA_NOME}[ \t]+){{1,2}}{_PAROLA_NOME}"

# 1) Titolo onorifico seguito dal nome.
_FIRMA_TITOLO_RE = re.compile(rf"(?:{_TITOLI})\s*(?P<nome>{_NOME})")

# 2) Formula di sottoscrizione (F.to / firmato / sottoscritto), con titolo opzionale.
# La formula è case-insensitive ma il nome resta case-sensitive — (?-i:...) —
# altrimenti qualunque sequenza di parole minuscole ("firmato digitalmente ai
# sensi...") verrebbe scambiata per un nome.
_FIRMA_FORMULA_RE = re.compile(
    rf"(?:F\.?to|firmato|sottoscritt[oa])\b[:\s]*(?:(?:{_TITOLI})\s*)?(?P<nome>(?-i:{_NOME}))",
    re.IGNORECASE,
)

# Parole con iniziale maiuscola che non possono chiudere un nome di persona
# (articoli/preposizioni/participi a inizio riga o frase dopo la firma).
_STOPWORD_FINALI = frozenset(
    {
        "Il", "Lo", "La", "Gli", "Le", "Un", "Una", "Uno",
        "Del", "Della", "Dello", "Dei", "Degli", "Delle",
        "Al", "Alla", "Allo", "Ai", "Agli", "Alle",
        "Per", "Con", "Ed", "Visto", "Vista", "Letto", "Atto",
    }
)
_RE_STOPWORD_FINALE = re.compile(
    r"[ \t]+(?:" + "|".join(_STOPWORD_FINALI) + r")$"
)


def _rifila_nome(grezzo: str) -> str:
    """Rimuove dalla coda del nome le parole maiuscole non-nome ("Il", "Del"…)."""
    while True:
        rifilato = _RE_STOPWORD_FINALE.sub("", grezzo)
        if rifilato == grezzo:
            return grezzo
        grezzo = rifilato

_PATTERN_FIRME = (_FIRMA_TITOLO_RE, _FIRMA_FORMULA_RE)


def estrai_firmatari(atto: TestoAtto) -> list[Entita]:
    """Firmatari riconosciuti per titolo onorifico o formula di sottoscrizione.

    Euristica: precisione privilegiata sul recall (meglio non segnalare che
    inventare un nome). L'offset punta al nome, non all'eventuale titolo.
    """
    trovati: list[Entita] = []
    visti: set[tuple[int, int]] = set()
    for pattern in _PATTERN_FIRME:
        for m in pattern.finditer(atto.testo):
            grezzo = _rifila_nome(m.group("nome"))
            # Dopo il rifilo servono ancora ≥ 2 parole per un nome plausibile.
            if len(grezzo.split()) < 2:
                continue
            # Lo span segue il rifilo: il nome è un prefisso del match originale.
            span = (m.start("nome"), m.start("nome") + len(grezzo))
            if span in visti:
                continue
            visti.add(span)
            nome = " ".join(grezzo.split())
            trovati.append(
                Entita(
                    tipo=TipoEntita.FIRMATARIO,
                    valore=nome,
                    testo_originale=m.group(0),
                    offset_inizio=span[0],
                    offset_fine=span[1],
                    pagina=atto.pagina_per_offset(span[0]),
                )
            )
    return sorted(trovati, key=lambda e: e.offset_inizio)


# Token dei titoli onorifici, da ignorare nel confronto tra nomi (forma già
# normalizzata: maiuscolo, senza punto finale).
_TITOLI_TOKEN = frozenset(
    {"DOTT", "DOTTSSA", "DR", "ING", "AVV", "ARCH", "GEOM", "RAG", "PROF", "SIG", "SIGRA", "CONS"}
)


def nome_normalizzato(nome: str) -> frozenset[str]:
    """Forma canonica di un nome per il confronto tra firmatari.

    Insensibile all'ordine (cognome-nome vs nome-cognome), al maiuscolo e ai
    titoli onorifici. Usata dal check 6 per stabilire se due atti hanno lo
    stesso firmatario.
    """
    token = {t.replace(".", "").strip("'").upper() for t in nome.split()}
    return frozenset(t for t in token if len(t) > 1 and t not in _TITOLI_TOKEN)
