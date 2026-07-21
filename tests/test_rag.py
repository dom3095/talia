"""Test RAG lessicale (BM25) sul corpus normativo — TAL-11."""

from __future__ import annotations

from pathlib import Path

from talia.engine.rag import _DIMENSIONE_CHUNK_MAX, IndiceCorpus


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


def test_offset_puntano_al_testo_esatto_nel_file_sorgente(tmp_path):
    # Riferimento puntuale (non un bare filename): offset_inizio/offset_fine
    # devono permettere di ritrovare il passaggio esatto nel file originale.
    cartella = _scrivi_corpus(tmp_path)
    indice = IndiceCorpus(cartella)
    risultati = indice.cerca("revoca per sopravvenuti motivi di interesse pubblico", k=1)
    passaggio = risultati[0]
    contenuto_file = (cartella / passaggio.fonte).read_text(encoding="utf-8")
    assert contenuto_file[passaggio.offset_inizio : passaggio.offset_fine] == passaggio.testo


def test_chunk_su_piu_paragrafi_ha_offset_del_primo_e_ultimo(tmp_path):
    cartella = _scrivi_corpus(tmp_path)
    indice = IndiceCorpus(cartella)
    passaggio = next(p for p in indice._passaggi if p.fonte == "nazionale/l-241-1990.md")
    contenuto_file = (cartella / passaggio.fonte).read_text(encoding="utf-8")
    assert passaggio.testo.startswith("# Legge 241/1990")
    assert passaggio.testo.endswith("termine ragionevole.")
    assert contenuto_file[passaggio.offset_inizio : passaggio.offset_fine] == passaggio.testo


def test_paragrafo_gigante_senza_righe_vuote_viene_comunque_spezzato(tmp_path):
    # Regressione: il corpus reale (scaricato da Normattiva/EUR-Lex) è spesso
    # un unico blocco di ~100k caratteri senza "\n\n". Senza lo split di
    # fallback, l'intero file diventerebbe un solo Passaggio: il ranking BM25
    # degraderebbe a corrispondenza per intero file e l'offset di citazione
    # coprirebbe l'intero documento (non più "puntuale" di un bare filename).
    cartella = tmp_path / "corpus"
    cartella.mkdir()
    blocco_unico = ("parola " * 20000).strip()  # ~140k caratteri, zero "\n\n"
    (cartella / "legge-gigante.md").write_text(blocco_unico, encoding="utf-8")

    indice = IndiceCorpus(cartella)
    assert len(indice) > 1
    for passaggio in indice._passaggi:
        assert len(passaggio.testo) <= _DIMENSIONE_CHUNK_MAX + 200
        assert blocco_unico[passaggio.offset_inizio : passaggio.offset_fine] == passaggio.testo
