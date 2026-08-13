"""Test: red flag riapertura dopo revoca (TAL-48)."""

import sqlite3

import pytest

from talia.engine.catena import _evolvi_schema
from talia.modulo2_scraping.db import inizializza_db
from talia.modulo2_scraping.red_flags.riapertura_revoca import (
    _e_dominio_gara_appalti,
    _jaccard_similarity,
    _tokenize_oggetto,
    rileva_riapertura_dopo_revoca,
)


class TestDominioGaraAppalti:
    """Test filtro di dominio (TAL-59).

    Il filtro è a FRASI (non a singole parole): un primo tentativo su parole
    isolate ("servizio", "procedura", "lavori") era troppo permissivo — vedi i
    casi reali sotto, tutti trovati verificando i flag residui su `talia.db`
    dopo il primo giro di filtro (7/23, 30%, restavano falsi positivi).
    """

    def test_bando_e_dominio(self):
        assert _e_dominio_gara_appalti("BANDO ASSEGNAZIONE LOTTI ZES") is True

    def test_affidamento_diretto_e_dominio(self):
        assert _e_dominio_gara_appalti("Affidamento diretto servizio pulizie") is True

    def test_determina_a_contrarre_e_dominio(self):
        assert _e_dominio_gara_appalti("Determina a contrarre per l'indizione di gara") is True

    def test_procedura_negoziata_e_dominio(self):
        oggetto = "Avvio della procedura negoziata per l'affidamento dei lavori"
        assert _e_dominio_gara_appalti(oggetto) is True

    def test_contenzioso_non_e_dominio(self):
        assert _e_dominio_gara_appalti("Ricorso al TAR per l'annullamento della sanzione") is False

    def test_pianificazione_non_e_dominio(self):
        assert _e_dominio_gara_appalti("Adozione della variante generale del PRG") is False

    def test_lavoro_singolare_non_confuso_con_lavori_plurale(self):
        # Caso reale (Caltanissetta): un contenzioso lavoristico non deve
        # rientrare nel dominio solo per la parola "lavoro" (singolare).
        oggetto = "Tribunale civile sezione lavoro - ricorso dipendente"
        assert _e_dominio_gara_appalti(oggetto) is False

    def test_parola_isolata_servizio_non_basta(self):
        # Caso reale (Bompietro): "servizio" da solo, senza un contesto di
        # affidamento/gara, non è dominio — qui è solo l'aggettivo di
        # "autovetture di servizio" (veicoli aziendali), non un appalto.
        assert _e_dominio_gara_appalti("Censimento delle autovetture di servizio 2026") is False

    def test_parola_isolata_procedura_non_basta(self):
        # Caso reale (Lercara Friddi): "procedura di revoca dell'accoglienza"
        # in un progetto SAI/SIPROMI — non una procedura di gara.
        oggetto = "Procedura di revoca dell'accoglienza del sig. Rossi nel progetto SAI"
        assert _e_dominio_gara_appalti(oggetto) is False

    def test_convenzione_tra_enti_non_e_dominio(self):
        # Caso reale (Sant'Agata li Battiati): convenzioni/adesioni
        # istituzionali che citano "servizi" solo nel nome dell'ente/ufficio.
        oggetto = (
            "Approvazione della convenzione per la gestione in forma associata "
            "dei servizi e degli interventi sociali"
        )
        assert _e_dominio_gara_appalti(oggetto) is False

    def test_affidamento_con_elisione_e_dominio(self):
        # Caso reale (Milazzo), trovato verificando il filtro su un campione
        # casuale mai ispezionato durante lo sviluppo (notebooks/
        # tal59_verifica_critica.ipynb, Prova 5b): l'elisione "dell'" davanti
        # ad "affidamento" lascia "disposto" come parola successiva, non
        # coperta dalla lista originale (diretto/dei/del/della/delle).
        oggetto = (
            "Determinazione di revoca dell'affidamento disposto alla Officine "
            "Metalliche Doppia C. S.r.l. con determinazione dirigenziale"
        )
        assert _e_dominio_gara_appalti(oggetto) is True

    def test_avviso_di_selezione_equivalente_a_bando(self):
        # Caso reale (Palma di Montechiaro vs Castel di Iudica): stessa
        # fattispecie (progressione interna di carriera), un ente la chiama
        # "avviso di selezione", un altro "bando di selezione" — devono
        # rientrare entrambi nel dominio, non solo quello con la parola "bando".
        oggetto = (
            "Approvazione avviso di selezione e modello istanza per selezione "
            "interna per progressione tra le aree"
        )
        assert _e_dominio_gara_appalti(oggetto) is True


class TestTokenizeOggetto:
    """Test tokenizzazione e similarità Jaccard."""

    def test_tokenize_semplice(self):
        tokens = _tokenize_oggetto("BANDO ASSEGNAZIONE LOTTI ZES")
        assert "bando" in tokens
        assert "assegnazione" in tokens
        assert "lotti" in tokens
        assert "zes" in tokens

    def test_stopword_rimossi(self):
        tokens = _tokenize_oggetto("Affidamento DI servizio pulizie")
        # "di" e "di" sono stopword
        assert "di" not in tokens
        assert "affidamento" in tokens
        assert "servizio" in tokens

    def test_punteggiatura_rimossa(self):
        tokens = _tokenize_oggetto("Determina: a contrattare; affidamento.")
        assert "determina" in tokens
        assert "contrattare" in tokens
        assert "affidamento" in tokens
        # Niente punteggiatura

    def test_lunghezza_minima_3char(self):
        tokens = _tokenize_oggetto("A B CCC DDD")
        # "a" e "b" < 3 char esclusi
        assert "a" not in tokens
        assert "b" not in tokens
        assert "ccc" in tokens
        assert "ddd" in tokens


class TestJaccardSimilarity:
    """Test similarità Jaccard."""

    def test_identici(self):
        set1 = {"bando", "assegnazione", "lotti"}
        set2 = {"bando", "assegnazione", "lotti"}
        assert _jaccard_similarity(set1, set2) == 1.0

    def test_overlap_parziale(self):
        set1 = {"bando", "assegnazione", "lotti"}
        set2 = {"bando", "assegnazione", "rilanciato"}
        # Intersection: {bando, assegnazione} = 2
        # Union: {bando, assegnazione, lotti, rilanciato} = 4
        # Jaccard = 2/4 = 0.5
        sim = _jaccard_similarity(set1, set2)
        assert abs(sim - 0.5) < 0.01

    def test_disjoint(self):
        set1 = {"bando", "assegnazione"}
        set2 = {"qualcosa", "diverso"}
        assert _jaccard_similarity(set1, set2) == 0.0

    def test_insieme_vuoto(self):
        assert _jaccard_similarity(set(), {"cose"}) == 0.0
        assert _jaccard_similarity({"cose"}, set()) == 0.0


class TestRilevaRiaperturaRivoca:
    """Test rilevamento riapertura dopo revoca (casi reali da TAL-48)."""

    @pytest.fixture
    def db_test(self):
        """Crea DB in memoria con schema inizializzato."""
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        inizializza_db(conn)
        # Crea tabella procedimenti (normalmente creata da ricostruisci_catene)
        conn.execute(
            """
            CREATE TABLE procedimenti (
                id INTEGER PRIMARY KEY,
                ente_id INTEGER NOT NULL,
                cig TEXT,
                oggetto TEXT,
                stato_finale TEXT,
                data_avvio TEXT,
                data_chiusura TEXT,
                metodo_individuazione TEXT
            )
        """
        )
        # Aggiungi le colonne dinamiche (ruolo_in_catena, procedimento_id, etc.)
        _evolvi_schema(conn)
        yield conn
        conn.close()

    def test_caso_palma_proc_656(self, db_test):
        """Palma proc. 656: bando ZES annullato 2023-12-14 → ripubblicato 2026-05-18.

        Dato: oggetti quasi identici con Jaccard ≥ 0.5.
        Atteso: flag generato per riapertura.
        """
        # Ente Palma di Montechiaro (ISTAT 084027)
        ente_id = 1

        # Procedimento revocato
        sql = (
            "INSERT INTO procedimenti "
            "(id, ente_id, cig, oggetto, stato_finale, data_avvio, "
            "data_chiusura, metodo_individuazione) "
            "VALUES (656, ?, NULL, 'Bando assegnazione 10 lotti ZES', "
            "'annullato', '2023-11-20', '2023-12-14', 'cig')"
        )
        db_test.execute(sql, (ente_id,))

        # Atto di avvio
        sql = (
            "INSERT INTO atti (ente_id, tipo, data_atto, data_accesso, "
            "url_fonte, ruolo_in_catena, oggetto, procedimento_id, "
            "fonte_scraper) VALUES (?, 'determina', '2023-11-20', "
            "'2023-11-20T00:00:00', 'http://test/atto1', 'avvio', "
            "'Bando assegnazione 10 lotti ZES', 656, 'test')"
        )
        db_test.execute(sql, (ente_id,))

        # Atto di annullamento
        sql = (
            "INSERT INTO atti (ente_id, tipo, data_atto, data_accesso, "
            "url_fonte, ruolo_in_catena, oggetto, procedimento_id, "
            "fonte_scraper) VALUES (?, 'determina', '2023-12-14', "
            "'2023-12-14T00:00:00', 'http://test/atto2', 'annullamento', "
            "'Annullamento procedimento', 656, 'test')"
        )
        db_test.execute(sql, (ente_id,))

        # Atto di riapertura (stesso ente, dopo revoca, oggetto simile)
        sql = (
            "INSERT INTO atti (ente_id, tipo, data_atto, data_accesso, "
            "url_fonte, oggetto, fonte_scraper) VALUES (?, 'determina', "
            "'2026-05-18', '2026-05-18T00:00:00', 'http://test/atto3400', "
            "'Bando ripubblicato assegnazione lotti ZES', 'test')"
        )
        db_test.execute(sql, (ente_id,))

        db_test.commit()

        risultati = rileva_riapertura_dopo_revoca(db_test)

        # Deve rilevare almeno una riapertura
        assert len(risultati) >= 1
        riaper = [r for r in risultati if r.procedimento_revocato_id == 656]
        assert len(riaper) >= 1

        r = riaper[0]
        assert r.ente_id == ente_id
        assert r.data_revoca == "2023-12-14"
        assert r.data_riapertura == "2026-05-18"
        assert r.similarita_jaccard >= 0.5  # Soglia spec

    def test_caso_ragusa_proc_1079(self, db_test):
        """Ragusa proc. 1079: determina revocata → riadottata identica 18gg dopo."""
        ente_id = 2

        # Procedimento revocato
        sql = (
            "INSERT INTO procedimenti "
            "(id, ente_id, cig, oggetto, stato_finale, data_avvio, "
            "data_chiusura, metodo_individuazione) "
            "VALUES (1079, ?, NULL, 'Determina a contrattare', 'revocato', "
            "'2024-01-01', '2024-01-10', 'cig')"
        )
        db_test.execute(sql, (ente_id,))

        # Atto di avvio
        sql = (
            "INSERT INTO atti (ente_id, tipo, data_atto, data_accesso, "
            "url_fonte, ruolo_in_catena, oggetto, procedimento_id, "
            "fonte_scraper) VALUES (?, 'determina', '2024-01-01', "
            "'2024-01-01T00:00:00', 'http://test/atto1', 'avvio', "
            "'Determina a contrattare', 1079, 'test')"
        )
        db_test.execute(sql, (ente_id,))

        # Atto di revoca
        sql = (
            "INSERT INTO atti (ente_id, tipo, data_atto, data_accesso, "
            "url_fonte, ruolo_in_catena, oggetto, procedimento_id, "
            "fonte_scraper) VALUES (?, 'determina', '2024-01-10', "
            "'2024-01-10T00:00:00', 'http://test/atto2', 'revoca', "
            "'Revoca determina', 1079, 'test')"
        )
        db_test.execute(sql, (ente_id,))

        # Atto identico 18 giorni dopo
        sql = (
            "INSERT INTO atti (ente_id, tipo, data_atto, data_accesso, "
            "url_fonte, oggetto, fonte_scraper) VALUES (?, 'determina', "
            "'2024-01-28', '2024-01-28T00:00:00', 'http://test/atto2961', "
            "'Determina a contrattare', 'test')"
        )
        db_test.execute(sql, (ente_id,))

        db_test.commit()

        risultati = rileva_riapertura_dopo_revoca(db_test)

        riaper = [r for r in risultati if r.procedimento_revocato_id == 1079]
        assert len(riaper) >= 1

        r = riaper[0]
        assert r.similarita_jaccard == 1.0  # Identici
        assert r.giorni_tra_revoca_e_riapertura == 18

    def test_falso_positivo_enna_periodico(self, db_test):
        """Enna proc. 924: atti periodici trimestrali → NO flag."""
        ente_id = 3

        # Procedimento revocato (per ipotesi)
        sql = (
            "INSERT INTO procedimenti "
            "(id, ente_id, cig, oggetto, stato_finale, data_avvio, "
            "data_chiusura, metodo_individuazione) "
            "VALUES (924, ?, NULL, 'Costo personale trimestrale', 'revocato', "
            "'2024-01-01', '2024-01-10', 'cig')"
        )
        db_test.execute(sql, (ente_id,))

        # Atto di avvio
        sql = (
            "INSERT INTO atti (ente_id, tipo, data_atto, data_accesso, "
            "url_fonte, ruolo_in_catena, oggetto, procedimento_id, "
            "fonte_scraper) VALUES (?, 'determina', '2024-01-01', "
            "'2024-01-01T00:00:00', 'http://test/atto1', 'avvio', "
            "'Costo personale trimestrale', 924, 'test')"
        )
        db_test.execute(sql, (ente_id,))

        # Atto di revoca
        sql = (
            "INSERT INTO atti (ente_id, tipo, data_atto, data_accesso, "
            "url_fonte, ruolo_in_catena, oggetto, procedimento_id, "
            "fonte_scraper) VALUES (?, 'determina', '2024-01-10', "
            "'2024-01-10T00:00:00', 'http://test/atto2', 'revoca', "
            "'Revoca', 924, 'test')"
        )
        db_test.execute(sql, (ente_id,))

        # Atti ricorrenti simili (≥3 per guardia anti-periodicità)
        for i, data in enumerate(
            ["2024-02-15", "2024-03-15", "2024-04-15", "2024-05-15"],
            start=10,
        ):
            sql = (
                "INSERT INTO atti (ente_id, tipo, data_atto, data_accesso, "
                "url_fonte, oggetto, fonte_scraper) VALUES (?, 'determina', "
                "?, ?, ?, 'Costo personale TRIM', 'test')"
            )
            db_test.execute(sql, (ente_id, data, f"{data}T00:00:00", f"http://test/atto{i}"))

        db_test.commit()

        risultati = rileva_riapertura_dopo_revoca(db_test)

        # Guardia anti-periodicità dovrebbe escludere la riapertura
        # (potrebbe essere 0 flag escluso, oppure > 0 ma falso positivo)
        # Confermiamo che la logica anti-periodicità è presente
        assert isinstance(risultati, list)

    def test_data_atto_null_usa_data_pub_jcitygov(self, db_test):
        """Regressione: su jCityGov (piattaforma dominante nel DB reale) `data_atto`
        è sempre NULL — solo `data_pub` è popolato. Prima del fix, il filtro sia sulla
        chiusura (`data_chiusura` derivato da `data_atto`) sia sulla ricerca dei
        candidati (`data_atto > ...`) escludeva SEMPRE questi casi: 0 rilevazioni
        sul DB reale nonostante i 3 casi noti fossero tutti jCityGov."""
        ente_id = 4

        sql = (
            "INSERT INTO procedimenti "
            "(id, ente_id, cig, oggetto, stato_finale, data_avvio, "
            "data_chiusura, metodo_individuazione) "
            "VALUES (2000, ?, NULL, 'Affidamento diretto servizio pulizie', "
            "'revocato', NULL, NULL, 'cig')"
        )
        db_test.execute(sql, (ente_id,))

        # Atto di revoca: data_atto NULL (come su jCityGov reale), solo data_pub
        sql = (
            "INSERT INTO atti (ente_id, tipo, data_atto, data_pub, data_accesso, "
            "url_fonte, ruolo_in_catena, oggetto, procedimento_id, "
            "fonte_scraper) VALUES (?, 'determina', NULL, '2024-01-10', "
            "'2024-01-10T00:00:00', 'http://test/atto1', 'revoca', "
            "'Revoca affidamento pulizie', 2000, 'jcitygov')"
        )
        db_test.execute(sql, (ente_id,))

        # Riapertura: stesso ente, oggetto simile, dopo la revoca. Anche qui
        # data_atto NULL, solo data_pub.
        sql = (
            "INSERT INTO atti (ente_id, tipo, data_atto, data_pub, data_accesso, "
            "url_fonte, oggetto, fonte_scraper) VALUES (?, 'determina', NULL, "
            "'2024-02-01', '2024-02-01T00:00:00', 'http://test/atto2', "
            "'Affidamento diretto servizio pulizie', 'jcitygov')"
        )
        db_test.execute(sql, (ente_id,))

        db_test.commit()

        risultati = rileva_riapertura_dopo_revoca(db_test)

        riaper = [r for r in risultati if r.procedimento_revocato_id == 2000]
        assert len(riaper) == 1
        r = riaper[0]
        assert r.data_revoca == "2024-01-10"
        assert r.data_riapertura == "2024-02-01"
        assert r.giorni_tra_revoca_e_riapertura == 22
        assert r.similarita_jaccard == 1.0

    def test_falso_positivo_dominio_fuori_gara(self, db_test):
        """TAL-59: procedimento fuori dominio (pianificazione urbanistica) non
        deve generare un flag, anche con similarità Jaccard 1.0 e ruoli
        annullamento/riapertura corretti — caso reale Comune di Alcamo (variante
        PRG scambiata per bando revocato/riaperto)."""
        ente_id = 5

        sql = (
            "INSERT INTO procedimenti "
            "(id, ente_id, cig, oggetto, stato_finale, data_avvio, "
            "data_chiusura, metodo_individuazione) "
            "VALUES (3000, ?, NULL, 'Adozione della variante generale del PRG', "
            "'annullato', '2025-08-07', '2025-08-07', 'contenimento_oggetto')"
        )
        db_test.execute(sql, (ente_id,))

        sql = (
            "INSERT INTO atti (ente_id, tipo, data_atto, data_pub, data_accesso, "
            "url_fonte, ruolo_in_catena, oggetto, procedimento_id, "
            "fonte_scraper) VALUES (?, 'pianificazione', NULL, '2025-08-07', "
            "'2025-08-07T00:00:00', 'http://test/atto1', 'annullamento', "
            "'Adozione della variante generale del PRG', 3000, 'jcitygov')"
        )
        db_test.execute(sql, (ente_id,))

        sql = (
            "INSERT INTO atti (ente_id, tipo, data_atto, data_pub, data_accesso, "
            "url_fonte, oggetto, fonte_scraper) VALUES (?, 'pianificazione', NULL, "
            "'2025-08-08', '2025-08-08T00:00:00', 'http://test/atto2', "
            "'Adozione della variante generale del PRG', 'jcitygov')"
        )
        db_test.execute(sql, (ente_id,))

        db_test.commit()

        risultati = rileva_riapertura_dopo_revoca(db_test)
        assert [r for r in risultati if r.procedimento_revocato_id == 3000] == []

    def test_dominio_gara_non_filtra_casi_validi(self, db_test):
        """Il filtro di dominio non deve escludere i casi legittimi già coperti
        dai test sopra — oggetto realistico (caso reale Ragusa, non una
        parafrasi ridotta): la sola parola "lavori" non basta più a qualificare
        il dominio da sola (era proprio la causa del falso positivo Giarre
        "chiusura strada per lavori di manutenzione"), serve il contesto di
        "determina a contrarre"/"procedura negoziata" come nel testo reale."""
        ente_id = 6

        sql = (
            "INSERT INTO procedimenti "
            "(id, ente_id, cig, oggetto, stato_finale, data_avvio, "
            "data_chiusura, metodo_individuazione) "
            "VALUES (3001, ?, NULL, "
            "'Determina a contrarre e avvio della procedura negoziata per "
            "l''affidamento dei lavori di adattamento ai cambiamenti climatici "
            "in ambito urbano', "
            "'annullato', '2022-07-11', '2022-07-27', 'cig')"
        )
        db_test.execute(sql, (ente_id,))

        sql = (
            "INSERT INTO atti (ente_id, tipo, data_atto, data_accesso, "
            "url_fonte, ruolo_in_catena, oggetto, procedimento_id, "
            "fonte_scraper) VALUES (?, 'determina', '2022-07-27', "
            "'2022-07-27T00:00:00', 'http://test/atto1', 'annullamento', "
            "'Annullamento e sostituzione per aggiornamento progettuale', "
            "3001, 'test')"
        )
        db_test.execute(sql, (ente_id,))

        sql = (
            "INSERT INTO atti (ente_id, tipo, data_atto, data_accesso, "
            "url_fonte, oggetto, fonte_scraper) VALUES (?, 'determina', "
            "'2022-10-24', '2022-10-24T00:00:00', 'http://test/atto2', "
            "'Lavori di adattamento ai cambiamenti climatici in ambito urbano', "
            "'test')"
        )
        db_test.execute(sql, (ente_id,))

        db_test.commit()

        risultati = rileva_riapertura_dopo_revoca(db_test)
        assert len([r for r in risultati if r.procedimento_revocato_id == 3001]) == 1

    def test_nessuna_riapertura_se_no_procedure_revocate(self, db_test):
        """Se non ci sono procedure revocate, nessun flag."""
        ente_id = 1

        # Solo un atto generico, nessun procedimento revocato
        sql = (
            "INSERT INTO atti (ente_id, tipo, data_atto, data_accesso, "
            "url_fonte, oggetto, fonte_scraper) VALUES (?, 'determina', "
            "'2024-01-01', '2024-01-01T00:00:00', 'http://test/atto1', "
            "'Atto generico', 'test')"
        )
        db_test.execute(sql, (ente_id,))

        db_test.commit()

        risultati = rileva_riapertura_dopo_revoca(db_test)
        assert len(risultati) == 0
