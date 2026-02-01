#!/usr/bin/env bash
# Install MetaTrader 5 terminal in Wine
# Handles MT5 download, WebView2 runtime, and installer execution

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
source "$SCRIPT_DIR/lib/detect.sh"

# Download URLs
MT5_SETUP_URL="https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe"
WEBVIEW2_URL="https://go.microsoft.com/fwlink/p/?LinkId=2124703"

# Default Wine prefix
DEFAULT_WINE_PREFIX="${HOME}/.mt5-wine"

# Installation timeout (10 minutes)
MT5_INSTALL_TIMEOUT=600

download_mt5_installer() {
    local temp_dir=$1

    log_step "Downloading MT5 installer"
    download_file "$MT5_SETUP_URL" "$temp_dir/mt5setup.exe"
    log_ok "MT5 installer downloaded"
}

download_webview2() {
    local temp_dir=$1

    log_step "Downloading WebView2 runtime"
    download_file "$WEBVIEW2_URL" "$temp_dir/MicrosoftEdgeWebView2RuntimeInstaller.exe"
    log_ok "WebView2 downloaded"
}

install_webview2() {
    local prefix=$1
    local installer=$2

    section "Installing WebView2 Runtime"

    export WINEPREFIX="$prefix"
    export WINEARCH="win64"

    local display_mode
    display_mode=$(detect_display_mode)

    log_step "Running WebView2 installer"

    case "$display_mode" in
        wayland)
            # Use virtual desktop for Wayland compatibility
            log_info "Using virtual desktop for Wayland"
            WAYLAND_DISPLAY="" wine explorer /desktop=WebView2,1024x768 "$installer" /silent /install &
            ;;
        xorg)
            wine "$installer" /silent /install &
            ;;
        headless)
            # Use Xvfb for headless
            log_info "Using Xvfb for headless environment"
            xvfb-run -a wine "$installer" /silent /install &
            ;;
    esac

    local installer_pid=$!

    if ! wait_with_timeout "$installer_pid" 300 "WebView2 installation"; then
        log_warn "WebView2 installation timed out, continuing anyway"
    fi

    wineserver --wait
    log_ok "WebView2 installation completed"
}

wait_for_mt5_installation() {
    local prefix=$1
    local timeout=$2
    local elapsed=0
    local check_interval=5

    log_info "Waiting for MT5 installation to complete..."
    log_info "Please complete the installation wizard if prompted"

    while [[ $elapsed -lt $timeout ]]; do
        # Check if terminal64.exe exists
        if find_mt5_terminal "$prefix" >/dev/null 2>&1; then
            log_ok "MT5 terminal found!"
            return 0
        fi

        # Check if installer is still running
        if ! pgrep -f "mt5setup.exe" >/dev/null 2>&1; then
            # Installer finished, check again for terminal
            sleep 2
            if find_mt5_terminal "$prefix" >/dev/null 2>&1; then
                log_ok "MT5 terminal found!"
                return 0
            else
                log_warn "Installer exited but terminal not found"
                break
            fi
        fi

        sleep $check_interval
        elapsed=$((elapsed + check_interval))

        if [[ $((elapsed % 30)) -eq 0 ]]; then
            log_info "Still waiting for MT5 installation... (${elapsed}s/${timeout}s)"
        fi
    done

    return 1
}

install_mt5_terminal() {
    local prefix=$1

    section "Installing MetaTrader 5"

    export WINEPREFIX="$prefix"
    export WINEARCH="win64"

    # Check if already installed
    local terminal_exe
    if terminal_exe=$(find_mt5_terminal "$prefix"); then
        log_ok "MT5 already installed: $terminal_exe"
        return 0
    fi

    # Check for display
    if is_headless; then
        log_error "MT5 installation requires a graphical display."
        log_error "Options:"
        log_error "  1. Connect via ThinLinc or VNC and run this script again"
        log_error "  2. Run on a desktop system"
        die "No display available for MT5 installation"
    fi

    local temp_dir
    temp_dir=$(mktemp -d)
    trap 'rm -rf "$temp_dir"' EXIT

    # Download installers
    download_mt5_installer "$temp_dir"
    download_webview2 "$temp_dir"

    # Install WebView2 first (required by MT5)
    install_webview2 "$prefix" "$temp_dir/MicrosoftEdgeWebView2RuntimeInstaller.exe"

    section "Running MT5 Installer"

    local display_mode
    display_mode=$(detect_display_mode)

    log_info "Display mode: $display_mode"
    log_warn "MT5 installer will open. Complete the installation wizard."
    log_warn "Choose the default installation path when prompted."

    case "$display_mode" in
        wayland)
            log_info "Using virtual desktop for Wayland compatibility"
            # Unset WAYLAND_DISPLAY and use virtual desktop
            WAYLAND_DISPLAY="" wine explorer /desktop=MT5Install,1280x1024 "$temp_dir/mt5setup.exe" &
            ;;
        xorg)
            wine "$temp_dir/mt5setup.exe" &
            ;;
    esac

    local installer_pid=$!

    # Wait for installation to complete
    if ! wait_for_mt5_installation "$prefix" "$MT5_INSTALL_TIMEOUT"; then
        log_error "MT5 installation did not complete successfully"
        log_error "Please try running the installer manually:"
        log_error "  WINEPREFIX=$prefix wine $temp_dir/mt5setup.exe"
        return 1
    fi

    wineserver --wait

    # Verify installation
    if terminal_exe=$(find_mt5_terminal "$prefix"); then
        log_ok "MT5 installed successfully: $terminal_exe"
    else
        log_error "MT5 terminal not found after installation"
        return 1
    fi
}

create_mt5_launcher() {
    local prefix=$1
    local project_root=$2

    section "Creating MT5 Launcher Scripts"

    local terminal_exe
    if ! terminal_exe=$(find_mt5_terminal "$prefix"); then
        die "MT5 terminal not found"
    fi

    # Convert to Windows path
    local terminal_win_path
    terminal_win_path=$(echo "$terminal_exe" | sed "s|$prefix/drive_c|C:|" | tr '/' '\\')

    # Create start-mt5.sh
    local launcher="$project_root/bin/start-mt5.sh"
    ensure_dir "$(dirname "$launcher")"

    cat > "$launcher" << EOF
#!/usr/bin/env bash
# Launch MetaTrader 5 terminal
# Generated by mt5linux install script

set -euo pipefail

export WINEPREFIX="$prefix"
export WINEARCH="win64"

# Handle Wayland
if [[ -n "\${WAYLAND_DISPLAY:-}" ]]; then
    unset WAYLAND_DISPLAY
    exec wine explorer /desktop=MT5,1920x1080 "$terminal_win_path" "\$@"
else
    exec wine "$terminal_win_path" "\$@"
fi
EOF

    chmod +x "$launcher"
    log_ok "Created: $launcher"

    # Create wine-wrapper for convenience
    local wine_wrapper="$project_root/bin/wine-mt5"
    cat > "$wine_wrapper" << EOF
#!/usr/bin/env bash
# Wine wrapper for MT5 prefix
export WINEPREFIX="$prefix"
export WINEARCH="win64"
exec wine "\$@"
EOF

    chmod +x "$wine_wrapper"
    log_ok "Created: $wine_wrapper"
}

verify_mt5_installation() {
    local prefix=$1

    section "Verifying MT5 Installation"

    local all_ok=true

    # Check Wine prefix
    if is_wine_prefix_valid "$prefix"; then
        log_ok "Wine prefix: $prefix"
    else
        log_error "Wine prefix invalid"
        all_ok=false
    fi

    # Check Python
    local python_exe
    if python_exe=$(find_wine_python "$prefix"); then
        log_ok "Windows Python: $python_exe"

        # Verify packages
        export WINEPREFIX="$prefix"
        export WINEARCH="win64"

        if wine "C:\\Python312\\python.exe" -c "import rpyc" 2>/dev/null; then
            log_ok "rpyc package installed"
        else
            log_warn "rpyc package not verified"
        fi

        if wine "C:\\Python312\\python.exe" -c "import MetaTrader5" 2>/dev/null; then
            log_ok "MetaTrader5 package installed"
        else
            log_warn "MetaTrader5 package not verified"
        fi
    else
        log_error "Windows Python not found"
        all_ok=false
    fi

    # Check MT5 terminal
    local terminal_exe
    if terminal_exe=$(find_mt5_terminal "$prefix"); then
        log_ok "MT5 terminal: $terminal_exe"
    else
        log_error "MT5 terminal not found"
        all_ok=false
    fi

    if $all_ok; then
        log_ok "MT5 installation verified successfully"
        return 0
    else
        log_error "MT5 installation verification failed"
        return 1
    fi
}

show_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Install MetaTrader 5 in Wine.

Options:
    --prefix PATH       Wine prefix path (default: $DEFAULT_WINE_PREFIX)
    --project PATH      Project root for launcher scripts (default: auto-detect)
    --install           Install MT5 (default action)
    --verify            Verify existing installation
    --launcher          Create/update launcher scripts only
    -h, --help          Show this help message

Examples:
    $(basename "$0") --prefix ~/.mt5-wine
    $(basename "$0") --verify
    $(basename "$0") --launcher --project /path/to/project
EOF
}

main() {
    local wine_prefix="$DEFAULT_WINE_PREFIX"
    local project_root=""
    local do_install=false
    local do_verify=false
    local do_launcher=false

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
            --install)
                do_install=true
                shift
                ;;
            --verify)
                do_verify=true
                shift
                ;;
            --launcher)
                do_launcher=true
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

    # Default to install if no action specified
    if ! $do_install && ! $do_verify && ! $do_launcher; then
        do_install=true
        do_launcher=true
    fi

    # Auto-detect project root if not specified
    if [[ -z "$project_root" ]]; then
        project_root=$(dirname "$SCRIPT_DIR")
    fi

    section "MetaTrader 5 Installation"
    print_environment_summary

    if ! command_exists wine; then
        die "Wine not installed. Run install-wine.sh first."
    fi

    if ! is_wine_prefix_valid "$wine_prefix"; then
        die "Wine prefix not found: $wine_prefix. Run install-wine.sh first."
    fi

    if $do_install; then
        install_mt5_terminal "$wine_prefix"
    fi

    if $do_launcher; then
        create_mt5_launcher "$wine_prefix" "$project_root"
    fi

    if $do_verify || $do_install; then
        verify_mt5_installation "$wine_prefix"
    fi

    section "MT5 Installation Complete"
    log_ok "Wine prefix: $wine_prefix"
    log_ok "You can now run: $project_root/bin/start-mt5.sh"
}

# Only run main if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
