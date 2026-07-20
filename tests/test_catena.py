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
        ("Liquidazione fattura n.120 fornitore ABC", "determina", "liquidazione"),
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


def test_collega_per_cig_data_atto_null_usa_data_pub(db, ente_ag):
    """Regressione: su jCityGov (piattaforma dominante nel DB, 76% degli atti)
    `data_atto` è sempre NULL — solo `data_pub` è popolato. Prima del fix,
    `collega_per_cig` calcolava data_avvio/data_chiusura solo da `data_atto`:
    per queste catene restavano sempre NULL, rompendo a valle qualunque check
    che ne dipende (revoca_in_catena, riapertura_dopo_revoca, dashboard)."""
    from talia.engine.catena import _evolvi_schema

    _evolvi_schema(db)

    inserisci_atto(
        db,
        _atto(
            "084028",
            "http://albo.ag/bando1",
            tipo="bando",
            cig="AB1234567D",
            oggetto="Bando concorso operatori",
            data_atto=None,
            data_pub="2025-07-01",
            testo_estratto="Bando di concorso pubblico per 7 operatori esperti",
        ),
    )
    inserisci_atto(
        db,
        _atto(
            "084028",
            "http://albo.ag/revoca1",
            tipo="determina",
            cig="AB1234567D",
            oggetto="Revoca concorso operatori",
            data_atto=None,
            data_pub="2025-12-22",
            testo_estratto="Si revoca il bando di concorso pubblico CIG AB1234567D",
        ),
    )

    proc_id = collega_per_cig(db, "AB1234567D")

    proc = db.execute("SELECT * FROM procedimenti WHERE id=?", (proc_id,)).fetchone()
    assert proc["data_avvio"] == "2025-07-01"
    assert proc["data_chiusura"] == "2025-12-22"


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

    n_proc = db.execute("SELECT COUNT(*) FROM procedimenti WHERE ente_id=?", (ente_ag,)).fetchone()[
        0
    ]
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


# ---------------------------------------------------------------------------
# Nuovi pattern: affidamento e liquidazione
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "oggetto,atteso",
    [
        ("AFFIDAMENTO DIRETTO AI SENSI DELL'ART. 50 COMMA 1", "aggiudicazione"),
        ("AFFIDAMENTO INCARICO DI PROGETTAZIONE DEFINITIVA ED ESECUTIVA", "aggiudicazione"),
        ("DETERMINAZIONE A CONTRATTARE E AFFIDAMENTO DEI SERVIZI", "aggiudicazione"),
        ("LIQUIDAZIONE FATTURE N. 330/2026 DEL 01.06.2026", "liquidazione"),
        ("Liquidazione fattura n. FPA 4/26 del 28/05/2026", "liquidazione"),
        ("LIQUIDAZIONE 3 SAL INTERVENTO RECUPERO CASTELLO", "liquidazione"),
    ],
)
def test_classifica_ruolo_nuovi_pattern(oggetto, atteso):
    assert classifica_ruolo(oggetto=oggetto) == atteso


def test_stato_finale_concluso_con_liquidazione(db, ente_ag):
    """Una catena avvio → liquidazione deve risultare 'concluso'."""
    from talia.engine.catena import _evolvi_schema

    _evolvi_schema(db)
    inserisci_atto(
        db,
        _atto(
            "084028",
            "http://albo/bando1",
            cig="ZZ9999999Z",
            oggetto="BANDO GARA SERVIZI PULIZIA",
            data_atto="2025-01-10",
        ),
    )
    inserisci_atto(
        db,
        _atto(
            "084028",
            "http://albo/liq1",
            cig="ZZ9999999Z",
            oggetto="LIQUIDAZIONE FATTURA N.55/2025 SERVIZI PULIZIA",
            data_atto="2025-06-20",
        ),
    )

    proc_id = collega_per_cig(db, "ZZ9999999Z")
    assert proc_id is not None
    proc = db.execute("SELECT stato_finale FROM procedimenti WHERE id=?", (proc_id,)).fetchone()
    assert proc["stato_finale"] == "concluso"


# ---------------------------------------------------------------------------
# classifica_ruolo_llm — fallback senza Ollama
# ---------------------------------------------------------------------------


def test_classifica_ruolo_llm_fallback_senza_ollama():
    """Senza Ollama raggiungibile deve restituire 'altro' senza eccezioni."""
    from talia.engine.catena import classifica_ruolo_llm

    risultato = classifica_ruolo_llm(
        "ATTO GENERICO NON CLASSIFICABILE",
        modello="llama3.2",
        base_url="http://localhost:19999",  # porta inesistente
        timeout=2,
    )
    assert risultato == "altro"


def test_aggiorna_sconosciuti_con_llm_skip_senza_ollama(db, ente_ag):
    """aggiorna_sconosciuti_con_llm deve returnare 0 senza crashare se Ollama è assente."""
    from talia.engine.catena import _evolvi_schema, aggiorna_sconosciuti_con_llm

    _evolvi_schema(db)
    n = aggiorna_sconosciuti_con_llm(
        db,
        modello="llama3.2",
        base_url="http://localhost:19999",
        limite=10,
    )
    assert n == 0


# ---------------------------------------------------------------------------
# TAL-46 — Strategia contenimento + guard-rail gemelli
# Oggetti reali dall'albo di Palma di Montechiaro (titoli pubblici, nessun
# dato personale): 3 selezioni interne gemelle + 3 revoche in autotutela.
# ---------------------------------------------------------------------------

_BOILERPLATE = (
    "PER PROGRESSIONE TRA LE AREE (VERTICALI) “IN DEROGA” RISERVATA AL PERSONALE "
    "DIPENDENTE DEL COMUNE DI AI SENSI DELL’ART. 13 C. 6, 7 E 8 CCNL 16.11.2022 "
)
OGG_AVVIO_B = (
    "APPROVAZIONE AVVISO DI SELEZIONE E MODELLO ISTANZA PER SELEZIONE INTERNA "
    + _BOILERPLATE
    + "PER N. 7 (SETTE) PASSAGGI DALL’AREA DEGLI OPERATORI ALL’AREA DEGLI "
    "OPERATORI ESPERTI (EX CAT. B)"
)
OGG_AVVIO_C = (
    "APPROVAZIONE AVVISO DI SELEZIONE E MODELLO ISTANZA PER SELEZIONE INTERNA "
    + _BOILERPLATE
    + "PER N. 7 (SETTE) PASSAGGI DALL’AREA DEGLI OPERATORI ESPERTI ALL’AREA "
    "DEGLI ISTRUTTORI (EX CAT. C)."
)
OGG_AVVIO_D = (
    "APPROVAZIONE AVVISO DI SELEZIONE E MODELLO ISTANZA PER SELEZIONE INTERNA "
    + _BOILERPLATE
    + "PER N. 3 (TRE) PASSAGGI DALL’AREA DEGLI ISTRUTTORI ALL'AREA DEI "
    "FUNZIONARI ED ELEVATA QUALIFICAZIONE (EX CAT. D)."
)
OGG_REVOCA_B = (
    "REVOCA IN AUTOTUTELA DELL'AVVISO DI SELEZIONE INTERNA APPROVATO CON "
    "PROPRIA DETERMINAZIONE N. 33/2025, "
    + _BOILERPLATE
    + "PER N. 7 (SETTE) PASSAGGI DALL’AREA DEGLI OPERATORI ALL’AREA DEGLI "
    "OPERATORI ESPERTI (EX CAT. B)"
)
OGG_REVOCA_C = (
    "REVOCA IN AUTOTUTELA DELL'AVVISO DI SELEZIONE INTERNA APPROVATO CON "
    "PROPRIA DETERMINAZIONE N. 34/2025, "
    + _BOILERPLATE
    + "PER N. 7 (SETTE) PASSAGGI DALL’AREA DEGLI OPERATORI ESPERTI ALL’AREA "
    "DEGLI ISTRUTTORI (EX CAT. C)."
)
# Caso reale: la revoca della selezione D cita "N. 33/2025" (numero SBAGLIATO,
# copia-incolla del comune) ma incorpora il titolo giusto → il contenimento
# deve collegarla comunque all'avvio D.
OGG_REVOCA_D = (
    "REVOCA IN AUTOTUTELA DELL'AVVISO DI SELEZIONE INTERNA APPROVATO CON "
    "PROPRIA DETERMINAZIONE N. 33/2025, "
    + _BOILERPLATE
    + "PER N. 3 (TRE) PASSAGGI DALL’AREA DEGLI ISTRUTTORI ALL'AREA DEI "
    "FUNZIONARI ED ELEVATA QUALIFICAZIONE (EX CAT. D) E DELLA RELATIVA "
    "PROCEDURA CONCORSUALE"
)


def _inserisci_caso_palma(db):
    coppie = [
        ("http://albo/avvio_b", OGG_AVVIO_B, "2025-12-22"),
        ("http://albo/avvio_c", OGG_AVVIO_C, "2025-12-22"),
        ("http://albo/avvio_d", OGG_AVVIO_D, "2025-12-22"),
        ("http://albo/revoca_b", OGG_REVOCA_B, "2026-05-28"),
        ("http://albo/revoca_c", OGG_REVOCA_C, "2026-05-28"),
        ("http://albo/revoca_d", OGG_REVOCA_D, "2026-05-28"),
    ]
    for url, oggetto, data in coppie:
        inserisci_atto(db, _atto("084028", url, oggetto=oggetto, data_atto=data))


def test_classifica_ruolo_avviso_di_selezione():
    assert classifica_ruolo(oggetto=OGG_AVVIO_B) == "avvio"
    assert classifica_ruolo(oggetto="SELEZIONE INTERNA PER PROGRESSIONE VERTICALE") == "avvio"
    # la revoca contiene anche "avviso di selezione", ma vince la revoca
    assert classifica_ruolo(oggetto=OGG_REVOCA_B) == "revoca"


def test_estrai_riferimenti_forme_estese():
    refs = estrai_riferimenti("REVOCA APPROVATO CON PROPRIA DETERMINAZIONE N. 33/2025, PER…")
    num = [r for r in refs if r.tipo == "numero_atto"]
    assert any("33" in r.valore for r in num)

    refs2 = estrai_riferimenti("Vista la deliberazione n. 55 del 18/04/2024 della Giunta")
    assert any(r.tipo == "numero_atto" and "55" in r.valore for r in refs2)


def test_oggetto_contenuto_suffisso():
    from talia.engine.catena import _oggetto_contenuto

    assert _oggetto_contenuto(OGG_REVOCA_B, OGG_AVVIO_B) > 0
    assert _oggetto_contenuto(OGG_REVOCA_B, OGG_AVVIO_C) == 0  # gemello: coda diversa
    assert _oggetto_contenuto(OGG_REVOCA_D, OGG_AVVIO_D) > 0  # coda extra nel derivato
    # oggetti troppo corti: mai collegare
    assert _oggetto_contenuto("REVOCA AVVISO PUBBLICO", "AVVISO PUBBLICO") == 0


def test_collega_per_contenimento_caso_palma(db, ente_ag):
    """I 6 atti reali devono produrre 3 catene distinte avvio→revoca."""
    from talia.engine.catena import _evolvi_schema, collega_per_contenimento

    _evolvi_schema(db)
    _inserisci_caso_palma(db)

    n = collega_per_contenimento(db, ente_ag)
    assert n == 3

    procs = db.execute(
        "SELECT id, stato_finale, metodo_individuazione FROM procedimenti WHERE ente_id=?",
        (ente_ag,),
    ).fetchall()
    assert len(procs) == 3
    assert all(p["stato_finale"] == "revocato" for p in procs)
    assert all(p["metodo_individuazione"] == "contenimento_oggetto" for p in procs)

    # ogni procedimento ha esattamente un avvio e una revoca
    for p in procs:
        ruoli = sorted(
            r["ruolo_in_catena"]
            for r in db.execute(
                "SELECT ruolo_in_catena FROM atti WHERE procedimento_id=?", (p["id"],)
            ).fetchall()
        )
        assert ruoli == ["avvio", "revoca"]

    # la revoca col numero citato sbagliato (33/2025) è agganciata all'avvio D
    revoca_d = db.execute(
        "SELECT procedimento_id FROM atti WHERE url_fonte='http://albo/revoca_d'"
    ).fetchone()
    avvio_d = db.execute(
        "SELECT procedimento_id FROM atti WHERE url_fonte='http://albo/avvio_d'"
    ).fetchone()
    assert revoca_d["procedimento_id"] == avvio_d["procedimento_id"]


def test_collega_per_contenimento_data_atto_null_usa_data_pub(db, ente_ag):
    """Stessa regressione di test_collega_per_cig_data_atto_null_usa_data_pub,
    ma per la strategia di contenimento (quella usata dal caso reale Palma
    692→703 in TAL-48): con data_atto sempre NULL (jCityGov), data_avvio e
    data_chiusura del procedimento non devono restare NULL."""
    from talia.engine.catena import _evolvi_schema, collega_per_contenimento

    _evolvi_schema(db)
    inserisci_atto(
        db,
        _atto(
            "084028",
            "http://albo/avvio_x",
            oggetto="AFFIDAMENTO SERVIZIO SORVEGLIANZA SANITARIA ANNO 2025",
            data_atto=None,
            data_pub="2025-01-10",
        ),
    )
    inserisci_atto(
        db,
        _atto(
            "084028",
            "http://albo/revoca_x",
            oggetto="ANNULLAMENTO AFFIDAMENTO SERVIZIO SORVEGLIANZA SANITARIA ANNO 2025",
            data_atto=None,
            data_pub="2025-06-20",
        ),
    )

    n = collega_per_contenimento(db, ente_ag)
    assert n == 1

    proc = db.execute(
        "SELECT data_avvio, data_chiusura FROM procedimenti WHERE ente_id=?", (ente_ag,)
    ).fetchone()
    assert proc["data_avvio"] == "2025-01-10"
    assert proc["data_chiusura"] == "2025-06-20"


def test_collega_per_contenimento_idempotente(db, ente_ag):
    from talia.engine.catena import _evolvi_schema, collega_per_contenimento

    _evolvi_schema(db)
    _inserisci_caso_palma(db)
    assert collega_per_contenimento(db, ente_ag) == 3
    assert collega_per_contenimento(db, ente_ag) == 0  # già tutti assegnati
    n_proc = db.execute("SELECT COUNT(*) FROM procedimenti").fetchone()[0]
    assert n_proc == 3


def test_collega_per_contenimento_ambiguo_skip(db, ente_ag):
    """Revoca cumulativa che incorpora due bandi distinti → nessun collegamento."""
    from talia.engine.catena import _evolvi_schema, collega_per_contenimento

    _evolvi_schema(db)
    bando_a = "BANDO GARA FORNITURA ARREDI SCOLASTICI PLESSO MATTARELLA ANNO 2025"
    bando_b = "BANDO GARA FORNITURA DERRATE ALIMENTARI MENSA SCOLASTICA ANNO 2025"
    inserisci_atto(db, _atto("084028", "http://albo/ba", oggetto=bando_a, data_atto="2025-01-01"))
    inserisci_atto(db, _atto("084028", "http://albo/bb", oggetto=bando_b, data_atto="2025-01-02"))
    inserisci_atto(
        db,
        _atto(
            "084028",
            "http://albo/rev_cum",
            oggetto=f"REVOCA IN AUTOTUTELA DEI BANDI: {bando_a} E {bando_b}",
            data_atto="2025-06-01",
        ),
    )

    assert collega_per_contenimento(db, ente_ag) == 0
    assert db.execute("SELECT COUNT(*) FROM procedimenti").fetchone()[0] == 0


def test_guard_rail_gemelli_no_merge_fuzzy(db, ente_ag):
    """Tre avvisi gemelli (stesso boilerplate, aree diverse) NON vanno fusi dal fuzzy."""
    from talia.engine.catena import _evolvi_schema

    _evolvi_schema(db)
    for url, ogg in [
        ("http://albo/g1", OGG_AVVIO_B),
        ("http://albo/g2", OGG_AVVIO_C),
        ("http://albo/g3", OGG_AVVIO_D),
    ]:
        inserisci_atto(db, _atto("084028", url, oggetto=ogg, data_atto="2025-12-22"))

    collega_per_oggetto_simile(db, ente_ag)

    # nessun procedimento deve contenere più di un atto gemello
    conteggi = [
        r[0]
        for r in db.execute(
            "SELECT COUNT(*) FROM atti WHERE procedimento_id IS NOT NULL GROUP BY procedimento_id"
        ).fetchall()
    ]
    assert all(c <= 1 for c in conteggi) or conteggi == []


def test_reset_procedimenti_da_verificare(db, ente_ag):
    from talia.engine.catena import _evolvi_schema, reset_procedimenti_da_verificare

    _evolvi_schema(db)
    inserisci_atto(
        db,
        _atto(
            "084028",
            "http://albo/f1",
            oggetto="SELEZIONE PUBBLICA OPERATORI ESPERTI COMUNI SICILIANI",
            data_atto="2025-04-01",
        ),
    )
    inserisci_atto(
        db,
        _atto(
            "084028",
            "http://albo/f2",
            oggetto="REVOCA SELEZIONE PUBBLICA OPERATORI ESPERTI COMUNI SICILIANI",
            data_atto="2025-11-01",
        ),
    )
    collega_per_oggetto_simile(db, ente_ag)
    assert db.execute("SELECT COUNT(*) FROM procedimenti").fetchone()[0] >= 1

    n = reset_procedimenti_da_verificare(db)
    assert n >= 1
    assert db.execute("SELECT COUNT(*) FROM procedimenti").fetchone()[0] == 0
    orfani = db.execute("SELECT COUNT(*) FROM atti WHERE procedimento_id IS NOT NULL").fetchone()[0]
    assert orfani == 0


def test_ricostruisci_catene_caso_palma_end_to_end(db, ente_ag):
    """Orchestratore completo sul caso reale: 3 catene, niente mega-catena fuzzy."""
    _inserisci_caso_palma(db)

    risultato = ricostruisci_catene(db, ente_id=ente_ag, reset_da_verificare=True)

    assert risultato["n_atti_collegati_da_contenimento"] == 3
    procs = db.execute(
        "SELECT metodo_individuazione, stato_finale FROM procedimenti WHERE ente_id=?",
        (ente_ag,),
    ).fetchall()
    da_contenimento = [p for p in procs if p["metodo_individuazione"] == "contenimento_oggetto"]
    assert len(da_contenimento) == 3
    assert all(p["stato_finale"] == "revocato" for p in da_contenimento)
