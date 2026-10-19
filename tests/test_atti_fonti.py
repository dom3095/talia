"""Test di `atti_fonti` e della deduplicazione tra fonti (TAL-64).

Il caso da coprire: lo stesso documento pubblicato sull'Albo Pretorio e su
Amministrazione Trasparente (TAL-62) non deve diventare due atti. Il caso da
non rompere: dentro un singolo portale, URL diverso = atto diverso.
"""

from __future__ import annotations

import pytest

from talia.modulo2_scraping.db import (
    AttoMetadato,
    EnteMetadato,
    connetti,
    fonti_atto,
    inizializza_db,
    inserisci_atto,
    upsert_ente,
)

_ISTAT = "088009"  # Ragusa


@pytest.fixture()
def conn():
    c = connetti(":memory:")
    inizializza_db(c)
    upsert_ente(c, EnteMetadato(denominazione="Ragusa", codice_istat=_ISTAT))
    return c


def _atto(url: str, fonte: str = "jcitygov", **campi) -> AttoMetadato:
    base = dict(
        ente_codice_istat=_ISTAT,
        tipo="determina",
        url_fonte=url,
        fonte_scraper=fonte,
        data_accesso="2026-10-19T03:30:00",
        numero="1217",
        data_pub="2026-09-01",
    )
    base.update(campi)
    return AttoMetadato(**base)


def _n(conn, tabella: str) -> int:
    return conn.execute(f"SELECT COUNT(*) FROM {tabella}").fetchone()[0]


# ---------------------------------------------------------------------------
# Comportamento invariato
# ---------------------------------------------------------------------------


def test_atto_nuovo_registra_anche_la_sua_fonte(conn):
    atto_id = inserisci_atto(conn, _atto("https://albo/1", cig="A1B2C3D4E5"))
    assert atto_id is not None
    fonti = fonti_atto(conn, atto_id)
    assert [(f["fonte_scraper"], f["url_fonte"]) for f in fonti] == [("jcitygov", "https://albo/1")]


def test_rerun_non_duplica_ne_atti_ne_fonti(conn):
    inserisci_atto(conn, _atto("https://albo/1"))
    assert inserisci_atto(conn, _atto("https://albo/1")) is None
    assert (_n(conn, "atti"), _n(conn, "atti_fonti")) == (1, 1)


def test_stesso_portale_url_diverso_resta_atto_diverso(conn):
    """Due righe dell'Albo con la stessa chiave sono due atti, come oggi."""
    inserisci_atto(conn, _atto("https://albo/1", cig="A1B2C3D4E5"))
    assert inserisci_atto(conn, _atto("https://albo/2", cig="A1B2C3D4E5")) is not None
    assert _n(conn, "atti") == 2


# ---------------------------------------------------------------------------
# Deduplicazione tra fonti
# ---------------------------------------------------------------------------


def test_stesso_url_su_fonte_diversa_registra_la_seconda_fonte(conn):
    """jCityGov: Albo e AT condividono il backend e l'URL — prima la seconda fonte si perdeva."""
    atto_id = inserisci_atto(conn, _atto("https://igrid/42"))
    assert inserisci_atto(conn, _atto("https://igrid/42", fonte="jcitygov_trasparenza")) is None
    assert _n(conn, "atti") == 1
    assert {f["fonte_scraper"] for f in fonti_atto(conn, atto_id)} == {
        "jcitygov",
        "jcitygov_trasparenza",
    }


def test_cig_e_numero_uguali_su_fonte_diversa_sono_lo_stesso_atto(conn):
    atto_id = inserisci_atto(conn, _atto("https://albo/1", cig="A1B2C3D4E5"))
    ritorno = inserisci_atto(
        conn, _atto("https://at/99", fonte="jcitygov_trasparenza", cig="A1B2C3D4E5")
    )
    assert ritorno is None
    assert _n(conn, "atti") == 1
    assert len(fonti_atto(conn, atto_id)) == 2


def test_stesso_cig_numero_diverso_non_fonde(conn):
    """Il CIG da solo non identifica un atto: una gara ne produce diversi."""
    inserisci_atto(conn, _atto("https://albo/1", cig="A1B2C3D4E5", numero="10"))
    inserisci_atto(
        conn, _atto("https://at/1", fonte="jcitygov_trasparenza", cig="A1B2C3D4E5", numero="11")
    )
    assert _n(conn, "atti") == 2


def test_cig_padre_non_entra_nell_identita(conn):
    """Un CIG di accordo quadro è condiviso da molte adesioni distinte (TAL-65)."""
    inserisci_atto(conn, _atto("https://albo/1", cig="A000000001", cig_padre="QUADRO0001"))
    inserisci_atto(
        conn,
        _atto(
            "https://at/1",
            fonte="jcitygov_trasparenza",
            cig="A000000002",
            cig_padre="QUADRO0001",
        ),
    )
    assert _n(conn, "atti") == 2


def test_senza_cig_tipo_e_numero_nello_stesso_anno(conn):
    inserisci_atto(conn, _atto("https://albo/1", tipo="bando di concorso", numero="5"))
    inserisci_atto(
        conn,
        _atto(
            "https://at/1",
            fonte="halley_trasparenza",
            tipo="bando di concorso",
            numero="5",
            data_pub="2026-10-02",
        ),
    )
    assert _n(conn, "atti") == 1


def test_senza_cig_anni_diversi_non_fonde(conn):
    """La determina n. 12 del 2019 non è quella del 2026."""
    inserisci_atto(conn, _atto("https://albo/1", numero="12", data_pub="2019-03-01"))
    inserisci_atto(
        conn,
        _atto("https://at/1", fonte="jcitygov_trasparenza", numero="12", data_pub="2026-03-01"),
    )
    assert _n(conn, "atti") == 2


def test_senza_cig_da_un_lato_solo_non_fonde(conn):
    inserisci_atto(conn, _atto("https://albo/1", cig="A1B2C3D4E5"))
    inserisci_atto(conn, _atto("https://at/1", fonte="jcitygov_trasparenza"))
    assert _n(conn, "atti") == 2


@pytest.mark.parametrize("numero", [None, "", "0"])
def test_numero_assente_o_sentinella_non_fonde(conn, numero):
    inserisci_atto(conn, _atto("https://albo/1", cig="A1B2C3D4E5", numero=numero))
    inserisci_atto(
        conn, _atto("https://at/1", fonte="jcitygov_trasparenza", cig="A1B2C3D4E5", numero=numero)
    )
    assert _n(conn, "atti") == 2


def test_candidato_ambiguo_inserisce_atto_nuovo(conn):
    """Due atti dell'Albo con la stessa chiave (6,2% su jCityGov): non si sceglie a caso."""
    inserisci_atto(conn, _atto("https://albo/1", cig="A1B2C3D4E5"))
    inserisci_atto(conn, _atto("https://albo/2", cig="A1B2C3D4E5"))
    inserisci_atto(conn, _atto("https://at/1", fonte="jcitygov_trasparenza", cig="A1B2C3D4E5"))
    assert _n(conn, "atti") == 3


def test_altro_ente_mai_fuso(conn):
    upsert_ente(conn, EnteMetadato(denominazione="Modica", codice_istat="088006"))
    inserisci_atto(conn, _atto("https://albo/1", cig="A1B2C3D4E5"))
    inserisci_atto(
        conn,
        _atto(
            "https://at/1",
            fonte="jcitygov_trasparenza",
            cig="A1B2C3D4E5",
            ente_codice_istat="088006",
        ),
    )
    assert _n(conn, "atti") == 2


# ---------------------------------------------------------------------------
# Link da mostrare e migrazione
# ---------------------------------------------------------------------------


def test_fonte_piu_duratura_per_prima(conn):
    """L'Albo scade in 15-30 giorni, AT resta anni: il link buono è quello di AT."""
    atto_id = inserisci_atto(conn, _atto("https://albo/1", data_scadenza="2026-09-16"))
    inserisci_atto(conn, _atto("https://albo/1", fonte="jcitygov_trasparenza"))
    assert fonti_atto(conn, atto_id)[0]["fonte_scraper"] == "jcitygov_trasparenza"


def test_migrazione_db_esistente_uno_a_uno_e_idempotente(conn):
    """Un `talia.db` creato prima di TAL-64 ha atti senza fonti: il backfill li copia 1:1."""
    for i in range(5):
        inserisci_atto(conn, _atto(f"https://albo/{i}", numero=str(100 + i)))
    conn.execute("DROP TABLE atti_fonti")
    conn.commit()

    inizializza_db(conn)
    assert _n(conn, "atti_fonti") == 5
    riga = conn.execute(
        "SELECT f.url_fonte, f.fonte_scraper, f.data_pub FROM atti_fonti f "
        "JOIN atti a ON a.id = f.atto_id WHERE a.numero = '100'"
    ).fetchone()
    assert tuple(riga) == ("https://albo/0", "jcitygov", "2026-09-01")

    inizializza_db(conn)
    assert _n(conn, "atti_fonti") == 5
