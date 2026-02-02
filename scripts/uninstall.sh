#!/usr/bin/env bash
# Uninstall and cleanup mt5linux components
# Provides options to remove Wine prefix, services, and generated scripts

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
source "$SCRIPT_DIR/lib/detect.sh"

# Default configuration (local to project)
DEFAULT_WINE_PREFIX=".mt5"

kill_mt5_processes() {
    local prefix=$1

    section "Stopping MT5 Processes"

    # Find and kill terminal64.exe processes for this prefix
    local pids
    pids=$(pgrep -f "terminal64.exe" 2>/dev/null || true)

    if [[ -z "$pids" ]]; then
        log_info "No MT5 processes running"
        return 0
    fi

    for pid in $pids; do
        # Check if process belongs to our Wine prefix
        if [[ -f "/proc/$pid/environ" ]]; then
            if grep -qz "WINEPREFIX=$prefix" "/proc/$pid/environ" 2>/dev/null; then
                log_step "Killing MT5 process: $pid"
                kill "$pid" 2>/dev/null || true
            fi
        fi
    done

    sleep 2

    # Force kill if still running
    pids=$(pgrep -f "terminal64.exe" 2>/dev/null || true)
    for pid in $pids; do
        if [[ -f "/proc/$pid/environ" ]]; then
            if grep -qz "WINEPREFIX=$prefix" "/proc/$pid/environ" 2>/dev/null; then
                log_step "Force killing MT5 process: $pid"
                kill -9 "$pid" 2>/dev/null || true
            fi
        fi
    done

    log_ok "MT5 processes stopped"
}

kill_rpyc_processes() {
    local prefix=$1
    local port=${2:-}

    section "Stopping RPyC Processes"

    # Find rpyc server processes
    local pids
    pids=$(pgrep -f "rpyc" 2>/dev/null || true)

    if [[ -z "$pids" ]]; then
        log_info "No RPyC processes running"
        return 0
    fi

    for pid in $pids; do
        local should_kill=false

        # Check Wine prefix
        if [[ -f "/proc/$pid/environ" ]]; then
            if grep -qz "WINEPREFIX=$prefix" "/proc/$pid/environ" 2>/dev/null; then
                should_kill=true
            fi
        fi

        # Check port if specified
        if [[ -n "$port" ]] && [[ -f "/proc/$pid/cmdline" ]]; then
            if grep -qz "$port" "/proc/$pid/cmdline" 2>/dev/null; then
                should_kill=true
            fi
        fi

        if $should_kill; then
            log_step "Killing RPyC process: $pid"
            kill "$pid" 2>/dev/null || true
        fi
    done

    sleep 1
    log_ok "RPyC processes stopped"
}

remove_launcher_scripts() {
    local project_root=$1

    section "Removing Launcher Scripts"

    local scripts=(
        "$project_root/bin/start-system.sh"
        "$project_root/bin/stop-system.sh"
        "$project_root/bin/start-mt5.sh"
        "$project_root/bin/start-rpyc-server.sh"
        "$project_root/bin/system-status.sh"
    )

    for script in "${scripts[@]}"; do
        if [[ -f "$script" ]]; then
            log_step "Removing: $script"
            rm -f "$script"
        fi
    done

    # Remove bin directory if empty
    if [[ -d "$project_root/bin" ]] && [[ -z "$(ls -A "$project_root/bin" 2>/dev/null)" ]]; then
        rmdir "$project_root/bin"
        log_substep "Removed empty bin directory"
    fi

    log_ok "Launcher scripts removed"
}

remove_config_files() {
    local project_root=$1

    section "Removing Configuration Files"

    local files=(
        "$project_root/.mt5env"
        "$project_root/.mt5-install-state"
    )

    for file in "${files[@]}"; do
        if [[ -f "$file" ]]; then
            log_step "Removing: $file"
            rm -f "$file"
        fi
    done

    log_ok "Configuration files removed"
}

remove_wine_prefix() {
    local prefix=$1

    section "Removing Wine Prefix"

    if [[ ! -d "$prefix" ]]; then
        log_info "Wine prefix does not exist: $prefix"
        return 0
    fi

    # Calculate size
    local size
    size=$(du -sh "$prefix" 2>/dev/null | cut -f1)
    log_warn "Wine prefix size: $size"
    log_warn "Location: $prefix"

    if confirm "Delete Wine prefix? This cannot be undone!" "n"; then
        log_step "Removing Wine prefix"
        rm -rf "$prefix"
        log_ok "Wine prefix removed"
    else
        log_info "Wine prefix preserved"
    fi
}

show_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS] [COMMAND]

Uninstall mt5linux components.

Commands:
    all             Remove all components (default)
    scripts         Remove launcher scripts only
    config          Remove configuration files only
    prefix          Remove Wine prefix only
    processes       Kill running MT5/RPyC processes only

Options:
    --prefix PATH       Wine prefix path (default: ./.mt5 in project folder)
    --project PATH      Project root (default: auto-detect)
    --keep-wine         Don't remove Wine prefix
    -y, --yes           Non-interactive mode (skip confirmations)
    -h, --help          Show this help message

Examples:
    $(basename "$0") all                      # Full uninstall
    $(basename "$0") all --keep-wine          # Keep Wine prefix
    $(basename "$0") processes                # Just kill processes
    $(basename "$0") scripts                  # Remove launcher scripts only
EOF
}

main() {
    local wine_prefix=""
    local project_root=""
    local keep_wine=false
    local non_interactive=false
    local command="all"

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
            --keep-wine)
                keep_wine=true
                shift
                ;;
            -y|--yes)
                non_interactive=true
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            all|scripts|config|prefix|processes)
                command="$1"
                shift
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

    # Load config if exists
    if [[ -f "$project_root/.mt5env" ]]; then
        source_mt5env "$project_root/.mt5env"
        wine_prefix="${wine_prefix:-${MT5_WINE_PREFIX:-}}"
    fi

    # Default to local .mt5 folder if not set
    wine_prefix="${wine_prefix:-$project_root/$DEFAULT_WINE_PREFIX}"

    section "mt5linux Uninstaller"

    echo "Wine prefix:    $wine_prefix"
    echo "Project root:   $project_root"
    echo "Command:        $command"
    echo

    if ! $non_interactive; then
        if ! confirm "Proceed with uninstallation?"; then
            log_info "Uninstallation cancelled"
            exit 0
        fi
    fi

    case "$command" in
        all)
            kill_rpyc_processes "$wine_prefix"
            kill_mt5_processes "$wine_prefix"
            remove_launcher_scripts "$project_root"
            remove_config_files "$project_root"

            if ! $keep_wine; then
                remove_wine_prefix "$wine_prefix"
            fi
            ;;

        processes)
            kill_rpyc_processes "$wine_prefix"
            kill_mt5_processes "$wine_prefix"
            ;;

        scripts)
            remove_launcher_scripts "$project_root"
            ;;

        config)
            remove_config_files "$project_root"
            ;;

        prefix)
            kill_rpyc_processes "$wine_prefix"
            kill_mt5_processes "$wine_prefix"
            remove_wine_prefix "$wine_prefix"
            ;;

        *)
            die "Unknown command: $command"
            ;;
    esac

    section "Uninstallation Complete"
    log_ok "Cleanup finished"

    echo
    echo "${BOLD}Note:${RESET}"
    echo "  - Wine application (wine-staging) was not removed"
    echo "  - System packages were not removed"
    echo "  - To remove Wine: sudo apt remove winehq-staging"
}

# Only run main if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
