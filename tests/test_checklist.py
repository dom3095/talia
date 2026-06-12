"""Test dei check deterministici (TAL-6, TAL-7, TAL-8, TAL-9)."""

from talia.engine.checklist.check1_base_giuridica import CheckBaseGiuridica
from talia.engine.checklist.check2_termini import CheckTerminiAutotutela
from talia.engine.checklist.check5_avvio import CheckComunicazioneAvvio
from talia.engine.checklist.check6_firmatari import CheckCoerenzaFirmatari
from talia.engine.fascicolo import AttoAnalizzato, ContestoFascicolo, RuoloAtto
from talia.engine.models import Stato
from talia.engine.pdf_text import da_testo


def _contesto(autotutela: str, originario: str | None = None) -> ContestoFascicolo:
    atto_aut = AttoAnalizzato.da_testo(da_testo(autotutela), RuoloAtto.AUTOTUTELA)
    atto_orig = (
        AttoAnalizzato.da_testo(da_testo(originario), RuoloAtto.ORIGINARIO)
        if originario is not None
        else None
    )
    return ContestoFascicolo(atto_autotutela=atto_aut, atto_originario=atto_orig)


# --- Check 1: base giuridica ------------------------------------------------


def test_check1_coerente_annullamento_verde():
    ctx = _contesto("annullamento ai sensi dell'art. 21-nonies: vizio di illegittimità")
    esito = CheckBaseGiuridica().valuta(ctx)
    assert esito.stato is Stato.VERDE
    assert esito.citazioni


def test_check1_base_assente_rosso():
    ctx = _contesto("si dispone l'annullamento della procedura senza altra indicazione")
    assert CheckBaseGiuridica().valuta(ctx).stato is Stato.ROSSO


def test_check1_incoerente_rosso():
    ctx = _contesto(
        "annullamento ai sensi dell'art. 21-nonies per sopravvenuti motivi di opportunità"
    )
    assert CheckBaseGiuridica().valuta(ctx).stato is Stato.ROSSO


def test_check1_ambiguo_giallo():
    ctx = _contesto("si richiamano gli artt. 21-quinquies e 21-nonies L. 241/1990")
    assert CheckBaseGiuridica().valuta(ctx).stato is Stato.GIALLO


def test_check1_revoca_coerente_verde():
    ctx = _contesto("revoca ex art. 21-quinquies per sopravvenuti motivi di opportunità")
    assert CheckBaseGiuridica().valuta(ctx).stato is Stato.VERDE


# --- Check 2: termini autotutela --------------------------------------------


def test_check2_entro_termine_verde():
    ctx = _contesto(
        "annullamento art. 21-nonies, adottato il 20/09/2024",
        originario="determina di indizione del 10/03/2024",
    )
    assert CheckTerminiAutotutela().valuta(ctx).stato is Stato.VERDE


def test_check2_oltre_termine_rosso():
    ctx = _contesto(
        "annullamento art. 21-nonies del 30/06/2024",
        originario="determina di indizione del 05/02/2022",
    )
    assert CheckTerminiAutotutela().valuta(ctx).stato is Stato.ROSSO


def test_check2_non_applicabile_a_revoca():
    ctx = _contesto("revoca ex art. 21-quinquies del 30/06/2024")
    assert CheckTerminiAutotutela().applicabile(ctx) is False


def test_check2_date_mancanti_giallo():
    ctx = _contesto("annullamento ai sensi dell'art. 21-nonies della L. 241/1990")
    assert CheckTerminiAutotutela().valuta(ctx).stato is Stato.GIALLO


# --- Check 5: comunicazione avvio -------------------------------------------


def test_check5_presente_verde():
    ctx = _contesto("data comunicazione di avvio del procedimento ai partecipanti")
    assert CheckComunicazioneAvvio().valuta(ctx).stato is Stato.VERDE


def test_check5_assente_rosso():
    ctx = _contesto("si dispone l'annullamento senza ulteriori comunicazioni")
    assert CheckComunicazioneAvvio().valuta(ctx).stato is Stato.ROSSO


# --- Check 6: coerenza firmatari --------------------------------------------


def test_check6_stesso_firmatario_giallo():
    ctx = _contesto(
        "annullamento\nF.to Dott. Mario Rossi",
        originario="indizione\nF.to Dott. Mario Rossi",
    )
    esito = CheckCoerenzaFirmatari().valuta(ctx)
    assert esito.stato is Stato.GIALLO
    assert esito.citazioni


def test_check6_firmatari_diversi_verde():
    ctx = _contesto(
        "annullamento\nF.to Dott.ssa Anna Bianchi",
        originario="indizione\nF.to Dott. Mario Rossi",
    )
    assert CheckCoerenzaFirmatari().valuta(ctx).stato is Stato.VERDE


def test_check6_secondo_nome_omesso_match():
    # Regressione dal primo fascicolo reale: "Pietro Amorosia" e
    # "Pietro Nicola Amorosia" sono la stessa persona → 🟡, non falso 🟢.
    ctx = _contesto(
        "revoca in autotutela\nF.to Dott. Pietro Amorosia",
        originario="approvazione avviso\nF.to Dott. Pietro Nicola Amorosia",
    )
    assert CheckCoerenzaFirmatari().valuta(ctx).stato is Stato.GIALLO


def test_check6_solo_cognome_condiviso_non_match():
    # Prudenza: il solo cognome in comune (parenti/omonimi) non basta.
    ctx = _contesto(
        "revoca in autotutela\nF.to Dott. Mario Rossi",
        originario="indizione\nF.to Dott.ssa Anna Rossi",
    )
    assert CheckCoerenzaFirmatari().valuta(ctx).stato is Stato.VERDE


def test_check6_non_applicabile_senza_originario():
    ctx = _contesto("annullamento\nF.to Dott. Mario Rossi")
    assert CheckCoerenzaFirmatari().applicabile(ctx) is False
