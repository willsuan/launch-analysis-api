#!/usr/bin/env bash
# Run the LL2 ingest unattended in a tmux session, with auto-restart.
# No-op if already complete or already running. Idempotent on re-run.
#
#   bash scripts/auto_ingest.sh           # start or report status
#   bash scripts/auto_ingest.sh status
#   bash scripts/auto_ingest.sh stop
#   bash scripts/auto_ingest.sh attach    # ctrl-b d to detach
#   bash scripts/auto_ingest.sh logs      # tail -f ingest.log

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SESSION="ingest"
DATA_FILE="$REPO_DIR/data/launches.json"
PROGRESS_FILE="$REPO_DIR/data/.ingest_progress"
LOG_FILE="$REPO_DIR/ingest.log"

bold()  { printf '\033[1m%s\033[0m\n' "$*"; }
green() { printf '\033[1;32m%s\033[0m\n' "$*"; }
blue()  { printf '\033[1;34m%s\033[0m\n' "$*"; }
warn()  { printf '\033[1;33m%s\033[0m\n' "$*"; }

is_done() {
    [[ -f "$PROGRESS_FILE" ]] && [[ "$(cat "$PROGRESS_FILE")" == "DONE" ]]
}

count_records() {
    if [[ -f "$DATA_FILE" ]]; then
        python3 -c "import json; print(len(json.load(open('$DATA_FILE'))))" 2>/dev/null || echo "0"
    else
        echo "0"
    fi
}

is_running() {
    TERM="${TERM:-xterm-256color}" tmux has-session -t "$SESSION" 2>/dev/null
}

print_status() {
    bold "ingest status"
    if is_done; then
        green "complete"
    elif is_running; then
        blue "running in tmux session '$SESSION'"
    else
        warn "not running"
    fi
    echo "  records on disk: $(count_records)"
    echo "  data file:       $DATA_FILE"
    echo "  log file:        $LOG_FILE"
    if [[ -f "$LOG_FILE" ]]; then
        echo
        echo "last 5 log lines:"
        tail -n 5 "$LOG_FILE" | sed 's/^/  /'
    fi
}

cmd_start() {
    if is_done; then
        green "already complete, $(count_records) records in $DATA_FILE"
        exit 0
    fi
    if is_running; then
        blue "ingest already running in tmux session '$SESSION'"
        print_status
        echo
        echo "re-attach: bash scripts/auto_ingest.sh attach"
        echo "tail logs: bash scripts/auto_ingest.sh logs"
        exit 0
    fi

    bold "starting ingest in tmux session '$SESSION'"
    cd "$REPO_DIR"

    # Inner shell does: cd, activate venv, loop the ingest until DONE,
    # tee to ingest.log so the log is readable from outside tmux.
    local inner
    inner=$(cat <<'INNER'
cd "$HOME/launch-analysis-api"
source .venv/bin/activate
echo "[$(date)] starting ingest" | tee -a ingest.log

while true; do
    PYTHONPATH=. DATA_FILE=data/launches.json python -m src.ingest 2>&1 | tee -a ingest.log
    if [ -f data/.ingest_progress ] && [ "$(cat data/.ingest_progress)" = "DONE" ]; then
        echo "[$(date)] ingest complete" | tee -a ingest.log
        break
    fi
    echo "[$(date)] ingest exited without DONE marker, restarting in 30s" | tee -a ingest.log
    sleep 30
done

# linger so an attach after completion still shows the result
sleep 30
INNER
)

    TERM="${TERM:-xterm-256color}" tmux new-session -d -s "$SESSION" "bash -lc '$inner'"
    sleep 1
    green "ingest launched"
    echo
    print_status
    echo
    echo "useful commands:"
    echo "  bash scripts/auto_ingest.sh status"
    echo "  bash scripts/auto_ingest.sh logs"
    echo "  bash scripts/auto_ingest.sh attach   # ctrl-b d to detach"
    echo "  bash scripts/auto_ingest.sh stop"
}

cmd_stop() {
    if is_running; then
        TERM="${TERM:-xterm-256color}" tmux kill-session -t "$SESSION"
        warn "killed tmux session '$SESSION'"
    else
        warn "nothing to stop, '$SESSION' isn't running"
    fi
}

cmd_attach() {
    if ! is_running; then
        warn "no '$SESSION' session, start it first: bash scripts/auto_ingest.sh"
        exit 1
    fi
    exec env TERM="${TERM:-xterm-256color}" tmux attach -t "$SESSION"
}

cmd_logs() {
    if [[ ! -f "$LOG_FILE" ]]; then
        warn "no log file yet at $LOG_FILE"
        exit 1
    fi
    echo "tailing $LOG_FILE (ctrl-c to stop)"
    exec tail -f "$LOG_FILE"
}

case "${1:-start}" in
    start)  cmd_start ;;
    status) print_status ;;
    stop)   cmd_stop ;;
    attach) cmd_attach ;;
    logs)   cmd_logs ;;
    *)
        echo "Usage: $0 {start|status|stop|attach|logs}"
        exit 1
        ;;
esac
