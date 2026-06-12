"""Checklist deterministiche del Modulo 1 (vedi wiki/04).

L'import di questo package registra automaticamente tutti i check disponibili nel
registry di `base`, così `esegui_checklist` li trova senza configurazione.
"""

from . import (
    check1_base_giuridica,
    check2_termini,
    check5_avvio,
    check6_firmatari,
)
from .base import Check, EsitoCheck, check_registrati, esegui_checklist, registra

# Riferimenti agli import con effetto collaterale (registrazione dei check).
_MODULI_CHECK = (
    check1_base_giuridica,
    check2_termini,
    check5_avvio,
    check6_firmatari,
)

__all__ = [
    "Check",
    "EsitoCheck",
    "check_registrati",
    "esegui_checklist",
    "registra",
]
