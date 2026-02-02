#!/usr/bin/env bash
# Stop MT5 system
# Stops both MT5 terminal and RPyC server for this instance
#
# Each instance is fully isolated - this script only stops processes
# belonging to the specified Wine prefix (local .mt5/ folder).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
source "$SCRIPT_DIR/lib/detect.sh"

# Graceful shutdown timeout before force kill
SHUTDOWN_TIMEOUT=10

stop_rpyc_server() {
    local prefix=$1
    local port=${2:-}

    log_step "Stopping RPyC server"

    local stopped=false

    # Method 1: Use PID file if exists
    local pid_file="${prefix}/.rpyc.pid"
    if [[ -f "$pid_file" ]]; then
        local pid
        pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            log_substep "Stopping RPyC server (PID: $pid)"
            kill "$pid" 2>/dev/null || true
            stopped=true
        fi
        rm -f "$pid_file"
    fi

    # Method 2: Find by port and Wine prefix
    if [[ -n "$port" ]]; then
        local pids
        pids=$(pgrep -f "rpyc.*$port" 2>/dev/null || true)

        for pid in $pids; do
            # Verify this process belongs to our Wine prefix
            if [[ -f "/proc/$pid/environ" ]]; then
                if grep -qz "WINEPREFIX=$prefix" "/proc/$pid/environ" 2>/dev/null; then
                    log_substep "Stopping RPyC process (PID: $pid)"
                    kill "$pid" 2>/dev/null || true
                    stopped=true
                fi
            fi
        done
    fi

    # Method 3: Find by Wine prefix only (fallback)
    local wine_pids
    wine_pids=$(pgrep -f "python.*rpyc" 2>/dev/null || true)

    for pid in $wine_pids; do
        if [[ -f "/proc/$pid/environ" ]]; then
            if grep -qz "WINEPREFIX=$prefix" "/proc/$pid/environ" 2>/dev/null; then
                log_substep "Stopping Wine Python/RPyC process (PID: $pid)"
                kill "$pid" 2>/dev/null || true
                stopped=true
            fi
        fi
    done

    if $stopped; then
        # Wait for graceful shutdown
        sleep 2

        # Force kill if still running
        if [[ -n "$port" ]] && test_port_connection "localhost" "$port" 1 2>/dev/null; then
            log_warn "RPyC server still running, force killing"
            pids=$(pgrep -f "rpyc.*$port" 2>/dev/null || true)
            for pid in $pids; do
                kill -9 "$pid" 2>/dev/null || true
            done
        fi

        log_ok "RPyC server stopped"
    else
        log_info "No RPyC server running for this prefix"
    fi
}

stop_mt5_terminal() {
    local prefix=$1

    log_step "Stopping MT5 terminal"

    local stopped=false

    # Method 1: Use PID file if exists
    local pid_file="${prefix}/.mt5.pid"
    if [[ -f "$pid_file" ]]; then
        local pid
        pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            log_substep "Stopping MT5 terminal (PID: $pid)"
            kill "$pid" 2>/dev/null || true
            stopped=true
        fi
        rm -f "$pid_file"
    fi

    # Method 2: Find terminal64.exe processes for this Wine prefix
    local pids
    pids=$(pgrep -f "terminal64.exe" 2>/dev/null || true)

    for pid in $pids; do
        # Verify this process belongs to our Wine prefix
        if [[ -f "/proc/$pid/environ" ]]; then
            if grep -qz "WINEPREFIX=$prefix" "/proc/$pid/environ" 2>/dev/null; then
                log_substep "Stopping MT5 process (PID: $pid)"
                kill "$pid" 2>/dev/null || true
                stopped=true
            fi
        fi
    done

    if $stopped; then
        # Wait for graceful shutdown
        local elapsed=0
        while [[ $elapsed -lt $SHUTDOWN_TIMEOUT ]]; do
            if ! pgrep -f "terminal64.exe" >/dev/null 2>&1; then
                break
            fi

            # Check if our specific processes are gone
            local still_running=false
            for pid in $pids; do
                if kill -0 "$pid" 2>/dev/null; then
                    still_running=true
                    break
                fi
            done

            if ! $still_running; then
                break
            fi

            sleep 1
            elapsed=$((elapsed + 1))
        done

        # Force kill if still running
        for pid in $pids; do
            if kill -0 "$pid" 2>/dev/null; then
                log_warn "MT5 process still running, force killing (PID: $pid)"
                kill -9 "$pid" 2>/dev/null || true
            fi
        done

        log_ok "MT5 terminal stopped"
    else
        log_info "No MT5 terminal running for this prefix"
    fi
}

stop_wineserver() {
    local prefix=$1

    log_step "Stopping Wine server"

    export WINEPREFIX="$prefix"
    wineserver -k 2>/dev/null || true

    log_ok "Wine server stopped"
}

print_status() {
    local prefix=$1
    local port=${2:-}
    local host=${3:-localhost}

    echo
    separator
    echo "${BOLD}MT5 System Status${RESET}"
    separator
    echo "Wine prefix: $prefix"

    # Check RPyC
    if [[ -n "$port" ]] && test_port_connection "$host" "$port" 1 2>/dev/null; then
        echo "${YELLOW}RPyC server:  STILL RUNNING on port $port${RESET}"
    else
        echo "${GREEN}RPyC server:  STOPPED${RESET}"
    fi

    # Check MT5 process
    local mt5_running=false
    local pids
    pids=$(pgrep -f "terminal64.exe" 2>/dev/null || true)
    for pid in $pids; do
        if [[ -f "/proc/$pid/environ" ]]; then
            if grep -qz "WINEPREFIX=$prefix" "/proc/$pid/environ" 2>/dev/null; then
                mt5_running=true
                break
            fi
        fi
    done

    if $mt5_running; then
        echo "${YELLOW}MT5 terminal: STILL RUNNING${RESET}"
    else
        echo "${GREEN}MT5 terminal: STOPPED${RESET}"
    fi

    separator
}

show_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Stop MT5 system (RPyC server + MT5 terminal).

This script only stops processes belonging to this instance's Wine prefix,
leaving other MT5 instances unaffected.

Options:
    --prefix PATH       Wine prefix path (default: from .mt5env or ./.mt5)
    --project PATH      Project root containing .mt5env (default: auto-detect)
    --port PORT         RPyC port to identify server (default: from .mt5env)
    --rpyc-only         Only stop RPyC server
    --mt5-only          Only stop MT5 terminal
    --kill-wine         Also stop Wine server for this prefix
    --force             Force kill without graceful shutdown
    --status            Show status after stopping
    -h, --help          Show this help message

Examples:
    # Stop system (reads config from .mt5env)
    $(basename "$0")

    # Only stop MT5 terminal (keep RPyC running)
    $(basename "$0") --mt5-only

    # Force stop everything including Wine server
    $(basename "$0") --kill-wine --force
EOF
}

main() {
    local wine_prefix=""
    local project_root=""
    local rpyc_port=""
    local rpyc_host="localhost"
    local rpyc_only=false
    local mt5_only=false
    local kill_wine=false
    local force=false
    local show_status_flag=false

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
            --rpyc-only)
                rpyc_only=true
                shift
                ;;
            --mt5-only)
                mt5_only=true
                shift
                ;;
            --kill-wine)
                kill_wine=true
                shift
                ;;
            --force)
                force=true
                SHUTDOWN_TIMEOUT=0
                shift
                ;;
            --status)
                show_status_flag=true
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
        rpyc_port="${rpyc_port:-${MT5_RPYC_PORT:-}}"
        rpyc_host="${rpyc_host:-${MT5_RPYC_HOST:-localhost}}"
    fi

    # Defaults if still not set (use local .mt5 folder)
    wine_prefix="${wine_prefix:-$project_root/.mt5}"

    section "Stopping MT5 System"
    log_info "Wine prefix: $wine_prefix"

    if [[ ! -d "$wine_prefix" ]]; then
        log_warn "Wine prefix does not exist: $wine_prefix"
        exit 0
    fi

    # Stop MT5 terminal (unless rpyc-only)
    if ! $rpyc_only; then
        stop_mt5_terminal "$wine_prefix"
    fi

    # Stop RPyC server (unless mt5-only)
    if ! $mt5_only; then
        stop_rpyc_server "$wine_prefix" "$rpyc_port"
    fi

    # Stop Wine server if requested
    if $kill_wine; then
        stop_wineserver "$wine_prefix"
    fi

    if $show_status_flag; then
        print_status "$wine_prefix" "$rpyc_port" "$rpyc_host"
    else
        log_ok "Trading environment stopped"
    fi
}

# Only run main if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
