"""Test TAL-13: estrazione attori (ruolo→nome) e riferimenti ad atti."""

from talia.engine.attori import estrai_attori, estrai_riferimenti_atti
from talia.engine.pdf_text import da_testo


def test_attore_ruolo_con_firmatario():
    atto = da_testo("Il Responsabile del Procedimento f.to: Dott. Pietro Amorosia")
    attori = estrai_attori(atto)
    assert ("Responsabile Del Procedimento", "Pietro Amorosia") in [
        (a.ruolo, a.nome) for a in attori
    ]


def test_attore_firma_digitale_maiuscola():
    atto = da_testo("Il Segretario Generale\nPIETRO NICOLA AMOROSIA / Provider S.A.")
    attori = estrai_attori(atto)
    segretari = [a for a in attori if a.ruolo == "Segretario Generale"]
    assert segretari and segretari[0].nome == "Pietro Nicola Amorosia"


def test_intestazione_maiuscola_non_e_nome():
    # "COMUNE DI ESEMPIO" non deve diventare il nome del Sindaco.
    atto = da_testo("Il Sindaco COMUNE DI ESEMPIO PROVINCIA")
    attori = estrai_attori(atto)
    sindaci = [a for a in attori if a.ruolo == "Sindaco"]
    assert sindaci and sindaci[0].nome is None


def test_ruolo_anonimo_scartato_se_esiste_con_nome():
    atto = da_testo(
        "Visto il parere del Segretario Generale.\n"
        "Il Segretario Generale F.to Dott.ssa Anna Bianchi"
    )
    attori = estrai_attori(atto)
    segretari = [a for a in attori if a.ruolo == "Segretario Generale"]
    assert len(segretari) == 1
    assert segretari[0].nome == "Anna Bianchi"


def test_riferimenti_atti_con_numero_e_data():
    atto = da_testo(
        "Vista la determinazione n. 35/2025; vista la deliberazione della "
        "Giunta Comunale n. 55 del 18/04/2024; vista la nota prot. n. 18443/2026 "
        "del 25/05/2026."
    )
    rif = estrai_riferimenti_atti(atto)
    chiavi = {r.chiave for r in rif}
    assert "determinazione 35/2025" in chiavi
    assert "deliberazione 55" in chiavi
    assert "nota 18443/2026" in chiavi
    con_data = {r.chiave: r.data for r in rif}
    assert con_data["deliberazione 55"] == "18/04/2024"


def test_numero_nudo_senza_etichetta_scartato():
    # "avviso 7" è troppo ambiguo: serve "n." o l'anno nel numero.
    atto = da_testo("come previsto dall'avviso 7 della procedura")
    assert estrai_riferimenti_atti(atto) == []


def test_riferimento_porta_offset_e_pagina():
    atto = da_testo("richiamata la determinazione n. 12 del 05/02/2022")
    rif = estrai_riferimenti_atti(atto)
    assert len(rif) == 1
    assert rif[0].pagina == 1
    assert "determinazione" in atto.testo[rif[0].offset_inizio : rif[0].offset_fine]
