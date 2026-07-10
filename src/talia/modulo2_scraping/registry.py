"""Modulo 2 — Registro: configurazione centralizzata degli scraper comuni."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EntryRegistro:
    """Una riga del registro scraper: configurazione di un comune/ente da scrapare."""

    slug: str
    denominazione: str
    codice_istat: str
    modulo: str
    piattaforma_tecnica: str
    base_url: str | None = None
    stato: str = "attivo"
    provincia: str | None = None
    qs_base: str | None = None
    ente_mittente: str | None = None
    skip_ssl: bool = False
    note: str = ""

    def __post_init__(self):
        """Valida i campi al momento della costruzione."""
        # Converti skip_ssl se arriva come stringa
        if isinstance(self.skip_ssl, str):
            object.__setattr__(self, "skip_ssl", self.skip_ssl.lower() in ("true", "1", "yes"))


def _percorso_default() -> Path:
    """Risolve il path assoluto di data/registro_scraper.csv dalla repo root."""
    return Path(__file__).resolve().parents[3] / "data" / "registro_scraper.csv"


def carica_registro(percorso: str | Path | None = None) -> list[EntryRegistro]:
    """Carica il registro degli scraper dal CSV.

    Args:
        percorso: path al CSV. Se None, usa il default data/registro_scraper.csv.

    Raises:
        ValueError: Se il registro è malformato (slug duplicato, modulo ignoto, ecc.)
    """
    if percorso is None:
        percorso = _percorso_default()
    else:
        percorso = Path(percorso)

    try:
        with open(percorso, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            entries = []
            for row in reader:
                entries.append(_row_to_entry(row))
    except FileNotFoundError as e:
        raise ValueError(f"Registro non trovato: {percorso}") from e

    problemi = valida_registro(entries)
    if problemi:
        raise ValueError("Registro malformato:\n" + "\n".join(f"  - {p}" for p in problemi))

    return entries


def _row_to_entry(row: dict) -> EntryRegistro:
    """Converte una riga CSV (dict) in EntryRegistro, coercendo i tipi."""
    return EntryRegistro(
        slug=row["slug"],
        denominazione=row["denominazione"],
        codice_istat=row["codice_istat"],
        modulo=row["modulo"],
        piattaforma_tecnica=row["piattaforma_tecnica"],
        base_url=row.get("base_url") or None,
        stato=row.get("stato") or "attivo",
        provincia=row.get("provincia") or None,
        qs_base=row.get("qs_base") or None,
        ente_mittente=row.get("ente_mittente") or None,
        skip_ssl=row.get("skip_ssl", "").lower() in ("true", "1", "yes"),
        note=row.get("note", ""),
    )


def valida_registro(entries: list[EntryRegistro]) -> list[str]:
    """Valida il registro, ritorna lista di problemi (non solleva).

    Checks:
    - slug duplicato → errore
    - modulo non riconosciuto → errore
    - codice_istat non 6 cifre → errore
    - base_url mancante su stato attivo/escluso_default/bloccato → errore
    - qs_base/ente_mittente mancanti su modulo urbi/catania con stato
      attivo/escluso_default/bloccato → errore
    - qs_base/ente_mittente valorizzati su modulo non-urbi/catania → warning
    - skip_ssl=true su modulo non-halley → warning

    ``modulo="pending"`` è un valore pseudo-modulo (nessuno scraper reale)
    per i comuni censiti ma non ancora implementati: righe con questo modulo
    hanno sempre ``stato="pending"`` (escluse da ``filtra_eseguibili`` prima
    di raggiungere `costruisci_scrapers`, quindi non serve una factory).
    """
    problemi = []
    slug_visti = set()
    moduli_validi = {
        "jcitygov",
        "portalepa",
        "halley",
        "urbi",
        "hspromila",
        "palermo",
        "catania",
        "trapani",
        "siracusa",
        "ribera",
        "agrigento",
        "anac",
        "pending",
    }

    for entry in entries:
        # Slug duplicato
        if entry.slug in slug_visti:
            problemi.append(f"slug duplicato: {entry.slug!r}")
        slug_visti.add(entry.slug)

        # Modulo ignoto
        if entry.modulo not in moduli_validi:
            problemi.append(f"modulo sconosciuto per slug {entry.slug!r}: {entry.modulo!r}")

        # Codice ISTAT malformato (salvo ANAC che non ha ente)
        if entry.codice_istat and len(entry.codice_istat) != 6:
            problemi.append(f"codice_istat non 6 cifre per {entry.slug!r}: {entry.codice_istat!r}")
        elif not entry.codice_istat and entry.modulo != "anac":
            problemi.append(f"codice_istat mancante per {entry.slug!r} (modulo={entry.modulo!r})")

        # base_url mancante su stato attivo/escluso_default/bloccato (salvo ANAC)
        if (
            entry.stato in ("attivo", "escluso_default", "bloccato")
            and not entry.base_url
            and entry.modulo != "anac"
        ):
            problemi.append(f"base_url mancante per slug {entry.slug!r} con stato={entry.stato!r}")

        # qs_base/ente_mittente mancanti su urbi/catania (gap trovato in code
        # review: senza questo controllo una riga catania/urbi con qs_base
        # vuoto passa la validazione e produce un URL con "?None" a runtime)
        if entry.modulo in ("urbi", "catania") and entry.stato in (
            "attivo",
            "escluso_default",
            "bloccato",
        ):
            if not entry.qs_base:
                problemi.append(
                    f"qs_base mancante per slug {entry.slug!r} "
                    f"(modulo={entry.modulo!r}, stato={entry.stato!r})"
                )
            if not entry.ente_mittente:
                problemi.append(
                    f"ente_mittente mancante per slug {entry.slug!r} "
                    f"(modulo={entry.modulo!r}, stato={entry.stato!r})"
                )

        # qs_base/ente_mittente fuori posto
        if entry.qs_base and entry.modulo not in ("urbi", "catania"):
            problemi.append(
                f"qs_base valorizzato su modulo non-urbi/catania per {entry.slug!r} "
                f"(modulo={entry.modulo!r})"
            )
        if entry.ente_mittente and entry.modulo not in ("urbi", "catania"):
            problemi.append(
                f"ente_mittente valorizzato su modulo non-urbi/catania per {entry.slug!r} "
                f"(modulo={entry.modulo!r})"
            )

        # skip_ssl fuori posto
        if entry.skip_ssl and entry.modulo != "halley":
            problemi.append(
                f"skip_ssl=true su modulo non-halley per {entry.slug!r} (modulo={entry.modulo!r})"
            )

    return problemi


def filtra_eseguibili(entries: list[EntryRegistro]) -> list[EntryRegistro]:
    """Filtra le entry eseguibili (stato in {attivo, escluso_default})."""
    return [e for e in entries if e.stato in ("attivo", "escluso_default")]


def entries_default(entries: list[EntryRegistro]) -> list[str]:
    """Ritorna la lista di slug da eseguire per default (stato == attivo)."""
    return [e.slug for e in entries if e.stato == "attivo"]


def sincronizza_enti_da_registro(conn, entries: list[EntryRegistro]) -> int:
    """Upsert in blocco di tutti gli enti del registro in `enti`.

    Indipendente da quali scraper vengono eseguiti nel run corrente: tiene
    `enti` sempre allineata al registro (inclusi bloccato/pending), così è
    interrogabile senza rileggere il CSV (es. ``SELECT * FROM enti WHERE
    stato_scraper='bloccato'``). ANAC e righe senza codice_istat sono escluse
    (non hanno un ente associato). Ritorna il numero di enti sincronizzati.
    """
    from talia.modulo2_scraping.db import EnteMetadato, upsert_ente

    n = 0
    for entry in entries:
        if entry.modulo == "anac" or not entry.codice_istat:
            continue
        upsert_ente(
            conn,
            EnteMetadato(
                denominazione=entry.denominazione,
                codice_istat=entry.codice_istat,
                provincia=entry.provincia,
                modulo=entry.modulo,
                url_base=entry.base_url,
                stato_scraper=entry.stato,
            ),
        )
        n += 1
    return n
