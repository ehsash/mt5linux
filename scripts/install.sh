#!/usr/bin/env bash
# Main installation orchestrator for mt5linux
# Runs all installation steps in the correct order with proper state management

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
source "$SCRIPT_DIR/lib/detect.sh"

# Version
VERSION="1.0.0"

# Default configuration (prefix is relative to project root)
DEFAULT_WINE_PREFIX=".mt5"
DEFAULT_RPYC_PORT=18812
DEFAULT_RPYC_HOST="localhost"

# Installation state file
STATE_FILE=""

# Installation phases
PHASE_BASE="base"
PHASE_WINE="wine"
PHASE_MT5="mt5"
PHASE_RPYC="rpyc"
PHASE_VERIFY="verify"

save_state() {
    local phase=$1
    local status=$2
    local message=${3:-""}

    if [[ -n "$STATE_FILE" ]]; then
        echo "PHASE=$phase" > "$STATE_FILE"
        echo "STATUS=$status" >> "$STATE_FILE"
        echo "MESSAGE=$message" >> "$STATE_FILE"
        echo "TIMESTAMP=$(date -Iseconds)" >> "$STATE_FILE"
    fi
}

load_state() {
    if [[ -f "$STATE_FILE" ]]; then
        # shellcheck source=/dev/null
        source "$STATE_FILE"
        echo "${PHASE:-}"
    fi
}

run_phase_base() {
    local install_xserver=$1
    local install_thinlinc=$2

    section "Phase 1: Base Dependencies"
    save_state "$PHASE_BASE" "running"

    local args=("--all")
    if $install_xserver; then
        args+=("--xserver")
    fi
    if $install_thinlinc; then
        args+=("--thinlinc")
    fi

    "$SCRIPT_DIR/install-base.sh" "${args[@]}"

    save_state "$PHASE_BASE" "completed"
}

run_phase_wine() {
    local wine_prefix=$1

    section "Phase 2: Wine Environment"
    save_state "$PHASE_WINE" "running"

    "$SCRIPT_DIR/install-wine.sh" --prefix "$wine_prefix" --all

    save_state "$PHASE_WINE" "completed"
}

run_phase_mt5() {
    local wine_prefix=$1
    local project_root=$2

    section "Phase 3: MetaTrader 5"
    save_state "$PHASE_MT5" "running"

    "$SCRIPT_DIR/install-mt5.sh" --prefix "$wine_prefix" --project "$project_root" --install --launcher

    save_state "$PHASE_MT5" "completed"
}

run_phase_rpyc() {
    local wine_prefix=$1
    local project_root=$2
    local rpyc_port=$3
    local rpyc_host=$4
    local instance_name=${5:-$(basename "$project_root")}

    section "Phase 4: RPyC Configuration"
    save_state "$PHASE_RPYC" "running"

    "$SCRIPT_DIR/setup-rpyc.sh" --prefix "$wine_prefix" --project "$project_root" \
        --port "$rpyc_port" --host "$rpyc_host" --name "$instance_name" setup

    save_state "$PHASE_RPYC" "completed"
}

run_phase_verify() {
    local wine_prefix=$1
    local rpyc_host=$2
    local rpyc_port=$3

    section "Phase 5: Verification"
    save_state "$PHASE_VERIFY" "running"

    local all_ok=true

    # Verify Wine
    if command_exists wine; then
        log_ok "Wine installed: $(detect_wine_version)"
    else
        log_error "Wine not installed"
        all_ok=false
    fi

    # Verify prefix
    if is_wine_prefix_valid "$wine_prefix"; then
        log_ok "Wine prefix: $wine_prefix"
    else
        log_error "Wine prefix invalid"
        all_ok=false
    fi

    # Verify Python
    local python_exe
    if python_exe=$(find_wine_python "$wine_prefix"); then
        log_ok "Windows Python: $python_exe"
    else
        log_error "Windows Python not found"
        all_ok=false
    fi

    # Verify MT5
    local terminal_exe
    if terminal_exe=$(find_mt5_terminal "$wine_prefix"); then
        log_ok "MT5 terminal: $terminal_exe"
    else
        log_error "MT5 terminal not found"
        all_ok=false
    fi

    # Verify RPyC connection (if server running)
    if test_port_connection "$rpyc_host" "$rpyc_port" 2; then
        log_ok "RPyC server responding on port $rpyc_port"
    else
        log_warn "RPyC server not responding (may need to start manually)"
    fi

    if $all_ok; then
        save_state "$PHASE_VERIFY" "completed"
        log_ok "All components verified successfully"
    else
        save_state "$PHASE_VERIFY" "failed"
        log_error "Some components failed verification"
        return 1
    fi
}

detect_resume_point() {
    local state_file=$1

    if [[ ! -f "$state_file" ]]; then
        echo ""
        return
    fi

    local phase status
    # shellcheck source=/dev/null
    source "$state_file"
    phase="${PHASE:-}"
    status="${STATUS:-}"

    if [[ "$status" == "completed" ]]; then
        # Return next phase
        case "$phase" in
            "$PHASE_BASE") echo "$PHASE_WINE" ;;
            "$PHASE_WINE") echo "$PHASE_MT5" ;;
            "$PHASE_MT5") echo "$PHASE_RPYC" ;;
            "$PHASE_RPYC") echo "$PHASE_VERIFY" ;;
            *) echo "" ;;
        esac
    else
        # Resume from failed/running phase
        echo "$phase"
    fi
}

print_summary() {
    local wine_prefix=$1
    local project_root=$2
    local rpyc_port=$3
    local instance_name
    instance_name=$(basename "$project_root")

    section "Installation Summary"

    echo "${BOLD}Instance: ${instance_name}${RESET}"
    echo
    echo "${BOLD}Configuration:${RESET}"
    echo "  Wine prefix:    $wine_prefix"
    echo "  Project root:   $project_root"
    echo "  RPyC endpoint:  localhost:$rpyc_port"
    echo

    echo "${BOLD}Scripts created:${RESET}"
    echo "  Start system:   $project_root/bin/start-system.sh"
    echo "  Stop system:    $project_root/bin/stop-system.sh"
    echo "  Check status:   $project_root/bin/system-status.sh"
    echo

    echo "${BOLD}Quick Start:${RESET}"
    echo "  1. Start everything:  ./bin/start-system.sh"
    echo "  2. Login to your broker account in MT5"
    echo "  3. In Python:"
    echo "     >>> from mt5linux import MetaTrader5"
    echo "     >>> mt5 = MetaTrader5(port=$rpyc_port)"
    echo "     >>> mt5.initialize()"
    echo "  4. When done:         ./bin/stop-system.sh"
    echo

    echo "${BOLD}All files stored locally in:${RESET}"
    echo "  $wine_prefix"
}

show_usage() {
    cat << EOF
mt5linux Installation Script v${VERSION}

Usage: $(basename "$0") [OPTIONS] [COMMAND]

Commands:
    full            Full installation (default)
    resume          Resume from last incomplete phase
    phase PHASE     Run specific phase only
    verify          Verify installation
    status          Show current installation state

Phases (for 'phase' command):
    base            Install base system dependencies
    wine            Install Wine and Python
    mt5             Install MetaTrader 5
    rpyc            Configure RPyC server and launcher scripts
    verify          Verify all components

Options:
    --prefix PATH       Wine prefix path (default: ./$DEFAULT_WINE_PREFIX in project)
    --project PATH      Project root (default: auto-detect from script location)
    --port PORT         RPyC port (default: $DEFAULT_RPYC_PORT)
    --host HOST         RPyC host (default: $DEFAULT_RPYC_HOST)
    --name NAME         Instance name (default: project directory name)
    --xserver           Install X server only (without ThinLinc remote access)
    --thinlinc          Install ThinLinc (auto-enabled on headless servers)
    -y, --yes           Non-interactive mode (assume yes)
    -h, --help          Show this help message

Environment Detection:
    Desktop with X11:       Standard installation
    Desktop with Wayland:   Uses XWayland for Wine compatibility
    Server (headless):      Auto-installs ThinLinc for remote access

All Files Local:
    All installation files are stored in the project folder:
    - Wine prefix:  ./.mt5/
    - Config:       ./.mt5env
    - Scripts:      ./bin/

Examples:
    # Full installation on Ubuntu Desktop
    $(basename "$0") full

    # Full installation on Ubuntu Server (ThinLinc auto-installed)
    $(basename "$0") full

    # Ubuntu Server with X server only (no remote access)
    $(basename "$0") full --xserver

    # Custom port
    $(basename "$0") full --port 18813

    # Resume interrupted installation
    $(basename "$0") resume
EOF
}

main() {
    local wine_prefix=""
    local project_root=""
    local rpyc_port="$DEFAULT_RPYC_PORT"
    local rpyc_host="$DEFAULT_RPYC_HOST"
    local instance_name=""
    local install_xserver=false
    local install_thinlinc=false
    local non_interactive=false
    local command="full"
    local target_phase=""

    # Parse arguments
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
            --name)
                instance_name="$2"
                shift 2
                ;;
            --xserver)
                install_xserver=true
                shift
                ;;
            --thinlinc)
                install_thinlinc=true
                install_xserver=true  # ThinLinc needs X server
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
            full|resume|verify|status)
                command="$1"
                shift
                ;;
            phase)
                command="phase"
                target_phase="${2:-}"
                shift
                [[ -n "$target_phase" ]] && shift
                ;;
            *)
                die "Unknown option: $1. Use --help for usage."
                ;;
        esac
    done

    check_not_root

    # Auto-detect project root
    if [[ -z "$project_root" ]]; then
        project_root=$(dirname "$SCRIPT_DIR")
    fi

    # Default Wine prefix to local .mt5 folder
    if [[ -z "$wine_prefix" ]]; then
        wine_prefix="$project_root/$DEFAULT_WINE_PREFIX"
    fi

    # State file in project root
    STATE_FILE="$project_root/.mt5-install-state"

    # Header
    echo
    echo "${BOLD}${CYAN}╔════════════════════════════════════════════════════════════════╗${RESET}"
    echo "${BOLD}${CYAN}║              mt5linux Installation Script v${VERSION}              ║${RESET}"
    echo "${BOLD}${CYAN}╚════════════════════════════════════════════════════════════════╝${RESET}"
    echo

    # Environment check
    print_environment_summary

    if ! validate_environment; then
        die "Environment validation failed"
    fi

    # Handle headless detection - auto-install ThinLinc if no display
    if is_headless; then
        log_warn "Headless environment detected"

        if ! $install_xserver && ! $install_thinlinc; then
            log_info "No display available, will install ThinLinc for remote access"
            install_thinlinc=true
            install_xserver=true
        fi
    fi

    # Default instance name if not set
    if [[ -z "$instance_name" ]]; then
        instance_name=$(basename "$project_root")
    fi

    # Confirmation
    if ! $non_interactive; then
        echo
        echo "${BOLD}Installation configuration:${RESET}"
        echo "  Instance name:  $instance_name"
        echo "  Wine prefix:    $wine_prefix"
        echo "  Project root:   $project_root"
        echo "  RPyC port:      $rpyc_port"
        if $install_xserver; then
            echo "  Install X server: yes"
        fi
        if $install_thinlinc; then
            echo "  Install ThinLinc: yes"
        fi
        echo

        if ! confirm "Proceed with installation?"; then
            log_info "Installation cancelled"
            exit 0
        fi
    fi

    # Start sudo keepalive
    start_sudo_keepalive
    trap stop_sudo_keepalive EXIT

    case "$command" in
        full)
            run_phase_base "$install_xserver" "$install_thinlinc"

            # If ThinLinc was installed on headless, pause for user to connect
            if $install_thinlinc && is_headless; then
                log_warn "ThinLinc installed. Please connect via ThinLinc client and run:"
                log_warn "  $SCRIPT_DIR/install.sh resume"
                save_state "$PHASE_BASE" "completed" "Waiting for ThinLinc connection"
                exit 0
            fi

            run_phase_wine "$wine_prefix"
            run_phase_mt5 "$wine_prefix" "$project_root"
            run_phase_rpyc "$wine_prefix" "$project_root" "$rpyc_port" "$rpyc_host" "$instance_name"
            run_phase_verify "$wine_prefix" "$rpyc_host" "$rpyc_port"
            print_summary "$wine_prefix" "$project_root" "$rpyc_port"
            ;;

        resume)
            local resume_phase
            resume_phase=$(detect_resume_point "$STATE_FILE")

            if [[ -z "$resume_phase" ]]; then
                log_info "No incomplete installation found. Starting fresh."
                exec "$0" full "$@"
            fi

            log_info "Resuming from phase: $resume_phase"

            case "$resume_phase" in
                "$PHASE_BASE")
                    run_phase_base "$install_xserver" "$install_thinlinc"
                    ;&  # Fall through
                "$PHASE_WINE")
                    run_phase_wine "$wine_prefix"
                    ;&
                "$PHASE_MT5")
                    run_phase_mt5 "$wine_prefix" "$project_root"
                    ;&
                "$PHASE_RPYC")
                    run_phase_rpyc "$wine_prefix" "$project_root" "$rpyc_port" "$rpyc_host" "$instance_name"
                    ;&
                "$PHASE_VERIFY")
                    run_phase_verify "$wine_prefix" "$rpyc_host" "$rpyc_port"
                    print_summary "$wine_prefix" "$project_root" "$rpyc_port"
                    ;;
            esac
            ;;

        phase)
            if [[ -z "$target_phase" ]]; then
                die "Phase name required. Use: $(basename "$0") phase <phase-name>"
            fi

            case "$target_phase" in
                base)   run_phase_base "$install_xserver" "$install_thinlinc" ;;
                wine)   run_phase_wine "$wine_prefix" ;;
                mt5)    run_phase_mt5 "$wine_prefix" "$project_root" ;;
                rpyc)   run_phase_rpyc "$wine_prefix" "$project_root" "$rpyc_port" "$rpyc_host" "$instance_name" ;;
                verify) run_phase_verify "$wine_prefix" "$rpyc_host" "$rpyc_port" ;;
                *)      die "Unknown phase: $target_phase" ;;
            esac
            ;;

        verify)
            run_phase_verify "$wine_prefix" "$rpyc_host" "$rpyc_port"
            ;;

        status)
            section "Installation Status"
            if [[ -f "$STATE_FILE" ]]; then
                cat "$STATE_FILE"
            else
                log_info "No installation state found"
            fi
            ;;

        *)
            die "Unknown command: $command"
            ;;
    esac

    section "Installation Complete"
    log_ok "mt5linux installation finished successfully"
}

# Only run main if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
