#!/usr/bin/env bash
# Start MT5 system
# Launches both MT5 terminal and RPyC server for this instance
#
# Each instance is fully isolated with its own:
# - Wine prefix (.mt5/ in project folder)
# - RPyC server on a unique port
# - Configuration file (.mt5env in project folder)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
source "$SCRIPT_DIR/lib/detect.sh"

# Default configuration
DEFAULT_RPYC_PORT=18812
DEFAULT_RPYC_HOST="localhost"
RPYC_STARTUP_TIMEOUT=30
MT5_STARTUP_TIMEOUT=60

start_rpyc_server() {
    local prefix=$1
    local port=$2
    local host=$3
    local log_file=$4

    log_step "Starting RPyC server on ${host}:${port}"

    # Check if already running on this port
    if test_port_connection "$host" "$port" 2 2>/dev/null; then
        log_warn "Port $port already in use"

        # Check if it's our RPyC server
        if pgrep -f "rpyc.*$port" >/dev/null 2>&1; then
            log_ok "RPyC server already running on port $port"
            return 0
        else
            die "Port $port is used by another process"
        fi
    fi

    export WINEPREFIX="$prefix"
    export WINEARCH="win64"

    # Handle Wayland
    if [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
        unset WAYLAND_DISPLAY
    fi

    local python_win_path="C:\\Python312\\python.exe"

    # Start RPyC server in background
    nohup wine "$python_win_path" -c "
from rpyc.utils.server import ThreadedServer
from rpyc.core.service import ClassicService
import sys

print(f'RPyC server starting on ${host}:${port}', flush=True)
server = ThreadedServer(ClassicService, hostname='${host}', port=${port})
server.start()
" > "$log_file" 2>&1 &

    local rpyc_pid=$!
    echo "$rpyc_pid" > "${prefix}/.rpyc.pid"

    # Wait for server to start
    local elapsed=0
    while [[ $elapsed -lt $RPYC_STARTUP_TIMEOUT ]]; do
        if test_port_connection "$host" "$port" 1 2>/dev/null; then
            log_ok "RPyC server started (PID: $rpyc_pid)"
            return 0
        fi

        # Check if process died
        if ! kill -0 "$rpyc_pid" 2>/dev/null; then
            log_error "RPyC server failed to start. Check log: $log_file"
            tail -20 "$log_file" 2>/dev/null || true
            return 1
        fi

        sleep 1
        elapsed=$((elapsed + 1))
    done

    log_error "RPyC server startup timeout"
    return 1
}

start_mt5_terminal() {
    local prefix=$1
    local background=${2:-false}

    log_step "Starting MT5 terminal"

    export WINEPREFIX="$prefix"
    export WINEARCH="win64"

    local terminal_exe
    if ! terminal_exe=$(find_mt5_terminal "$prefix"); then
        die "MT5 terminal not found in prefix: $prefix"
    fi

    local terminal_win_path
    terminal_win_path=$(echo "$terminal_exe" | sed "s|$prefix/drive_c|C:|" | tr '/' '\\')

    # Handle Wayland - need virtual desktop
    local wine_cmd="wine"
    if [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
        unset WAYLAND_DISPLAY
        wine_cmd="wine explorer /desktop=MT5,1920x1080"
    fi

    if $background; then
        nohup $wine_cmd "$terminal_win_path" > "${prefix}/.mt5-terminal.log" 2>&1 &
        local mt5_pid=$!
        echo "$mt5_pid" > "${prefix}/.mt5.pid"
        log_ok "MT5 terminal started in background (PID: $mt5_pid)"
    else
        log_info "Launching MT5 terminal (foreground)"
        log_info "Close the terminal window to stop, or use stop-trading.sh"
        $wine_cmd "$terminal_win_path"
    fi
}

wait_for_mt5_ready() {
    local prefix=$1
    local port=$2
    local host=$3
    local timeout=${4:-$MT5_STARTUP_TIMEOUT}

    log_step "Waiting for MT5 to initialize"

    local elapsed=0
    while [[ $elapsed -lt $timeout ]]; do
        # Try to import MT5 module via RPyC
        if python3 -c "
import rpyc
try:
    conn = rpyc.classic.connect('$host', $port)
    mt5 = conn.modules.MetaTrader5
    # Try to get version - this confirms MT5 is loaded
    ver = mt5.__version__
    conn.close()
    exit(0)
except:
    exit(1)
" 2>/dev/null; then
            log_ok "MT5 module ready via RPyC"
            return 0
        fi

        sleep 2
        elapsed=$((elapsed + 2))

        if [[ $((elapsed % 10)) -eq 0 ]]; then
            log_info "Waiting for MT5... (${elapsed}s/${timeout}s)"
        fi
    done

    log_warn "MT5 readiness check timeout (this may be normal on first startup)"
    log_info "MT5 may still be initializing. Try connecting manually."
    return 0
}

print_status() {
    local prefix=$1
    local port=$2
    local host=$3
    local project_name=$4

    echo
    separator
    echo "${BOLD}MT5 System Status: ${project_name}${RESET}"
    separator
    echo "Wine prefix:    $prefix"
    echo "RPyC endpoint:  ${host}:${port}"
    echo

    # Check RPyC
    if test_port_connection "$host" "$port" 2 2>/dev/null; then
        echo "${GREEN}RPyC server:    RUNNING${RESET}"
    else
        echo "${RED}RPyC server:    NOT RUNNING${RESET}"
    fi

    # Check MT5 process
    if pgrep -f "terminal64.exe" >/dev/null 2>&1; then
        echo "${GREEN}MT5 terminal:   RUNNING${RESET}"
    else
        echo "${YELLOW}MT5 terminal:   NOT RUNNING${RESET}"
    fi

    echo
    echo "${BOLD}Python usage:${RESET}"
    echo "  from mt5linux import MetaTrader5"
    echo "  mt5 = MetaTrader5(host='${host}', port=${port})"
    echo "  mt5.initialize()"
    separator
}

show_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Start MT5 system (RPyC server + MT5 terminal).

Each instance is fully isolated with its own Wine prefix, MT5 installation,
broker account, and RPyC server port - all within the project folder.

Options:
    --prefix PATH       Wine prefix path (default: from .mt5env or ./.mt5)
    --project PATH      Project root containing .mt5env (default: auto-detect)
    --port PORT         RPyC port (default: from .mt5env or 18812)
    --host HOST         RPyC host (default: localhost)
    --background        Run MT5 terminal in background
    --rpyc-only         Only start RPyC server, not MT5 terminal
    --mt5-only          Only start MT5 terminal, not RPyC server
    --no-wait           Don't wait for MT5 to be ready
    --status            Show status and exit
    -h, --help          Show this help message

Examples:
    # Start system (reads config from .mt5env)
    $(basename "$0")

    # Start MT5 in background
    $(basename "$0") --background

    # Only start RPyC server (MT5 already running)
    $(basename "$0") --rpyc-only
EOF
}

main() {
    local wine_prefix=""
    local project_root=""
    local rpyc_port=""
    local rpyc_host="$DEFAULT_RPYC_HOST"
    local background=false
    local rpyc_only=false
    local mt5_only=false
    local no_wait=false
    local show_status_only=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            --prefix)
                wine_prefix="$2"
                shift 2
                ;;
            --project)
                project_root="$2"
                shift 2
                ;;
            --port)
                rpyc_port="$2"
                shift 2
                ;;
            --host)
                rpyc_host="$2"
                shift 2
                ;;
            --background)
                background=true
                shift
                ;;
            --rpyc-only)
                rpyc_only=true
                shift
                ;;
            --mt5-only)
                mt5_only=true
                shift
                ;;
            --no-wait)
                no_wait=true
                shift
                ;;
            --status)
                show_status_only=true
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                die "Unknown option: $1"
                ;;
        esac
    done

    check_not_root

    # Auto-detect project root
    if [[ -z "$project_root" ]]; then
        project_root=$(dirname "$SCRIPT_DIR")
    fi

    # Load configuration from .mt5env
    if [[ -f "$project_root/.mt5env" ]]; then
        source_mt5env "$project_root/.mt5env"
        wine_prefix="${wine_prefix:-${MT5_WINE_PREFIX:-}}"
        rpyc_port="${rpyc_port:-${MT5_RPYC_PORT:-$DEFAULT_RPYC_PORT}}"
        rpyc_host="${rpyc_host:-${MT5_RPYC_HOST:-$DEFAULT_RPYC_HOST}}"
    fi

    # Defaults if still not set (use local .mt5 folder)
    wine_prefix="${wine_prefix:-$project_root/.mt5}"
    rpyc_port="${rpyc_port:-$DEFAULT_RPYC_PORT}"

    local project_name
    project_name=$(basename "$project_root")

    # Status only mode
    if $show_status_only; then
        print_status "$wine_prefix" "$rpyc_port" "$rpyc_host" "$project_name"
        exit 0
    fi

    # Validate Wine prefix
    if ! is_wine_prefix_valid "$wine_prefix"; then
        die "Wine prefix not found: $wine_prefix. Run install.sh first."
    fi

    # Check for Python in Wine
    if ! find_wine_python "$wine_prefix" >/dev/null; then
        die "Windows Python not found in Wine prefix"
    fi

    section "Starting MT5 System: $project_name"
    log_info "Wine prefix: $wine_prefix"
    log_info "RPyC endpoint: ${rpyc_host}:${rpyc_port}"

    local log_dir="$wine_prefix/logs"
    ensure_dir "$log_dir"
    local rpyc_log="$log_dir/rpyc-server.log"

    # Start RPyC server (unless mt5-only)
    if ! $mt5_only; then
        start_rpyc_server "$wine_prefix" "$rpyc_port" "$rpyc_host" "$rpyc_log"
    fi

    # Start MT5 terminal (unless rpyc-only)
    if ! $rpyc_only; then
        start_mt5_terminal "$wine_prefix" "$background"
    fi

    # Wait for MT5 to be ready (if both started and not skipped)
    if ! $rpyc_only && ! $mt5_only && ! $no_wait && $background; then
        wait_for_mt5_ready "$wine_prefix" "$rpyc_port" "$rpyc_host"
    fi

    print_status "$wine_prefix" "$rpyc_port" "$rpyc_host" "$project_name"
}

# Only run main if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
