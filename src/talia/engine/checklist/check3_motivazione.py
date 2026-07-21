"""TAL-11 — Check 3: qualità della motivazione (unico check che usa LLM).

Eseguito **solo** su fascicoli già flaggati (🟡/🔴) da almeno un check
deterministico precedente: la componente LLM è un'eccezione mirata, non la
regola (principio "determinismo prima" — vedi CLAUDE.md). Isola la sezione di
motivazione dell'atto di autotutela, recupera dal corpus normativo (via BM25,
`engine.rag`) i passaggi più pertinenti, e chiede al LLM locale (Ollama,
`engine.llm`) di valutare densità/specificità della motivazione rispetto ai
requisiti giurisprudenziali (interesse pubblico concreto e attuale,
comparazione con l'affidamento dei privati destinatari dell'atto).

A differenza degli altri check, **non è registrato** nel registry automatico
di `checklist/base.py`: richiede sia gli esiti dei check precedenti sia una
chiamata di rete (LLM locale), quindi viene invocato esplicitamente da
`analizza_testi`/`analizza_fascicolo` con `valuta_llm=True` — mai a sorpresa
durante un'esecuzione "solo checklist deterministica".
"""

from __future__ import annotations

import json
import re

from ..fascicolo import ContestoFascicolo
from ..llm import genera
from ..models import Citazione, Stato
from ..rag import IndiceCorpus, Passaggio
from .base import EsitoCheck

ID = "check-3"
TITOLO = "Qualità della motivazione (LLM)"

_RIFERIMENTI = (
    "Requisito giurisprudenziale: interesse pubblico concreto e attuale alla revoca/annullamento",
    "Requisito giurisprudenziale: comparazione con l'affidamento dei privati destinatari dell'atto",
)

# Sotto questa soglia la motivazione è considerata assente: 🔴 automatico,
# senza invocare il LLM (spec TAL-11 — evita una chiamata di rete inutile).
SOGLIA_ASSENTE = 50

_STATI_FLAG = (Stato.ROSSO, Stato.GIALLO)

# La sezione di motivazione tipicamente inizia con formule di stile
# "premesso/considerato/ritenuto che..." e termina dove comincia il dispositivo
# ("determina/decreta/dispone"). Se non trovata, l'intero testo è trattato come
# motivazione (fallback prudente: mai restituire una motivazione vuota per un
# atto che in realtà la contiene, solo perché non riconosciamo il pattern).
_RE_MOTIVAZIONE = re.compile(
    r"(?:premesso che|considerato che|ritenuto che|dato atto che)"
    r"(.+?)(?=\n\s*(?:determina|decreta|dispone)\b|\Z)",
    re.IGNORECASE | re.DOTALL,
)

_PROMPT_TEMPLATE = """Sei un giurista che valuta la qualità della motivazione di un atto \
amministrativo di autotutela (revoca/annullamento).

MOTIVAZIONE DA VALUTARE:
\"\"\"{motivazione}\"\"\"

NORME E GIURISPRUDENZA PERTINENTI (contesto di riferimento, non necessariamente citate nell'atto):
{contesto_normativo}

Valuta la motivazione su due aspetti distinti:

1. SPECIFICITÀ: è SPECIFICA (indica un interesse pubblico concreto e attuale, e tiene \
conto dell'affidamento dei privati destinatari) oppure GENERICA/BOILERPLATE (mero \
richiamo formale, es. "ripristino della legalità", senza elementi concreti)?

2. ISTRUTTORIA: la motivazione tratta come accertato un fatto che l'atto stesso descrive \
come presunto, segnalato da terzi o non ancora verificato (es. "presunta violazione", una \
segnalazione riportata senza indicare alcuna verifica autonoma svolta dall'amministrazione \
prima di agire)? Se sì, è una carenza di istruttoria — anche quando la motivazione è \
narrativamente ricca e dettagliata, una motivazione specifica basata su fatti non \
verificati non equivale a una motivazione robusta.

Rispondi SOLO con un oggetto JSON, senza altro testo prima o dopo:
{{"giudizio": "specifica|generica|incerta", "carenza_istruttoria": true|false, \
"spiegazione": "una frase che motiva entrambi i giudizi"}}
"""


def _calcola_stato(giudizio: str, carenza_istruttoria: bool) -> Stato:
    """Deriva lo stato dai due giudizi del LLM.

    Una motivazione "specifica" ma basata su un fatto che l'atto stesso
    definisce presunto/non verificato, senza istruttoria autonoma
    documentata, non merita un 🟢 pieno: la ricchezza narrativa non compensa
    l'aver agito su un'allegazione data per scontata (osservazione concreta
    su un fascicolo reale, TAL-12/fascicolo 1 — la revoca tratta come
    accertata una "presunta divulgazione" senza descrivere alcuna verifica).
    """
    if giudizio == "generica":
        return Stato.ROSSO
    if giudizio == "incerta":
        return Stato.GIALLO
    return Stato.GIALLO if carenza_istruttoria else Stato.VERDE


_NOTA_CARENZA_ISTRUTTORIA = (
    "Motivazione narrativamente specifica, ma il LLM segnala che tratta come accertato "
    "un fatto che l'atto stesso descrive come presunto/non verificato, senza istruttoria "
    "autonoma documentata: non è un giudizio pieno."
)


def _unisci_frasi(prima: str, seconda: str) -> str:
    """Concatena due frasi assicurando la punteggiatura tra loro.

    La spiegazione del LLM non sempre termina con un punto (dipende dal
    modello): senza questo accorgimento due frasi si fondevano senza
    separazione visiva nel report (es. "...accertamenti interni Motivazione
    narrativamente...").
    """
    prima = prima.rstrip()
    if prima and not prima.endswith((".", "!", "?")):
        prima += "."
    return f"{prima} {seconda}".strip()


def flaggato_da_check_precedenti(esiti_precedenti: list[EsitoCheck]) -> bool:
    """True se almeno un check deterministico precedente ha dato 🟡/🔴."""
    return any(e.stato in _STATI_FLAG for e in esiti_precedenti)


def _isola_motivazione(testo: str) -> str:
    match = _RE_MOTIVAZIONE.search(testo)
    return match.group(1).strip() if match else testo.strip()


_GIUDIZI_VALIDI = frozenset({"specifica", "generica", "incerta"})


def _estrai_giudizio(risposta: str) -> tuple[str, bool, str]:
    """Estrae {giudizio, carenza_istruttoria, spiegazione} dal JSON nella risposta del LLM.

    I modelli "thinking" locali (es. qwen3) spesso ragionano ad alta voce prima
    della risposta finale, ripetendo talvolta l'esempio di formato del prompt
    (con lo stesso schema di chiavi) prima di dare la risposta vera: si cercano
    tutti gli oggetti JSON non annidati nella risposta e si prende l'**ultimo**
    che contiene la chiave "giudizio" (verificato empiricamente contro qwen3:4b
    via Ollama — un singolo regex greedy `\\{.*\\}` cattura tutto tra la prima
    e l'ultima graffa e fallisce il parsing quando compaiono più oggetti).
    """
    candidati = re.findall(r"\{[^{}]*\}", risposta, re.DOTALL)
    for candidato in reversed(candidati):
        try:
            dati = json.loads(candidato)
        except json.JSONDecodeError:
            continue
        if "giudizio" not in dati:
            continue
        giudizio = dati.get("giudizio", "incerta")
        if giudizio not in _GIUDIZI_VALIDI:
            giudizio = "incerta"
        # Assenza/valore non booleano → False: non si presume una carenza di
        # istruttoria che il modello non ha esplicitamente segnalato.
        carenza_istruttoria = dati.get("carenza_istruttoria") is True
        return giudizio, carenza_istruttoria, dati.get("spiegazione", "")
    return "incerta", False, f"Risposta LLM non interpretabile come JSON: {risposta[:200]!r}"


def _cita_passaggio(passaggio: Passaggio) -> str:
    """Riferimento puntuale a un passaggio del corpus normativo.

    Un bare filename non è un riferimento verificabile: come per le citazioni
    dell'atto, serve il testo esatto e un locatore (qui: offset di carattere
    nel file sorgente) — principio di esplicabilità (CLAUDE.md).
    """
    estratto = " ".join(passaggio.testo.split())
    if len(estratto) > 220:
        estratto = estratto[:220].rstrip() + "…"
    return (
        f"{passaggio.fonte} (car. {passaggio.offset_inizio}-{passaggio.offset_fine}): «{estratto}»"
    )


def _esito_non_applicabile(spiegazione: str) -> EsitoCheck:
    return EsitoCheck(
        id=ID,
        titolo=TITOLO,
        stato=Stato.NON_APPLICABILE,
        spiegazione=spiegazione,
        riferimenti_normativi=list(_RIFERIMENTI),
    )


def valuta_motivazione(
    contesto: ContestoFascicolo,
    esiti_precedenti: list[EsitoCheck],
    indice: IndiceCorpus | None = None,
) -> EsitoCheck:
    """Check 3 (TAL-11): valutazione LLM della motivazione, con RAG sul corpus.

    Va invocato dopo `esegui_checklist`, passandone gli esiti: se nessun check
    precedente ha flaggato il fascicolo (🟡/🔴), il check è saltato — non ha
    senso interrogare il LLM su un fascicolo che i check deterministici non
    hanno segnalato ("solo sui flaggati", spec TAL-11).

    `indice` è iniettabile per i test (evita di ricostruire l'indice BM25 sul
    corpus reale ad ogni chiamata); se omesso viene costruito sul corpus di
    `data/corpus_normativo/`.
    """
    if not flaggato_da_check_precedenti(esiti_precedenti):
        return _esito_non_applicabile(
            "Nessun check precedente ha flaggato il fascicolo: il check LLM è "
            "riservato ai casi già segnalati da almeno un check deterministico."
        )

    atto = contesto.atto_autotutela.testo
    motivazione = _isola_motivazione(atto.testo)
    if len(motivazione) < SOGLIA_ASSENTE:
        return EsitoCheck(
            id=ID,
            titolo=TITOLO,
            stato=Stato.ROSSO,
            spiegazione=f"Motivazione assente o troppo breve (<{SOGLIA_ASSENTE} caratteri): "
            "non è possibile valutarne la qualità.",
            riferimenti_normativi=list(_RIFERIMENTI),
        )

    indice = indice if indice is not None else IndiceCorpus()
    passaggi = indice.cerca(motivazione, k=5)
    contesto_normativo = "\n\n".join(f"[{p.fonte}]\n{p.testo}" for p in passaggi) or (
        "(nessun passaggio pertinente trovato nel corpus)"
    )

    prompt = _PROMPT_TEMPLATE.format(motivazione=motivazione, contesto_normativo=contesto_normativo)
    risposta = genera(prompt)
    giudizio, carenza_istruttoria, spiegazione_llm = _estrai_giudizio(risposta)
    stato = _calcola_stato(giudizio, carenza_istruttoria)
    if giudizio == "specifica" and carenza_istruttoria:
        spiegazione_llm = _unisci_frasi(spiegazione_llm, _NOTA_CARENZA_ISTRUTTORIA)

    inizio = atto.testo.find(motivazione)
    citazioni: list[Citazione] = []
    if inizio >= 0:
        # offset_fine deve corrispondere a dove finisce il testo effettivamente
        # citato, non alla fine dell'intera motivazione: per motivazioni lunghe
        # (>200 caratteri) la citazione è troncata, e offset_fine deve seguirla
        # — altrimenti dichiarerebbe un intervallo più ampio di quanto è
        # davvero riportato tra virgolette (stesso principio applicato ai
        # riferimenti al corpus normativo).
        fine_citata = min(inizio + len(motivazione), inizio + 200)
        citazioni.append(
            Citazione(
                testo=atto.estratto(inizio, fine_citata),
                offset_inizio=inizio,
                offset_fine=fine_citata,
                pagina=atto.pagina_per_offset(inizio),
            )
        )

    return EsitoCheck(
        id=ID,
        titolo=TITOLO,
        stato=stato,
        spiegazione=spiegazione_llm or f"Giudizio LLM: motivazione {giudizio}.",
        citazioni=citazioni,
        riferimenti_normativi=list(_RIFERIMENTI) + [_cita_passaggio(p) for p in passaggi],
    )


__all__ = [
    "ID",
    "TITOLO",
    "SOGLIA_ASSENTE",
    "flaggato_da_check_precedenti",
    "valuta_motivazione",
]
