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
from dataclasses import replace as dc_replace

from .models import Entita, TestoAtto, TipoEntita

# ---------------------------------------------------------------------------
# Norme citate
# ---------------------------------------------------------------------------

_SUFFISSI = (
    "bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies|undecies|duodecies"
)

# 1) Articolo con suffisso, anche senza prefisso "art." (es. "21-nonies").
#    Trattino opzionale: negli atti reali compare anche "21 nonies".
_ART_SUFFISSO_RE = re.compile(
    rf"\b(?:art(?:icolo)?\.?\s*)?\d{{1,3}}\s*-?\s*(?:{_SUFFISSI})\b", re.IGNORECASE
)

# 2) Articolo semplice: richiede la parola "art."/"articolo" per non agganciare
#    qualunque numero.
_ART_SEMPLICE_RE = re.compile(r"\bart(?:icolo)?\.?\s*\d{1,3}\b", re.IGNORECASE)

# 3) Riferimento a legge/decreto con numero/anno.
_LEGGE_RE = re.compile(
    r"\b(?:d\.?\s*lgs\.?|decreto\s+legislativo|d\.?\s*l\.?|l\.?\s*r\.?|legge|l\.)"
    r"\s*(?:n\.?\s*)?\d{1,4}\s*/\s*\d{2,4}\b",
    re.IGNORECASE,
)

# 4) Contratto collettivo nazionale: "CCNL comparto Funzioni Locali del 16.11.2022"
#    o "CCNL 16.11.2022". Fino a 5 parole-descrittore (sole lettere) prima della data.
_CCNL_RE = re.compile(
    r"\bCCNL\b(?:\s+[A-Za-zÀ-ùà-ù]+){0,5}\s+\d{2}[./]\d{2}[./]\d{4}",
    re.IGNORECASE,
)

# Filtro per "1-bis", "2-ter" senza prefisso "art." (riferimenti a commi, non ad articoli).
_BARE_COMMA_RE = re.compile(rf"^\d\s*-?\s*(?:{_SUFFISSI})\b", re.IGNORECASE)

# Distanza massima (caratteri) per ancorare un art. alla legge sullo stesso rigo.
_FINESTRA_ANCORAGGIO = 200


def estrai_norme(atto: TestoAtto) -> list[Entita]:
    """Riferimenti normativi citati nel testo, con ancoraggio contestuale.

    Strategia in tre passi:
    1. Estrae articoli con suffisso (21-quinquies ecc., self-explanatory) e leggi
       complete (D.Lgs. N/anno, L. N/anno, CCNL data).
    2. Per ogni articolo semplice (art. X) cerca la legge più vicina nella stessa
       riga (nessun newline tra loro, entro 200 caratteri); se trovata li fonde in
       "art. X [LEGGE]", altrimenti scarta l'articolo (troppo vago).
    3. Rimuove span contenuti in altri, poi deduplicà per valore normalizzato.
    """
    testo = atto.testo

    # -- Passo 1: norme "assolute" (self-contained) --
    arts_suffisso: list[Entita] = []
    for m in _ART_SUFFISSO_RE.finditer(testo):
        norm = _normalizza_norma(m.group(0))
        if _BARE_COMMA_RE.match(norm):
            continue  # "1-bis" senza art. = riferimento a comma, non norma
        arts_suffisso.append(_entita(m, atto))

    leggi_refs: list[Entita] = [
        _entita(m, atto)
        for pattern in (_LEGGE_RE, _CCNL_RE)
        for m in pattern.finditer(testo)
    ]

    # -- Passo 2: articoli semplici ancorati alla legge più vicina --
    arts_ancorati: list[Entita] = []
    for m in _ART_SEMPLICE_RE.finditer(testo):
        e = _entita(m, atto)
        legge = _trova_legge_vicina(e, leggi_refs, testo)
        if legge:
            arts_ancorati.append(dc_replace(e, valore=f"{e.valore} {legge.valore}"))
        # senza legge vicina → scartato ("art. 13 di cosa?")

    # -- Passo 3: pulizia --
    tutti = arts_suffisso + leggi_refs + arts_ancorati
    return _deduplica_per_valore(_rimuovi_contenuti(tutti))


def _entita(m: re.Match, atto: TestoAtto) -> Entita:
    return Entita(
        tipo=TipoEntita.NORMA,
        valore=_normalizza_norma(m.group(0)),
        testo_originale=m.group(0),
        offset_inizio=m.start(),
        offset_fine=m.end(),
        pagina=atto.pagina_per_offset(m.start()),
    )


def _trova_legge_vicina(art: Entita, leggi: list[Entita], testo: str) -> Entita | None:
    """Restituisce la legge più vicina nella stessa riga (nessun newline tra loro)."""
    migliore: Entita | None = None
    dist_min = _FINESTRA_ANCORAGGIO + 1
    for legge in leggi:
        if legge.offset_fine <= art.offset_inizio:
            dist = art.offset_inizio - legge.offset_fine
            testo_tra = testo[legge.offset_fine : art.offset_inizio]
        elif legge.offset_inizio >= art.offset_fine:
            dist = legge.offset_inizio - art.offset_fine
            testo_tra = testo[art.offset_fine : legge.offset_inizio]
        else:
            continue
        if dist <= _FINESTRA_ANCORAGGIO and "\n" not in testo_tra and dist < dist_min:
            dist_min = dist
            migliore = legge
    return migliore


def _normalizza_norma(testo: str) -> str:
    return " ".join(testo.split())


def _rimuovi_contenuti(entita: list[Entita]) -> list[Entita]:
    """Elimina le entità il cui intervallo è contenuto in quello di un'altra."""
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


def _deduplica_per_valore(entita: list[Entita]) -> list[Entita]:
    """Mantiene la prima occorrenza per ogni valore normalizzato (case-insensitive)."""
    visti: dict[str, Entita] = {}
    for e in sorted(entita, key=lambda e: e.offset_inizio):
        k = " ".join(e.valore.upper().split())
        if k not in visti:
            visti[k] = e
    return list(visti.values())


# ---------------------------------------------------------------------------
# Firmatari
# ---------------------------------------------------------------------------

_TITOLI = r"Dott\.ssa|Dott\.|Dr\.|Ing\.|Avv\.|Arch\.|Geom\.|Rag\.|Prof\.|Sig\.ra|Sig\.|Cons\."
_PAROLA_NOME = r"[A-ZÀ-Ù][A-Za-zà-ùÀ-Ù']+"
_NOME = rf"(?:{_PAROLA_NOME}[ \t]+){{1,2}}{_PAROLA_NOME}"

_FIRMA_TITOLO_RE = re.compile(rf"(?:{_TITOLI})\s*(?P<nome>{_NOME})")
_FIRMA_FORMULA_RE = re.compile(
    rf"(?:F\.?to|firmato|sottoscritt[oa])\b[:\s]*(?:(?:{_TITOLI})\s*)?(?P<nome>(?-i:{_NOME}))",
    re.IGNORECASE,
)

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
    """Firmatari riconosciuti per titolo onorifico o formula di sottoscrizione."""
    trovati: list[Entita] = []
    visti: set[tuple[int, int]] = set()
    for pattern in _PATTERN_FIRME:
        for m in pattern.finditer(atto.testo):
            grezzo = _rifila_nome(m.group("nome"))
            if len(grezzo.split()) < 2:
                continue
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


_TITOLI_TOKEN = frozenset(
    {"DOTT", "DOTTSSA", "DR", "ING", "AVV", "ARCH", "GEOM", "RAG", "PROF", "SIG", "SIGRA", "CONS"}
)


def nome_normalizzato(nome: str) -> frozenset[str]:
    """Forma canonica di un nome: insensibile a ordine, maiuscolo e titoli."""
    token = {t.replace(".", "").strip("'").upper() for t in nome.split()}
    return frozenset(t for t in token if len(t) > 1 and t not in _TITOLI_TOKEN)
