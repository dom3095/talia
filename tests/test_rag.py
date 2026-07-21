"""Test RAG lessicale (BM25) sul corpus normativo — TAL-11."""

from __future__ import annotations

from pathlib import Path

from talia.engine.rag import IndiceCorpus


def _scrivi_corpus(tmp_path: Path) -> Path:
    cartella = tmp_path / "corpus"
    (cartella / "nazionale").mkdir(parents=True)
    (cartella / "ue").mkdir(parents=True)
    (cartella / "nazionale" / "l-241-1990.md").write_text(
        "# Legge 241/1990\n\n"
        "L'art. 21-quinquies disciplina la revoca del provvedimento per "
        "sopravvenuti motivi di pubblico interesse o mutamento della "
        "situazione di fatto.\n\n"
        "L'art. 21-nonies disciplina l'annullamento d'ufficio del "
        "provvedimento illegittimo, entro un termine ragionevole.",
        encoding="utf-8",
    )
    (cartella / "ue" / "gdpr-679-2016.md").write_text(
        "# Regolamento GDPR\n\n"
        "Il trattamento dei dati personali deve rispettare i principi di "
        "liceità, correttezza e trasparenza nei confronti dell'interessato.",
        encoding="utf-8",
    )
    return cartella


def test_indice_costruito_su_tutti_i_file_md(tmp_path):
    indice = IndiceCorpus(_scrivi_corpus(tmp_path))
    assert len(indice) == 2


def test_cerca_ritorna_il_passaggio_piu_pertinente(tmp_path):
    indice = IndiceCorpus(_scrivi_corpus(tmp_path))
    risultati = indice.cerca("revoca per sopravvenuti motivi di interesse pubblico", k=1)
    assert len(risultati) == 1
    assert risultati[0].fonte == "nazionale/l-241-1990.md"


def test_cerca_query_senza_termini_comuni_non_ritorna_nulla(tmp_path):
    indice = IndiceCorpus(_scrivi_corpus(tmp_path))
    risultati = indice.cerca("xyz qwerty asdf", k=3)
    assert risultati == []


def test_cerca_rispetta_il_k(tmp_path):
    indice = IndiceCorpus(_scrivi_corpus(tmp_path))
    risultati = indice.cerca("provvedimento dati personali trattamento", k=1)
    assert len(risultati) <= 1


def test_indice_su_cartella_vuota_non_crasha(tmp_path):
    vuota = tmp_path / "vuoto"
    vuota.mkdir()
    indice = IndiceCorpus(vuota)
    assert len(indice) == 0
    assert indice.cerca("qualsiasi cosa") == []
