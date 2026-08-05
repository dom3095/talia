"""Test client LLM locale via Ollama — TAL-11.

Nessuna chiamata di rete reale: un opener finto simula le risposte di
`urllib.request.urlopen` (stessa convenzione di `test_pdf_download.py`).
"""

from __future__ import annotations

import json
import urllib.error

import pytest

from talia.engine.llm import LLMNonDisponibile, genera


class _RispostaFinta:
    def __init__(self, corpo: dict):
        self._corpo = json.dumps(corpo).encode("utf-8")

    def read(self):
        return self._corpo

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _OpenerFinto:
    def __init__(self, risposta=None, eccezione: Exception | None = None):
        self._risposta = risposta
        self._eccezione = eccezione
        self.ultima_richiesta = None

    def urlopen(self, richiesta, timeout=None):
        self.ultima_richiesta = richiesta
        if self._eccezione is not None:
            raise self._eccezione
        return self._risposta


def test_genera_ritorna_il_testo_generato():
    opener = _OpenerFinto(risposta=_RispostaFinta({"response": "esito: specifica"}))
    testo = genera("un prompt qualsiasi", opener=opener)
    assert testo == "esito: specifica"


def test_genera_invia_il_modello_e_il_prompt_nel_payload():
    opener = _OpenerFinto(risposta=_RispostaFinta({"response": "ok"}))
    genera("prompt di test", modello="qwen3:4b", opener=opener)
    corpo = json.loads(opener.ultima_richiesta.data.decode("utf-8"))
    assert corpo["model"] == "qwen3:4b"
    assert corpo["prompt"] == "prompt di test"
    assert corpo["stream"] is False


def test_genera_solleva_llm_non_disponibile_su_errore_di_rete():
    opener = _OpenerFinto(eccezione=urllib.error.URLError("connection refused"))
    with pytest.raises(LLMNonDisponibile):
        genera("un prompt", opener=opener)


def test_genera_solleva_llm_non_disponibile_su_timeout():
    opener = _OpenerFinto(eccezione=TimeoutError())
    with pytest.raises(LLMNonDisponibile):
        genera("un prompt", opener=opener)


def test_genera_solleva_llm_non_disponibile_su_risposta_senza_testo():
    opener = _OpenerFinto(risposta=_RispostaFinta({}))
    with pytest.raises(LLMNonDisponibile):
        genera("un prompt", opener=opener)
