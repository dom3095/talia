"""TAL-13 — Estrazione attori nominati e procedimenti/atti citati.

Due estrazioni deterministiche, entrambe con offset/pagina (esplicabilità):

- **attori**: persona + ruolo istituzionale (Sindaco, Segretario Generale, RUP,
  Responsabile del Procedimento, Dirigente, …). Un ruolo senza nome associato è
  comunque registrato: indica un attore presente ma non identificato.
- **riferimenti ad atti**: determinazioni, delibere, note di protocollo, avvisi,
  con numero/anno e data se presenti. Servono a ricostruire la catena del
  procedimento (futuro check 7: follow-up).

⚠️ I nomi sono **dati personali**: l'output resta interno/locale e non finisce
in viste pubbliche non anonimizzate (wiki/09).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .firmatari import estrai_firmatari
from .models import TestoAtto

# ---------------------------------------------------------------------------
# Attori: ruolo istituzionale + nome
# ---------------------------------------------------------------------------

# Ruoli istituzionali ricorrenti negli atti comunali. L'ordine conta: i più
# specifici prima (es. "Responsabile del Procedimento" prima di "Responsabile").
_RUOLI = (
    "Segretario Generale",
    "Responsabile del Procedimento",
    "Responsabile del Settore",
    "Dirigente del Settore",
    "Sindaco",
    "RUP",
    "RPCT",
    "Assessore",
    "Presidente della Commissione",
    "Presidente",
    "Dirigente",
    "Funzionario",
    "Responsabile",
)

_RE_RUOLO = re.compile(
    r"\b(?:Il|La|Lo)?\s*(?P<ruolo>" + "|".join(_RUOLI) + r")\b",
    re.IGNORECASE,
)

# Nome in maiuscolo pieno (firme digitali): "PIETRO NICOLA AMOROSIA".
_RE_NOME_CAPS = re.compile(r"\b(?:[A-ZÀ-Ù]{2,}\s+){1,2}[A-ZÀ-Ù]{2,}\b")

# Parole tutte-maiuscole che NON sono nomi di persona (intestazioni, sigle).
_CAPS_NON_NOME = frozenset(
    {
        "COMUNE", "PROVINCIA", "DETERMINAZIONE", "DELIBERAZIONE", "OGGETTO",
        "DETERMINA", "AREA", "AREE", "SETTORE", "CCNL", "REVOCA", "ANNULLAMENTO",
        "AUTOTUTELA", "AVVISO", "SELEZIONE", "BANDO", "ALLEGATO", "SEGRETARIO",
        "GENERALE", "RESPONSABILE", "PROCEDIMENTO", "SINDACO", "IL", "DEL",
        "DELLA", "PER", "TRA", "CON", "GIUNTA", "CONSIGLIO", "COMUNALE",
        "OPERATORI", "ESPERTI", "ISTRUTTORI", "FUNZIONARI", "CAT", "ANNO",
    }
)

# Quanto testo guardare dopo la menzione del ruolo per trovare il nome.
_FINESTRA_NOME = 90


@dataclass(frozen=True)
class Attore:
    """Persona con ruolo istituzionale, ancorata al testo sorgente."""

    ruolo: str
    nome: str | None  # None = ruolo menzionato ma nome non identificato
    offset_inizio: int
    offset_fine: int
    pagina: int | None = None


def _nome_caps_valido(grezzo: str) -> bool:
    token = grezzo.split()
    return all(t not in _CAPS_NON_NOME for t in token)


def estrai_attori(atto: TestoAtto) -> list[Attore]:
    """Attori = menzioni di ruolo, con il nome agganciato quando individuabile.

    Strategia per ogni menzione di ruolo, nell'ordine:
    1. un firmatario (TAL-5) che inizia entro `_FINESTRA_NOME` caratteri;
    2. un nome in maiuscolo pieno (firma digitale) nella stessa finestra;
    3. nessun nome → attore anonimo (il ruolo è comunque un dato utile).
    I duplicati (stesso ruolo+nome) sono compattati tenendo la prima occorrenza.
    """
    testo = atto.testo
    firmatari = estrai_firmatari(atto)

    attori: list[Attore] = []
    visti: set[tuple[str, str | None]] = set()

    for m in _RE_RUOLO.finditer(testo):
        ruolo = _canonico_ruolo(m["ruolo"])
        fine_finestra = min(len(testo), m.end() + _FINESTRA_NOME)

        nome: str | None = None
        # 1. firmatario nelle vicinanze (dopo il ruolo).
        for f in firmatari:
            if m.end() <= f.offset_inizio < fine_finestra:
                nome = str(f.valore)
                break
        # 2. nome in maiuscolo pieno (firma digitale).
        if nome is None:
            m_caps = _RE_NOME_CAPS.search(testo, m.end(), fine_finestra)
            if m_caps and _nome_caps_valido(m_caps.group(0)):
                nome = m_caps.group(0).title()

        chiave = (ruolo, nome)
        if chiave in visti:
            continue
        visti.add(chiave)
        attori.append(
            Attore(
                ruolo=ruolo,
                nome=nome,
                offset_inizio=m.start(),
                offset_fine=m.end(),
                pagina=atto.pagina_per_offset(m.start()),
            )
        )

    # Se per uno stesso ruolo esiste una versione con nome, le menzioni anonime
    # dello stesso ruolo sono rumore: si scartano.
    ruoli_con_nome = {a.ruolo for a in attori if a.nome}
    return [a for a in attori if a.nome or a.ruolo not in ruoli_con_nome]


def _canonico_ruolo(grezzo: str) -> str:
    """Forma canonica del ruolo (capitalizzazione uniforme)."""
    return " ".join(
        parola if parola.isupper() and len(parola) <= 4 else parola.capitalize()
        for parola in grezzo.split()
    )


# ---------------------------------------------------------------------------
# Riferimenti a procedimenti / atti citati
# ---------------------------------------------------------------------------

_TIPI_ATTO = (
    "determinazione",
    "determina",
    "deliberazione",
    "delibera",
    "decreto",
    "ordinanza",
    "nota",
    "avviso",
    "bando",
)

# "determinazione n. 35/2025", "deliberazione della Giunta Comunale n. 55 del
# 18/04/2024", "nota Prot n. 18443/2026 del 25/05/2026", ...
_RE_RIF_ATTO = re.compile(
    r"""
    \b(?P<tipo>""" + "|".join(_TIPI_ATTO) + r""")
    (?P<qualifica>
        (?:\s+(?:dirigenziale|sindacale|della\s+giunta\s+comunale|
                 del\s+consiglio\s+comunale|prot(?:\.|ocollo)?))*
    )
    \s*(?:n|num|nr)?\.?\s*
    (?P<numero>\d{1,6}(?:\s*/\s*\d{2,4})?)
    (?:\s+del\s+(?P<data>\d{1,2}[/.\-]\d{1,2}[/.\-]\d{2,4}))?
    """,
    re.IGNORECASE | re.VERBOSE,
)


@dataclass(frozen=True)
class RiferimentoAtto:
    """Citazione di un altro atto/procedimento dentro il documento."""

    tipo: str  # determinazione, deliberazione, nota, ...
    numero: str  # "35/2025", "55", "18443/2026"
    data: str | None  # com'è scritta nell'atto, se presente
    testo_originale: str
    offset_inizio: int
    offset_fine: int
    pagina: int | None = None

    @property
    def chiave(self) -> str:
        """Identificatore di confronto: tipo + numero normalizzato."""
        return f"{self.tipo.lower()} {self.numero.replace(' ', '')}"


def estrai_riferimenti_atti(atto: TestoAtto) -> list[RiferimentoAtto]:
    """Atti citati nel testo, con numero e data quando presenti.

    Per ridurre i falsi positivi, un riferimento senza "n." esplicito è tenuto
    solo se il numero contiene l'anno ("35/2025"): un numero nudo dopo il tipo
    ("avviso 7") è troppo ambiguo.
    """
    riferimenti: list[RiferimentoAtto] = []
    for m in _RE_RIF_ATTO.finditer(atto.testo):
        numero = m["numero"].replace(" ", "")
        ha_etichetta_n = re.search(r"\bn(?:um|r)?\.?\s*$", atto.testo[: m.start("numero")][-6:],
                                   re.IGNORECASE)
        if not ha_etichetta_n and "/" not in numero:
            continue
        riferimenti.append(
            RiferimentoAtto(
                tipo=m["tipo"].lower(),
                numero=numero,
                data=m["data"],
                testo_originale=" ".join(m.group(0).split()),
                offset_inizio=m.start(),
                offset_fine=m.end(),
                pagina=atto.pagina_per_offset(m.start()),
            )
        )
    return riferimenti
