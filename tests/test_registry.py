"""Test del modulo registry (caricamento e validazione registro scraper)."""

import csv
from pathlib import Path

import pytest

from talia.modulo2_scraping.registry import (
    MODULI_SENZA_ENTE,
    EntryRegistro,
    carica_registro,
    entries_default,
    filtra_eseguibili,
    sincronizza_enti_da_registro,
    valida_registro,
)


@pytest.fixture
def registro_fixture_csv(tmp_path: Path) -> Path:
    """Crea un CSV di test minimale."""
    csv_path = tmp_path / "test_registro.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "slug",
                "denominazione",
                "codice_istat",
                "provincia",
                "modulo",
                "piattaforma_tecnica",
                "base_url",
                "qs_base",
                "ente_mittente",
                "skip_ssl",
                "stato",
                "note",
            ],
        )
        writer.writeheader()
        writer.writerows(
            [
                {
                    "slug": "test_jcitygov",
                    "denominazione": "Comune Test jCityGov",
                    "codice_istat": "123456",
                    "provincia": "PA",
                    "modulo": "jcitygov",
                    "piattaforma_tecnica": "jCityGov",
                    "base_url": "https://test.trasparenza.it",
                    "qs_base": "",
                    "ente_mittente": "",
                    "skip_ssl": "",
                    "stato": "attivo",
                    "note": "",
                },
                {
                    "slug": "test_urbi",
                    "denominazione": "Comune Test URBI",
                    "codice_istat": "234567",
                    "provincia": "CT",
                    "modulo": "urbi",
                    "piattaforma_tecnica": "URBI Cloud",
                    "base_url": "https://cloud.urbi.it",
                    "qs_base": "DB_NAME=test",
                    "ente_mittente": "COMUNE TEST",
                    "skip_ssl": "",
                    "stato": "attivo",
                    "note": "",
                },
                {
                    "slug": "test_halley",
                    "denominazione": "Comune Test Halley",
                    "codice_istat": "345678",
                    "provincia": "AG",
                    "modulo": "halley",
                    "piattaforma_tecnica": "Halley EG",
                    "base_url": "https://test.halley.it",
                    "qs_base": "",
                    "ente_mittente": "",
                    "skip_ssl": "true",
                    "stato": "attivo",
                    "note": "test skip_ssl",
                },
                {
                    "slug": "test_escluso",
                    "denominazione": "Comune Escluso",
                    "codice_istat": "456789",
                    "provincia": "ME",
                    "modulo": "agrigento",
                    "piattaforma_tecnica": "ASP.NET",
                    "base_url": "https://test.ag.it",
                    "qs_base": "",
                    "ente_mittente": "",
                    "skip_ssl": "",
                    "stato": "escluso_default",
                    "note": "",
                },
                {
                    "slug": "test_bloccato",
                    "denominazione": "Comune Bloccato",
                    "codice_istat": "567890",
                    "provincia": "TP",
                    "modulo": "palermo",
                    "piattaforma_tecnica": "SISPI",
                    "base_url": "https://test.pa.it",
                    "qs_base": "",
                    "ente_mittente": "",
                    "skip_ssl": "",
                    "stato": "bloccato",
                    "note": "cert scaduto",
                },
            ]
        )
    return csv_path


class TestEntryRegistro:
    """Test della dataclass EntryRegistro."""

    def test_creazione_base(self):
        """Crea una entry minimale."""
        e = EntryRegistro(
            slug="test",
            denominazione="Test",
            codice_istat="123456",
            modulo="jcitygov",
            piattaforma_tecnica="jCityGov",
            base_url="https://test.it",
        )
        assert e.slug == "test"
        assert e.skip_ssl is False

    def test_skip_ssl_coercizione_string_true(self):
        """Converti skip_ssl="true" in bool."""
        e = EntryRegistro(
            slug="test",
            denominazione="Test",
            codice_istat="123456",
            modulo="halley",
            piattaforma_tecnica="Halley",
            base_url="https://test.it",
            skip_ssl="true",
        )
        assert e.skip_ssl is True

    def test_skip_ssl_coercizione_string_false(self):
        """skip_ssl="" rimane falso."""
        e = EntryRegistro(
            slug="test",
            denominazione="Test",
            codice_istat="123456",
            modulo="halley",
            piattaforma_tecnica="Halley",
            base_url="https://test.it",
            skip_ssl="",
        )
        assert e.skip_ssl is False


class TestCaricaRegistro:
    """Test del caricamento del registro."""

    def test_carica_da_file(self, registro_fixture_csv: Path):
        """Carica il registro da un CSV fixture."""
        entries = carica_registro(registro_fixture_csv)
        assert len(entries) == 5
        assert entries[0].slug == "test_jcitygov"
        assert entries[0].stato == "attivo"

    def test_file_non_trovato(self):
        """Solleva ValueError se il file non esiste."""
        with pytest.raises(ValueError, match="Registro non trovato"):
            carica_registro("/non/esiste/registro.csv")

    def test_slug_duplicato_solleva_errore(self, tmp_path: Path):
        """Solleva ValueError se due righe hanno lo stesso slug."""
        csv_path = tmp_path / "bad_registro.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "slug",
                    "denominazione",
                    "codice_istat",
                    "provincia",
                    "modulo",
                    "piattaforma_tecnica",
                    "base_url",
                    "qs_base",
                    "ente_mittente",
                    "skip_ssl",
                    "stato",
                    "note",
                ],
            )
            writer.writeheader()
            writer.writerows(
                [
                    {
                        "slug": "duplicate",
                        "denominazione": "Test1",
                        "codice_istat": "111111",
                        "provincia": "PA",
                        "modulo": "jcitygov",
                        "piattaforma_tecnica": "jCityGov",
                        "base_url": "https://test1.it",
                        "qs_base": "",
                        "ente_mittente": "",
                        "skip_ssl": "",
                        "stato": "attivo",
                        "note": "",
                    },
                    {
                        "slug": "duplicate",
                        "denominazione": "Test2",
                        "codice_istat": "222222",
                        "provincia": "CT",
                        "modulo": "jcitygov",
                        "piattaforma_tecnica": "jCityGov",
                        "base_url": "https://test2.it",
                        "qs_base": "",
                        "ente_mittente": "",
                        "skip_ssl": "",
                        "stato": "attivo",
                        "note": "",
                    },
                ]
            )
        with pytest.raises(ValueError, match="slug duplicato"):
            carica_registro(csv_path)

    def test_stato_cella_vuota_usa_default_attivo(self):
        """Bug trovato in code review: row.get("stato", "attivo") applicava il
        default solo se la CHIAVE mancava, non se la cella era presente ma
        vuota — una riga con colonna stato vuota diventava stato="" e spariva
        silenziosamente da tutto lo scraping senza errore di validazione."""
        from talia.modulo2_scraping.registry import _row_to_entry

        row = {
            "slug": "test",
            "denominazione": "Test",
            "codice_istat": "123456",
            "modulo": "jcitygov",
            "piattaforma_tecnica": "jCityGov",
            "base_url": "https://test.it",
            "stato": "",
        }
        entry = _row_to_entry(row)
        assert entry.stato == "attivo"


class TestModuliSenzaEnte:
    """Test della centralizzazione del caso speciale ANAC (code review 2026-07-11):
    prima "anac" era ripetuto come stringa letterale in 6 punti sparsi tra
    registry.py e run_scrapers.py, ora è un'unica costante nominata."""

    def test_anac_in_moduli_senza_ente(self):
        assert "anac" in MODULI_SENZA_ENTE

    def test_codice_istat_non_richiesto_per_modulo_senza_ente(self):
        e = EntryRegistro(
            slug="anac",
            denominazione="ANAC",
            codice_istat="",
            modulo="anac",
            piattaforma_tecnica="CSV",
            base_url=None,
            stato="escluso_default",
        )
        problemi = valida_registro([e])
        assert not any("codice_istat mancante" in p for p in problemi)

    def test_base_url_non_richiesto_per_modulo_senza_ente(self):
        e = EntryRegistro(
            slug="anac",
            denominazione="ANAC",
            codice_istat="",
            modulo="anac",
            piattaforma_tecnica="CSV",
            base_url=None,
            stato="attivo",
        )
        problemi = valida_registro([e])
        assert not any("base_url mancante" in p for p in problemi)

    def test_sincronizza_enti_salta_moduli_senza_ente(self):
        from talia.modulo2_scraping.db import connetti, inizializza_db

        conn = connetti(":memory:")
        inizializza_db(conn)
        e = EntryRegistro(
            slug="anac",
            denominazione="ANAC",
            codice_istat="",
            modulo="anac",
            piattaforma_tecnica="CSV",
            base_url=None,
            stato="escluso_default",
        )
        n = sincronizza_enti_da_registro(conn, [e])
        assert n == 0
        assert conn.execute("SELECT COUNT(*) AS c FROM enti").fetchone()["c"] == 0


class TestValidaRegistro:
    """Test della validazione."""

    def test_valida_registro_buono(self, registro_fixture_csv: Path):
        """Un registro valido ritorna lista vuota."""
        entries = carica_registro(registro_fixture_csv)
        problemi = valida_registro(entries)
        assert problemi == []

    def test_modulo_sconosciuto(self):
        """Modulo ignoto → errore."""
        e = EntryRegistro(
            slug="test",
            denominazione="Test",
            codice_istat="123456",
            modulo="unknown_module",
            piattaforma_tecnica="X",
            base_url="https://test.it",
        )
        problemi = valida_registro([e])
        assert any("modulo sconosciuto" in p for p in problemi)

    def test_codice_istat_malformato(self):
        """Codice ISTAT non 6 cifre → errore."""
        e = EntryRegistro(
            slug="test",
            denominazione="Test",
            codice_istat="12345",  # solo 5
            modulo="jcitygov",
            piattaforma_tecnica="jCityGov",
            base_url="https://test.it",
        )
        problemi = valida_registro([e])
        assert any("codice_istat non 6 cifre" in p for p in problemi)

    def test_base_url_mancante_su_attivo(self):
        """base_url mancante su stato=attivo → errore."""
        e = EntryRegistro(
            slug="test",
            denominazione="Test",
            codice_istat="123456",
            modulo="jcitygov",
            piattaforma_tecnica="jCityGov",
            base_url=None,
            stato="attivo",
        )
        problemi = valida_registro([e])
        assert any("base_url mancante" in p for p in problemi)

    def test_qs_base_fuori_posto(self):
        """qs_base su modulo non-urbi/catania → warning."""
        e = EntryRegistro(
            slug="test",
            denominazione="Test",
            codice_istat="123456",
            modulo="jcitygov",
            piattaforma_tecnica="jCityGov",
            base_url="https://test.it",
            qs_base="DB_NAME=test",  # Su jCityGov è spurio
        )
        problemi = valida_registro([e])
        assert any("qs_base valorizzato" in p for p in problemi)

    def test_skip_ssl_fuori_posto(self):
        """skip_ssl=true su modulo non-halley → warning."""
        e = EntryRegistro(
            slug="test",
            denominazione="Test",
            codice_istat="123456",
            modulo="jcitygov",
            piattaforma_tecnica="jCityGov",
            base_url="https://test.it",
            skip_ssl=True,  # Su jCityGov è spurio
        )
        problemi = valida_registro([e])
        assert any("skip_ssl=true" in p for p in problemi)

    def test_qs_base_mancante_su_catania_attivo(self):
        """qs_base mancante su modulo=catania con stato=attivo → errore.

        Gap trovato in code review: senza questo controllo una riga catania/urbi
        con qs_base vuoto passa la validazione e produce un URL con "?None" a runtime.
        """
        e = EntryRegistro(
            slug="test",
            denominazione="Test",
            codice_istat="123456",
            modulo="catania",
            piattaforma_tecnica="URBI/Maggioli",
            base_url="https://test.it",
            qs_base=None,
            ente_mittente="COMUNE DI TEST",
            stato="attivo",
        )
        problemi = valida_registro([e])
        assert any("qs_base mancante" in p for p in problemi)

    def test_ente_mittente_mancante_su_urbi_attivo(self):
        """ente_mittente mancante su modulo=urbi con stato=attivo → errore."""
        e = EntryRegistro(
            slug="test",
            denominazione="Test",
            codice_istat="123456",
            modulo="urbi",
            piattaforma_tecnica="URBI Cloud",
            base_url="https://test.it",
            qs_base="DB_NAME=test",
            ente_mittente=None,
            stato="attivo",
        )
        problemi = valida_registro([e])
        assert any("ente_mittente mancante" in p for p in problemi)

    def test_qs_base_non_richiesto_su_catania_pending(self):
        """qs_base mancante su modulo=catania con stato=pending non è un errore
        (pending non richiede nemmeno base_url, coerentemente)."""
        e = EntryRegistro(
            slug="test",
            denominazione="Test",
            codice_istat="123456",
            modulo="catania",
            piattaforma_tecnica="URBI/Maggioli",
            base_url=None,
            qs_base=None,
            ente_mittente=None,
            stato="pending",
        )
        problemi = valida_registro([e])
        assert not any("qs_base mancante" in p for p in problemi)

    def test_modulo_pending_valido(self):
        """modulo='pending' è riconosciuto (pseudo-modulo per comuni censiti
        ma non ancora implementati)."""
        e = EntryRegistro(
            slug="test",
            denominazione="Test",
            codice_istat="123456",
            modulo="pending",
            piattaforma_tecnica="ComuneWeb",
            base_url=None,
            stato="pending",
        )
        problemi = valida_registro([e])
        assert problemi == []


class TestFiltriEseguibili:
    """Test dei filtri sul registro."""

    def test_filtra_eseguibili(self, registro_fixture_csv: Path):
        """Filtra solo entry eseguibili (attivo + escluso_default)."""
        entries = carica_registro(registro_fixture_csv)
        eseguibili = filtra_eseguibili(entries)
        # 3 attivo + 1 escluso_default = 4; 1 bloccato è escluso
        assert len(eseguibili) == 4
        assert all(e.stato in ("attivo", "escluso_default") for e in eseguibili)

    def test_entries_default(self, registro_fixture_csv: Path):
        """entries_default() ritorna solo slug con stato=attivo."""
        entries = carica_registro(registro_fixture_csv)
        default_slugs = entries_default(entries)
        # 3 attivo (jcitygov, urbi, halley); 1 escluso_default e 1 bloccato non inclusi
        assert len(default_slugs) == 3
        assert "test_escluso" not in default_slugs
        assert "test_bloccato" not in default_slugs
        assert "test_jcitygov" in default_slugs


class TestCaricaRegistroProduzione:
    """Test che carica il vero registro di produzione (se esiste)."""

    def test_carica_registro_produzione(self):
        """Carica data/registro_scraper.csv se esiste."""
        csv_path = Path("data/registro_scraper.csv")
        if not csv_path.exists():
            pytest.skip("Registro di produzione non trovato")

        # Deve caricarlo senza errori
        entries = carica_registro(csv_path)
        assert len(entries) > 0

        # Deve avere almeno i moduli principali
        moduli = {e.modulo for e in entries}
        assert "jcitygov" in moduli or len(moduli) > 0

        # Validazione deve passare
        problemi = valida_registro(entries)
        assert problemi == [], "Registro di produzione ha problemi:\n" + "\n".join(problemi)
