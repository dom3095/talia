"""Test TAL-14: check-7 GDPR data breach."""

import pytest
from talia.engine.checklist.check7_gdpr import CheckGdprBreach, _breach_descritto
from talia.engine.fascicolo import AttoAnalizzato, ContestoFascicolo, RuoloAtto
from talia.engine.pdf_text import da_testo
from talia.engine.models import Stato


def _contesto(testo_autotutela: str) -> ContestoFascicolo:
    atto = AttoAnalizzato.da_testo(da_testo(testo_autotutela), ruolo=RuoloAtto.AUTOTUTELA)
    return ContestoFascicolo(atto_autotutela=atto)


_CHECK = CheckGdprBreach()


def test_breach_descritto_divulgazione_graduatoria():
    testo = (
        "Accertato che la divulgazione della bozza di graduatoria ha compromesso "
        "l'imparzialità della procedura selettiva."
    )
    assert _breach_descritto(testo) is not None


def test_breach_descritto_fuga_notizie():
    testo = (
        "Rilevata una fuga di notizie riguardante il verbale di valutazione "
        "della commissione selezionatrice."
    )
    assert _breach_descritto(testo) is not None


def test_breach_descritto_assente():
    testo = "Vista la sopravvenuta esigenza di revocare il procedimento per motivi di opportunità."
    assert _breach_descritto(testo) is None


def test_check_rosso_senza_notifica_garante():
    testo = (
        "Considerato che la divulgazione della bozza di graduatoria ha determinato "
        "una violazione dei principi di riservatezza e par condicio dei candidati."
    )
    contesto = _contesto(testo)
    assert _CHECK.applicabile(contesto)
    esito = _CHECK.valuta(contesto)
    assert esito.stato is Stato.ROSSO
    assert esito.citazioni


def test_check_verde_con_notifica_garante():
    testo = (
        "Rilevata la divulgazione di dati personali relativi alla graduatoria. "
        "La violazione è stata notificata al Garante per la protezione dei dati "
        "ai sensi dell'art. 33 GDPR entro 72 ore dall'accertamento."
    )
    contesto = _contesto(testo)
    esito = _CHECK.valuta(contesto)
    assert esito.stato is Stato.VERDE


def test_check_non_applicabile_senza_breach():
    testo = (
        "Vista la determinazione n. 15/2024 e la delibera di Giunta n. 8/2024, "
        "si revoca il concorso per sopravvenuti motivi di opportunità amministrativa."
    )
    contesto = _contesto(testo)
    assert not _CHECK.applicabile(contesto)
