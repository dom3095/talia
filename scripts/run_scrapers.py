"""Orchestratore scraper TALIA — esecuzione manuale (TAL-20/22/23).

Lancia i crawler disponibili in sequenza, salva nel DB e calcola i red flags.

Scrapers implementati:
  anac       — Dataset SmartCIG ANAC Sicilia (~400 MB CSV, HTTP)
  siracusa   — Albo pretorio Comune di Siracusa (HTTP)
  trapani    — Albo pretorio Comune di Trapani (HTTP)
  agrigento  — Albo pretorio Comune di Agrigento (Playwright/browser headless)

Uso tipico:
    python scripts/run_scrapers.py                               # tutti (escluso agrigento)
    python scripts/run_scrapers.py --scrapers siracusa trapani   # solo HTTP
    python scripts/run_scrapers.py --scrapers agrigento          # solo Agrigento
    python scripts/run_scrapers.py --scrapers anac --no-red-flags
    python scripts/run_scrapers.py --db /tmp/test.db --max-pagine 3
    TALIA_DB=prod.db python scripts/run_scrapers.py

Output: summary testuale su stdout; errori su stderr.
Il DB viene creato se non esiste. Ogni run è idempotente (UNIQUE su ente×url_fonte).
"""

from __future__ import annotations

import argparse
import functools
import sys
import time
import traceback
from pathlib import Path

# ---------------------------------------------------------------------------
# Setup path (funziona anche senza `pip install -e .`)
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from talia.modulo2_scraping.db import (  # noqa: E402
    connetti,
    inizia_run,
    inizializza_db,
    termina_run,
)
from talia.modulo2_scraping.red_flags.runner import esegui_tutti  # noqa: E402
from talia.modulo2_scraping.registry import (  # noqa: E402
    EntryRegistro,
    carica_registro,
    entries_default,
    filtra_eseguibili,
    sincronizza_enti_da_registro,
)
from talia.modulo2_scraping.run_report import e_transitorio  # noqa: E402
from talia.modulo2_scraping.tetto_tempo import (  # noqa: E402
    TETTO_SCRAPER_DEFAULT_S,
    TettoTempoSuperato,
    descrivi_interruzione,
    tetto_supportato,
    tetto_tempo,
)

# Quanti duplicati consecutivi senza un inserimento prima di fermare la paginazione.
# 20 = una pagina jCityGov intera — se è tutta già nota, abbiamo raggiunto il confine.
_STOP_CONSECUTIVI = 20

# ---------------------------------------------------------------------------
# Runner per ogni fonte
# ---------------------------------------------------------------------------


def _errore_db(traceback_completo: str, max_len: int = 500) -> str:
    """Traceback compattato per `scraper_runs.errore`, con l'eccezione in testa.

    Il campo è troncato a 500 caratteri, e un traceback tagliato in coda perde
    proprio la riga che serve (`ConnectionRefusedError: ...`): senza quella, il
    riepilogo dei run mostra una riga di codice a caso invece della causa.
    """
    righe = [r for r in traceback_completo.strip().splitlines() if r.strip()]
    if not righe:
        return "errore sconosciuto"
    return f"{righe[-1].strip()}\n{traceback_completo}"[:max_len]


def tetto_effettivo(timeout_scraper: int | None, no_stop: bool) -> int | None:
    """Tetto per scraper da applicare, in secondi; ``None`` = nessun tetto (TAL-72).

    Un valore esplicito vince sempre (``0`` disattiva). Senza valore esplicito
    il tetto vale :data:`TETTO_SCRAPER_DEFAULT_S`, tranne con ``--no-stop``: un
    backfill storico *deve* poter durare ore, e interromperlo a 20 minuti
    vanificherebbe proprio l'operazione richiesta.
    """
    if timeout_scraper is not None:
        return timeout_scraper if timeout_scraper > 0 else None
    return None if no_stop else TETTO_SCRAPER_DEFAULT_S


def _max_id_atti(conn) -> int:
    return conn.execute("SELECT COALESCE(MAX(id), 0) FROM atti").fetchone()[0]


def esegui_scraper(conn, nome: str, fn, kwargs: dict, tetto_s: int | None) -> tuple[str, dict]:
    """Esegue uno scraper registrandone l'esito in `scraper_runs`.

    Ritorna ``(stato, esito)`` con ``stato`` in ``ok`` / ``errore`` /
    ``interrotto``. L'interruzione per tetto di tempo è tenuta distinta
    dall'errore (TAL-72): non conta come fallimento del run — una notifica che
    suona ogni notte per un host lento si impara a ignorarla — e il report la
    mostra a parte.

    Il conteggio degli atti inseriti prima dell'interruzione si ricava dagli
    id: il run è sequenziale su un'unica connessione, quindi gli atti con id
    oltre il massimo di partenza sono tutti di questo scraper. È l'unico
    numero affidabile, perché lo scraper interrotto non ha restituito il suo
    dict di esito.
    """
    run_id = inizia_run(conn, nome)
    id_partenza = _max_id_atti(conn)
    try:
        with tetto_tempo(tetto_s):
            esito = fn(conn, **kwargs)
    except TettoTempoSuperato as exc:
        # Si annulla solo ciò che non era ancora committato (es. un caricamento
        # in blocco a metà): inserisci_atto committa per atto, quindi gli atti
        # d'albo già salvati restano, e il conteggio sotto vede solo quelli.
        if conn.in_transaction:
            conn.rollback()
        n_inseriti = conn.execute(
            "SELECT COUNT(*) FROM atti WHERE id > ?", (id_partenza,)
        ).fetchone()[0]
        descrizione = descrivi_interruzione(exc)
        print(f"  INTERROTTO: {descrizione} — {n_inseriti} atti inseriti prima dello stop")
        termina_run(
            conn,
            run_id,
            # n_trovati non è noto: gli inseriti ne sono il limite inferiore.
            n_trovati=n_inseriti,
            n_inseriti=n_inseriti,
            n_duplicati=0,
            errore=descrizione[:500],
        )
        return "interrotto", {"inseriti": n_inseriti, "tetto_s": tetto_s}
    except Exception:
        msg = traceback.format_exc()
        print(f"  ERRORE:\n{msg}", file=sys.stderr)
        errore = _errore_db(msg)
        termina_run(conn, run_id, n_trovati=0, n_inseriti=0, n_duplicati=0, errore=errore)
        return "errore", {"errore": errore}
    termina_run(
        conn,
        run_id,
        n_trovati=esito.get("n_trovati", 0),
        n_inseriti=esito.get("inseriti", 0),
        n_duplicati=esito.get("duplicati", 0),
        data_min=esito.get("data_min"),
        data_max=esito.get("data_max"),
    )
    return "ok", esito


#: Tempo massimo complessivo del ripasso a fine run (TAL-75). In una notte di
#: rete degradata possono fallire per timeout decine di scraper: ritentarli
#: tutti col tetto da 20 minuti ciascuno riporterebbe il run oltre le 24h, che
#: è esattamente il guasto di TAL-72.
BUDGET_RIPASSO_DEFAULT_S = 3600


def ripassa_transitori(
    conn,
    falliti: dict[str, str],
    scrapers: dict,
    kwargs: dict,
    tetto_s: int | None,
    budget_s: int | None,
    orologio=time.monotonic,
) -> dict[str, tuple[str, dict]]:
    """Ritenta una volta gli scraper falliti per cause transitorie (TAL-75).

    Le notti con rete instabile fanno fallire per timeout anche i capoluoghi
    (Catania 3 volte su 8, Palermo e Trapani 2 su 8 nella settimana 12-19/10),
    che di norma finiscono in 2 minuti: ore dopo il primo tentativo, quasi
    sempre l'host risponde. Gli errori strutturali (certificato, 403) si
    ripresenterebbero identici e non si ritentano.

    Il nuovo tentativo scrive una sua riga in ``scraper_runs``: il report legge
    l'ultima, quindi un recupero risulta come OK senza perdere traccia del primo
    fallimento. Superato ``budget_s`` i restanti non vengono ritentati.
    """
    candidati = [n for n, err in falliti.items() if e_transitorio(err)]
    if not candidati:
        return {}
    print(f"\n── RIPASSO ({len(candidati)} falliti per cause transitorie) ──")
    inizio = orologio()
    esiti: dict[str, tuple[str, dict]] = {}
    for nome in candidati:
        if budget_s and orologio() - inizio >= budget_s:
            saltati = len(candidati) - len(esiti)
            print(f"  budget di {budget_s}s esaurito: {saltati} non ritentati")
            break
        print(f"\n── {nome.upper()} (ripasso) ──")
        esiti[nome] = esegui_scraper(conn, nome, scrapers[nome], kwargs, tetto_s)
    return esiti


#: Tetto della fase di estrazione testo (TAL-77): ~2,5s per atto misurati,
#: 400 atti ≈ 17 minuti; il tetto evita che un host lento la trascini per ore.
TETTO_TESTO_S = 1800


def esegui_testo_atti(conn, limite: int) -> None:
    """Estrae il testo degli atti nuovi (TAL-77). Non fa mai fallire il run.

    È un arricchimento: se manca `pdfplumber` o il portale non risponde, gli
    atti restano con ``testo_estratto IS NULL`` e si riprovano la notte dopo,
    finché sono nella finestra di :data:`testo_atti.GIORNI_DEFAULT` giorni.
    """
    from talia.modulo2_scraping.testo_atti import estrai_testo_atti

    print(f"\n── TESTO ATTI (max {limite}) ──")
    try:
        with tetto_tempo(TETTO_TESTO_S if tetto_supportato() else None):
            print(f"  {estrai_testo_atti(conn, limite=limite)}")
    except TettoTempoSuperato:
        # Come in `esegui_scraper`: si annulla solo l'atto a metà, gli altri
        # sono già committati uno per uno.
        if conn.in_transaction:
            conn.rollback()
        print(f"  interrotto dopo {TETTO_TESTO_S}s: gli atti già elaborati restano salvati")
    except Exception:
        print(traceback.format_exc(), file=sys.stderr)


def _date_range(atti) -> tuple[str | None, str | None]:
    dates = [a.data_pub or a.data_atto for a in atti if a.data_pub or a.data_atto]
    return (min(dates) if dates else None, max(dates) if dates else None)


def _run_anac(conn, anac_file: str | None = None, anac_anno: int | None = None, **_kwargs) -> dict:
    from talia.modulo2_scraping.fonti.anac import (
        _anno_default,
        carica_csv_anac,
        scarica_e_carica,
    )

    t0 = time.monotonic()
    if anac_file:
        print(f"  [ANAC] Carico da file locale: {anac_file}")
        with open(anac_file, encoding="utf-8", errors="replace") as f:
            contenuto = f.read()
        esito = carica_csv_anac(contenuto, conn)
    else:
        anno = anac_anno or _anno_default()
        # SmartCIG è pubblicato per mese (~40 MB zippati l'uno): 12 richieste,
        # non un unico file annuale. Resta fuori dal run notturno perché il
        # dataset si aggiorna mensilmente — rilanciarlo ogni notte sarebbe
        # mezzo giga al giorno per nulla.
        print(f"  [ANAC] Scarico SmartCIG {anno}, 12 file mensili (~450 MB totali)…")
        esito = scarica_e_carica(conn, anno=anno)
    elapsed = time.monotonic() - t0
    print(f"  [ANAC] {esito} — {elapsed:.0f}s")
    esito["n_trovati"] = esito.get("inseriti", 0) + esito.get("duplicati", 0)
    return esito


def _run_siracusa_comune(
    conn, base_url, codice_istat, denominazione, max_pagine: int = 50, **_kwargs
) -> dict:
    from talia.modulo2_scraping.fonti.siracusa import prepara_ente, salva_atti, scarica_atti

    prepara_ente(conn, base_url=base_url, codice_istat=codice_istat, denominazione=denominazione)
    print(f"  [Siracusa] Scarico albo pretorio (max {max_pagine} pagine)…")
    t0 = time.monotonic()
    atti = list(scarica_atti(max_pagine=max_pagine, base_url=base_url))
    esito = salva_atti(atti, conn)
    elapsed = time.monotonic() - t0
    print(f"  [Siracusa] {len(atti)} atti trovati → {esito} — {elapsed:.0f}s")
    esito["n_trovati"] = len(atti)
    esito["data_min"], esito["data_max"] = _date_range(atti)
    return esito


def _make_siracusa_runner(entry: EntryRegistro):
    def _runner(conn, **kwargs):
        return _run_siracusa_comune(
            conn, entry.base_url, entry.codice_istat, entry.denominazione, **kwargs
        )

    return _runner


def _run_trapani_comune(
    conn, base_url, codice_istat, denominazione, max_pagine: int = 50, **_kwargs
) -> dict:
    from talia.modulo2_scraping.fonti.trapani import prepara_ente, salva_atti, scarica_atti

    prepara_ente(conn, base_url=base_url, codice_istat=codice_istat, denominazione=denominazione)
    print(f"  [Trapani] Scarico albo pretorio (max {max_pagine} pagine)…")
    t0 = time.monotonic()
    atti = list(scarica_atti(max_pagine=max_pagine, base_url=base_url))
    esito = salva_atti(atti, conn)
    elapsed = time.monotonic() - t0
    print(f"  [Trapani] {len(atti)} atti trovati → {esito} — {elapsed:.0f}s")
    esito["n_trovati"] = len(atti)
    esito["data_min"], esito["data_max"] = _date_range(atti)
    return esito


def _make_trapani_runner(entry: EntryRegistro):
    def _runner(conn, **kwargs):
        return _run_trapani_comune(
            conn, entry.base_url, entry.codice_istat, entry.denominazione, **kwargs
        )

    return _runner


def _run_palermo_comune(
    conn, base_url, codice_istat, denominazione, max_pagine: int = 50, **_kwargs
) -> dict:
    from talia.modulo2_scraping.fonti.palermo import prepara_ente, salva_atti, scarica_atti

    prepara_ente(conn, base_url=base_url, codice_istat=codice_istat, denominazione=denominazione)
    print(f"  [Palermo] Scarico albo pretorio SISPI (max {max_pagine} pagine)…")
    t0 = time.monotonic()
    atti = list(scarica_atti(max_pagine=max_pagine, base_url=base_url))
    esito = salva_atti(atti, conn)
    elapsed = time.monotonic() - t0
    print(f"  [Palermo] {len(atti)} atti trovati → {esito} — {elapsed:.0f}s")
    esito["n_trovati"] = len(atti)
    esito["data_min"], esito["data_max"] = _date_range(atti)
    return esito


def _make_palermo_runner(entry: EntryRegistro):
    def _runner(conn, **kwargs):
        return _run_palermo_comune(
            conn, entry.base_url, entry.codice_istat, entry.denominazione, **kwargs
        )

    return _runner


def _run_catania_comune(
    conn,
    base_url,
    codice_istat,
    denominazione,
    qs_base,
    ente_mittente,
    max_pagine: int = 100,
    **_kwargs,
) -> dict:
    from talia.modulo2_scraping.fonti.catania import prepara_ente, salva_atti, scarica_atti

    prepara_ente(
        conn,
        base_url=base_url,
        qs_base=qs_base,
        ente_mittente=ente_mittente,
        codice_istat=codice_istat,
        denominazione=denominazione,
    )
    print(f"  [Catania] Scarico albo pretorio URBI (max {max_pagine} pagine)…")
    t0 = time.monotonic()
    atti = list(
        scarica_atti(
            max_pagine=max_pagine, base_url=base_url, qs_base=qs_base, ente_mittente=ente_mittente
        )
    )
    esito = salva_atti(atti, conn)
    elapsed = time.monotonic() - t0
    print(f"  [Catania] {len(atti)} atti trovati → {esito} — {elapsed:.0f}s")
    esito["n_trovati"] = len(atti)
    esito["data_min"], esito["data_max"] = _date_range(atti)
    return esito


def _make_catania_runner(entry: EntryRegistro):
    def _runner(conn, **kwargs):
        return _run_catania_comune(
            conn,
            entry.base_url,
            entry.codice_istat,
            entry.denominazione,
            entry.qs_base,
            entry.ente_mittente,
            **kwargs,
        )

    return _runner


def _run_ribera_comune(
    conn, base_url, codice_istat, denominazione, max_pagine: int = 50, **_kwargs
) -> dict:
    from talia.modulo2_scraping.fonti.ribera import prepara_ente, salva_atti, scarica_atti

    prepara_ente(conn, base_url=base_url, codice_istat=codice_istat, denominazione=denominazione)
    print(f"  [Ribera] Scarico albo pretorio WordPress (max {max_pagine} pagine)…")
    t0 = time.monotonic()
    atti = list(scarica_atti(max_pagine=max_pagine, base_url=base_url))
    esito = salva_atti(atti, conn)
    elapsed = time.monotonic() - t0
    print(f"  [Ribera] {len(atti)} atti trovati → {esito} — {elapsed:.0f}s")
    esito["n_trovati"] = len(atti)
    esito["data_min"], esito["data_max"] = _date_range(atti)
    return esito


def _make_ribera_runner(entry: EntryRegistro):
    def _runner(conn, **kwargs):
        return _run_ribera_comune(
            conn, entry.base_url, entry.codice_istat, entry.denominazione, **kwargs
        )

    return _runner


def _run_nicosia_comune(conn, codice_istat, denominazione, max_pagine: int = 20, **_kwargs) -> dict:
    from talia.modulo2_scraping.fonti.nicosia import prepara_ente, salva_atti, scarica_atti

    prepara_ente(conn, codice_istat=codice_istat, denominazione=denominazione)
    print("  [Nicosia] Scarico albo pretorio WordPress (tassonomia)…")
    t0 = time.monotonic()
    atti = list(scarica_atti(max_pagine=max_pagine, codice_istat=codice_istat))
    esito = salva_atti(atti, conn)
    elapsed = time.monotonic() - t0
    print(f"  [Nicosia] {len(atti)} atti trovati → {esito} — {elapsed:.0f}s")
    esito["n_trovati"] = len(atti)
    esito["data_min"], esito["data_max"] = _date_range(atti)
    return esito


def _make_nicosia_runner(entry: EntryRegistro):
    def _runner(conn, **kwargs):
        return _run_nicosia_comune(conn, entry.codice_istat, entry.denominazione, **kwargs)

    return _runner


def _run_agrigento_comune(
    conn, base_url, codice_istat, denominazione, max_pagine: int = 20, **_kwargs
) -> dict:
    try:
        from talia.modulo2_scraping.fonti.agrigento import prepara_ente, salva_atti, scarica_atti
    except ImportError as exc:
        raise RuntimeError(
            "Agrigento richiede Playwright: pip install playwright && playwright install chromium"
        ) from exc

    prepara_ente(conn, base_url=base_url, codice_istat=codice_istat, denominazione=denominazione)
    print(f"  [Agrigento] Scarico albo pretorio con Playwright (max {max_pagine} pagine)…")
    t0 = time.monotonic()
    atti = list(scarica_atti(max_pagine=max_pagine, base_url=base_url))
    esito = salva_atti(atti, conn)
    elapsed = time.monotonic() - t0
    print(f"  [Agrigento] {len(atti)} atti trovati → {esito} — {elapsed:.0f}s")
    esito["n_trovati"] = len(atti)
    esito["data_min"], esito["data_max"] = _date_range(atti)
    return esito


def _make_agrigento_runner(entry: EntryRegistro):
    def _runner(conn, **kwargs):
        return _run_agrigento_comune(
            conn, entry.base_url, entry.codice_istat, entry.denominazione, **kwargs
        )

    return _runner


def _run_serviziolinealbo_comune(
    conn, base_url, codice_istat, denominazione, provincia, max_pagine: int = 20, **_kwargs
) -> dict:
    try:
        from talia.modulo2_scraping.fonti.serviziolinealbo import (
            prepara_ente,
            salva_atti,
            scarica_atti,
        )
    except ImportError as exc:
        raise RuntimeError(
            "serviziolinealbo richiede Playwright: "
            "pip install playwright && playwright install chromium"
        ) from exc

    prepara_ente(conn, codice_istat=codice_istat, denominazione=denominazione, provincia=provincia)
    print(
        f"  [{denominazione}] Scarico albo pretorio ServiziOnLine con Playwright "
        f"(max {max_pagine} pagine)…"
    )
    t0 = time.monotonic()
    atti = list(scarica_atti(base_url, codice_istat, max_pagine=max_pagine))
    esito = salva_atti(atti, conn)
    elapsed = time.monotonic() - t0
    print(f"  [{denominazione}] {len(atti)} atti trovati → {esito} — {elapsed:.0f}s")
    esito["n_trovati"] = len(atti)
    esito["data_min"], esito["data_max"] = _date_range(atti)
    return esito


def _make_serviziolinealbo_runner(entry: EntryRegistro):
    def _runner(conn, **kwargs):
        return _run_serviziolinealbo_comune(
            conn,
            entry.base_url,
            entry.codice_istat,
            entry.denominazione,
            entry.provincia,
            **kwargs,
        )

    return _runner


# jCityGov (Liferay *.trasparenza-valutazione-merito.it)
# Messina esclusa: SSL self-signed cert — da risolvere separatamente.


def _run_jcitygov_comune(
    conn, nome, base_url, codice_istat, denominazione, max_pagine=10, no_stop=False, **_kwargs
):
    from talia.modulo2_scraping.db import EnteMetadato, inserisci_atto, upsert_ente
    from talia.modulo2_scraping.fonti.jcitygov import scarica_atti

    upsert_ente(conn, EnteMetadato(denominazione=denominazione, codice_istat=codice_istat))
    limit = max_pagine * 20
    stop_label = " [backfill, stop disabilitato]" if no_stop else ""
    print(
        f"  [{nome.capitalize()}] Scarico albo pretorio jCityGov"
        f" (max {max_pagine} pagine){stop_label}…"
    )
    t0 = time.monotonic()

    inseriti = duplicati = consecutivi_dup = 0
    dates: list[str] = []
    for atto in scarica_atti(base_url, codice_istat, limit=limit):
        if inserisci_atto(conn, atto) is not None:
            inseriti += 1
            consecutivi_dup = 0
            if atto.data_pub:
                dates.append(atto.data_pub)
        else:
            duplicati += 1
            consecutivi_dup += 1
        if not no_stop and consecutivi_dup >= _STOP_CONSECUTIVI:
            break
    conn.commit()

    n_trovati = inseriti + duplicati
    elapsed = time.monotonic() - t0
    esito = {"inseriti": inseriti, "duplicati": duplicati}
    print(f"  [{nome.capitalize()}] {n_trovati} atti trovati → {esito} — {elapsed:.0f}s")
    esito["n_trovati"] = n_trovati
    esito["data_min"] = min(dates) if dates else None
    esito["data_max"] = max(dates) if dates else None
    return esito


def _make_jcitygov_runner(entry: EntryRegistro):
    def _runner(conn, **kwargs):
        return _run_jcitygov_comune(
            conn, entry.slug, entry.base_url, entry.codice_istat, entry.denominazione, **kwargs
        )

    return _runner


# portalepa PHP: stessa piattaforma di Siracusa, riusata da altri comuni
# sotto domini diversi (TAL-49). Partinico ha un layout colonne diverso
# ("_full"): non compatibile con questo modulo, vedi docs/wiki/14-censimento-albi.md.
def _run_portalepa_comune(
    conn, nome, base_url, codice_istat, denominazione, max_pagine=10, no_stop=False, **_kwargs
):
    from talia.modulo2_scraping.db import EnteMetadato, inserisci_atto, upsert_ente
    from talia.modulo2_scraping.fonti.portalepa import scarica_atti

    upsert_ente(conn, EnteMetadato(denominazione=denominazione, codice_istat=codice_istat))
    stop_label = " [backfill, stop disabilitato]" if no_stop else ""
    print(
        f"  [{nome.capitalize()}] Scarico albo pretorio portalepa"
        f" (max {max_pagine} pagine){stop_label}…"
    )
    t0 = time.monotonic()

    inseriti = duplicati = consecutivi_dup = 0
    dates: list[str] = []
    for atto in scarica_atti(base_url, codice_istat, max_pagine=max_pagine):
        if inserisci_atto(conn, atto) is not None:
            inseriti += 1
            consecutivi_dup = 0
            if atto.data_atto:
                dates.append(atto.data_atto)
        else:
            duplicati += 1
            consecutivi_dup += 1
        if not no_stop and consecutivi_dup >= _STOP_CONSECUTIVI:
            break
    conn.commit()

    n_trovati = inseriti + duplicati
    elapsed = time.monotonic() - t0
    esito = {"inseriti": inseriti, "duplicati": duplicati}
    print(f"  [{nome.capitalize()}] {n_trovati} atti trovati → {esito} — {elapsed:.0f}s")
    esito["n_trovati"] = n_trovati
    esito["data_min"] = min(dates) if dates else None
    esito["data_max"] = max(dates) if dates else None
    return esito


def _make_portalepa_runner(entry: EntryRegistro):
    def _runner(conn, **kwargs):
        return _run_portalepa_comune(
            conn, entry.slug, entry.base_url, entry.codice_istat, entry.denominazione, **kwargs
        )

    return _runner


# Halley EG (Halley Informatica): vendor diffuso tra più comuni siciliani
# sotto domini diversi (TAL-49). Paginazione stateless via ?pag=N.


def _run_halley_comune(
    conn,
    nome,
    base_url,
    codice_istat,
    denominazione,
    max_pagine=10,
    no_stop=False,
    skip_ssl=False,
    **_kwargs,
):
    from talia.modulo2_scraping.db import EnteMetadato, inserisci_atto, upsert_ente
    from talia.modulo2_scraping.fonti.halley import scarica_atti

    upsert_ente(conn, EnteMetadato(denominazione=denominazione, codice_istat=codice_istat))
    stop_label = " [backfill, stop disabilitato]" if no_stop else ""
    print(
        f"  [{nome.capitalize()}] Scarico albo pretorio Halley EG"
        f" (max {max_pagine} pagine){stop_label}…"
    )
    t0 = time.monotonic()

    inseriti = duplicati = consecutivi_dup = 0
    dates: list[str] = []
    for atto in scarica_atti(base_url, codice_istat, max_pagine=max_pagine, skip_ssl=skip_ssl):
        if inserisci_atto(conn, atto) is not None:
            inseriti += 1
            consecutivi_dup = 0
            if atto.data_atto:
                dates.append(atto.data_atto)
        else:
            duplicati += 1
            consecutivi_dup += 1
        if not no_stop and consecutivi_dup >= _STOP_CONSECUTIVI:
            break
    conn.commit()

    n_trovati = inseriti + duplicati
    elapsed = time.monotonic() - t0
    esito = {"inseriti": inseriti, "duplicati": duplicati}
    print(f"  [{nome.capitalize()}] {n_trovati} atti trovati → {esito} — {elapsed:.0f}s")
    esito["n_trovati"] = n_trovati
    esito["data_min"] = min(dates) if dates else None
    esito["data_max"] = max(dates) if dates else None
    return esito


def _make_halley_runner(entry: EntryRegistro):
    def _runner(conn, **kwargs):
        return _run_halley_comune(
            conn,
            entry.slug,
            entry.base_url,
            entry.codice_istat,
            entry.denominazione,
            skip_ssl=entry.skip_ssl,
            **kwargs,
        )

    return _runner


# URBI Cloud (Maggioli): stessa piattaforma di Catania (`catania.py`), riusata
# da comuni ospitati su cloud.urbi.it con un DB_NAME diverso per tenant
# (Favara, Raffadali — TAL-49).


def _run_urbi_comune(
    conn,
    nome,
    base_url,
    qs_base,
    codice_istat,
    ente_mittente,
    denominazione,
    max_pagine=50,
    no_stop=False,
    **_kwargs,
):
    from talia.modulo2_scraping.db import EnteMetadato, inserisci_atto, upsert_ente
    from talia.modulo2_scraping.fonti.urbi import MAX_PAGINE_PER_TIPOLOGIA, scarica_atti

    upsert_ente(conn, EnteMetadato(denominazione=denominazione, codice_istat=codice_istat))
    stop_label = " [backfill, stop disabilitato]" if no_stop else ""
    print(
        f"  [{nome.capitalize()}] Scarico albo pretorio URBI Cloud"
        f" (max {max_pagine} pagine){stop_label}…"
    )
    t0 = time.monotonic()

    inseriti = duplicati = consecutivi_dup = 0
    dates: list[str] = []
    # Sui tenant che pretendono una Tipologia esplicita (TAL-68) lo scraper
    # scandisce una tipologia alla volta e la marca sull'atto. Lo stop-on-known
    # va allora applicato *dentro* ciascuna tipologia: fermarsi del tutto alla
    # prima già nota lascerebbe le successive mai scandite, e lo scraper
    # tornerebbe muto dal secondo run in poi.
    tipologia_corrente: str | None = None
    salta_tipologia = False
    for atto in scarica_atti(
        base_url,
        qs_base,
        codice_istat,
        ente_mittente,
        max_pagine=max_pagine,
        # In backfill si vuole tutto l'archivio, tetto per tipologia incluso.
        max_pagine_per_tipologia=None if no_stop else MAX_PAGINE_PER_TIPOLOGIA,
    ):
        tipologia = atto.metadati.get("tipologia_ricerca")
        if tipologia != tipologia_corrente:
            tipologia_corrente = tipologia
            consecutivi_dup = 0
            salta_tipologia = False
        if salta_tipologia:
            continue
        if inserisci_atto(conn, atto) is not None:
            inseriti += 1
            consecutivi_dup = 0
            if atto.data_pub:
                dates.append(atto.data_pub)
        else:
            duplicati += 1
            consecutivi_dup += 1
        if not no_stop and consecutivi_dup >= _STOP_CONSECUTIVI:
            if tipologia is None:
                break  # tenant normale: una sola scansione, si chiude qui
            salta_tipologia = True  # riprende alla prossima tipologia
    conn.commit()

    n_trovati = inseriti + duplicati
    elapsed = time.monotonic() - t0
    esito = {"inseriti": inseriti, "duplicati": duplicati}
    print(f"  [{nome.capitalize()}] {n_trovati} atti trovati → {esito} — {elapsed:.0f}s")
    esito["n_trovati"] = n_trovati
    esito["data_min"] = min(dates) if dates else None
    esito["data_max"] = max(dates) if dates else None
    return esito


def _make_urbi_runner(entry: EntryRegistro):
    def _runner(conn, **kwargs):
        return _run_urbi_comune(
            conn,
            entry.slug,
            entry.base_url,
            entry.qs_base,
            entry.codice_istat,
            entry.ente_mittente,
            entry.denominazione,
            **kwargs,
        )

    return _runner


# Halley HSPromila (ASP.NET): variante Halley diversa da quella "EG"
# (`halley.py`), riusata da Sambuca di Sicilia e Santo Stefano Quisquina
# (TAL-49). Nessuna paginazione nota: un solo blocco di atti per comune.


def _run_hspromila_comune(conn, nome, url, codice_istat, denominazione, **_kwargs) -> dict:
    from talia.modulo2_scraping.db import EnteMetadato, inserisci_atto, upsert_ente
    from talia.modulo2_scraping.fonti.hspromila import scarica_atti

    upsert_ente(conn, EnteMetadato(denominazione=denominazione, codice_istat=codice_istat))
    print(f"  [{nome.capitalize()}] Scarico albo pretorio Halley HSPromila…")
    t0 = time.monotonic()
    atti = list(scarica_atti(url, codice_istat))
    esito = {"inseriti": 0, "duplicati": 0}
    for atto in atti:
        if inserisci_atto(conn, atto) is not None:
            esito["inseriti"] += 1
        else:
            esito["duplicati"] += 1
    conn.commit()
    elapsed = time.monotonic() - t0
    print(f"  [{nome.capitalize()}] {len(atti)} atti trovati → {esito} — {elapsed:.0f}s")
    esito["n_trovati"] = len(atti)
    esito["data_min"], esito["data_max"] = _date_range(atti)
    return esito


def _make_hspromila_runner(entry: EntryRegistro):
    def _runner(conn, **kwargs):
        return _run_hspromila_comune(
            conn, entry.slug, entry.base_url, entry.codice_istat, entry.denominazione, **kwargs
        )

    return _runner


# TAL-51 PENDING (comuni Trapani/Palermo, reverse-engineering in progress, non
# ancora nel registro perché richiedono scraper dedicati): vedi docs/cards/TAL-51.md.

# - Trapani: Petrosino (7.7k, WordPress), Pantelleria (7.5k, HyperSIC),
#   Calatafimi-Segesta (6.7k, HyperSIC), Poggioreale (1.5k, HyperSIC)
# - Palermo: 11 comuni >5k su ComuneWeb (6), Halley (1), HyperSIC (1), APKAPPA (1),
#   SaturnWeb (1), custom (1) — vedi docs/cards/TAL-51.md per dettagli.
# Questi comuni sono censiti (data/censimento_albi_pa_tp_COMPLETO.csv) ma non ancora
# nel registry perché richiedono scraper dedicati o reverse-engineering ulteriore.


def _make_anac_runner(entry: EntryRegistro):
    # ANAC non ha base_url/codice_istat nello stesso senso degli altri
    # moduli (scarica un CSV SmartCIG regionale, non un albo pretorio): il
    # runner è fisso e non dipende dai campi dell'entry.
    return _run_anac


_FACTORY_PER_MODULO = {
    "jcitygov": _make_jcitygov_runner,
    "portalepa": _make_portalepa_runner,
    "halley": _make_halley_runner,
    "urbi": _make_urbi_runner,
    "hspromila": _make_hspromila_runner,
    "palermo": _make_palermo_runner,
    "catania": _make_catania_runner,
    "trapani": _make_trapani_runner,
    "siracusa": _make_siracusa_runner,
    "ribera": _make_ribera_runner,
    "nicosia": _make_nicosia_runner,
    "agrigento": _make_agrigento_runner,
    "serviziolinealbo": _make_serviziolinealbo_runner,
    "anac": _make_anac_runner,
}


def costruisci_scrapers(
    registro: list[EntryRegistro],
) -> tuple[dict[str, callable], list[str]]:
    """Costruisce il dict degli scraper eseguibili e la lista di default dal registro.

    Ogni modulo (incluso ANAC) è dispatchato uniformemente via
    ``_FACTORY_PER_MODULO``: nessun caso speciale hardcoded qui — l'unica
    conoscenza di quali moduli non richiedono un ente vive in
    ``registry.MODULI_SENZA_ENTE``, usata dalla validazione del registro.
    """
    scrapers: dict[str, callable] = {}
    for entry in filtra_eseguibili(registro):
        if entry.modulo not in _FACTORY_PER_MODULO:
            raise RuntimeError(
                f"Modulo sconosciuto nel registro: {entry.modulo!r} (slug {entry.slug!r})"
            )
        scrapers[entry.slug] = _FACTORY_PER_MODULO[entry.modulo](entry)
    return scrapers, entries_default(registro)


@functools.lru_cache(maxsize=1)
def _registro_e_scrapers() -> tuple[list[EntryRegistro], dict[str, callable], list[str]]:
    """Carica il registro e costruisce gli scraper alla prima chiamata.

    Lazy (non a import time): un CSV malformato fallisce solo quando lo si
    usa davvero — dentro `_parse_args()`/`main()`, il punto di ingresso reale
    — non ad ogni import di questo modulo (es. da parte dei test, che prima
    di questo fix pagavano il costo/rischio di un parse+validate CSV
    completo solo per riusare una funzione non correlata).
    """
    registro = carica_registro()
    scrapers, scrapers_default = costruisci_scrapers(registro)
    return registro, scrapers, scrapers_default


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    _, scrapers, scrapers_default = _registro_e_scrapers()
    p = argparse.ArgumentParser(
        description="Lancia gli scraper TALIA e calcola i red flags.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Scrapers disponibili:
  anac       Dataset SmartCIG ANAC Sicilia (~400 MB, HTTP)
  siracusa   Albo pretorio Siracusa (HTTP)
  trapani    Albo pretorio Trapani (HTTP)
  agrigento  Albo pretorio Agrigento (Playwright — browser headless)

Non inclusi nel default: agrigento (Playwright), iCity comuni (config mancante).

Esempi:
  python scripts/run_scrapers.py
  python scripts/run_scrapers.py --scrapers siracusa trapani --max-pagine 5
  python scripts/run_scrapers.py --scrapers anac --no-red-flags
  python scripts/run_scrapers.py --scrapers siracusa trapani agrigento
  TALIA_DB=prod.db python scripts/run_scrapers.py
        """,
    )
    p.add_argument(
        "--db",
        default=None,
        help="Percorso DB SQLite (default: $TALIA_DB o talia.db)",
    )
    p.add_argument(
        "--scrapers",
        nargs="+",
        choices=list(scrapers),
        default=scrapers_default,
        metavar="SCRAPER",
        help=f"Scrapers da eseguire (default: {' '.join(scrapers_default)})",
    )
    p.add_argument(
        "--extra-scrapers",
        nargs="+",
        choices=list(scrapers),
        default=[],
        dest="extra_scrapers",
        metavar="SCRAPER",
        help=(
            "Scrapers da aggiungere alla lista (invece di sostituirla come --scrapers)."
            " Serve al run automatico per includere gli 'escluso_default' che restano"
            " comunque eseguibili, es. i Playwright: --extra-scrapers agrigento pachino"
        ),
    )
    p.add_argument(
        "--max-pagine",
        type=int,
        default=50,
        dest="max_pagine",
        help="Pagine massime per gli albi pretori (default: 50)",
    )
    p.add_argument(
        "--no-red-flags",
        action="store_true",
        dest="no_red_flags",
        help="Salta il calcolo dei red flags batch",
    )
    p.add_argument(
        "--anac-file",
        default=None,
        dest="anac_file",
        metavar="FILE",
        help=(
            "Carica il CSV SmartCIG da file locale invece di scaricarlo"
            " (utile se il WAF ANAC blocca il download automatico)"
        ),
    )
    p.add_argument(
        "--anac-anno",
        type=int,
        default=None,
        dest="anac_anno",
        metavar="ANNO",
        help="Anno civile SmartCIG da scaricare (default: anno corrente - 1)",
    )
    p.add_argument(
        "--no-stop",
        action="store_true",
        dest="no_stop",
        help=(
            "Disabilita lo stop-on-known"
            " (backfill storico: scarica tutte le pagine anche se già in DB)"
        ),
    )
    p.add_argument(
        "--timeout-scraper",
        type=int,
        default=None,
        dest="timeout_scraper",
        metavar="SECONDI",
        help=(
            "Tetto di tempo per singolo scraper: oltre, lo scraper viene interrotto"
            " (gli atti già salvati restano) e il run prosegue col successivo."
            f" Default: {TETTO_SCRAPER_DEFAULT_S}s, nessun tetto con --no-stop."
            " 0 = nessun tetto (TAL-72)."
        ),
    )
    p.add_argument(
        "--budget-ripasso",
        type=int,
        default=BUDGET_RIPASSO_DEFAULT_S,
        dest="budget_ripasso",
        metavar="SECONDI",
        help=(
            "A fine run ritenta una volta gli scraper falliti per cause di rete"
            " transitorie (timeout, connessione chiusa, DNS), entro questo tempo"
            f" complessivo. Default: {BUDGET_RIPASSO_DEFAULT_S}s; 0 = nessun ripasso (TAL-75)."
        ),
    )
    p.add_argument(
        "--testo-atti",
        type=int,
        default=0,
        dest="testo_atti",
        metavar="N",
        help=(
            "Dopo lo scraping, scarica il PDF ed estrae il testo di al massimo N atti"
            " jCityGov recenti (determine, delibere, bandi…), salvando solo il testo."
            " Default: 0 (disattivato); il run notturno usa 400 (TAL-77)."
        ),
    )
    p.add_argument(
        "--llm-modello",
        default=None,
        dest="llm_modello",
        metavar="MODELLO",
        help=(
            "Modello Ollama per classificare i procedimenti non classificati dalle regex"
            " (es. 'llama3.2'). Richiede Ollama attivo su localhost:11434."
            " Default: skip (solo classificazione deterministica)."
        ),
    )
    p.add_argument(
        "--llm-limite",
        type=int,
        default=200,
        dest="llm_limite",
        metavar="N",
        help="Numero massimo di procedimenti da passare all'LLM per run (default: 200).",
    )
    return p.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    args = _parse_args()
    registro, scrapers, _ = _registro_e_scrapers()

    import os

    db_path = args.db or os.environ.get("TALIA_DB", "talia.db")
    print(f"DB: {db_path}")

    conn = connetti(db_path)
    inizializza_db(conn)
    n_sync = sincronizza_enti_da_registro(conn, registro)
    print(f"Registro sincronizzato: {n_sync} enti")

    risultati: dict[str, dict | str] = {}
    falliti: dict[str, str] = {}
    errori = 0

    # `dict.fromkeys` invece di un set: preserva l'ordine e non riesegue uno
    # scraper già presente nella lista principale.
    da_eseguire = list(dict.fromkeys([*args.scrapers, *args.extra_scrapers]))

    tetto_s = tetto_effettivo(args.timeout_scraper, args.no_stop)
    if tetto_s and not tetto_supportato():
        print("Tetto per scraper non applicabile su questa piattaforma: nessun limite.")
        tetto_s = None
    print(f"Tetto per scraper: {f'{tetto_s}s' if tetto_s else 'nessuno'}")
    kwargs = dict(
        max_pagine=args.max_pagine,
        anac_file=args.anac_file,
        anac_anno=args.anac_anno,
        no_stop=args.no_stop,
    )

    for nome in da_eseguire:
        print(f"\n── {nome.upper()} ──")
        stato, esito = esegui_scraper(conn, nome, scrapers[nome], kwargs, tetto_s)
        if stato == "ok":
            risultati[nome] = esito
        elif stato == "interrotto":
            risultati[nome] = f"INTERROTTO dopo {tetto_s}s (+{esito['inseriti']} ins)"
        else:
            risultati[nome] = "ERRORE"
            falliti[nome] = esito.get("errore", "")

    if args.budget_ripasso > 0:
        ripasso = ripassa_transitori(conn, falliti, scrapers, kwargs, tetto_s, args.budget_ripasso)
        for nome, (stato, esito) in ripasso.items():
            if stato == "ok":
                risultati[nome] = esito
                del falliti[nome]
            elif stato == "interrotto":
                risultati[nome] = f"INTERROTTO al ripasso (+{esito['inseriti']} ins)"
                del falliti[nome]
    errori += len(falliti)

    if args.testo_atti > 0:
        esegui_testo_atti(conn, args.testo_atti)

    if not args.no_red_flags:
        print("\n── RED FLAGS ──")
        if args.llm_modello:
            print(
                f"  [LLM] Classificazione procedimenti sconosciuto con '{args.llm_modello}'"
                f" (max {args.llm_limite})…"
            )
        try:
            report = esegui_tutti(
                conn,
                modello_llm=args.llm_modello,
                llm_limite=args.llm_limite,
            )
            print(
                f"  frazionamento:  {report.frazionamento}\n"
                f"  concentrazione: {report.concentrazione}\n"
                f"  tempi anomali:  {report.tempi_anomali}\n"
                f"  revoche catena: {report.revoche_catena}\n"
                f"  riaperture:     {report.riapertura_dopo_revoca}\n"
                f"  totale flag:    {report.totale_flag}"
            )
        except Exception:
            print(traceback.format_exc(), file=sys.stderr)
            errori += 1

    print("\n── SUMMARY ──")
    for nome, esito in risultati.items():
        if isinstance(esito, dict):
            ins = esito.get("inseriti", 0)
            dup = esito.get("duplicati", 0)
            d0 = esito.get("data_min") or "?"
            d1 = esito.get("data_max") or "?"
            print(f"  {nome:15s}  +{ins:>4} ins  {dup:>4} dup  {d0} → {d1}")
        else:
            print(f"  {nome:15s}  {esito}")

    print("\n── COPERTURA DB ──")
    rows = conn.execute(
        """SELECT e.denominazione,
                  MIN(COALESCE(a.data_pub, a.data_atto)),
                  MAX(COALESCE(a.data_pub, a.data_atto)),
                  COUNT(*)
           FROM atti a JOIN enti e ON a.ente_id = e.id
           GROUP BY e.id ORDER BY e.denominazione"""
    ).fetchall()
    for r in rows:
        print(f"  {r[0]:<28s}  {r[3]:>5} atti  {r[1] or '?':>10} → {r[2] or '?'}")

    n_atti = conn.execute("SELECT COUNT(*) FROM atti").fetchone()[0]
    n_enti = conn.execute("SELECT COUNT(*) FROM enti").fetchone()[0]
    n_flags = conn.execute("SELECT COUNT(*) FROM red_flags").fetchone()[0]
    print(f"\n  DB: {n_enti} enti | {n_atti} atti | {n_flags} red flags")

    conn.close()
    return 1 if errori else 0


if __name__ == "__main__":
    sys.exit(main())
