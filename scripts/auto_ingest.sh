#!/usr/bin/env bash
# auto_ingest.sh — fully unattended ingest runner.
#
# What it does:
#   - If the dataset is already complete, exits immediately.
#   - Otherwise launches the ingest inside a tmux session named "ingest".
#   - Inside tmux, runs the ingest in a restart loop so a transient crash
#     (network blip, OOM, anything other than DONE) automatically respawns it.
#   - Mirrors all output to ingest.log for easy `tail -f` from outside tmux.
#   - Idempotent: re-running while it's already going just prints status.
#
# Usage:
#   bash scripts/auto_ingest.sh         # start (or report status if already running)
#   bash scripts/auto_ingest.sh status  # just print status
#   bash scripts/auto_ingest.sh stop    # kill the running ingest
#   bash scripts/auto_ingest.sh attach  # attach to the live tmux session
#   bash scripts/auto_ingest.sh logs    # tail -f ingest.log

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
    bold "=== Artemis ingest status ==="
    if is_done; then
        green "✔ Ingest complete."
    elif is_running; then
        blue "⟳ Ingest is RUNNING in tmux session '$SESSION'."
    else
        warn "✗ Ingest is NOT running."
    fi
    echo "  Records on disk: $(count_records)"
    echo "  Data file:       $DATA_FILE"
    echo "  Log file:        $LOG_FILE"
    if [[ -f "$LOG_FILE" ]]; then
        echo
        bold "Last 5 log lines:"
        tail -n 5 "$LOG_FILE" | sed 's/^/  /'
    fi
}

cmd_start() {
    if is_done; then
        green "✔ Already complete. $(count_records) records in $DATA_FILE."
        exit 0
    fi
    if is_running; then
        blue "⟳ Ingest already running in tmux session '$SESSION'."
        print_status
        echo
        echo "Re-attach: bash scripts/auto_ingest.sh attach"
        echo "Tail logs: bash scripts/auto_ingest.sh logs"
        exit 0
    fi

    bold "Starting ingest in tmux session '$SESSION'..."
    cd "$REPO_DIR"

    # The inner command:
    #   - cd into repo
    #   - activate venv
    #   - run ingest in a restart loop until DONE
    #   - tee output into ingest.log so we can tail it from outside tmux
    #   - on completion, print a banner and keep the pane open briefly
    local inner
    inner=$(cat <<'INNER'
cd "$HOME/launch-analysis-api"
source .venv/bin/activate
echo "[$(date)] Starting ingest..." | tee -a ingest.log

while true; do
    PYTHONPATH=. DATA_FILE=data/launches.json python -m src.ingest 2>&1 | tee -a ingest.log
    if [ -f data/.ingest_progress ] && [ "$(cat data/.ingest_progress)" = "DONE" ]; then
        echo "[$(date)] ✔ Ingest complete." | tee -a ingest.log
        break
    fi
    echo "[$(date)] ✗ Ingest exited without DONE marker. Restarting in 30s..." | tee -a ingest.log
    sleep 30
done

# Keep the tmux pane around for 30s so you can attach and see the result.
sleep 30
INNER
)

    TERM="${TERM:-xterm-256color}" tmux new-session -d -s "$SESSION" "bash -lc '$inner'"
    sleep 1
    green "✔ Ingest launched."
    echo
    print_status
    echo
    bold "Useful commands:"
    echo "  bash scripts/auto_ingest.sh status"
    echo "  bash scripts/auto_ingest.sh logs"
    echo "  bash scripts/auto_ingest.sh attach   # Ctrl+b then d to detach"
    echo "  bash scripts/auto_ingest.sh stop"
}

cmd_stop() {
    if is_running; then
        TERM="${TERM:-xterm-256color}" tmux kill-session -t "$SESSION"
        warn "Killed tmux session '$SESSION'."
    else
        warn "Nothing to stop — '$SESSION' isn't running."
    fi
}

cmd_attach() {
    if ! is_running; then
        warn "No '$SESSION' session — start it first with: bash scripts/auto_ingest.sh"
        exit 1
    fi
    exec env TERM="${TERM:-xterm-256color}" tmux attach -t "$SESSION"
}

cmd_logs() {
    if [[ ! -f "$LOG_FILE" ]]; then
        warn "No log file yet at $LOG_FILE."
        exit 1
    fi
    echo "Tailing $LOG_FILE — Ctrl+C to stop"
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
