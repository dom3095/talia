"""Tetto di tempo per singolo scraper nel run notturno (TAL-72).

Il run notturno è sequenziale: uno scraper che resta appeso a un host lento o
semi-morto (retry, timeout di socket, handshake SSL che non chiude) tiene in
ostaggio tutti quelli dopo di lui. Misurato il 01/09/2026: ~10 scraper su 266
facevano il 98% dei 53.011s del run, quattro dei quali per restituire **zero**
atti. I timeout per singola richiesta esistono già negli scraper; mancava un
tetto sulla *somma* delle richieste e dei retry di uno scraper.

Meccanismo: ``SIGALRM`` via ``signal.setitimer``. Il gestore solleva
:class:`TettoTempoSuperato`, che interrompe anche una ``recv`` bloccata o una
``time.sleep`` di backoff (PEP 475: se il gestore solleva, la syscall non viene
ritentata). Niente thread né sottoprocessi: lo scraper continua a usare la
stessa connessione SQLite dell'orchestratore, e gli atti già salvati restano —
``inserisci_atto`` committa atto per atto.

:class:`TettoTempoSuperato` deriva da ``BaseException`` e non da ``Exception``
apposta: gli scraper hanno blocchi ``except Exception`` (retry, fallback,
"salta questa pagina") che altrimenti la intercetterebbero e continuerebbero a
girare, cioè esattamente il comportamento che il tetto deve impedire. È la
stessa scelta di ``KeyboardInterrupt``.

Su piattaforme senza ``setitimer`` (Windows) o fuori dal thread principale il
tetto non è applicabile: il blocco gira senza limite, e
:func:`tetto_supportato` permette al chiamante di dirlo invece di fingere.
"""

from __future__ import annotations

import signal
import threading
import traceback
from collections.abc import Iterator
from contextlib import contextmanager

#: Tetto di default in secondi, scelto sulle durate misurate il 01/09/2026
#: (TAL-72): i 259 scraper fuori dai ~7 patologici sommavano ~9.200s, cioè
#: ~35s di media, e i più lenti tra quelli sani (Playwright di Agrigento, URBI
#: di Caccamo dopo TAL-68) stanno sotto i 3 minuti. 20 minuti lasciano un
#: margine di ~7x sui sani e chiudono il run entro poche ore anche se una
#: decina di host restano appesi: 9.200s + 10 x 1.200s ≈ 6h nel caso peggiore,
#: contro le 14,7h misurate.
TETTO_SCRAPER_DEFAULT_S = 1200

#: Marcatore con cui l'interruzione viene registrata in ``scraper_runs.errore``:
#: è il nome dell'eccezione, quindi compare sia nel messaggio scritto
#: dall'orchestratore sia in un eventuale traceback grezzo.
MARCATORE_ERRORE = "TettoTempoSuperato"


class TettoTempoSuperato(BaseException):  # noqa: N818 — nome di dominio, non "...Error"
    """Lo scraper ha superato il tetto di tempo assegnato.

    Deriva da ``BaseException``: vedi la docstring del modulo.
    """

    def __init__(self, secondi: float) -> None:
        super().__init__(f"interrotto dopo {secondi:g}s (tetto per scraper, TAL-72)")
        self.secondi = secondi


def tetto_supportato() -> bool:
    """Vero se il tetto può essere applicato in questo contesto."""
    return hasattr(signal, "setitimer") and threading.current_thread() is threading.main_thread()


@contextmanager
def tetto_tempo(secondi: float | None) -> Iterator[None]:
    """Esegue il blocco con un tetto di ``secondi``; ``None`` o ``<= 0`` = nessun tetto.

    Allo scadere solleva :class:`TettoTempoSuperato` nel punto in cui il blocco
    si trova. Il timer e il gestore precedente vengono sempre ripristinati,
    anche se il blocco esce con un'altra eccezione.
    """
    if not secondi or secondi <= 0 or not tetto_supportato():
        yield
        return

    def _scaduto(_signum, _frame):
        raise TettoTempoSuperato(secondi)

    precedente = signal.signal(signal.SIGALRM, _scaduto)
    signal.setitimer(signal.ITIMER_REAL, secondi)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, precedente)


def descrivi_interruzione(exc: TettoTempoSuperato) -> str:
    """Testo per ``scraper_runs.errore``: causa in testa, poi *dove* era fermo.

    Il frame più interno è l'informazione utile per la diagnosi (``recv`` di un
    socket, ``sleep`` di un retry, attesa Playwright): un traceback grezzo
    troncato a 500 caratteri conserverebbe invece i frame più esterni,
    cioè l'orchestratore.
    """
    riga = f"{MARCATORE_ERRORE}: {exc}"
    frames = traceback.extract_tb(exc.__traceback__)
    # Il frame del gestore del segnale non dice nulla: si mostra il chiamante.
    frames = [f for f in frames if f.name != "_scaduto"]
    if not frames:
        return riga
    dove = " ← ".join(
        f"{f.name} ({f.filename.rsplit('/', 1)[-1]}:{f.lineno})" for f in frames[-3:][::-1]
    )
    return f"{riga}\nfermo in: {dove}"


def e_interruzione_tetto(errore: str | None) -> bool:
    """Vero se ``scraper_runs.errore`` registra un'interruzione per tetto di tempo."""
    return bool(errore) and MARCATORE_ERRORE in errore
