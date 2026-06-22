"""Red flags batch deterministici (TAL-23).

Modulo a sé stante: legge dal DB atti già raccolti, applica regole SQL+Python,
scrive i risultati nella tabella ``red_flags``.

Ogni regola è in un file dedicato. Il ``runner`` le esegue tutte in sequenza.

Struttura:
    frazionamento  — affidamenti diretti ripetuti sotto soglia (art. 50 D.lgs. 36/2023)
    concentrazione — eccessiva concentrazione su affidamenti diretti vs gare
    tempi_anomali  — finestre di pubblicazione bandi troppo brevi (art. 71 D.lgs. 36/2023)
    runner         — esegui_tutti(): orchestrazione + salvataggio su DB
"""

from .concentrazione import rileva_concentrazione
from .frazionamento import rileva_frazionamento
from .runner import esegui_tutti
from .tempi_anomali import rileva_tempi_anomali

__all__ = [
    "esegui_tutti",
    "rileva_frazionamento",
    "rileva_concentrazione",
    "rileva_tempi_anomali",
]
