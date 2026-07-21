"""Test TAL-11: check-3 qualità della motivazione (unico check LLM).

Nessuna chiamata di rete reale: `genera` (client Ollama) è monkeypatchato.
L'indice RAG usato nei test è uno stub minimale (non il corpus reale), per
tenere i test veloci e deterministici.
"""

from __future__ import annotations

from talia.engine.checklist import check3_motivazione as mod
from talia.engine.checklist.base import EsitoCheck
from talia.engine.checklist.check3_motivazione import (
    SOGLIA_ASSENTE,
    _calcola_stato,
    _estrai_giudizio,
    flaggato_da_check_precedenti,
    valuta_motivazione,
)
from talia.engine.fascicolo import AttoAnalizzato, ContestoFascicolo, RuoloAtto
from talia.engine.models import Stato
from talia.engine.pdf_text import da_testo
from talia.engine.rag import Passaggio


def _esito(stato: Stato, id_: str = "check-x") -> EsitoCheck:
    return EsitoCheck(id=id_, titolo="test", stato=stato, spiegazione="")


def _contesto(testo: str) -> ContestoFascicolo:
    atto = AttoAnalizzato.da_testo(da_testo(testo), ruolo=RuoloAtto.AUTOTUTELA)
    return ContestoFascicolo(atto_autotutela=atto)


class _IndiceFinto:
    def __init__(self, passaggi=None):
        self._passaggi = passaggi or []

    def cerca(self, query, k=5):
        return self._passaggi[:k]


_MOTIVAZIONE_LUNGA = (
    "considerato che " + "l'interesse pubblico concreto e attuale impone la revoca " * 3
)
# Oltre 200 caratteri dopo l'isolamento: esercita il ramo di troncamento della
# citazione (vedi test_citazione_troncata_ha_offset_coerente_col_testo).
_MOTIVAZIONE_MOLTO_LUNGA = "considerato che " + "l'interesse pubblico concreto e attuale " * 10


def test_flaggato_da_check_precedenti_true_con_rosso():
    assert flaggato_da_check_precedenti([_esito(Stato.VERDE), _esito(Stato.ROSSO)])


def test_flaggato_da_check_precedenti_true_con_giallo():
    assert flaggato_da_check_precedenti([_esito(Stato.GIALLO)])


def test_flaggato_da_check_precedenti_false_solo_verde_o_na():
    assert not flaggato_da_check_precedenti([_esito(Stato.VERDE), _esito(Stato.NON_APPLICABILE)])


def test_non_applicabile_se_nessun_check_precedente_ha_flaggato():
    contesto = _contesto(_MOTIVAZIONE_LUNGA)
    esito = valuta_motivazione(contesto, [_esito(Stato.VERDE)], indice=_IndiceFinto())
    assert esito.stato is Stato.NON_APPLICABILE


def test_rosso_automatico_su_motivazione_assente_senza_chiamare_llm(monkeypatch):
    def _fallisce(*a, **k):
        raise AssertionError("genera() non deve essere chiamato per motivazione assente")

    monkeypatch.setattr(mod, "genera", _fallisce)
    contesto = _contesto("considerato che urge.")
    assert len("considerato che urge.") < SOGLIA_ASSENTE
    esito = valuta_motivazione(contesto, [_esito(Stato.ROSSO)], indice=_IndiceFinto())
    assert esito.stato is Stato.ROSSO
    assert "breve" in esito.spiegazione or "assente" in esito.spiegazione


def test_verde_su_giudizio_llm_specifica(monkeypatch):
    monkeypatch.setattr(
        mod,
        "genera",
        lambda prompt: '{"giudizio": "specifica", "spiegazione": "motivazione concreta"}',
    )
    contesto = _contesto(_MOTIVAZIONE_LUNGA)
    passaggi = [
        Passaggio(
            testo="testo norma", fonte="nazionale/l-241-1990.md", offset_inizio=10, offset_fine=21
        )
    ]
    esito = valuta_motivazione(contesto, [_esito(Stato.ROSSO)], indice=_IndiceFinto(passaggi))
    assert esito.stato is Stato.VERDE
    assert esito.spiegazione == "motivazione concreta"
    # Riferimento puntuale: filename + offset + testo esatto, non un bare filename.
    rif_corpus = esito.riferimenti_normativi[-1]
    assert "nazionale/l-241-1990.md" in rif_corpus
    assert "10-21" in rif_corpus
    assert "testo norma" in rif_corpus
    assert esito.citazioni


def test_calcola_stato_specifica_senza_carenza_istruttoria_e_verde():
    assert _calcola_stato("specifica", carenza_istruttoria=False) is Stato.VERDE


def test_calcola_stato_specifica_con_carenza_istruttoria_e_giallo():
    # Osservazione concreta su un fascicolo reale (TAL-12/fascicolo 1): una
    # motivazione narrativamente ricca che tratta come accertata una "presunta
    # divulgazione" (parola dell'atto stesso), senza descrivere alcuna
    # istruttoria autonoma, non merita un 🟢 pieno.
    assert _calcola_stato("specifica", carenza_istruttoria=True) is Stato.GIALLO


def test_calcola_stato_generica_e_rosso_a_prescindere_dalla_istruttoria():
    assert _calcola_stato("generica", carenza_istruttoria=False) is Stato.ROSSO
    assert _calcola_stato("generica", carenza_istruttoria=True) is Stato.ROSSO


def test_calcola_stato_incerta_e_giallo():
    assert _calcola_stato("incerta", carenza_istruttoria=False) is Stato.GIALLO


def test_giallo_su_specifica_con_carenza_istruttoria_rilevata_dal_llm(monkeypatch):
    monkeypatch.setattr(
        mod,
        "genera",
        lambda prompt: (
            '{"giudizio": "specifica", "carenza_istruttoria": true, '
            '"spiegazione": "cita un interesse concreto ma su un fatto solo presunto"}'
        ),
    )
    contesto = _contesto(_MOTIVAZIONE_LUNGA)
    esito = valuta_motivazione(contesto, [_esito(Stato.ROSSO)], indice=_IndiceFinto())
    assert esito.stato is Stato.GIALLO
    assert "presunto" in esito.spiegazione
    assert "non è un giudizio pieno" in esito.spiegazione


def test_carenza_istruttoria_assente_dalla_risposta_non_penalizza(monkeypatch):
    # Un modello che non usa il nuovo campo (o lo omette) non deve essere
    # penalizzato: assenza di segnalazione ≠ carenza presunta.
    monkeypatch.setattr(
        mod, "genera", lambda prompt: '{"giudizio": "specifica", "spiegazione": "ok"}'
    )
    contesto = _contesto(_MOTIVAZIONE_LUNGA)
    esito = valuta_motivazione(contesto, [_esito(Stato.ROSSO)], indice=_IndiceFinto())
    assert esito.stato is Stato.VERDE


def test_citazione_troncata_ha_offset_coerente_col_testo(monkeypatch):
    # Regressione: offset_fine indicava la fine dell'INTERA motivazione anche
    # quando il testo citato era troncato a 200 caratteri — dichiarando un
    # intervallo più ampio di quanto effettivamente riportato tra virgolette
    # (stesso principio dei riferimenti puntuali al corpus normativo).
    assert len(_MOTIVAZIONE_MOLTO_LUNGA) - len("considerato che ") > 200
    monkeypatch.setattr(
        mod, "genera", lambda prompt: '{"giudizio": "specifica", "spiegazione": "ok"}'
    )
    contesto = _contesto(_MOTIVAZIONE_MOLTO_LUNGA)
    esito = valuta_motivazione(contesto, [_esito(Stato.ROSSO)], indice=_IndiceFinto())
    citazione = esito.citazioni[0]
    assert citazione.offset_fine - citazione.offset_inizio == 200


def test_rosso_su_giudizio_llm_generica(monkeypatch):
    monkeypatch.setattr(
        mod, "genera", lambda prompt: '{"giudizio": "generica", "spiegazione": "boilerplate"}'
    )
    contesto = _contesto(_MOTIVAZIONE_LUNGA)
    esito = valuta_motivazione(contesto, [_esito(Stato.ROSSO)], indice=_IndiceFinto())
    assert esito.stato is Stato.ROSSO


def test_giallo_su_risposta_llm_non_json(monkeypatch):
    monkeypatch.setattr(mod, "genera", lambda prompt: "risposta senza json valido")
    contesto = _contesto(_MOTIVAZIONE_LUNGA)
    esito = valuta_motivazione(contesto, [_esito(Stato.ROSSO)], indice=_IndiceFinto())
    assert esito.stato is Stato.GIALLO


def test_estrai_giudizio_ignora_json_di_esempio_ripetuto_dal_modello():
    # Regressione: qwen3:4b (verificato con Ollama reale) a volte "ragiona ad
    # alta voce" ripetendo lo schema JSON del prompt prima di dare la risposta
    # vera. Un regex greedy \{.*\} catturerebbe tutto tra la prima e l'ultima
    # graffa (JSON non valido); si deve prendere l'ultimo oggetto valido.
    risposta = (
        'Il formato atteso è {"giudizio": "specifica|generica|incerta", '
        '"spiegazione": "..."}. Analizzando il testo, concludo che: '
        '{"giudizio": "generica", "spiegazione": "boilerplate senza elementi concreti"}'
    )
    giudizio, carenza_istruttoria, spiegazione = _estrai_giudizio(risposta)
    assert giudizio == "generica"
    assert carenza_istruttoria is False
    assert spiegazione == "boilerplate senza elementi concreti"


def test_estrai_giudizio_risposta_senza_json_ritorna_incerta():
    giudizio, carenza_istruttoria, spiegazione = _estrai_giudizio(
        "non sono in grado di rispondere in JSON"
    )
    assert giudizio == "incerta"
    assert carenza_istruttoria is False
    assert "non interpretabile" in spiegazione


def test_giudizio_sconosciuto_trattato_come_incerta(monkeypatch):
    monkeypatch.setattr(
        mod, "genera", lambda prompt: '{"giudizio": "boh", "spiegazione": "non chiaro"}'
    )
    contesto = _contesto(_MOTIVAZIONE_LUNGA)
    esito = valuta_motivazione(contesto, [_esito(Stato.ROSSO)], indice=_IndiceFinto())
    assert esito.stato is Stato.GIALLO
