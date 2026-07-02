"""Test motore catena di eventi — TAL-43."""

from __future__ import annotations

import pytest

from talia.engine.catena import (
    CatenaEventi,
    classifica_ruolo,
    collega_per_cig,
    collega_per_oggetto_simile,
    costruisci_catena_da_testi,
    estrai_riferimenti,
    ricostruisci_catene,
)
from talia.modulo2_scraping.db import (
    AttoMetadato,
    EnteMetadato,
    connetti,
    inizializza_db,
    inserisci_atto,
    upsert_ente,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db():
    conn = connetti(":memory:")
    inizializza_db(conn)
    return conn


@pytest.fixture()
def ente_ag(db):
    return upsert_ente(
        db,
        EnteMetadato(
            denominazione="Comune di Palma di Montechiaro",
            codice_istat="084028",
            provincia="AG",
        ),
    )


def _atto(istat: str, url: str, **kw) -> AttoMetadato:
    return AttoMetadato(
        ente_codice_istat=istat,
        tipo=kw.get("tipo", "determina"),
        url_fonte=url,
        fonte_scraper="test",
        data_accesso="2025-01-10T00:00:00",
        **{k: v for k, v in kw.items() if k != "tipo"},
    )


# ---------------------------------------------------------------------------
# classifica_ruolo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "testo,tipo,atteso",
    [
        ("Si revoca il bando di concorso pubblico per 7 operatori esperti", "determina", "revoca"),
        ("Si annulla la procedura aperta n.3/2024", "determina", "annullamento"),
        ("Avviso pubblico per manifestazione d'interesse", "avviso", "avvio"),
        ("Bando di concorso pubblico per operatori esperti", "bando", "avvio"),
        ("Aggiudicazione definitiva della gara CIG XY12345678", "", "aggiudicazione"),
        ("Rettifica bando: modifica art. 5", "avviso", "modifica"),
        ("Proroga termini presentazione domande", "determina", "proroga"),
        ("Liquidazione fattura n.120 fornitore ABC", "determina", "altro"),
    ],
)
def test_classifica_ruolo(testo, tipo, atteso):
    assert classifica_ruolo(testo, tipo) == atteso


def test_classifica_ruolo_priorita_revoca_su_avvio():
    # Un testo che cita "bando" ma nel contesto di revoca → ruolo = revoca
    testo = "Si revoca il bando di concorso pubblico per operatori esperti (art. 21-nonies)"
    assert classifica_ruolo(testo) == "revoca"


def test_classifica_ruolo_solo_oggetto_senza_testo():
    # Caso M2: testo_estratto è NULL, ma oggetto già basta come proxy
    assert classifica_ruolo(oggetto="REVOCA CONCORSO PUBBLICO 7 OPERATORI ESPERTI") == "revoca"
    assert classifica_ruolo(oggetto="ANNULLAMENTO GARA PULIZIE UFFICI") == "annullamento"
    assert classifica_ruolo(oggetto="BANDO SELEZIONE PUBBLICA OPERATORI") == "avvio"
    assert classifica_ruolo(oggetto="AGGIUDICAZIONE DEFINITIVA SERVIZIO MENSA") == "aggiudicazione"


# ---------------------------------------------------------------------------
# estrai_riferimenti
# ---------------------------------------------------------------------------


def test_estrai_riferimenti_cig():
    testo = "La gara con CIG AB1234567C è stata aggiudicata."
    refs = estrai_riferimenti(testo)
    cig_refs = [r for r in refs if r.tipo == "cig"]
    assert len(cig_refs) == 1
    assert cig_refs[0].valore == "AB1234567C"


def test_estrai_riferimenti_numero_atto():
    testo = "Si revoca la determina n.35 del 22/12/2025 approvata dal RUP."
    refs = estrai_riferimenti(testo)
    num_refs = [r for r in refs if r.tipo == "numero_atto"]
    assert any("35" in r.valore for r in num_refs)


def test_estrai_riferimenti_cup():
    testo = "Progetto CUP J89H20000120006 avviato nel 2024."
    refs = estrai_riferimenti(testo)
    cup_refs = [r for r in refs if r.tipo == "cup"]
    assert len(cup_refs) == 1
    assert cup_refs[0].valore == "J89H20000120006"


def test_estrai_riferimenti_vuoto():
    assert estrai_riferimenti("Testo senza riferimenti specifici.") == []


# ---------------------------------------------------------------------------
# collega_per_cig
# ---------------------------------------------------------------------------


def test_collega_per_cig_crea_procedimento(db, ente_ag):
    from talia.engine.catena import _evolvi_schema

    _evolvi_schema(db)

    inserisci_atto(
        db,
        _atto(
            "084028",
            "http://albo.ag/bando1",
            tipo="bando",
            cig="AB1234567C",
            oggetto="Bando concorso operatori",
            data_atto="2025-07-01",
            testo_estratto="Bando di concorso pubblico per 7 operatori esperti",
        ),
    )
    inserisci_atto(
        db,
        _atto(
            "084028",
            "http://albo.ag/revoca1",
            tipo="determina",
            cig="AB1234567C",
            oggetto="Revoca concorso operatori",
            data_atto="2025-12-22",
            testo_estratto="Si revoca il bando di concorso pubblico CIG AB1234567C",
        ),
    )

    proc_id = collega_per_cig(db, "AB1234567C")

    assert proc_id is not None
    proc = db.execute("SELECT * FROM procedimenti WHERE id=?", (proc_id,)).fetchone()
    assert proc["stato_finale"] == "revocato"
    assert proc["cig"] == "AB1234567C"

    atti_collegati = db.execute(
        "SELECT id, ruolo_in_catena FROM atti WHERE procedimento_id=? ORDER BY id", (proc_id,)
    ).fetchall()
    assert len(atti_collegati) == 2
    ruoli = {a["ruolo_in_catena"] for a in atti_collegati}
    assert "avvio" in ruoli
    assert "revoca" in ruoli


def test_collega_per_cig_idempotente(db, ente_ag):
    from talia.engine.catena import _evolvi_schema

    _evolvi_schema(db)
    inserisci_atto(
        db,
        _atto(
            "084028",
            "http://albo.ag/bando2",
            cig="ZZ9999999Z",
            testo_estratto="Bando di concorso pubblico",
            data_atto="2025-01-01",
        ),
    )
    proc_id_1 = collega_per_cig(db, "ZZ9999999Z")
    proc_id_2 = collega_per_cig(db, "ZZ9999999Z")
    assert proc_id_1 == proc_id_2
    n_proc = db.execute("SELECT COUNT(*) FROM procedimenti WHERE cig='ZZ9999999Z'").fetchone()[0]
    assert n_proc == 1


def test_collega_per_cig_solo_metadati_senza_testo(db, ente_ag):
    """Caso M2 realistico: testo_estratto NULL, classificazione da oggetto."""
    from talia.engine.catena import _evolvi_schema

    _evolvi_schema(db)
    inserisci_atto(
        db,
        _atto(
            "084028",
            "http://albo.ag/bando_meta",
            tipo="bando",
            cig="MM5555555M",
            oggetto="BANDO DI CONCORSO PUBBLICO PER 7 OPERATORI ESPERTI",
            data_atto="2025-07-01",
            # testo_estratto assente: PDF non scaricato
        ),
    )
    inserisci_atto(
        db,
        _atto(
            "084028",
            "http://albo.ag/revoca_meta",
            tipo="determina",
            cig="MM5555555M",
            oggetto="REVOCA CONCORSO PUBBLICO PER 7 OPERATORI ESPERTI",
            data_atto="2025-12-22",
            # testo_estratto assente
        ),
    )

    proc_id = collega_per_cig(db, "MM5555555M")
    assert proc_id is not None

    proc = db.execute("SELECT stato_finale FROM procedimenti WHERE id=?", (proc_id,)).fetchone()
    assert proc["stato_finale"] == "revocato"

    ruoli = {
        r["ruolo_in_catena"]
        for r in db.execute(
            "SELECT ruolo_in_catena FROM atti WHERE procedimento_id=?", (proc_id,)
        ).fetchall()
    }
    assert "avvio" in ruoli
    assert "revoca" in ruoli


def test_collega_per_cig_cig_inesistente(db, ente_ag):
    from talia.engine.catena import _evolvi_schema

    _evolvi_schema(db)
    assert collega_per_cig(db, "XXXXXXXXXX") is None


# ---------------------------------------------------------------------------
# collega_per_oggetto_simile
# ---------------------------------------------------------------------------


def test_collega_per_oggetto_simile(db, ente_ag):
    from talia.engine.catena import _evolvi_schema

    _evolvi_schema(db)

    inserisci_atto(
        db,
        _atto(
            "084028",
            "http://albo.ag/bando3",
            tipo="bando",
            oggetto="SELEZIONE PUBBLICA OPERATORI ESPERTI COMUNI SICILIANI",
            data_atto="2025-04-01",
            testo_estratto="Bando di concorso pubblico per operatori esperti",
        ),
    )
    inserisci_atto(
        db,
        _atto(
            "084028",
            "http://albo.ag/revoca3",
            tipo="determina",
            oggetto="REVOCA SELEZIONE PUBBLICA OPERATORI ESPERTI COMUNI SICILIANI",
            data_atto="2025-11-01",
            testo_estratto="Si revoca il concorso pubblico per operatori esperti",
        ),
    )

    n = collega_per_oggetto_simile(db, ente_ag)
    assert n >= 1

    n_proc = db.execute(
        "SELECT COUNT(*) FROM procedimenti WHERE ente_id=?", (ente_ag,)
    ).fetchone()[0]
    assert n_proc >= 1

    proc = db.execute(
        "SELECT stato_finale FROM procedimenti WHERE ente_id=? ORDER BY id DESC LIMIT 1",
        (ente_ag,),
    ).fetchone()
    assert proc["stato_finale"] == "revocato"


# ---------------------------------------------------------------------------
# ricostruisci_catene (orchestratore)
# ---------------------------------------------------------------------------


def test_ricostruisci_catene(db, ente_ag):
    inserisci_atto(
        db,
        _atto(
            "084028",
            "http://albo.ag/bando4",
            tipo="bando",
            cig="CC3333333C",
            oggetto="Bando gara servizi",
            data_atto="2024-03-01",
            testo_estratto="Avviso pubblico per procedura aperta CIG CC3333333C",
        ),
    )
    inserisci_atto(
        db,
        _atto(
            "084028",
            "http://albo.ag/agg4",
            tipo="determina",
            cig="CC3333333C",
            oggetto="Aggiudicazione gara servizi",
            data_atto="2024-09-01",
            testo_estratto="Aggiudicazione definitiva gara CIG CC3333333C",
        ),
    )

    risultato = ricostruisci_catene(db, ente_id=ente_ag)

    assert risultato["n_procedimenti_da_cig"] >= 1
    assert risultato["n_atti_collegati_totale"] >= 2


# ---------------------------------------------------------------------------
# costruisci_catena_da_testi (fascicolo M1)
# ---------------------------------------------------------------------------


def test_costruisci_catena_da_testi_revoca():
    testi = [
        {
            "testo": "Bando di concorso pubblico per 7 operatori esperti.",
            "tipo": "bando",
            "data": "2025-07-01",
            "percorso": "BANDO7OPERATORIESPERTI.pdf",
        },
        {
            "testo": "Si revoca il concorso pubblico per operatori esperti in autotutela.",
            "tipo": "determina",
            "data": "2025-12-22",
            "percorso": "revoca_concorso_autotutela.pdf",
        },
    ]
    catena = costruisci_catena_da_testi(testi)

    assert isinstance(catena, CatenaEventi)
    assert catena.stato_finale == "revocato"
    assert len(catena.eventi) == 2
    assert catena.eventi[0].ruolo == "avvio"
    assert catena.eventi[1].ruolo == "revoca"


def test_costruisci_catena_da_testi_aggiudicazione():
    testi = [
        {"testo": "Bando gara CIG AB1234567C", "tipo": "bando", "data": "2024-01-10"},
        {
            "testo": "Aggiudicazione definitiva gara CIG AB1234567C",
            "tipo": "determina",
            "data": "2024-06-01",
        },
    ]
    catena = costruisci_catena_da_testi(testi)
    assert catena.stato_finale == "aggiudicato"
    assert catena.cig == "AB1234567C"


def test_costruisci_catena_ordinamento_cronologico():
    testi = [
        {"testo": "Si revoca il bando.", "data": "2025-12-01"},
        {"testo": "Bando di concorso pubblico.", "data": "2025-03-01"},
    ]
    catena = costruisci_catena_da_testi(testi)
    assert catena.eventi[0].data == "2025-03-01"
    assert catena.eventi[1].data == "2025-12-01"
