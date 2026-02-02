#!/usr/bin/env bash
# Diagnostic script for mt5linux installation
# Checks all components and reports status

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
source "$SCRIPT_DIR/lib/detect.sh"

# Default prefix (local to project)
DEFAULT_WINE_PREFIX=".mt5"

run_diagnostics() {
    local wine_prefix="${1:-$DEFAULT_WINE_PREFIX}"
    local project_root="${2:-$(dirname "$SCRIPT_DIR")}"

    echo
    echo "${BOLD}${CYAN}╔════════════════════════════════════════════════════════════════╗${RESET}"
    echo "${BOLD}${CYAN}║                 mt5linux Diagnostic Report                     ║${RESET}"
    echo "${BOLD}${CYAN}╚════════════════════════════════════════════════════════════════╝${RESET}"
    echo

    # System Information
    section "System Information"
    log_info "OS: $(get_os_info)"
    log_info "Architecture: $(detect_arch)"
    log_info "Hostname: $(hostname)"
    log_info "User: $USER"
    log_info "Date: $(date)"

    # Display Environment
    section "Display Environment"
    local display_mode
    display_mode=$(detect_display_mode)

    case "$display_mode" in
        wayland)
            log_ok "Display: Wayland"
            log_info "  WAYLAND_DISPLAY: ${WAYLAND_DISPLAY:-}"
            log_info "  DISPLAY: ${DISPLAY:-not set}"
            ;;
        xorg)
            log_ok "Display: X11/Xorg"
            log_info "  DISPLAY: ${DISPLAY:-}"
            ;;
        headless)
            log_warn "Display: Headless (no display server detected)"
            log_info "  DISPLAY: ${DISPLAY:-not set}"
            log_info "  WAYLAND_DISPLAY: ${WAYLAND_DISPLAY:-not set}"
            ;;
    esac

    if is_xserver_installed; then
        log_ok "X server: installed"
    else
        log_warn "X server: not installed"
    fi

    local desktop
    desktop=$(detect_desktop_environment)
    log_info "Desktop environment: $desktop"

    if is_thinlinc_installed; then
        log_ok "ThinLinc: installed"
    fi

    # Wine Status
    section "Wine Status"
    if command_exists wine; then
        log_ok "Wine: installed"
        log_info "  Version: $(detect_wine_version)"
        log_info "  Path: $(which wine)"

        if is_wine_staging; then
            log_ok "  Wine Staging: yes"
        else
            log_warn "  Wine Staging: no (recommended)"
        fi
    else
        log_error "Wine: not installed"
    fi

    # Wine Prefix
    section "Wine Prefix: $wine_prefix"
    if is_wine_prefix_valid "$wine_prefix"; then
        log_ok "Wine prefix: valid"

        # Check for Python
        local python_exe
        if python_exe=$(find_wine_python "$wine_prefix"); then
            log_ok "Windows Python: $python_exe"

            # Check Python packages
            export WINEPREFIX="$wine_prefix"
            export WINEARCH="win64"

            local wine_rpyc_version
            if wine_rpyc_version=$(wine "C:\\Python312\\python.exe" -c "import rpyc; print(rpyc.__version__)" 2>/dev/null); then
                log_ok "  rpyc (Wine): $wine_rpyc_version"
            else
                log_warn "  rpyc (Wine): not verified"
            fi

            if wine "C:\\Python312\\python.exe" -c "import MetaTrader5" 2>/dev/null; then
                log_ok "  MetaTrader5: installed"
            else
                log_warn "  MetaTrader5: not verified"
            fi
        else
            log_error "Windows Python: not found"
        fi

        # Check for MT5 terminal
        local terminal_exe
        if terminal_exe=$(find_mt5_terminal "$wine_prefix"); then
            log_ok "MT5 terminal: $terminal_exe"
        else
            log_error "MT5 terminal: not found"
        fi
    else
        log_error "Wine prefix: not found or invalid"
    fi

    # Configuration Files
    section "Configuration Files"
    local env_file="$project_root/.mt5env"
    if [[ -f "$env_file" ]]; then
        log_ok "Config file: $env_file"
        source_mt5env "$env_file"
        log_info "  MT5_WINE_PREFIX: ${MT5_WINE_PREFIX:-not set}"
        log_info "  MT5_RPYC_PORT: ${MT5_RPYC_PORT:-not set}"
        log_info "  MT5_RPYC_HOST: ${MT5_RPYC_HOST:-not set}"
        log_info "  MT5_VENV: ${MT5_VENV:-not set}"
    else
        log_warn "Config file: not found"
    fi

    # Launcher Scripts
    section "Launcher Scripts"
    for script in "$project_root/bin/start-system.sh" \
                  "$project_root/bin/stop-system.sh" \
                  "$project_root/bin/start-mt5.sh" \
                  "$project_root/bin/start-rpyc-server.sh" \
                  "$project_root/bin/system-status.sh"; do
        if [[ -x "$script" ]]; then
            log_ok "$(basename "$script"): exists"
        elif [[ -f "$script" ]]; then
            log_warn "$(basename "$script"): exists but not executable"
        else
            log_info "$(basename "$script"): not found"
        fi
    done

    # Network/Port Status
    section "Network Status"
    local rpyc_port="${MT5_RPYC_PORT:-18812}"
    local rpyc_host="${MT5_RPYC_HOST:-localhost}"

    if port_in_use "$rpyc_port"; then
        log_ok "Port $rpyc_port: in use"

        if test_port_connection "$rpyc_host" "$rpyc_port" 5; then
            log_ok "RPyC connection: responding"
        else
            log_warn "RPyC connection: not responding"
        fi
    else
        log_warn "Port $rpyc_port: not in use"
    fi

    # Running Processes
    section "Running Processes"
    local mt5_pids
    mt5_pids=$(pgrep -f "terminal64.exe" 2>/dev/null || true)
    if [[ -n "$mt5_pids" ]]; then
        log_ok "MT5 terminal: running (PIDs: $mt5_pids)"
    else
        log_info "MT5 terminal: not running"
    fi

    local rpyc_pids
    rpyc_pids=$(pgrep -f "rpyc" 2>/dev/null || true)
    if [[ -n "$rpyc_pids" ]]; then
        log_ok "RPyC server: running (PIDs: $rpyc_pids)"
    else
        log_info "RPyC server: not running"
    fi

    # Python Virtual Environment
    section "Python Environment (Linux)"
    local venv_path="${MT5_VENV:-$project_root/.venv}"
    if [[ -d "$venv_path" ]]; then
        log_ok "Virtual env: $venv_path"

        if [[ -f "$venv_path/bin/python" ]]; then
            local py_version
            py_version=$("$venv_path/bin/python" --version 2>&1)
            log_info "  Python: $py_version"
        fi

        local linux_rpyc_version
        if linux_rpyc_version=$("$venv_path/bin/python" -c "import rpyc; print(rpyc.__version__)" 2>/dev/null); then
            log_ok "  rpyc (Linux): $linux_rpyc_version"
        else
            log_warn "  rpyc (Linux): not installed"
        fi
    else
        log_warn "Virtual env: not found at $venv_path"
    fi

    echo
    separator
    log_info "Diagnostic complete"
    echo
}

show_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Run diagnostics on mt5linux installation.

Options:
    --prefix PATH       Wine prefix path (default: ./.mt5 in project folder)
    --project PATH      Project root (default: auto-detect)
    -h, --help          Show this help message

Output is suitable for sharing when troubleshooting issues.

All files are stored locally in the project folder.
EOF
}

main() {
    local wine_prefix=""
    local project_root=""

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
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                die "Unknown option: $1"
                ;;
        esac
    done

    if [[ -z "$project_root" ]]; then
        project_root=$(dirname "$SCRIPT_DIR")
    fi

    # Load config if exists
    if [[ -f "$project_root/.mt5env" ]]; then
        source_mt5env "$project_root/.mt5env"
        wine_prefix="${wine_prefix:-${MT5_WINE_PREFIX:-}}"
    fi

    # Default to local .mt5 folder
    wine_prefix="${wine_prefix:-$project_root/$DEFAULT_WINE_PREFIX}"

    run_diagnostics "$wine_prefix" "$project_root"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
