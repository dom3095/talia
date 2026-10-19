"""Riepilogo dello stato dei run scraper (TAL-66).

Legge `scraper_runs` e produce un quadro leggibile di **cosa è andato storto**,
usato da due chiamanti:

* `scripts/report_run.py` — riepilogo testuale a fine run giornaliero, con
  exit code non-zero se ci sono problemi (il wrapper del cron lo usa per
  decidere se notificare).
* la dashboard (tab Aggregati) — stessa informazione, per chi guarda l'app.

Tre condizioni distinte, deliberatamente separate: un run *fallito* (eccezione,
`errore` valorizzato) non è la stessa cosa di un run *muto* (completato, zero
atti trovati: parsing rotto in silenzio, la fragilità nota di CLAUDE.md) né di
uno scraper *fermo* (attivo nel registro ma non eseguito da giorni — la causa
per cui il DB può invecchiare senza che nessuno se ne accorga).

Dal TAL-72 se ne aggiungono due:

* *interrotto*: lo scraper ha superato il tetto di tempo per scraper ed è stato
  fermato dall'orchestratore. Non è un'eccezione dello scraper e non concorre
  all'exit code: è informativo, ma resta visibile — e se lo scraper stava
  ancora inserendo atti, il report lo dice, perché è il segnale che il tetto è
  troppo basso e non che lo scraper è rotto;
* *causa dominante*: quando una sola causa spiega la gran parte dei falliti
  (il 31/08/2026: 225 errori DNS su 232) è un guasto unico — di solito la rete
  locale — e non 225 portali rotti. Il report lo dice in testa e separa quei
  falliti dalle rotture vere, invece di elencarne 15 a caso.
"""

from __future__ import annotations

import re
import sqlite3
import statistics
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from talia.modulo2_scraping.tetto_tempo import e_interruzione_tetto

#: Quanti scraper elencare per sezione prima di riassumere il resto: quando
#: *nessun* run gira da giorni la sezione "fermi" contiene tutti e 265 gli
#: scraper, e un elenco così lungo nasconde le sezioni davvero azionabili.
MAX_ELENCO = 15

#: Oltre questa soglia uno scraper attivo è considerato "fermo".
GIORNI_STALE_DEFAULT = 3

#: Finestra di pubblicazione tipica di un albo pretorio: oltre questa soglia
#: senza run, gli atti nel frattempo pubblicati e già scaduti sono persi.
GIORNI_PERDITA_DATI = 15

#: Una causa è "dominante" se spiega almeno questa quota dei falliti…
QUOTA_CAUSA_DOMINANTE = 0.6
#: …e almeno questo numero di scraper: con 3 falliti su 266, due errori uguali
#: sono una coincidenza, non un guasto comune.
MIN_FALLITI_CAUSA_DOMINANTE = 10


#: Soglia minima per dire che uno scraper è "stagnante" (TAL-69): sopra la
#: finestra tipica di pubblicazione di un albo, sotto il mese.
GIORNI_STAGNANTE_MIN = 14
#: …che si allarga per i comuni che pubblicano poco: stagnante = silenzioso da
#: più di questo multiplo del suo intervallo tipico tra due giorni con atti
#: nuovi. Enna (~3 atti/mese) con una soglia fissa risulterebbe sempre ferma.
MULTIPLO_INTERVALLO_STAGNANTE = 3
#: Finestra su cui si misura l'intervallo tipico.
GIORNI_STORICO_STAGNANTE = 180


@dataclass(frozen=True)
class CausaErrore:
    """Famiglia di errore, per raggruppare cause uguali scritte in modi diversi."""

    descrizione: str
    #: Vero se la causa è quasi certamente dalla nostra parte (rete, DNS
    #: della macchina che fa girare il run) e non dei portali.
    locale: bool = False


#: Famiglie riconosciute, nell'ordine in cui vanno provate. I messaggi variano
#: tra macOS e Linux (`[Errno 8] nodename nor servname` vs `[Errno -2] Name or
#: service not known`): raggrupparli è il punto, altrimenti lo stesso guasto
#: DNS sembra due cause diverse.
_FAMIGLIE_ERRORE: list[tuple[re.Pattern[str], CausaErrore]] = [
    (
        re.compile(
            r"nodename nor servname|Name or service not known|name resolution"
            r"|getaddrinfo failed|No address associated with hostname",
            re.IGNORECASE,
        ),
        CausaErrore("risoluzione DNS fallita", locale=True),
    ),
    (
        re.compile(r"Network is unreachable|No route to host|Network is down", re.IGNORECASE),
        CausaErrore("rete non raggiungibile", locale=True),
    ),
    (
        re.compile(r"CERTIFICATE_VERIFY_FAILED|SSLError|\[SSL|handshake", re.IGNORECASE),
        CausaErrore("errore SSL/TLS"),
    ),
    (
        re.compile(r"timed out|TimeoutError|\bTimeout\b", re.IGNORECASE),
        CausaErrore("timeout di rete"),
    ),
    (
        re.compile(r"Connection refused|Connection reset|RemoteDisconnected", re.IGNORECASE),
        CausaErrore("connessione rifiutata o chiusa dal server"),
    ),
]


def causa_errore(errore: str | None) -> CausaErrore:
    """Riconduce un errore registrato alla sua famiglia.

    Si guarda solo la riga dell'eccezione, non il traceback intero: un
    timeout durante una lettura TLS ha `ssl.py` tra i frame, e classificarlo
    come errore SSL sarebbe sbagliato. Se nessuna famiglia nota corrisponde, la
    causa è la riga stessa: due errori identici restano raggruppabili anche se
    non previsti qui.
    """
    testo = sintesi_errore(errore, max_len=300)
    for regex, causa in _FAMIGLIE_ERRORE:
        if regex.search(testo):
            return causa
    return CausaErrore(sintesi_errore(errore))


def trova_causa_dominante(
    falliti: list[StatoScraper],
    *,
    quota: float = QUOTA_CAUSA_DOMINANTE,
    minimo: int = MIN_FALLITI_CAUSA_DOMINANTE,
) -> CausaErrore | None:
    """La causa che spiega almeno ``quota`` dei falliti (e almeno ``minimo``), se c'è."""
    if len(falliti) < minimo:
        return None
    conteggio = Counter(causa_errore(s.errore) for s in falliti)
    causa, n = conteggio.most_common(1)[0]
    if n >= minimo and n / len(falliti) >= quota:
        return causa
    return None


@dataclass(frozen=True)
class StatoScraper:
    """Esito dell'ultimo run noto di uno scraper."""

    scraper_id: str
    avviato_a: str | None
    completato_a: str | None
    n_inseriti: int
    n_trovati: int
    errore: str | None
    giorni_fa: float | None

    @property
    def interrotto(self) -> bool:
        """Fermato dall'orchestratore per tetto di tempo (TAL-72), non da un'eccezione."""
        return e_interruzione_tetto(self.errore)

    @property
    def fallito(self) -> bool:
        return bool(self.errore) and not self.interrotto

    @property
    def muto(self) -> bool:
        """Completato senza errori ma senza trovare nulla."""
        return not self.errore and self.completato_a is not None and self.n_trovati == 0


@dataclass(frozen=True)
class Stagnante:
    """Scraper che gira e trova righe, ma non inserisce atti nuovi da troppo (TAL-69)."""

    scraper_id: str
    giorni_senza_nuovi: int
    #: Mediana dei giorni tra due giorni con inserimenti; None se lo storico è troppo corto.
    intervallo_tipico: float | None
    soglia: float
    #: Altro scraper dello stesso comune (TAL-52), se c'è: lo stagnante può
    #: essere solo il doppione di un gemello che fa il lavoro.
    gemello: str | None = None


def trova_stagnanti(
    conn: sqlite3.Connection,
    ultimi: dict[str, StatoScraper],
    *,
    oggi: date | None = None,
    gemelli: dict[str, str] | None = None,
) -> list[Stagnante]:
    """Scraper sani in ogni altra metrica ma senza atti nuovi da troppo tempo.

    Uno stagnante gira, non dà errori e trova righe: semplicemente sono sempre
    le stesse (albo fermo, pagina d'archivio al posto dell'albo vivo, scraper
    gemello che fa il lavoro — TAL-52). La soglia è relativa al comune:
    ``max(GIORNI_STAGNANTE_MIN, MULTIPLO × intervallo tipico)``.
    """
    oggi = oggi or date.today()
    giorni_con_atti: dict[str, list[date]] = {}
    for scraper_id, giorno in conn.execute(
        """
        SELECT scraper_id, date(avviato_a) FROM scraper_runs
        WHERE  COALESCE(n_inseriti, 0) > 0
        GROUP  BY scraper_id, date(avviato_a)
        ORDER  BY scraper_id, date(avviato_a)
        """
    ):
        giorni_con_atti.setdefault(scraper_id, []).append(date.fromisoformat(giorno))
    primi_run = dict(
        conn.execute("SELECT scraper_id, date(MIN(avviato_a)) FROM scraper_runs GROUP BY 1")
    )

    stagnanti = []
    for sid, stato in sorted(ultimi.items()):
        if stato.errore or stato.completato_a is None or stato.n_trovati == 0:
            continue  # già fallito, interrotto o muto: lo dicono le altre sezioni
        giorni = giorni_con_atti.get(sid, [])
        ultimo = giorni[-1] if giorni else date.fromisoformat(primi_run[sid])
        silenzio = (oggi - ultimo).days
        recenti = [g for g in giorni if (oggi - g).days <= GIORNI_STORICO_STAGNANTE]
        intervalli = [(b - a).days for a, b in zip(recenti, recenti[1:], strict=False)]
        tipico = statistics.median(intervalli) if len(intervalli) >= 3 else None
        soglia = max(GIORNI_STAGNANTE_MIN, MULTIPLO_INTERVALLO_STAGNANTE * (tipico or 0))
        if silenzio > soglia:
            gemello = (gemelli or {}).get(sid)
            stagnanti.append(Stagnante(sid, silenzio, tipico, soglia, gemello))
    return sorted(stagnanti, key=lambda s: -s.giorni_senza_nuovi)


@dataclass
class RiepilogoRun:
    """Quadro complessivo dell'ultimo giro di run."""

    totale: int = 0
    ok: int = 0
    falliti: list[StatoScraper] = field(default_factory=list)
    muti: list[StatoScraper] = field(default_factory=list)
    fermi: list[StatoScraper] = field(default_factory=list)
    mai_eseguiti: list[str] = field(default_factory=list)
    #: Scraper con run in DB ma non più previsti (bloccati o esclusi dal
    #: default): informativi, mai contati come problemi — vedi `riepiloga`.
    non_previsti: list[StatoScraper] = field(default_factory=list)
    #: Fermati per tetto di tempo (TAL-72): informativi, non concorrono a
    #: `ha_problemi` — vedi la docstring del modulo.
    interrotti: list[StatoScraper] = field(default_factory=list)
    #: Senza atti nuovi da troppo (TAL-69): informativi, non concorrono a `ha_problemi`.
    stagnanti: list[Stagnante] = field(default_factory=list)
    #: Causa che spiega la gran parte dei falliti, se c'è (TAL-72).
    causa_dominante: CausaErrore | None = None
    atti_inseriti: int = 0
    ultimo_run: str | None = None
    giorni_da_ultimo_run: float | None = None

    @property
    def ha_problemi(self) -> bool:
        return bool(self.falliti or self.muti or self.fermi or self.mai_eseguiti)

    @property
    def falliti_per_altra_causa(self) -> list[StatoScraper]:
        """I falliti non spiegati dalla causa dominante: le rotture da guardare una a una."""
        if self.causa_dominante is None:
            return self.falliti
        return [s for s in self.falliti if causa_errore(s.errore) != self.causa_dominante]

    @property
    def rischio_perdita_dati(self) -> bool:
        """Vero se è passato tanto tempo da perdere atti scaduti dall'albo."""
        return (
            self.giorni_da_ultimo_run is not None
            and self.giorni_da_ultimo_run > GIORNI_PERDITA_DATI
        )


def _ultimi_run(conn: sqlite3.Connection) -> dict[str, StatoScraper]:
    """L'ultimo run per ciascuno scraper mai eseguito."""
    righe = conn.execute(
        """
        SELECT r.scraper_id, r.avviato_a, r.completato_a,
               COALESCE(r.n_inseriti, 0) AS n_inseriti,
               COALESCE(r.n_trovati, 0)  AS n_trovati,
               r.errore,
               (julianday('now') - julianday(r.avviato_a)) AS giorni_fa
        FROM scraper_runs r
        JOIN (
            SELECT scraper_id, MAX(avviato_a) AS ultimo
            FROM scraper_runs GROUP BY scraper_id
        ) u ON u.scraper_id = r.scraper_id AND u.ultimo = r.avviato_a
        """
    ).fetchall()
    return {
        r["scraper_id"]: StatoScraper(
            scraper_id=r["scraper_id"],
            avviato_a=r["avviato_a"],
            completato_a=r["completato_a"],
            n_inseriti=r["n_inseriti"],
            n_trovati=r["n_trovati"],
            errore=r["errore"],
            giorni_fa=r["giorni_fa"],
        )
        for r in righe
    }


def gemelli_da_registro(entries) -> dict[str, str]:
    """Slug → altro slug con lo stesso codice ISTAT, tra gli scraper attivi (TAL-52)."""
    per_istat: dict[str, list[str]] = {}
    for e in entries:
        if e.stato == "attivo":
            per_istat.setdefault(e.codice_istat, []).append(e.slug)
    return {
        slug: next(altro for altro in slugs if altro != slug)
        for slugs in per_istat.values()
        if len(slugs) > 1
        for slug in slugs
    }


def riepiloga(
    conn: sqlite3.Connection,
    *,
    scraper_attesi: list[str] | None = None,
    giorni_stale: int = GIORNI_STALE_DEFAULT,
    gemelli: dict[str, str] | None = None,
) -> RiepilogoRun:
    """Costruisce il riepilogo dello stato dei run.

    ``scraper_attesi`` è la lista degli slug che *dovrebbero* girare (il
    default del registro più gli eventuali extra del run automatico). Serve a
    due cose:

    * distinguere "mai eseguito" da "non previsto";
    * **non segnalare come problema ciò che è rotto per scelta.** Gli scraper
      `bloccato` (Corleone, Messina) o esclusi dal default (ANAC, che richiede
      `--anac-file`) hanno un ultimo run vecchio e fallito *per definizione*:
      contarli farebbe scattare la notifica ogni singola notte, e una notifica
      che suona sempre è una notifica che si impara a ignorare.

    Se ``scraper_attesi`` è omessa non si filtra nulla (si guardano tutti gli
    scraper presenti nel DB).
    """
    ultimi = _ultimi_run(conn)
    attesi = set(scraper_attesi) if scraper_attesi else None
    riepilogo = RiepilogoRun(totale=len(ultimi))

    for stato in sorted(ultimi.values(), key=lambda s: s.scraper_id):
        riepilogo.atti_inseriti += stato.n_inseriti
        if attesi is not None and stato.scraper_id not in attesi:
            riepilogo.non_previsti.append(stato)
            continue
        if stato.interrotto:
            riepilogo.interrotti.append(stato)
        elif stato.fallito:
            riepilogo.falliti.append(stato)
        elif stato.muto:
            riepilogo.muti.append(stato)
        else:
            riepilogo.ok += 1
        if stato.giorni_fa is not None and stato.giorni_fa > giorni_stale:
            riepilogo.fermi.append(stato)

    riepilogo.totale -= len(riepilogo.non_previsti)
    riepilogo.stagnanti = trova_stagnanti(
        conn,
        {k: v for k, v in ultimi.items() if attesi is None or k in attesi},
        gemelli=gemelli,
    )
    riepilogo.causa_dominante = trova_causa_dominante(riepilogo.falliti)
    if attesi:
        riepilogo.mai_eseguiti = sorted(attesi - set(ultimi))

    riga = conn.execute(
        "SELECT MAX(avviato_a), (julianday('now') - julianday(MAX(avviato_a))) FROM scraper_runs"
    ).fetchone()
    riepilogo.ultimo_run, riepilogo.giorni_da_ultimo_run = riga[0], riga[1]
    return riepilogo


#: Righe di traceback da cui non si capisce nulla, se prese da sole.
_RE_RIGA_INUTILE = re.compile(r"^\s*(File \"|Traceback|\^+\s*$|\.\.\.)")

#: Riga che nomina davvero l'eccezione, es. `urllib.error.URLError: timed out`.
_RE_ECCEZIONE = re.compile(r"^\s*[\w.]*(Error|Exception|Timeout|Interrupt)\b")


def sintesi_errore(errore: str | None, *, max_len: int = 120) -> str:
    """Estrae dal traceback la riga che nomina l'eccezione.

    Il traceback in `scraper_runs.errore` è troncato (500 caratteri): a seconda
    di quando è stato scritto, la riga dell'eccezione può trovarsi in testa o
    essere andata persa in coda. Si cerca quindi la riga più informativa
    ovunque sia, con fallback sulla prima riga non generica.
    """
    righe = [r.strip() for r in (errore or "").splitlines() if r.strip()]
    if not righe:
        return "errore non registrato"
    for r in righe:
        if _RE_ECCEZIONE.match(r):
            return r[:max_len]
    for r in righe:
        if not _RE_RIGA_INUTILE.match(r):
            return r[:max_len]
    return righe[-1][:max_len]


def _riga_scraper(s: StatoScraper) -> str:
    quando = f"{s.giorni_fa:.1f}g fa" if s.giorni_fa is not None else "?"
    if s.interrotto:
        riga = f"- `{s.scraper_id}` ({quando}): {s.n_inseriti} atti inseriti prima dello stop"
        if s.n_inseriti:
            # Stava lavorando, non era appeso: è il tetto a essere stretto.
            riga += " — ⚠️ stava ancora inserendo: valutare se il tetto è troppo basso"
        return riga
    if s.fallito:
        return f"- `{s.scraper_id}` ({quando}): {sintesi_errore(s.errore)}"
    return f"- `{s.scraper_id}` ({quando}): {s.n_trovati} trovati, {s.n_inseriti} inseriti"


def formatta_markdown(riepilogo: RiepilogoRun, *, giorni_stale: int = GIORNI_STALE_DEFAULT) -> str:
    """Riepilogo in Markdown, per log del cron / notifica / step summary."""
    righe = ["# TALIA — riepilogo run scraper", ""]
    righe.append(
        f"**{riepilogo.ok}/{riepilogo.totale} OK** · "
        f"{riepilogo.atti_inseriti:,} atti inseriti nell'ultimo run di ciascuno scraper"
    )
    if riepilogo.ultimo_run:
        giorni = riepilogo.giorni_da_ultimo_run or 0
        righe.append(f"Ultimo run in assoluto: `{riepilogo.ultimo_run}` ({giorni:.1f} giorni fa)")
    righe.append("")

    if riepilogo.rischio_perdita_dati:
        righe += [
            f"> ⚠️ **Nessun run da più di {GIORNI_PERDITA_DATI} giorni.** Gli albi pretori"
            " espongono solo gli atti in pubblicazione (~15-30 giorni): quelli scaduti"
            " nel frattempo non sono più recuperabili da lì.",
            "",
        ]

    causa = riepilogo.causa_dominante
    falliti_elencati = riepilogo.falliti_per_altra_causa
    if causa is not None:
        n_causa = len(riepilogo.falliti) - len(falliti_elencati)
        origine = (
            "probabile guasto di rete locale della macchina del run, non dei portali"
            if causa.locale
            else "probabile causa comune, da guardare una volta sola"
        )
        righe += [
            f"> 🌐 **{n_causa} dei {len(riepilogo.falliti)} falliti hanno la stessa causa:"
            f" {causa.descrizione}** — {origine}. Il prossimo run recupera gli atti ancora"
            " in pubblicazione; quelli usciti dall'albo nel frattempo restano persi.",
            "",
        ]

    sezioni = [
        (
            "❌ Falliti" + (" per altre cause" if causa is not None else ""),
            falliti_elencati,
        ),
        ("🔇 Muti (0 atti trovati, nessun errore)", riepilogo.muti),
        (f"🕒 Fermi da più di {giorni_stale} giorni", riepilogo.fermi),
        ("⏱️ Interrotti per tetto di tempo (informativo)", riepilogo.interrotti),
    ]
    for titolo, elenco in sezioni:
        if elenco:
            righe.append(f"## {titolo} ({len(elenco)})")
            righe += [_riga_scraper(s) for s in elenco[:MAX_ELENCO]]
            if len(elenco) > MAX_ELENCO:
                righe.append(f"- … e altri {len(elenco) - MAX_ELENCO}")
            righe.append("")

    if riepilogo.stagnanti:
        righe.append(
            f"## 🥶 Stagnanti: righe sì, atti nuovi no (informativo, {len(riepilogo.stagnanti)})"
        )
        for st in riepilogo.stagnanti[:MAX_ELENCO]:
            di_solito = (
                f"di solito ogni {st.intervallo_tipico:g}"
                if st.intervallo_tipico
                else "storico troppo corto"
            )
            gemello = f" — stesso comune di `{st.gemello}` (TAL-52)" if st.gemello else ""
            righe.append(
                f"- `{st.scraper_id}`: nessun atto nuovo da {st.giorni_senza_nuovi} giorni"
                f" ({di_solito}){gemello}"
            )
        if len(riepilogo.stagnanti) > MAX_ELENCO:
            righe.append(f"- … e altri {len(riepilogo.stagnanti) - MAX_ELENCO}")
        righe.append("")

    if riepilogo.mai_eseguiti:
        mostrati = riepilogo.mai_eseguiti[:MAX_ELENCO]
        coda = (
            f" … e altri {len(riepilogo.mai_eseguiti) - MAX_ELENCO}"
            if len(riepilogo.mai_eseguiti) > MAX_ELENCO
            else ""
        )
        righe.append(f"## ❓ Mai eseguiti ({len(riepilogo.mai_eseguiti)})")
        righe.append(", ".join(f"`{s}`" for s in mostrati) + coda)
        righe.append("")

    if not riepilogo.ha_problemi:
        righe.append("✅ Nessun problema rilevato.")

    if riepilogo.non_previsti:
        # Informativi: non concorrono all'exit code né alla notifica.
        righe += [
            "",
            f"<sub>Non previsti dal run automatico ({len(riepilogo.non_previsti)}): "
            + ", ".join(f"`{s.scraper_id}`" for s in riepilogo.non_previsti[:MAX_ELENCO])
            + (
                f" … e altri {len(riepilogo.non_previsti) - MAX_ELENCO}"
                if len(riepilogo.non_previsti) > MAX_ELENCO
                else ""
            )
            + " — bloccati nel registro o esclusi dal default.</sub>",
        ]
    return "\n".join(righe).rstrip() + "\n"
