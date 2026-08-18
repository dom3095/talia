#!/bin/bash
# Run giornaliero degli scraper TALIA (TAL-66).
#
# Pensato per essere lanciato da launchd (vedi scripts/setup_launchd.sh) ma
# eseguibile anche a mano. Fa quattro cose che il cron nudo non farebbe:
#
#   1. lock:      un run completo dura ~4-5h su 260 scraper — due run
#                 sovrapposti si contenderebbero lo stesso SQLite.
#   2. caffeinate: impedisce al Mac di addormentarsi a metà run.
#   3. backup:    copia del DB prima di scrivere (il DB non è in git).
#   4. report:    riepilogo dei fallimenti + notifica macOS se qualcosa è rotto,
#                 altrimenti un run fallito passa inosservato per giorni.
#
# Uso:
#   ./scripts/run_daily.sh                       # run completo
#   ./scripts/run_daily.sh --max-pagine 5        # argomenti passati a run_scrapers.py
#   TALIA_DB=/altro/talia.db ./scripts/run_daily.sh
#
# Exit code: 0 tutto ok, 1 problemi rilevati (run falliti/muti), 2 lock occupato.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT" || exit 2

DB_PATH="${TALIA_DB:-$REPO_ROOT/talia.db}"
LOG_DIR="$REPO_ROOT/logs"
BACKUP_DIR="${TALIA_BACKUP_DIR:-$REPO_ROOT/backups}"
LOCK_DIR="$REPO_ROOT/.run_daily.lock"
STAMP="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$LOG_DIR/run_daily_$STAMP.log"
REPORT_FILE="$LOG_DIR/ultimo_report.md"

# Scraper `escluso_default` da includere comunque nel run notturno (vedi sotto).
# Svuotabile con TALIA_EXTRA_SCRAPERS="" se Playwright non è installato.
EXTRA_SCRAPERS="${TALIA_EXTRA_SCRAPERS-agrigento pachino barrafranca}"

# Quanti log e backup tenere (il DB reale è ~150 MB: senza rotazione il disco
# si riempie in fretta).
MAX_LOG=30
MAX_BACKUP=7

mkdir -p "$LOG_DIR" "$BACKUP_DIR"

# --- Lock -------------------------------------------------------------------
# `mkdir` è atomico anche su filesystem di rete; il PID dentro permette di
# riconoscere un lock orfano lasciato da un run ucciso a metà.
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    VECCHIO_PID="$(cat "$LOCK_DIR/pid" 2>/dev/null || echo "")"
    if [ -n "$VECCHIO_PID" ] && kill -0 "$VECCHIO_PID" 2>/dev/null; then
        echo "[$(date -Iseconds)] Run già in corso (PID $VECCHIO_PID) — esco." >&2
        exit 2
    fi
    echo "[$(date -Iseconds)] Lock orfano (PID '$VECCHIO_PID' non attivo) — lo rimuovo." >&2
    rm -rf "$LOCK_DIR"
    mkdir "$LOCK_DIR" || exit 2
fi
echo $$ > "$LOCK_DIR/pid"
trap 'rm -rf "$LOCK_DIR"' EXIT

# --- Python -----------------------------------------------------------------
# launchd non eredita il PATH della shell interattiva: il venv va risolto qui.
if [ -x "$REPO_ROOT/.venv/bin/python" ]; then
    PYTHON="$REPO_ROOT/.venv/bin/python"
elif [ -n "${VIRTUAL_ENV:-}" ] && [ -x "$VIRTUAL_ENV/bin/python" ]; then
    PYTHON="$VIRTUAL_ENV/bin/python"
else
    PYTHON="$(command -v python3 || command -v python)"
fi

# Senza questo, stdout di Python finisce in un buffer da 8 KB perché è
# rediretto su una pipe (`| tee`): su un run da 4-5h il log resterebbe muto
# per decine di minuti e sarebbe impossibile capire a che punto è.
export PYTHONUNBUFFERED=1

notifica() {
    # Notifica macOS best-effort: se osascript non c'è (o gira senza sessione
    # grafica) il run non deve fallire per questo.
    local titolo="$1" messaggio="$2"
    command -v osascript >/dev/null 2>&1 || return 0
    osascript -e "display notification \"${messaggio//\"/\\\"}\" with title \"${titolo//\"/\\\"}\"" \
        >/dev/null 2>&1 || true
}

{
    echo "=== TALIA run giornaliero — $(date -Iseconds) ==="
    echo "Repo:   $REPO_ROOT"
    echo "DB:     $DB_PATH"
    echo "Python: $PYTHON"
    echo

    # --- Backup del DB ------------------------------------------------------
    if [ -f "$DB_PATH" ]; then
        BACKUP_FILE="$BACKUP_DIR/talia.db.$(date +%Y%m%d)"
        # `.backup` di sqlite3 è consistente anche con il DB aperto in WAL,
        # a differenza di `cp` (che può cogliere un WAL a metà checkpoint).
        if command -v sqlite3 >/dev/null 2>&1; then
            sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'" && echo "Backup: $BACKUP_FILE"
        else
            cp "$DB_PATH" "$BACKUP_FILE" && echo "Backup (cp): $BACKUP_FILE"
        fi
    fi

    # --- Scraping -----------------------------------------------------------
    # Agrigento (capoluogo), Pachino e Barrafranca sono `escluso_default` nel
    # registro perché richiedono Playwright ed erano lenti per un run manuale.
    # In un run notturno ~3 min a testa sono irrilevanti, mentre escluderli
    # significherebbe perdere per sempre i loro atti quando escono dalla
    # finestra di pubblicazione dell'albo — lo stesso problema che questo run
    # esiste per risolvere. `anac` resta fuori: richiede `--anac-file`.
    echo
    echo "--- run_scrapers.py ---"
    TALIA_DB="$DB_PATH" caffeinate -i "$PYTHON" scripts/run_scrapers.py \
        ${EXTRA_SCRAPERS:+--extra-scrapers $EXTRA_SCRAPERS} "$@"
    ESITO_SCRAPING=$?
    echo "run_scrapers.py exit=$ESITO_SCRAPING"

    # --- Report -------------------------------------------------------------
    echo
    echo "--- report_run.py ---"
    # Gli stessi extra passati al runner, altrimenti il report li considererebbe
    # "non previsti" e non ne segnalerebbe mai i fallimenti.
    TALIA_DB="$DB_PATH" "$PYTHON" scripts/report_run.py --db "$DB_PATH" \
        --output "$REPORT_FILE" ${EXTRA_SCRAPERS:+--extra-scrapers $EXTRA_SCRAPERS}
    ESITO_REPORT=$?

    # --- Rotazione ----------------------------------------------------------
    ls -1t "$LOG_DIR"/run_daily_*.log 2>/dev/null | tail -n +$((MAX_LOG + 1)) | while read -r f; do
        rm -f "$f"
    done
    ls -1t "$BACKUP_DIR"/talia.db.* 2>/dev/null | tail -n +$((MAX_BACKUP + 1)) | while read -r f; do
        rm -f "$f"
    done

    echo
    echo "=== Fine — $(date -Iseconds) (scraping=$ESITO_SCRAPING report=$ESITO_REPORT) ==="
    exit $((ESITO_SCRAPING != 0 || ESITO_REPORT != 0))
} 2>&1 | tee -a "$LOG_FILE"

ESITO=${PIPESTATUS[0]}
if [ "$ESITO" -ne 0 ]; then
    notifica "TALIA — run con problemi" "Dettagli: logs/ultimo_report.md"
fi
exit "$ESITO"
