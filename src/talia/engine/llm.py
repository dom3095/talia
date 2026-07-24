"""Client minimale per LLM locale via Ollama — TAL-11.

Nessuna dipendenza a pagamento: interroga un'istanza Ollama in esecuzione in
locale (`ollama serve`, default `localhost:11434`). Se il servizio non
risponde, l'errore è propagato esplicitamente — nessun fallback silenzioso:
un giudizio non ottenuto va segnalato all'utente, non mascherato da un esito
di comodo (🟢/🟡) che sembrerebbe un giudizio genuino.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

_OLLAMA_URL = "http://localhost:11434/api/generate"
MODELLO_DEFAULT = "qwen3:4b"
# Modelli locali "thinking" (es. qwen3) generano un ragionamento esteso prima
# della risposta finale anche su prompt brevi: verificato empiricamente che
# 120s non bastano su CPU per un prompt con contesto RAG allegato.
_TIMEOUT_SECONDI = 300


class LLMNonDisponibile(RuntimeError):
    """Il servizio LLM locale (Ollama) non è raggiungibile o ha risposto con errore."""


def genera(
    prompt: str,
    modello: str = MODELLO_DEFAULT,
    timeout: int = _TIMEOUT_SECONDI,
    opener: urllib.request.OpenerDirector | None = None,
) -> str:
    """Invoca il modello locale via Ollama e ritorna il testo generato.

    Solleva `LLMNonDisponibile` se Ollama non è in esecuzione, risponde con
    errore, o la risposta non contiene testo generato. `opener` è iniettabile
    per i test (evita chiamate di rete reali nella suite).
    """
    opener = opener or urllib.request
    payload = json.dumps({"model": modello, "prompt": prompt, "stream": False}).encode("utf-8")
    richiesta = urllib.request.Request(
        _OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with opener.urlopen(richiesta, timeout=timeout) as risposta:
            corpo = json.loads(risposta.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise LLMNonDisponibile(
            f"LLM locale non raggiungibile su {_OLLAMA_URL} (modello {modello}): {exc}. "
            "Verificare che 'ollama serve' sia attivo e che il modello sia scaricato "
            "('ollama pull <modello>')."
        ) from exc

    testo = corpo.get("response")
    if not testo:
        raise LLMNonDisponibile(f"Risposta Ollama senza campo 'response': {corpo}")
    return testo


__all__ = ["LLMNonDisponibile", "MODELLO_DEFAULT", "genera"]
