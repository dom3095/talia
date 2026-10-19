"""Testo degli atti nuovi, estratto ogni notte finché il link è vivo (TAL-77).

Fino a TAL-77 nessun atto aveva `testo_estratto` (0 su 395.966): red flag,
catene ed estrazione del CIG lavoravano sul solo `oggetto` della pagina-lista
(in media 205 caratteri). E l'Albo Pretorio ritira l'atto dopo 15-30 giorni,
quindi il testo o si prende mentre è pubblicato o non si prende più.

Scope deliberatamente stretto:

- **solo jCityGov** (`fonte_scraper='jcitygov'`), l'unica piattaforma di cui
  sappiamo già leggere gli allegati (`pdf_download.trova_allegati`, TAL-47) —
  ~240 atti nuovi al giorno, tutti sulla stessa infrastruttura del fornitore;
- **solo atti recenti** (`data_accesso` negli ultimi :data:`GIORNI_DEFAULT`
  giorni): quelli più vecchi hanno spesso il link già morto;
- **solo testo nativo**, niente OCR: Tesseract su centinaia di scansioni
  allungherebbe il run notturno di ore (TAL-72). Le scansioni restano con
  testo vuoto e si possono riprendere a mano con `engine.pdf_text`;
- **il PDF non si conserva**: si estrae il testo in una directory temporanea e
  si salvano solo testo e `hash_sha256` (spazio disco e dati nominativi);
- **solo i tipi d'atto che servono ai red flag** (determine, delibere, bandi,
  avvisi, contratti, liquidazioni): pubblicazioni di matrimonio, notifiche e
  depositi del messo, ordinanze-ingiunzione e permessi di costruire sono testi
  pieni di dati di privati cittadini che nessuna regola usa. Minimizzazione,
  principio 4 di `CLAUDE.md`.

Molti albi allegano lo stesso atto due volte, firmato (`.pdf.p7m`, busta
CAdES) e in chiaro: si prende il primo allegato che è davvero un PDF (magic
bytes `%PDF`), fino a :data:`MAX_ALLEGATI_PROVATI` per atto.

Stato per atto: `testo_estratto IS NULL` = mai tentato; `''` = tentato senza
risultato (nessun PDF in chiaro, scansione, errore) — non si ritenta ogni
notte lo stesso atto.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from talia.engine.entita import trova_cig

from .pdf_download import _build_opener, _diversifica_per_ente, scarica_pdf_allegato, trova_allegati

_logger = logging.getLogger(__name__)

#: Fonti supportate: quelle di cui `trova_allegati` sa leggere la pagina di dettaglio.
FONTI_SUPPORTATE = ("jcitygov",)

#: Atti per run. ~240 atti jCityGov nuovi al giorno: 400 lascia margine per
#: recuperare un arretrato di qualche giorno senza diventare un backfill.
LIMITE_DEFAULT = 400

#: Finestra in giorni su `data_accesso`. Oltre, il link d'albo è spesso già scaduto.
GIORNI_DEFAULT = 20

#: Allegati provati per atto prima di arrendersi (il `.p7m` viene di solito prima del PDF).
MAX_ALLEGATI_PROVATI = 3

#: Tetto alla lunghezza del testo salvato: un atto reale sta in poche decine di
#: migliaia di caratteri; oltre è quasi sempre un allegato tecnico (elenchi, tabelle).
MAX_CARATTERI = 200_000


#: Tipi d'atto (su `tipo` + `oggetto`) di cui serve il testo.
_RE_TIPI_UTILI = re.compile(
    r"determin|delib|band[oi]|\bgar[ae]\b|avvis|contratt|affidament|liquidaz|aggiudicaz",
    re.IGNORECASE,
)
#: Esclusi anche se rientrano sopra: testi con dati di privati, inutili alle regole.
_RE_TIPI_ESCLUSI = re.compile(
    r"matrimon|\bmess[oi]\b|deposit|notific|anagraf|cittadinanz|stato civile"
    r"|permess[oi] di costruire|ordinanz|ingiunzion",
    re.IGNORECASE,
)


def tipo_utile(tipo: str | None, oggetto: str | None) -> bool:
    """Vero se il testo dell'atto serve alle regole e non è un atto su privati."""
    testo = f"{tipo or ''} {oggetto or ''}"
    return bool(_RE_TIPI_UTILI.search(testo)) and not _RE_TIPI_ESCLUSI.search(testo)


@dataclass
class EsitoTesto:
    tentati: int = 0
    con_testo: int = 0
    senza_testo: int = 0
    cig_aggiunti: int = 0

    def __str__(self) -> str:
        return (
            f"{self.tentati} atti: {self.con_testo} con testo, {self.senza_testo} senza"
            f" (scansione, solo .p7m o errore); CIG ricavati dal testo: {self.cig_aggiunti}"
        )


def atti_da_estrarre(
    conn: sqlite3.Connection, limite: int = LIMITE_DEFAULT, giorni: int = GIORNI_DEFAULT
) -> list[int]:
    """Id degli atti candidati, alternati tra enti (round-robin)."""
    segnaposto = ",".join("?" * len(FONTI_SUPPORTATE))
    rows = conn.execute(
        f"""
        SELECT id, ente_id, tipo, oggetto FROM atti
        WHERE  fonte_scraper IN ({segnaposto})
          AND  testo_estratto IS NULL
          AND  url_fonte IS NOT NULL
          AND  data_accesso >= date('now', ?)
        ORDER  BY data_accesso DESC, id DESC
        """,
        (*FONTI_SUPPORTATE, f"-{giorni} days"),
    ).fetchall()
    utili = [(r[0], r[1]) for r in rows if tipo_utile(r[2], r[3])]
    return _diversifica_per_ente(utili, limite)


def testo_pdf_nativo(percorso: Path) -> str:
    """Testo nativo di un PDF, pagine separate da newline. Nessun OCR."""
    import pdfplumber

    with pdfplumber.open(percorso) as pdf:
        return "\n".join((pagina.extract_text() or "") for pagina in pdf.pages)


def cig_univoco(testo: str) -> str | None:
    """Il CIG proprio dell'atto, solo se nel testo ce n'è **uno solo**.

    Una determina può citare più CIG (altri contratti, lotti, impegni
    precedenti): sceglierne uno a caso collegherebbe l'atto al procedimento
    sbagliato nella strategia CIG della catena, che è un match esatto e non
    viene più rimesso in discussione.
    """
    propri = {m.group(1).upper() for m, e_padre in trova_cig(testo) if not e_padre}
    return propri.pop() if len(propri) == 1 else None


def _primo_pdf(url_fonte: str, opener, cartella: Path, delay: float) -> tuple[str, str] | None:
    """``(testo, hash)`` del primo allegato che è un PDF vero, oppure ``None``."""
    allegati = [a for a in trova_allegati(url_fonte, opener=opener) if a.url_download]
    for i, allegato in enumerate(allegati[:MAX_ALLEGATI_PROVATI]):
        time.sleep(delay)
        risultato = scarica_pdf_allegato(
            allegato.url_download, cartella / f"{i}_{allegato.chiave_allegato}", opener=opener
        )
        if risultato is None:
            continue
        percorso, _nome, hash_sha = risultato
        try:
            if percorso.suffix != ".pdf":
                continue
            return testo_pdf_nativo(percorso), hash_sha
        finally:
            percorso.unlink(missing_ok=True)
    return None


def estrai_testo_atti(
    conn: sqlite3.Connection,
    *,
    limite: int = LIMITE_DEFAULT,
    giorni: int = GIORNI_DEFAULT,
    opener=None,
    delay: float = 1.0,
    estrai=_primo_pdf,
) -> EsitoTesto:
    """Scarica, estrae e salva il testo degli atti candidati. Commit per atto.

    Commit per atto: il run notturno lo esegue sotto un tetto di tempo
    (`tetto_tempo`), e un'interruzione non deve buttare il lavoro già fatto.
    """
    opener = opener or _build_opener()
    esito = EsitoTesto()
    ids = atti_da_estrarre(conn, limite=limite, giorni=giorni)
    _logger.info(f"Testo atti: {len(ids)} candidati")

    with tempfile.TemporaryDirectory(prefix="talia_testo_") as tmp:
        cartella = Path(tmp)
        for atto_id in ids:
            url_fonte, cig = conn.execute(
                "SELECT url_fonte, cig FROM atti WHERE id = ?", (atto_id,)
            ).fetchone()
            esito.tentati += 1
            try:
                risultato = estrai(url_fonte, opener, cartella, delay)
            except Exception as exc:  # un atto rotto non deve fermare gli altri
                _logger.warning(f"Atto {atto_id}: estrazione testo fallita: {exc}")
                risultato = None

            testo, hash_sha = risultato if risultato else ("", None)
            testo = testo.strip()[:MAX_CARATTERI]
            if testo:
                esito.con_testo += 1
            else:
                esito.senza_testo += 1

            nuovo_cig = cig_univoco(testo) if testo and not cig else None
            if nuovo_cig:
                esito.cig_aggiunti += 1
            conn.execute(
                """
                UPDATE atti
                SET    testo_estratto = ?,
                       hash_sha256    = COALESCE(?, hash_sha256),
                       cig            = COALESCE(cig, ?)
                WHERE  id = ?
                """,
                (testo, hash_sha, nuovo_cig, atto_id),
            )
            conn.commit()

    if esito.tentati and not esito.con_testo:
        _logger.warning(f"Testo atti: nessun testo estratto su {esito.tentati} atti")
    return esito
