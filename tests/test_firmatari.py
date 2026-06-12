"""Test TAL-5: estrazione norme citate e firmatari."""

from talia.engine.firmatari import estrai_firmatari, estrai_norme, nome_normalizzato
from talia.engine.pdf_text import da_testo


def test_norme_articolo_e_legge():
    atto = da_testo("ai sensi dell'art. 21-nonies della L. 241/1990")
    valori = [str(e.valore) for e in estrai_norme(atto)]
    assert any("21-nonies" in v for v in valori)
    assert any("241/1990" in v.replace(" ", "") for v in valori)


def test_norme_dedup_contenute():
    # "art. 21" non deve comparire separato da "art. 21-nonies".
    atto = da_testo("art. 21-nonies L. 241/1990")
    testi = [e.testo_originale for e in estrai_norme(atto)]
    assert "art. 21-nonies" in " ".join(testi)
    assert "art. 21" not in [t.strip() for t in testi]


def test_firmatario_per_titolo_e_formula():
    atto = da_testo("Il Dirigente\nF.to Dott. Mario Rossi")
    firmatari = estrai_firmatari(atto)
    # Titolo e formula puntano allo stesso nome → un solo firmatario.
    assert [f.valore for f in firmatari] == ["Mario Rossi"]


def test_formula_minuscola_non_inventa_nomi():
    # Regressione: con IGNORECASE il nome non deve agganciare parole minuscole.
    atto = da_testo("documento firmato digitalmente ai sensi del CAD")
    assert estrai_firmatari(atto) == []


def test_nome_non_attraversa_il_newline():
    # Regressione: la riga successiva ("Il Segretario") non entra nel nome.
    atto = da_testo("F.to Dott. Mario Rossi\nIl Segretario Comunale")
    firmatari = estrai_firmatari(atto)
    assert [f.valore for f in firmatari] == ["Mario Rossi"]


def test_stopword_finale_rifilata():
    # "Il" maiuscolo subito dopo il cognome (stessa riga) non è parte del nome.
    atto = da_testo("F.to Dott. Mario Rossi Il quale attesta")
    firmatari = estrai_firmatari(atto)
    assert [f.valore for f in firmatari] == ["Mario Rossi"]
    # Lo span rifilato copre esattamente il nome.
    ent = firmatari[0]
    assert atto.testo[ent.offset_inizio:ent.offset_fine] == "Mario Rossi"


def test_nome_normalizzato_insensibile_ordine():
    assert nome_normalizzato("Mario Rossi") == nome_normalizzato("Rossi Mario")
    assert nome_normalizzato("Dott. Mario Rossi") == nome_normalizzato("ROSSI MARIO")
