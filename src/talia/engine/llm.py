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

_OLLAMA_BASE_URL = "http://localhost:11434"
MODELLO_DEFAULT = "qwen3:4b"
# Modelli locali "thinking" (es. qwen3) generano un ragionamento esteso prima
# della risposta finale anche su prompt brevi: 120s non bastano su CPU per un
# prompt con contesto RAG allegato. 300s neanche: verificato su due fascicoli
# reali (TAL-12/TAL-54, prompt ~10-12k caratteri) tempi di 344.8s e 423.8s,
# entrambi in timeout con la soglia precedente — margine ampio per non
# ripetere lo stesso problema su un fascicolo più pesante.
_TIMEOUT_SECONDI = 900


class LLMNonDisponibile(RuntimeError):
    """Il servizio LLM locale (Ollama) non è raggiungibile o ha risposto con errore."""


def chiama_ollama(
    prompt: str,
    modello: str,
    *,
    base_url: str = _OLLAMA_BASE_URL,
    timeout: int,
    opener: urllib.request.OpenerDirector | None = None,
    opzioni: dict | None = None,
) -> dict:
    """POST a `{base_url}/api/generate`, ritorna il corpo della risposta già decodificato.

    Helper di basso livello condiviso tra `genera()` (qui, nessun fallback
    silenzioso) e `engine.catena.classifica_ruolo_llm` (fallback silenzioso,
    Strategia 4 opt-in): evita di duplicare la costruzione della richiesta
    HTTP/JSON in due punti del codice — prima duplicata, i due client erano già
    andati alla deriva (temperatura, gestione errori). Solleva sempre
    `LLMNonDisponibile` su errore di rete o risposta non-JSON; i chiamanti che
    vogliono degradare in silenzio la catturano esplicitamente.
    """
    opener = opener or urllib.request
    payload: dict = {"model": modello, "prompt": prompt, "stream": False}
    if opzioni:
        payload["options"] = opzioni
    richiesta = urllib.request.Request(
        f"{base_url}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with opener.urlopen(richiesta, timeout=timeout) as risposta:
            return json.loads(risposta.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise LLMNonDisponibile(
            f"LLM locale non raggiungibile su {base_url} (modello {modello}): {exc}"
        ) from exc


def genera(
    prompt: str,
    modello: str = MODELLO_DEFAULT,
    timeout: int = _TIMEOUT_SECONDI,
    opener: urllib.request.OpenerDirector | None = None,
) -> str:
    """Invoca il modello locale via Ollama e ritorna il testo generato.

    Solleva `LLMNonDisponibile` se Ollama non è in esecuzione, risponde con
    errore (compresa una risposta non-JSON), o la risposta non contiene testo
    generato. `opener` è iniettabile per i test (evita chiamate di rete reali
    nella suite).
    """
    try:
        corpo = chiama_ollama(prompt, modello, timeout=timeout, opener=opener)
    except LLMNonDisponibile as exc:
        raise LLMNonDisponibile(
            f"{exc}. Verificare che 'ollama serve' sia attivo e che il modello sia "
            "scaricato ('ollama pull <modello>')."
        ) from exc

    testo = corpo.get("response")
    if not testo:
        raise LLMNonDisponibile(f"Risposta Ollama senza campo 'response': {corpo}")
    return testo


__all__ = ["LLMNonDisponibile", "MODELLO_DEFAULT", "chiama_ollama", "genera"]
