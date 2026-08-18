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
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field

#: Quanti scraper elencare per sezione prima di riassumere il resto: quando
#: *nessun* run gira da giorni la sezione "fermi" contiene tutti e 265 gli
#: scraper, e un elenco così lungo nasconde le sezioni davvero azionabili.
MAX_ELENCO = 15

#: Oltre questa soglia uno scraper attivo è considerato "fermo".
GIORNI_STALE_DEFAULT = 3

#: Finestra di pubblicazione tipica di un albo pretorio: oltre questa soglia
#: senza run, gli atti nel frattempo pubblicati e già scaduti sono persi.
GIORNI_PERDITA_DATI = 15


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
    def fallito(self) -> bool:
        return bool(self.errore)

    @property
    def muto(self) -> bool:
        """Completato senza errori ma senza trovare nulla."""
        return not self.errore and self.completato_a is not None and self.n_trovati == 0


@dataclass
class RiepilogoRun:
    """Quadro complessivo dell'ultimo giro di run."""

    totale: int = 0
    ok: int = 0
    falliti: list[StatoScraper] = field(default_factory=list)
    muti: list[StatoScraper] = field(default_factory=list)
    fermi: list[StatoScraper] = field(default_factory=list)
    mai_eseguiti: list[str] = field(default_factory=list)
    atti_inseriti: int = 0
    ultimo_run: str | None = None
    giorni_da_ultimo_run: float | None = None

    @property
    def ha_problemi(self) -> bool:
        return bool(self.falliti or self.muti or self.fermi or self.mai_eseguiti)

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


def riepiloga(
    conn: sqlite3.Connection,
    *,
    scraper_attesi: list[str] | None = None,
    giorni_stale: int = GIORNI_STALE_DEFAULT,
) -> RiepilogoRun:
    """Costruisce il riepilogo dello stato dei run.

    ``scraper_attesi`` è la lista degli slug che *dovrebbero* girare (di norma
    il default del registro): serve a distinguere "mai eseguito" da "non
    previsto". Se omessa, si guardano solo gli scraper già presenti nel DB.
    """
    ultimi = _ultimi_run(conn)
    riepilogo = RiepilogoRun(totale=len(ultimi))

    for stato in sorted(ultimi.values(), key=lambda s: s.scraper_id):
        riepilogo.atti_inseriti += stato.n_inseriti
        if stato.fallito:
            riepilogo.falliti.append(stato)
        elif stato.muto:
            riepilogo.muti.append(stato)
        else:
            riepilogo.ok += 1
        if stato.giorni_fa is not None and stato.giorni_fa > giorni_stale:
            riepilogo.fermi.append(stato)

    if scraper_attesi:
        riepilogo.mai_eseguiti = sorted(set(scraper_attesi) - set(ultimi))

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

    sezioni = [
        ("❌ Falliti", riepilogo.falliti),
        ("🔇 Muti (0 atti trovati, nessun errore)", riepilogo.muti),
        (f"🕒 Fermi da più di {giorni_stale} giorni", riepilogo.fermi),
    ]
    for titolo, elenco in sezioni:
        if elenco:
            righe.append(f"## {titolo} ({len(elenco)})")
            righe += [_riga_scraper(s) for s in elenco[:MAX_ELENCO]]
            if len(elenco) > MAX_ELENCO:
                righe.append(f"- … e altri {len(elenco) - MAX_ELENCO}")
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
    return "\n".join(righe).rstrip() + "\n"
