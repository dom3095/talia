"""Diagnosi e campionamento dei red flag di frazionamento (TAL-73).

Dopo il caricamento dei contratti SmartCIG (TAL-70) i red flag sono passati da
665 a 13.964, di cui 12.892 `frazionamento`. SmartCIG contiene *per
definizione* affidamenti sotto soglia, quindi una regola che cerca "almeno 3
affidamenti sotto soglia in 90 giorni con totale oltre soglia" lì trova quasi
ovunque qualcosa. Prima di pubblicare questi flag serve sapere quanti sono
rumore — e **perché**, così che la correzione della regola sia guidata dai
numeri e non da un'impressione.

Questo modulo non modifica nulla: legge `red_flags` e `atti` e produce

* una **diagnosi strutturale**, che misura le ipotesi di falso positivo
  verificabili senza leggere gli atti (stesso CIG contato più volte, tipi di
  appalto mescolati, oggetti eterogenei, flag sovrapposti o superati);
* un **campione stratificato** da etichettare a mano (ANAC / Albo / misti),
  da cui stimare il tasso di falsi positivi reale.

Ogni ipotesi diagnostica corrisponde a una correzione candidata della regola
in `frazionamento.py` — vedi la card TAL-73.
"""

from __future__ import annotations

import json
import random
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass, field

from .frazionamento import SOGLIA_FORNITURE

FONTE_ANAC = "anac"

#: Due oggetti sono "lo stesso affidamento" sopra questa similarità di token.
#: Volutamente bassa: è un'euristica per *escludere* i casi palesemente
#: eterogenei (cancelleria + manutenzione strade + mensa), non per confermare.
SIMILARITA_OGGETTI = 0.35

_STOPWORD = {
    "della", "delle", "dello", "degli", "dell", "nella", "nelle", "nello", "negli",
    "alla", "alle", "allo", "agli", "dalla", "dalle", "dallo", "dagli", "sulla",
    "sulle", "anno", "anni", "comune", "comunale", "comunali", "servizio",
    "servizi", "fornitura", "forniture", "affidamento", "affidamenti", "diretto",
    "diretta", "determina", "determinazione", "impegno", "spesa", "liquidazione",
    "ditta", "presso", "relativo", "relativa", "periodo", "mediante", "lavori",
    "intervento", "interventi", "acquisto", "procedura", "sensi", "art",
}  # fmt: skip

_RE_TOKEN = re.compile(r"[a-zàèéìòù]{4,}")

#: Nei dati SmartCIG di ANAC `oggetto` non descrive l'acquisto: contiene solo il
#: tipo di appalto (3 valori distinti su 176.827 righe, misurato il 2026-10-19)
#: e `metadati.tipo_appalto` è vuoto. Il tipo si legge quindi da `oggetto`.
_TIPI_APPALTO = {"lavori", "servizi", "forniture"}

#: Atti mostrati per flag nel CSV. Un flag può avere centinaia di atti (939 a
#: Ragusa): la cella supererebbe il limite di Excel (32.767 caratteri) e quello
#: del modulo `csv` di Python (131.072), e nessuno etichetta 939 righe a mano.
MAX_ATTI_CSV = 10


@dataclass
class AttoFlag:
    id: int
    importo: float | None
    data: str | None
    cig: str | None
    oggetto: str | None
    fonte: str | None
    tipo: str | None
    tipo_appalto: str | None
    url: str | None

    @property
    def tipo_effettivo(self) -> str | None:
        """Tipo di appalto: dai metadati, altrimenti da `oggetto` (dati ANAC)."""
        tipo = (self.tipo_appalto or "").strip().lower()
        if tipo:
            return tipo
        oggetto = (self.oggetto or "").strip().lower()
        return oggetto if oggetto in _TIPI_APPALTO else None

    @property
    def categoria_soglia(self) -> str | None:
        """`lavori` (soglia 150k€) oppure `beni_servizi` (140k€); None se ignoto."""
        tipo = self.tipo_effettivo
        if tipo is None:
            return None
        return "lavori" if tipo.startswith("lavor") else "beni_servizi"


@dataclass
class FlagFrazionamento:
    id: int
    ente_id: int
    ente: str
    periodo_da: str | None
    periodo_a: str | None
    atti: list[AttoFlag] = field(default_factory=list)

    @property
    def strato(self) -> str:
        fonti = {a.fonte == FONTE_ANAC for a in self.atti}
        if fonti == {True}:
            return "solo_anac"
        if fonti == {False}:
            return "solo_albo"
        return "misto"

    @property
    def cig_ripetuti(self) -> bool:
        """Lo stesso CIG compare più volte: lo stesso affidamento sommato due volte."""
        cig = [a.cig for a in self.atti if a.cig]
        return len(cig) != len(set(cig))

    @property
    def totale_dedup_cig(self) -> float:
        """Totale contando ogni CIG una volta sola (il più alto importo visto)."""
        per_cig: dict[str, float] = {}
        senza_cig = 0.0
        for a in self.atti:
            importo = a.importo or 0.0
            if a.cig:
                per_cig[a.cig] = max(per_cig.get(a.cig, 0.0), importo)
            else:
                senza_cig += importo
        return sum(per_cig.values()) + senza_cig

    @property
    def n_affidamenti_dedup_cig(self) -> int:
        return len({a.cig for a in self.atti if a.cig}) + sum(1 for a in self.atti if not a.cig)

    @property
    def tipo_valutabile(self) -> bool:
        """Almeno un atto dichiara il tipo di appalto: senza, H4 non si può misurare."""
        return any(a.categoria_soglia for a in self.atti)

    @property
    def tipi_appalto_misti(self) -> bool:
        """Lavori e beni/servizi nella stessa finestra: soglie diverse (150k€ / 140k€).

        Forniture e servizi insieme non contano: hanno la stessa soglia.
        """
        return len({a.categoria_soglia for a in self.atti if a.categoria_soglia}) > 1

    def oggetti_valutabili(self, n_min: int = 3) -> bool:
        """Almeno `n_min` atti con un oggetto che descrive davvero l'acquisto.

        Se mancano, H5 non può dire né "omogenei" né "eterogenei": dichiarare
        eterogeneo un flag i cui atti non hanno testo confrontabile darebbe
        un 100% che è un artefatto della misura, non un risultato.
        """
        return sum(1 for a in self.atti if _token(a.oggetto)) >= n_min

    @property
    def gruppo_omogeneo_max(self) -> int:
        """Il gruppo più grande di atti con oggetto simile tra loro."""
        insiemi = [_token(a.oggetto) for a in self.atti]
        migliore = 0
        for i, base in enumerate(insiemi):
            if not base:
                continue
            gruppo = sum(
                1
                for j, altro in enumerate(insiemi)
                if _jaccard(base, altro) >= SIMILARITA_OGGETTI or i == j
            )
            migliore = max(migliore, gruppo)
        return migliore


def _token(testo: str | None) -> set[str]:
    return {t for t in _RE_TOKEN.findall((testo or "").lower()) if t not in _STOPWORD}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def carica_flag(conn: sqlite3.Connection) -> list[FlagFrazionamento]:
    """Tutti i flag `frazionamento` con i loro atti, letti da `atti_cig`."""
    righe = conn.execute(
        """
        SELECT rf.id, rf.ente_id, e.denominazione, rf.periodo_da, rf.periodo_a, rf.atti_cig
        FROM red_flags rf JOIN enti e ON e.id = rf.ente_id
        WHERE rf.tipo_flag = 'frazionamento'
        ORDER BY rf.id
        """
    ).fetchall()
    flags: list[FlagFrazionamento] = []
    for r in righe:
        try:
            ids = [int(x["id"]) for x in json.loads(r["atti_cig"] or "[]") if "id" in x]
        except (ValueError, TypeError, KeyError):
            ids = []
        flags.append(
            FlagFrazionamento(
                r["id"], r["ente_id"], r["denominazione"], r["periodo_da"], r["periodo_a"]
            )
        )
        flags[-1].atti = _carica_atti(conn, ids)
    return flags


def _carica_atti(conn: sqlite3.Connection, ids: list[int]) -> list[AttoFlag]:
    if not ids:
        return []
    segnaposto = ",".join("?" * len(ids))
    righe = conn.execute(
        f"""
        SELECT id, importo_euro, COALESCE(data_atto, data_pub) AS data, cig, oggetto,
               fonte_scraper, tipo, url_fonte, metadati
        FROM atti WHERE id IN ({segnaposto})
        """,
        ids,
    ).fetchall()
    atti = []
    for r in righe:
        try:
            tipo_appalto = json.loads(r["metadati"] or "{}").get("tipo_appalto") or None
        except (ValueError, AttributeError):
            tipo_appalto = None
        atti.append(
            AttoFlag(
                id=r["id"],
                importo=r["importo_euro"],
                data=r["data"],
                cig=r["cig"],
                oggetto=r["oggetto"],
                fonte=r["fonte_scraper"],
                tipo=r["tipo"],
                tipo_appalto=tipo_appalto,
                url=r["url_fonte"],
            )
        )
    return sorted(atti, key=lambda a: (a.data or "", a.id))


@dataclass
class Diagnosi:
    n_flag: int
    n_enti: int
    per_strato: Counter
    top_enti: list[tuple[str, int]]
    #: Ipotesi di falso positivo strutturale: nome → numero di flag.
    ipotesi: dict[str, int]
    #: Flag che resistono a tutte le ipotesi *valutabili*: il limite superiore dei
    #: veri segnali, valido solo se nessuna ipotesi è rimasta non valutabile.
    superstiti: int
    #: Ipotesi → flag per cui i dati non permettono di valutarla (non contano nel conteggio).
    non_valutabili: dict[str, int] = field(default_factory=dict)
    #: Flag con almeno un'ipotesi non valutabile: per loro `superstiti` è solo un limite.
    con_ipotesi_non_valutabili: int = 0


def diagnostica(
    flags: list[FlagFrazionamento],
    *,
    soglia: float = SOGLIA_FORNITURE,
    n_atti_soglia: int = 3,
) -> Diagnosi:
    """Misura quanti flag cadono sotto ciascuna ipotesi di falso positivo."""
    # Flag "superati": stessa ancora (ente, periodo_da) registrata più volte con
    # periodo_a diversi — la finestra si allunga a ogni run e il vecchio flag
    # resta in tabella (unique su ente, tipo, periodo_da, periodo_a).
    fine_max: dict[tuple, str] = {}
    for f in flags:
        chiave = (f.ente_id, f.periodo_da)
        fine_max[chiave] = max(fine_max.get(chiave, ""), f.periodo_a or "")
    superati = {f.id for f in flags if (f.periodo_a or "") < fine_max[(f.ente_id, f.periodo_da)]}

    # Flag "contenuti": tutti i loro atti sono anche in un altro flag dello
    # stesso ente — finestre sovrapposte che segnalano lo stesso gruppo.
    insiemi = {f.id: frozenset(a.id for a in f.atti) for f in flags}
    per_ente: dict[int, list[FlagFrazionamento]] = {}
    for f in flags:
        per_ente.setdefault(f.ente_id, []).append(f)
    contenuti: set[int] = set()
    for gruppo in per_ente.values():
        # Solo un insieme più grande può contenere strettamente un altro.
        per_dimensione = sorted(gruppo, key=lambda g: len(insiemi[g.id]), reverse=True)
        for i, f in enumerate(per_dimensione):
            atti_f = insiemi[f.id]
            if atti_f and any(atti_f < insiemi[g.id] for g in per_dimensione[:i]):
                contenuti.add(f.id)

    sotto_soglia_dedup = {
        f.id
        for f in flags
        if f.cig_ripetuti
        and (f.totale_dedup_cig <= soglia or f.n_affidamenti_dedup_cig < n_atti_soglia)
    }
    misti = {f.id for f in flags if f.tipi_appalto_misti}
    eterogenei = {
        f.id
        for f in flags
        if f.oggetti_valutabili(n_atti_soglia) and f.gruppo_omogeneo_max < n_atti_soglia
    }
    h4_non_valutabili = {f.id for f in flags if not f.tipo_valutabile}
    h5_non_valutabili = {f.id for f in flags if not f.oggetti_valutabili(n_atti_soglia)}

    ipotesi = {
        "superato da un flag più recente con la stessa ancora": len(superati),
        "atti tutti contenuti in un altro flag dello stesso ente": len(contenuti),
        "stesso CIG contato più volte (con CIG unici non scatterebbe)": len(sotto_soglia_dedup),
        "tipi di appalto mescolati (lavori + forniture/servizi)": len(misti),
        f"oggetti eterogenei (nessun gruppo di {n_atti_soglia} atti simili)": len(eterogenei),
    }
    non_valutabili = {
        "tipi di appalto mescolati (lavori + forniture/servizi)": len(h4_non_valutabili),
        f"oggetti eterogenei (nessun gruppo di {n_atti_soglia} atti simili)": len(
            h5_non_valutabili
        ),
    }
    scartati = superati | contenuti | sotto_soglia_dedup | misti | eterogenei
    return Diagnosi(
        n_flag=len(flags),
        n_enti=len(per_ente),
        per_strato=Counter(f.strato for f in flags),
        top_enti=Counter(f.ente for f in flags).most_common(10),
        ipotesi=ipotesi,
        superstiti=len(flags) - len(scartati),
        non_valutabili=non_valutabili,
        con_ipotesi_non_valutabili=len(h4_non_valutabili | h5_non_valutabili),
    )


def campiona(
    flags: list[FlagFrazionamento], *, per_strato: int = 20, seme: int = 72
) -> list[FlagFrazionamento]:
    """Campione stratificato per fonte, riproducibile (seme fisso)."""
    rng = random.Random(seme)
    campione: list[FlagFrazionamento] = []
    for strato in ("solo_anac", "solo_albo", "misto"):
        gruppo = [f for f in flags if f.strato == strato]
        campione += rng.sample(gruppo, min(per_strato, len(gruppo)))
    return campione


COLONNE_CSV = [
    "flag_id",
    "strato",
    "ente",
    "periodo_da",
    "periodo_a",
    "n_atti",
    "totale_euro",
    "totale_dedup_cig",
    "cig_ripetuti",
    "tipi_appalto_misti",
    "gruppo_omogeneo_max",
    "atti",
    "esito",
    "note",
]


def righe_csv(campione: list[FlagFrazionamento]) -> list[dict]:
    """Una riga per flag; `esito` e `note` vuoti, da compilare a mano.

    Valori attesi per `esito`: `vero_segnale` / `falso_positivo` / `incerto`.
    """
    righe = []
    for f in campione:
        atti = " | ".join(
            f"{a.data or '?'} · {a.importo or 0:,.0f}€ · {a.cig or '-'} · "
            f"{(a.oggetto or '').strip()[:80]} · {a.url or ''}"
            for a in f.atti[:MAX_ATTI_CSV]
        )
        if len(f.atti) > MAX_ATTI_CSV:
            atti += f" | … (+{len(f.atti) - MAX_ATTI_CSV} altri atti, vedi n_atti)"
        righe.append(
            {
                "flag_id": f.id,
                "strato": f.strato,
                "ente": f.ente,
                "periodo_da": f.periodo_da,
                "periodo_a": f.periodo_a,
                "n_atti": len(f.atti),
                "totale_euro": round(sum(a.importo or 0 for a in f.atti), 2),
                "totale_dedup_cig": round(f.totale_dedup_cig, 2),
                "cig_ripetuti": f.cig_ripetuti,
                "tipi_appalto_misti": f.tipi_appalto_misti if f.tipo_valutabile else "n/d",
                "gruppo_omogeneo_max": (f.gruppo_omogeneo_max if f.oggetti_valutabili() else "n/d"),
                "atti": atti,
                "esito": "",
                "note": "",
            }
        )
    return righe


def formatta_diagnosi(d: Diagnosi) -> str:
    righe = [
        "# Diagnosi red flag `frazionamento`",
        "",
        f"**{d.n_flag:,} flag** su {d.n_enti} enti.",
        "",
        "| Strato | Flag |",
        "|---|---|",
    ]
    righe += [f"| {s} | {n:,} |" for s, n in sorted(d.per_strato.items())]
    righe += [
        "",
        "## Ipotesi di falso positivo strutturale",
        "",
        "| Ipotesi | Flag | % | Non valutabili |",
        "|---|---|---|---|",
    ]
    for nome, n in d.ipotesi.items():
        quota = 100 * n / d.n_flag if d.n_flag else 0
        nv = d.non_valutabili.get(nome)
        righe.append(f"| {nome} | {n:,} | {quota:.0f}% | {f'{nv:,}' if nv else '—'} |")
    righe += [
        "",
        f"**Resistono a tutte le ipotesi: {d.superstiti:,} flag** "
        f"({100 * d.superstiti / d.n_flag if d.n_flag else 0:.0f}%) — limite superiore dei "
        "segnali da guardare davvero. Le ipotesi si sovrappongono: le percentuali non si sommano.",
    ]
    if d.con_ipotesi_non_valutabili:
        righe += [
            "",
            f"⚠️ **{d.con_ipotesi_non_valutabili:,} flag su {d.n_flag:,} hanno almeno "
            "un'ipotesi non valutabile** (dati assenti, tipicamente `oggetto` di ANAC che "
            "contiene solo il tipo di appalto). Per loro il conteggio dei superstiti "
            '*sovrastima* la fiducia nel risultato: non leggerlo come "X flag sono veri".',
        ]
    righe += [
        "",
        "## Enti con più flag",
        "",
    ]
    righe += [f"- {ente}: {n:,}" for ente, n in d.top_enti]
    return "\n".join(righe) + "\n"
