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
    _cerca_passaggi_rag,
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


class _IndiceSelettivo:
    """Stub che ritorna passaggi diversi a seconda del contenuto della query.

    Simula il caso reale scoperto in TAL-54: la query sulla sola motivazione
    (`_generico`) non intercetta il passaggio pertinente, mentre una query sui
    riferimenti normativi del check che l'ha già individuato sì (`_mirato`,
    restituito solo se `_termine_chiave` compare nella query).
    """

    def __init__(self, generico, mirato, termine_chiave):
        self._generico = generico
        self._mirato = mirato
        self._termine_chiave = termine_chiave

    def cerca(self, query, k=5):
        if self._termine_chiave in query:
            return [self._mirato][:k]
        return self._generico[:k]


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
        lambda prompt, **_: '{"giudizio": "specifica", "spiegazione": "motivazione concreta"}',
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


def test_valuta_motivazione_chiama_genera_con_temperatura_zero(monkeypatch):
    # TAL-54: senza temperature=0 il giudizio non è riproducibile — osservato
    # in sessione un giudizio diverso tra due run identici sullo stesso atto.
    chiamate = []

    def _spia(prompt, **kwargs):
        chiamate.append(kwargs)
        return '{"giudizio": "specifica", "spiegazione": "ok"}'

    monkeypatch.setattr(mod, "genera", _spia)
    contesto = _contesto(_MOTIVAZIONE_LUNGA)
    valuta_motivazione(contesto, [_esito(Stato.ROSSO)], indice=_IndiceFinto())
    assert chiamate == [{"opzioni": {"temperature": 0}}]


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
        lambda prompt, **_: (
            '{"giudizio": "specifica", "carenza_istruttoria": true, '
            '"spiegazione": "cita un interesse concreto ma su un fatto solo presunto"}'
        ),
    )
    contesto = _contesto(_MOTIVAZIONE_LUNGA)
    esito = valuta_motivazione(contesto, [_esito(Stato.ROSSO)], indice=_IndiceFinto())
    assert esito.stato is Stato.GIALLO
    assert "presunto" in esito.spiegazione
    assert "non è un giudizio pieno" in esito.spiegazione
    # Regressione: la spiegazione del LLM (senza punto finale nel fixture) e la
    # nota aggiunta non devono fondersi senza separazione ("...presunto Motivazione...").
    assert "presunto. Motivazione narrativamente specifica" in esito.spiegazione


def test_carenza_istruttoria_assente_dalla_risposta_non_penalizza(monkeypatch):
    # Un modello che non usa il nuovo campo (o lo omette) non deve essere
    # penalizzato: assenza di segnalazione ≠ carenza presunta.
    monkeypatch.setattr(
        mod, "genera", lambda prompt, **_: '{"giudizio": "specifica", "spiegazione": "ok"}'
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
        mod, "genera", lambda prompt, **_: '{"giudizio": "specifica", "spiegazione": "ok"}'
    )
    contesto = _contesto(_MOTIVAZIONE_MOLTO_LUNGA)
    esito = valuta_motivazione(contesto, [_esito(Stato.ROSSO)], indice=_IndiceFinto())
    citazione = esito.citazioni[0]
    assert citazione.offset_fine - citazione.offset_inizio == 200


def test_rosso_su_giudizio_llm_generica(monkeypatch):
    monkeypatch.setattr(
        mod, "genera", lambda prompt, **_: '{"giudizio": "generica", "spiegazione": "boilerplate"}'
    )
    contesto = _contesto(_MOTIVAZIONE_LUNGA)
    esito = valuta_motivazione(contesto, [_esito(Stato.ROSSO)], indice=_IndiceFinto())
    assert esito.stato is Stato.ROSSO


def test_giallo_su_risposta_llm_non_json(monkeypatch):
    monkeypatch.setattr(mod, "genera", lambda prompt, **_: "risposta senza json valido")
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


def test_estrai_giudizio_gestisce_graffe_letterali_nella_spiegazione():
    # Regressione code review: un regex piatto \{[^{}]*\} spezza il parsing se
    # un valore (qui "spiegazione") contiene una graffa letterale, perché la
    # trova come chiusura prematura dell'oggetto. Serve un conteggio di
    # profondità che ignori le graffe dentro le stringhe JSON.
    risposta = (
        '{"giudizio": "generica", "carenza_istruttoria": false, '
        '"spiegazione": "richiama solo {ripristino della legalità} senza altro"}'
    )
    giudizio, carenza_istruttoria, spiegazione = _estrai_giudizio(risposta)
    assert giudizio == "generica"
    assert carenza_istruttoria is False
    assert spiegazione == "richiama solo {ripristino della legalità} senza altro"


def test_giallo_su_incerta_con_carenza_istruttoria_include_nota(monkeypatch):
    # Regressione code review: la nota di carenza istruttoria veniva aggiunta
    # solo per giudizio == "specifica", non per "incerta" — pur essendo un
    # segnale del LLM comunque rilevante da mostrare.
    monkeypatch.setattr(
        mod,
        "genera",
        lambda prompt, **_: (
            '{"giudizio": "incerta", "carenza_istruttoria": true, '
            '"spiegazione": "non è chiaro se la motivazione sia specifica"}'
        ),
    )
    contesto = _contesto(_MOTIVAZIONE_LUNGA)
    esito = valuta_motivazione(contesto, [_esito(Stato.ROSSO)], indice=_IndiceFinto())
    assert esito.stato is Stato.GIALLO
    assert "non è un giudizio pieno" in esito.spiegazione


def test_cita_passaggio_troncato_ha_offset_coerente_col_testo():
    # Regressione code review: l'estratto del passaggio era troncato a 220
    # caratteri per la resa a schermo, ma offset_fine riportava comunque la
    # fine dell'intero chunk — un intervallo più ampio di quanto citato tra
    # virgolette (stesso principio già corretto per la citazione dell'atto).
    testo_lungo = "articolo di legge rilevante " * 20  # ben oltre 220 caratteri
    passaggio = Passaggio(
        testo=testo_lungo,
        fonte="nazionale/x.md",
        offset_inizio=100,
        offset_fine=100 + len(testo_lungo),
    )
    rif_corpus = mod._cita_passaggio(passaggio)
    assert "100-320" in rif_corpus  # 100 + 220
    estratto = rif_corpus.split("«")[1].rstrip("»")
    assert estratto.endswith("…")


def test_giudizio_sconosciuto_trattato_come_incerta(monkeypatch):
    monkeypatch.setattr(
        mod, "genera", lambda prompt, **_: '{"giudizio": "boh", "spiegazione": "non chiaro"}'
    )
    contesto = _contesto(_MOTIVAZIONE_LUNGA)
    esito = valuta_motivazione(contesto, [_esito(Stato.ROSSO)], indice=_IndiceFinto())
    assert esito.stato is Stato.GIALLO


# --- TAL-54: retrieval arricchito coi riferimenti dei check già flaggati ----

_RIF_GDPR = ["Art. 33 GDPR (notifica violazione dati all'Autorità di controllo entro 72h)"]


def _passaggio(fonte: str, testo: str = "norma") -> Passaggio:
    return Passaggio(testo=testo, fonte=fonte, offset_inizio=0, offset_fine=10)


def test_cerca_passaggi_rag_recupera_passaggio_di_check_flaggato_non_visto_dalla_motivazione():
    # Caso reale (TAL-54, fascicolo 1): la motivazione parla di "riservatezza",
    # mai di "GDPR"/"dati personali" — la query sulla sola motivazione manca il
    # passaggio, ma check-7 l'aveva già individuato coi suoi riferimenti.
    generico = [_passaggio("nazionale/a.md"), _passaggio("nazionale/b.md")]
    gdpr = _passaggio("ue/gdpr-679-2016.md")
    indice = _IndiceSelettivo(generico, gdpr, termine_chiave="GDPR")
    check7 = EsitoCheck(
        id="check-7", titolo="t", stato=Stato.ROSSO, spiegazione="", riferimenti_normativi=_RIF_GDPR
    )
    passaggi = _cerca_passaggi_rag(indice, "motivazione senza vocabolario pertinente", [check7])
    assert gdpr in passaggi
    assert generico[0] in passaggi  # la query sulla motivazione resta comunque interrogata


def test_cerca_passaggi_rag_ignora_check_non_flaggati():
    generico = [_passaggio("nazionale/a.md")]
    gdpr = _passaggio("ue/gdpr-679-2016.md")
    indice = _IndiceSelettivo(generico, gdpr, termine_chiave="GDPR")
    verde = EsitoCheck(
        id="check-7", titolo="t", stato=Stato.VERDE, spiegazione="", riferimenti_normativi=_RIF_GDPR
    )
    passaggi = _cerca_passaggi_rag(indice, "motivazione", [verde])
    assert gdpr not in passaggi


def test_cerca_passaggi_rag_ignora_check_senza_riferimenti():
    generico = [_passaggio("nazionale/a.md")]
    gdpr = _passaggio("ue/gdpr-679-2016.md")
    indice = _IndiceSelettivo(generico, gdpr, termine_chiave="GDPR")
    senza_rif = EsitoCheck(id="check-7", titolo="t", stato=Stato.ROSSO, spiegazione="")
    passaggi = _cerca_passaggi_rag(indice, "motivazione", [senza_rif])
    assert gdpr not in passaggi


def test_cerca_passaggi_rag_dedup_passaggio_gia_trovato_dalla_motivazione():
    p = _passaggio("ue/gdpr-679-2016.md")
    indice = _IndiceSelettivo([p], p, termine_chiave="GDPR")
    check7 = EsitoCheck(
        id="check-7", titolo="t", stato=Stato.ROSSO, spiegazione="", riferimenti_normativi=_RIF_GDPR
    )
    passaggi = _cerca_passaggi_rag(indice, "motivazione", [check7])
    assert passaggi.count(p) == 1


def test_cerca_passaggi_rag_non_tronca_il_contributo_di_ogni_check():
    # Regressione: un taglio secco sul totale (k=5) dopo aver iterato tutti i
    # check scartava il contributo dei check flaggati per ultimi — qui 4 check
    # diversi devono comparire tutti, anche con k_motivazione già a 3.
    generico = [
        _passaggio("nazionale/a.md"),
        _passaggio("nazionale/b.md"),
        _passaggio("nazionale/c.md"),
    ]
    mirati = {f"CHIAVE{i}": _passaggio(f"nazionale/mirato{i}.md") for i in range(4)}

    class _IndiceMultiChiave:
        def cerca(self, query, k=5):
            for chiave, passaggio in mirati.items():
                if chiave in query:
                    return [passaggio][:k]
            return generico[:k]

    esiti = [
        EsitoCheck(
            id=f"check-{i}",
            titolo="t",
            stato=Stato.ROSSO,
            spiegazione="",
            riferimenti_normativi=[f"CHIAVE{i}"],
        )
        for i in range(4)
    ]
    passaggi = _cerca_passaggi_rag(_IndiceMultiChiave(), "motivazione", esiti)
    for mirato in mirati.values():
        assert mirato in passaggi


def test_valuta_motivazione_include_riferimento_di_check_flaggato_non_coperto_dalla_motivazione(
    monkeypatch,
):
    monkeypatch.setattr(
        mod, "genera", lambda prompt, **_: '{"giudizio": "specifica", "spiegazione": "ok"}'
    )
    contesto = _contesto(_MOTIVAZIONE_LUNGA)
    generico = [_passaggio("nazionale/a.md")]
    gdpr = _passaggio("ue/gdpr-679-2016.md", testo="disciplina della violazione dei dati personali")
    indice = _IndiceSelettivo(generico, gdpr, termine_chiave="GDPR")
    check7 = EsitoCheck(
        id="check-7", titolo="t", stato=Stato.ROSSO, spiegazione="", riferimenti_normativi=_RIF_GDPR
    )
    esito = valuta_motivazione(contesto, [check7], indice=indice)
    assert any("gdpr" in rif.lower() for rif in esito.riferimenti_normativi)


def test_prompt_istruisce_il_llm_a_dichiarare_il_fondamento_normativo():
    # TAL-54: senza questa istruzione la spiegazione del LLM non citava mai i
    # passaggi allegati, anche quando pertinenti — nessuna garanzia che il
    # giudizio fosse davvero fondato sul contesto normativo recuperato.
    assert "tra parentesi quadre" in mod._PROMPT_TEMPLATE
    assert "nessuna delle norme elencate è pertinente" in mod._PROMPT_TEMPLATE
