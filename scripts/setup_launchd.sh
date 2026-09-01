#!/bin/bash
# Installa/rimuove l'agente launchd che lancia il run giornaliero TALIA (TAL-66).
#
# Perché launchd e non GitHub Actions: il WAF Akamai di portalepa blocca gli IP
# dei runner GitHub (87% di fallimenti misurati il 2026-07-12), e il vincolo di
# budget zero esclude una VM. Lo scraping resta quindi sulla macchina locale —
# questa è la parte che lo rende continuo invece che manuale.
#
# Perché StartCalendarInterval e non StartInterval: se il Mac è spento o
# addormentato all'ora prevista, launchd esegue il job appena la macchina torna
# disponibile (un run "saltato" viene recuperato). Con StartInterval il
# conteggio riparte da zero ad ogni avvio e l'ora è imprevedibile.
#
# Uso:
#   ./scripts/setup_launchd.sh                 # installa (default 03:30)
#   ./scripts/setup_launchd.sh --ora 4 --minuto 15
#   ./scripts/setup_launchd.sh --status
#   ./scripts/setup_launchd.sh --uninstall

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

LABEL="com.talia.scrapers"
PLIST_FILE="$HOME/Library/LaunchAgents/$LABEL.plist"
ORA=3
MINUTO=30
AZIONE="install"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --ora) ORA="$2"; shift 2 ;;
        --minuto) MINUTO="$2"; shift 2 ;;
        --uninstall) AZIONE="uninstall"; shift ;;
        --status) AZIONE="status"; shift ;;
        *) echo "Uso: $0 [--ora H] [--minuto M] [--status] [--uninstall]"; exit 1 ;;
    esac
done

UID_CORRENTE="$(id -u)"

case "$AZIONE" in
uninstall)
    launchctl bootout "gui/$UID_CORRENTE/$LABEL" 2>/dev/null || true
    rm -f "$PLIST_FILE"
    echo "Agente rimosso: $LABEL"
    exit 0
    ;;
status)
    if launchctl print "gui/$UID_CORRENTE/$LABEL" >/dev/null 2>&1; then
        launchctl print "gui/$UID_CORRENTE/$LABEL" | grep -E "state|last exit code|runs =" || true
        echo
        echo "Ultimo report: $REPO_ROOT/logs/ultimo_report.md"
        ls -1t "$REPO_ROOT"/logs/run_daily_*.log 2>/dev/null | head -3 || true
    else
        echo "Agente non installato ($LABEL)."
    fi
    exit 0
    ;;
esac

LOG_DIR="$REPO_ROOT/logs"
mkdir -p "$LOG_DIR" "$(dirname "$PLIST_FILE")"

cat > "$PLIST_FILE" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>

  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$REPO_ROOT/scripts/run_daily.sh</string>
  </array>

  <key>WorkingDirectory</key>
  <string>$REPO_ROOT</string>

  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>$ORA</integer>
    <key>Minute</key><integer>$MINUTO</integer>
  </dict>

  <!-- Il run dura ~4-5h su 260 scraper: niente KeepAlive, altrimenti launchd
       lo rilancerebbe in loop appena termina. -->
  <key>KeepAlive</key>
  <false/>
  <key>RunAtLoad</key>
  <false/>

  <!-- Priorità bassa: il run non deve rendere il Mac inutilizzabile se parte
       mentre qualcuno ci sta lavorando (recupero di un run saltato). -->
  <key>Nice</key>
  <integer>5</integer>
  <key>ProcessType</key>
  <string>Background</string>

  <key>StandardOutPath</key>
  <string>$LOG_DIR/launchd.log</string>
  <key>StandardErrorPath</key>
  <string>$LOG_DIR/launchd_error.log</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$UID_CORRENTE/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$UID_CORRENTE" "$PLIST_FILE"

printf 'Agente installato: %s\n' "$LABEL"
printf '  Orario:  %02d:%02d (ora locale, ogni giorno)\n' "$ORA" "$MINUTO"
printf '  Plist:   %s\n' "$PLIST_FILE"
printf '  Log:     %s/run_daily_*.log\n' "$LOG_DIR"
echo
echo "Se il Mac è spento all'orario previsto, launchd recupera il run al riavvio."
echo "Lancio manuale immediato:  launchctl kickstart -k gui/$UID_CORRENTE/$LABEL"
echo "Stato:                     ./scripts/setup_launchd.sh --status"
echo "Disinstalla:               ./scripts/setup_launchd.sh --uninstall"
