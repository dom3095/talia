"""Test TAL-8: check-5 comunicazione di avvio del procedimento (art. 7 L. 241/1990)."""

from talia.engine.checklist.check5_avvio import CheckComunicazioneAvvio
from talia.engine.fascicolo import AttoAnalizzato, ContestoFascicolo, RuoloAtto
from talia.engine.models import Stato
from talia.engine.pdf_text import da_testo


def _contesto(testo: str) -> ContestoFascicolo:
    atto = AttoAnalizzato.da_testo(da_testo(testo), ruolo=RuoloAtto.AUTOTUTELA)
    return ContestoFascicolo(atto_autotutela=atto)


_CHECK = CheckComunicazioneAvvio()


def test_verde_comunicazione_avvio_esplicita():
    testo = (
        "Dato atto che è stata inviata la comunicazione di avvio del procedimento "
        "ai sensi dell'art. 7 della legge 241/1990 a tutti i candidati partecipanti."
    )
    esito = _CHECK.valuta(_contesto(testo))
    assert esito.stato is Stato.VERDE
    assert esito.citazioni


def test_verde_art7_241_vicini():
    testo = "Vista la comunicazione ex art. 7 L. 241/1990 trasmessa in data 10/01/2024."
    esito = _CHECK.valuta(_contesto(testo))
    assert esito.stato is Stato.VERDE


def test_giallo_pubblicazione_sito_concorso_interno():
    testo = (
        "Visto che trattasi di concorso interno riservato al personale dipendente "
        "dell'ente, la notifica è effettuata mediante pubblicazione sul sito "
        "istituzionale con valore di notifica ai sensi di legge."
    )
    esito = _CHECK.valuta(_contesto(testo))
    assert esito.stato is Stato.GIALLO
    assert esito.citazioni


def test_rosso_pubblicazione_sito_senza_interno():
    testo = (
        "La notifica del presente atto è effettuata mediante pubblicazione sul sito "
        "istituzionale con valore di notifica, in luogo della comunicazione individuale."
    )
    esito = _CHECK.valuta(_contesto(testo))
    assert esito.stato is Stato.ROSSO
    assert esito.citazioni


def test_rosso_assenza_totale_comunicazione():
    testo = (
        "Vista la determinazione n. 15/2024 e la delibera di Giunta n. 8/2024, "
        "si revoca il concorso pubblico per sopravvenuti motivi di opportunità."
    )
    esito = _CHECK.valuta(_contesto(testo))
    assert esito.stato is Stato.ROSSO
    assert not esito.citazioni
