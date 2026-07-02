"""Test red flag revoca in catena — TAL-44."""

from __future__ import annotations

import pytest

from talia.engine.catena import ricostruisci_catene
from talia.modulo2_scraping.db import (
    AttoMetadato,
    EnteMetadato,
    connetti,
    inizializza_db,
    inserisci_atto,
    upsert_ente,
)
from talia.modulo2_scraping.red_flags.catena_revoca import rileva_revoche_in_catena

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db():
    conn = connetti(":memory:")
    inizializza_db(conn)
    return conn


@pytest.fixture()
def ente_id(db):
    return upsert_ente(
        db,
        EnteMetadato(
            denominazione="Comune di Palma di Montechiaro",
            codice_istat="084028",
            provincia="AG",
        ),
    )


def _atto(url: str, **kw) -> AttoMetadato:
    return AttoMetadato(
        ente_codice_istat="084028",
        tipo=kw.get("tipo", "determina"),
        url_fonte=url,
        fonte_scraper="test",
        data_accesso="2025-12-22T00:00:00",
        **{k: v for k, v in kw.items() if k != "tipo"},
    )


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


def test_rileva_revoca_in_catena_da_cig(db, ente_id):
    inserisci_atto(
        db,
        _atto(
            "http://albo.ag/bando",
            tipo="bando",
            cig="AB1234567C",
            oggetto="Concorso pubblico 7 operatori esperti",
            data_atto="2025-07-01",
            testo_estratto="Bando di concorso pubblico per operatori esperti",
        ),
    )
    inserisci_atto(
        db,
        _atto(
            "http://albo.ag/revoca",
            tipo="determina",
            cig="AB1234567C",
            oggetto="Revoca concorso operatori",
            data_atto="2025-12-22",
            testo_estratto="Si revoca il bando di concorso pubblico per operatori esperti",
        ),
    )

    ricostruisci_catene(db)
    revoche = rileva_revoche_in_catena(db)

    assert len(revoche) == 1
    r = revoche[0]
    assert r.stato_finale == "revocato"
    assert r.cig == "AB1234567C"
    assert r.giorni_elapsed is not None and r.giorni_elapsed > 0
    assert any(a["ruolo"] == "avvio" for a in r.atti)
    assert any(a["ruolo"] == "revoca" for a in r.atti)


def test_rileva_annullamento_in_catena(db, ente_id):
    inserisci_atto(
        db,
        _atto(
            "http://albo.ag/bando2",
            tipo="bando",
            cig="ZZ0000000Z",
            oggetto="Procedura aperta servizi manutenzione",
            data_atto="2024-01-10",
            testo_estratto="Avviso pubblico procedura aperta CIG ZZ0000000Z",
        ),
    )
    inserisci_atto(
        db,
        _atto(
            "http://albo.ag/annullamento",
            tipo="determina",
            cig="ZZ0000000Z",
            oggetto="Annullamento gara manutenzione",
            data_atto="2024-06-15",
            testo_estratto="Si annulla la procedura aperta CIG ZZ0000000Z",
        ),
    )

    ricostruisci_catene(db)
    revoche = rileva_revoche_in_catena(db)

    assert any(r.stato_finale == "annullato" and r.cig == "ZZ0000000Z" for r in revoche)


def test_no_flag_senza_avvio(db, ente_id):
    """Un procedimento con solo revoca (senza avvio) non deve generare flag."""
    inserisci_atto(
        db,
        _atto(
            "http://albo.ag/solorevoca",
            tipo="determina",
            cig="XX1111111X",
            oggetto="Revoca procedura",
            data_atto="2024-09-01",
            testo_estratto="Si revoca la gara CIG XX1111111X",
        ),
    )

    ricostruisci_catene(db)
    revoche = rileva_revoche_in_catena(db)
    assert not any(r.cig == "XX1111111X" for r in revoche)


def test_no_flag_aggiudicazione_normale(db, ente_id):
    """Un procedimento completato regolarmente non deve generare flag revoca."""
    inserisci_atto(
        db,
        _atto(
            "http://albo.ag/bando_ok",
            tipo="bando",
            cig="OK2222222K",
            oggetto="Bando regolare con aggiudicazione",
            data_atto="2024-02-01",
            testo_estratto="Bando di gara procedura aperta CIG OK2222222K",
        ),
    )
    inserisci_atto(
        db,
        _atto(
            "http://albo.ag/aggiudicazione_ok",
            tipo="determina",
            cig="OK2222222K",
            oggetto="Aggiudicazione definitiva gara",
            data_atto="2024-08-01",
            testo_estratto="Aggiudicazione definitiva CIG OK2222222K",
        ),
    )

    ricostruisci_catene(db)
    revoche = rileva_revoche_in_catena(db)
    assert not any(r.cig == "OK2222222K" for r in revoche)


def test_db_senza_tabella_procedimenti_non_crasha(db):
    """Se procedimenti non esiste, rileva_revoche_in_catena ritorna lista vuota."""
    revoche = rileva_revoche_in_catena(db)
    assert revoche == []


def test_calcolo_giorni_elapsed(db, ente_id):
    inserisci_atto(
        db,
        _atto(
            "http://albo.ag/bando_d",
            tipo="bando",
            cig="DD4444444D",
            oggetto="BANDO DI CONCORSO PUBBLICO PER OPERATORI ESPERTI",
            data_atto="2025-01-01",
            testo_estratto="Bando di concorso pubblico CIG DD4444444D",
        ),
    )
    inserisci_atto(
        db,
        _atto(
            "http://albo.ag/revoca_d",
            tipo="determina",
            cig="DD4444444D",
            oggetto="REVOCA CONCORSO PUBBLICO OPERATORI ESPERTI",
            data_atto="2025-01-31",
            testo_estratto="Si revoca il bando CIG DD4444444D",
        ),
    )

    ricostruisci_catene(db)
    revoche = rileva_revoche_in_catena(db)
    r = next((x for x in revoche if x.cig == "DD4444444D"), None)
    assert r is not None
    assert r.giorni_elapsed == 30
