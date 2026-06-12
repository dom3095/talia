#!/usr/bin/env python3
"""TAL-13 — Report attori e procedimenti di un fascicolo (uso interno).

Per ogni atto del fascicolo stampa:
- gli **attori** (ruolo istituzionale → nome) estratti deterministicamente;
- i **procedimenti/atti citati** (tipo, numero, data) → catena del fascicolo;
- (se spaCy è installato) le entità **NER** PER/ORG non già coperte dalle
  regex: servono a scoprire pattern da promuovere a regole deterministiche.

⚠️ L'output contiene nomi reali (dato personale): solo uso locale/interno,
mai committarlo né pubblicarlo (wiki/09).

Uso:
    python scripts/estrai_attori.py data/samples/1/
    python scripts/estrai_attori.py atto1.pdf atto2.pdf
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

from talia.engine.attori import estrai_attori, estrai_riferimenti_atti
from talia.engine.firmatari import nome_normalizzato
from talia.engine.models import TestoAtto
from talia.engine.pdf_text import da_pagine, estrai_testo

_ESTENSIONI = {".pdf", ".txt"}
# Modelli spaCy italiani in ordine di preferenza (lg = qualità, sm = fallback).
_MODELLI_SPACY = ("it_core_news_lg", "it_core_news_md", "it_core_news_sm")


def _carica(percorso: Path) -> TestoAtto:
    if percorso.suffix.lower() == ".pdf":
        return estrai_testo(percorso)
    return da_pagine([percorso.read_text(encoding="utf-8")], percorso=percorso.name)


def _carica_spacy():
    """Carica il primo modello spaCy disponibile, o None con spiegazione."""
    try:
        import spacy
    except ImportError:
        print("ℹ️  spaCy non installato: salto il livello NER.")
        print("   Per abilitarlo: pip install -e '.[nlp]'")
        print("   poi: python -m spacy download it_core_news_lg")
        return None
    for nome in _MODELLI_SPACY:
        try:
            nlp = spacy.load(nome)
            print(f"ℹ️  NER spaCy attivo (modello: {nome})")
            return nlp
        except OSError:
            continue
    print("ℹ️  spaCy installato ma nessun modello italiano trovato: salto il NER.")
    print("   Scaricane uno: python -m spacy download it_core_news_lg")
    return None


def _ner_extra(nlp, atto: TestoAtto, nomi_noti: set[frozenset[str]]) -> list[tuple[str, str]]:
    """Entità PER/ORG di spaCy non già trovate dalle regex (pattern discovery)."""
    extra: list[tuple[str, str]] = []
    visti: set[str] = set()
    doc = nlp(atto.testo)
    for ent in doc.ents:
        if ent.label_ not in {"PER", "ORG"}:
            continue
        chiave = " ".join(ent.text.split())
        if chiave in visti or len(chiave) < 4:
            continue
        visti.add(chiave)
        # Filtro anti-rumore (i modelli generici inciampano nel lessico
        # giuridico): servono ≥2 parole, non tutte in maiuscolo pieno
        # (intestazioni), e la prima con l'iniziale maiuscola.
        token = chiave.split()
        if len(token) < 2 or all(t.isupper() for t in token):
            continue
        if not token[0][0].isupper():
            continue
        if ent.label_ == "PER" and nome_normalizzato(chiave) in nomi_noti:
            continue  # già estratto deterministicamente
        extra.append((ent.label_, chiave))
    return extra


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1

    file: list[Path] = []
    for grezzo in argv:
        p = Path(grezzo)
        if p.is_dir():
            file.extend(sorted(f for f in p.iterdir() if f.suffix.lower() in _ESTENSIONI))
        elif p.suffix.lower() in _ESTENSIONI:
            file.append(p)
    if not file:
        print("Nessun file .pdf/.txt trovato.", file=sys.stderr)
        return 1

    nlp = _carica_spacy()
    print()

    presenze_attori: Counter[tuple[str, str]] = Counter()  # (nome, ruolo) → n. atti
    presenze_riferimenti: Counter[str] = Counter()  # chiave riferimento → n. atti

    for percorso in file:
        atto = _carica(percorso)
        attori = estrai_attori(atto)
        riferimenti = estrai_riferimenti_atti(atto)

        print(f"═══ {percorso.name} ═══")
        print("  Attori:")
        if not attori:
            print("    (nessuno riconosciuto)")
        for a in attori:
            nome = a.nome or "(nome non identificato)"
            print(f"    • {a.ruolo}: {nome}  [p. {a.pagina}, offset {a.offset_inizio}]")
            if a.nome:
                presenze_attori[(a.nome, a.ruolo)] += 1

        print("  Procedimenti/atti citati:")
        if not riferimenti:
            print("    (nessuno)")
        chiavi_in_questo_atto = set()
        for r in riferimenti:
            data = f" del {r.data}" if r.data else ""
            print(f"    • {r.tipo} n. {r.numero}{data}  [p. {r.pagina}]")
            chiavi_in_questo_atto.add(r.chiave)
        for chiave in chiavi_in_questo_atto:
            presenze_riferimenti[chiave] += 1

        if nlp is not None:
            nomi_noti = {nome_normalizzato(a.nome) for a in attori if a.nome}
            extra = _ner_extra(nlp, atto, nomi_noti)
            if extra:
                print("  NER spaCy (non coperte dalle regex — candidate a nuove regole):")
                for label, testo in extra[:15]:
                    print(f"    ◦ [{label}] {testo}")
        print()

    # Pattern tra atti: ricorrenze.
    ricorrenti_attori = {k: v for k, v in presenze_attori.items() if v > 1}
    ricorrenti_rif = {k: v for k, v in presenze_riferimenti.items() if v > 1}
    if ricorrenti_attori or ricorrenti_rif:
        print("═══ Pattern nel fascicolo ═══")
        for (nome, ruolo), n in sorted(ricorrenti_attori.items(), key=lambda x: -x[1]):
            print(f"  • {nome} ({ruolo}) compare in {n} atti")
        for chiave, n in sorted(ricorrenti_rif.items(), key=lambda x: -x[1]):
            print(f"  • riferimento «{chiave}» citato in {n} atti")

    print("\n⚠️  Dati personali: output a solo uso interno, non pubblicare.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
