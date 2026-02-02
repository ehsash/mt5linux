#!/usr/bin/env bash
# Configure RPyC and MT5 system for mt5linux
# Creates configuration files and convenience launcher scripts
# All files are stored locally in the project folder

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
source "$SCRIPT_DIR/lib/detect.sh"

# Default configuration (prefix is relative to project root)
DEFAULT_WINE_PREFIX=".mt5"
DEFAULT_RPYC_PORT=18812
DEFAULT_RPYC_HOST="localhost"

create_launcher_scripts() {
    local project_root=$1
    local prefix=$2
    local port=$3
    local host=$4

    section "Creating Launcher Scripts"

    local bin_dir="$project_root/bin"
    ensure_dir "$bin_dir"

    # Create start-system wrapper
    local start_script="$bin_dir/start-system.sh"
    cat > "$start_script" << EOF
#!/usr/bin/env bash
# Start MT5 system
# Wrapper script - delegates to scripts/start-system.sh

SCRIPT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="\$(dirname "\$SCRIPT_DIR")"

exec "\$PROJECT_ROOT/scripts/start-system.sh" \\
    --prefix "$prefix" \\
    --port "$port" \\
    --host "$host" \\
    "\$@"
EOF
    chmod +x "$start_script"
    log_ok "Created: $start_script"

    # Create stop-system wrapper
    local stop_script="$bin_dir/stop-system.sh"
    cat > "$stop_script" << EOF
#!/usr/bin/env bash
# Stop MT5 system
# Wrapper script - delegates to scripts/stop-system.sh

SCRIPT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="\$(dirname "\$SCRIPT_DIR")"

exec "\$PROJECT_ROOT/scripts/stop-system.sh" \\
    --prefix "$prefix" \\
    --port "$port" \\
    "\$@"
EOF
    chmod +x "$stop_script"
    log_ok "Created: $stop_script"

    # Create start-mt5 wrapper (MT5 terminal only)
    local mt5_script="$bin_dir/start-mt5.sh"
    cat > "$mt5_script" << EOF
#!/usr/bin/env bash
# Start MT5 terminal only (without RPyC server)
# Wrapper script - delegates to scripts/start-system.sh

SCRIPT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="\$(dirname "\$SCRIPT_DIR")"

exec "\$PROJECT_ROOT/scripts/start-system.sh" \\
    --prefix "$prefix" \\
    --mt5-only \\
    "\$@"
EOF
    chmod +x "$mt5_script"
    log_ok "Created: $mt5_script"

    # Create start-rpyc-server wrapper (RPyC only)
    local rpyc_script="$bin_dir/start-rpyc-server.sh"
    cat > "$rpyc_script" << EOF
#!/usr/bin/env bash
# Start RPyC server only (without MT5 terminal)
# Wrapper script - delegates to scripts/start-system.sh

SCRIPT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="\$(dirname "\$SCRIPT_DIR")"

exec "\$PROJECT_ROOT/scripts/start-system.sh" \\
    --prefix "$prefix" \\
    --port "$port" \\
    --host "$host" \\
    --rpyc-only \\
    "\$@"
EOF
    chmod +x "$rpyc_script"
    log_ok "Created: $rpyc_script"

    # Create status script
    local status_script="$bin_dir/system-status.sh"
    cat > "$status_script" << EOF
#!/usr/bin/env bash
# Show MT5 system status

SCRIPT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="\$(dirname "\$SCRIPT_DIR")"

exec "\$PROJECT_ROOT/scripts/start-system.sh" \\
    --prefix "$prefix" \\
    --port "$port" \\
    --host "$host" \\
    --status
EOF
    chmod +x "$status_script"
    log_ok "Created: $status_script"
}

generate_mt5env_file() {
    local project_root=$1
    local prefix=$2
    local port=$3
    local host=$4
    local venv_path=$5
    local instance_name=$6

    section "Generating Configuration File"

    local env_file="$project_root/.mt5env"

    cat > "$env_file" << EOF
# MT5 Linux Configuration
# Instance: ${instance_name}
# All files are stored locally in this project folder

MT5_WINE_PREFIX="${prefix}"
MT5_RPYC_PORT=${port}
MT5_RPYC_HOST="${host}"
MT5_VENV="${venv_path}"
MT5_INSTANCE_NAME="${instance_name}"
EOF

    log_ok "Configuration saved to: $env_file"
}

test_rpyc_connection() {
    local host=$1
    local port=$2
    local timeout=${3:-10}

    section "Testing RPyC Connection"

    log_step "Checking if port $port is reachable"

    if test_port_connection "$host" "$port" "$timeout"; then
        log_ok "Port $port is responding"
    else
        log_error "Port $port is not responding"
        log_info "Start the system first:"
        log_info "  ./bin/start-system.sh"
        return 1
    fi

    # Try a Python connection test
    log_step "Testing Python RPyC connection"

    if python3 -c "
import socket
import sys

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    sock.connect(('$host', $port))
    data = sock.recv(100)
    sock.close()
    if data:
        print('OK: RPyC server responded')
        sys.exit(0)
    else:
        print('WARN: Connected but no response')
        sys.exit(0)
except socket.timeout:
    print('ERROR: Connection timeout')
    sys.exit(1)
except ConnectionRefusedError:
    print('ERROR: Connection refused')
    sys.exit(1)
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)
" 2>/dev/null; then
        log_ok "RPyC server responding"
        return 0
    else
        log_error "RPyC connection test failed"
        return 1
    fi
}

test_rpyc_mt5_import() {
    local host=$1
    local port=$2

    section "Testing MT5 Module Import via RPyC"

    log_step "Attempting to import MetaTrader5 module"

    if python3 -c "
import sys
try:
    import rpyc
    conn = rpyc.classic.connect('$host', $port)
    mt5 = conn.modules.MetaTrader5
    print(f'MT5 module version: {mt5.__version__}')
    conn.close()
    sys.exit(0)
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)
" 2>/dev/null; then
        log_ok "MT5 module accessible via RPyC"
        return 0
    else
        log_warn "Could not import MT5 module"
        log_info "This may be normal if MT5 terminal is not running"
        return 1
    fi
}

show_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS] COMMAND

Configure RPyC server and MT5 system for mt5linux.
All configuration and files are stored locally in the project folder.

Commands:
    setup               Create configuration and launcher scripts
    test                Test RPyC connection
    test-mt5            Test MT5 import via RPyC

Options:
    --prefix PATH       Wine prefix path (default: ./$DEFAULT_WINE_PREFIX)
    --project PATH      Project root (default: auto-detect)
    --port PORT         RPyC port (default: $DEFAULT_RPYC_PORT)
    --host HOST         RPyC host (default: $DEFAULT_RPYC_HOST)
    --venv PATH         Python venv path (default: project/.venv)
    --name NAME         Instance name (default: project directory name)
    -h, --help          Show this help message

Examples:
    $(basename "$0") setup                  # Create scripts with defaults
    $(basename "$0") --port 18813 setup     # Use custom port
    $(basename "$0") test                   # Test connection
EOF
}

main() {
    local wine_prefix=""
    local project_root=""
    local rpyc_port="$DEFAULT_RPYC_PORT"
    local rpyc_host="$DEFAULT_RPYC_HOST"
    local venv_path=""
    local instance_name=""
    local command=""

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
            --venv)
                venv_path="$2"
                shift 2
                ;;
            --name)
                instance_name="$2"
                shift 2
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            setup|test|test-mt5)
                command="$1"
                shift
                ;;
            *)
                die "Unknown option: $1"
                ;;
        esac
    done

    check_not_root

    if [[ -z "$command" ]]; then
        show_usage
        exit 1
    fi

    # Auto-detect project root if not specified
    if [[ -z "$project_root" ]]; then
        project_root=$(dirname "$SCRIPT_DIR")
    fi

    # Default venv path
    if [[ -z "$venv_path" ]]; then
        venv_path="$project_root/.venv"
    fi

    # Default instance name
    if [[ -z "$instance_name" ]]; then
        instance_name=$(basename "$project_root")
    fi

    # Default Wine prefix (local to project)
    if [[ -z "$wine_prefix" ]]; then
        wine_prefix="$project_root/$DEFAULT_WINE_PREFIX"
    fi

    # Load existing config if available
    if [[ -f "$project_root/.mt5env" ]]; then
        source_mt5env "$project_root/.mt5env"
        wine_prefix="${MT5_WINE_PREFIX:-$wine_prefix}"
        rpyc_port="${MT5_RPYC_PORT:-$rpyc_port}"
        rpyc_host="${MT5_RPYC_HOST:-$rpyc_host}"
        venv_path="${MT5_VENV:-$venv_path}"
        instance_name="${MT5_INSTANCE_NAME:-$instance_name}"
    fi

    section "RPyC Configuration"

    case "$command" in
        setup)
            if ! is_wine_prefix_valid "$wine_prefix"; then
                die "Wine prefix not found: $wine_prefix"
            fi

            # Validate port is available
            if port_in_use "$rpyc_port"; then
                log_warn "Port $rpyc_port is currently in use"
                log_info "Make sure no other instance is using this port"
            fi

            create_launcher_scripts "$project_root" "$wine_prefix" "$rpyc_port" "$rpyc_host"
            generate_mt5env_file "$project_root" "$wine_prefix" "$rpyc_port" "$rpyc_host" "$venv_path" "$instance_name"

            echo
            separator
            log_ok "RPyC setup complete for instance: $instance_name"
            echo
            echo "${BOLD}Quick Start:${RESET}"
            echo "  Start system:   $project_root/bin/start-system.sh"
            echo "  Stop system:    $project_root/bin/stop-system.sh"
            echo "  Check status:   $project_root/bin/system-status.sh"
            echo
            echo "${BOLD}Instance Details:${RESET}"
            echo "  Wine prefix:    $wine_prefix"
            echo "  RPyC endpoint:  ${rpyc_host}:${rpyc_port}"
            separator
            ;;
        test)
            test_rpyc_connection "$rpyc_host" "$rpyc_port"
            ;;
        test-mt5)
            test_rpyc_mt5_import "$rpyc_host" "$rpyc_port"
            ;;
        *)
            die "Unknown command: $command"
            ;;
    esac
}

# Only run main if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
