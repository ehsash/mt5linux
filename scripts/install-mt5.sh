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

automate_webview2_installer() {
    # Automate WebView2 installer GUI using xdotool
    # The installer shows: "Install" button -> progress -> "Close" button
    local window_timeout=120
    local elapsed=0
    local found_window=false

    log_info "Waiting for WebView2 installer window..."

    # Phase 1: Wait for the installer window to appear
    while [[ $elapsed -lt $window_timeout ]]; do
        local window_id
        window_id=$(xdotool search --name "WebView2" 2>/dev/null | head -1) || true

        if [[ -n "$window_id" ]]; then
            found_window=true
            log_info "Found WebView2 installer window (ID: $window_id)"
            break
        fi

        sleep 1
        elapsed=$((elapsed + 1))
    done

    if ! $found_window; then
        log_warn "WebView2 installer window not detected (may have completed silently)"
        return 0
    fi

    # Phase 2: Click the Install button
    local window_id
    window_id=$(xdotool search --name "WebView2" 2>/dev/null | head -1) || true

    # Give the window a moment to fully render
    sleep 2

    # Focus and click Install button (Enter key activates focused button)
    xdotool windowactivate --sync "$window_id" 2>/dev/null || true
    sleep 0.5
    xdotool key --window "$window_id" Return 2>/dev/null || true
    log_info "Clicked Install button, installation starting..."

    # Phase 3: Wait for user confirmation that installation is complete
    echo
    echo "${BOLD}${YELLOW}>>> WebView2 is installing. When you see the 'Close' button, press Enter here to continue...${RESET}"
    read -r _

    # Phase 4: Click Close button to dismiss the installer
    window_id=$(xdotool search --name "WebView2" 2>/dev/null | head -1) || true
    if [[ -n "$window_id" ]]; then
        log_info "Closing WebView2 installer window..."
        xdotool windowactivate --sync "$window_id" 2>/dev/null || true
        sleep 0.3
        xdotool key --window "$window_id" Return 2>/dev/null || true
        sleep 1
    fi

    # Verify window closed
    if ! xdotool search --name "WebView2" >/dev/null 2>&1; then
        log_ok "WebView2 installation completed"
    else
        log_warn "WebView2 window still open - you may need to close it manually"
    fi

    return 0
}

install_webview2() {
    local prefix=$1
    local installer=$2

    section "Installing WebView2 Runtime"

    export WINEPREFIX="$prefix"
    export WINEARCH="win64"
    export WINEDEBUG=-all

    # Kill any existing wineserver to ensure fresh start with WINEDEBUG
    wineserver -k 2>/dev/null || true
    sleep 1

    # Check for xdotool (required for GUI automation)
    if ! command_exists xdotool; then
        log_warn "xdotool not installed - WebView2 installer may require manual interaction"
        log_warn "Install with: sudo apt install xdotool"
    fi

    local display_mode
    display_mode=$(detect_display_mode)

    log_step "Running WebView2 installer"
    log_info "Display mode: $display_mode"

    # Run wine in a subshell with all output suppressed
    # WINEDEBUG must be exported for all child processes
    case "$display_mode" in
        wayland)
            # Use virtual desktop for Wayland compatibility
            log_info "Using virtual desktop for Wayland"
            ( WINEDEBUG=-all WAYLAND_DISPLAY="" wine explorer /desktop=WebView2,1024x768 "$installer" ) >/dev/null 2>&1 &
            ;;
        xorg|*)
            # xorg or fallback for any other mode
            ( WINEDEBUG=-all wine "$installer" ) >/dev/null 2>&1 &
            ;;
    esac

    local installer_pid=$!

    # Give Wine a moment to start the installer
    sleep 3

    # Automate the installer if xdotool is available
    if command_exists xdotool; then
        automate_webview2_installer
    else
        # Fallback: wait with timeout and hope for manual intervention
        log_warn "Please click 'Install' then 'Close' in the WebView2 installer window"
        if ! wait_with_timeout "$installer_pid" 300 "WebView2 installation"; then
            log_warn "WebView2 installation timed out"
        fi
    fi

    # Wait for any remaining Wine processes
    wineserver --wait 2>/dev/null || true
    log_ok "WebView2 installation completed"
}

automate_mt5_installer() {
    # Automate MT5 installer GUI using xdotool
    # The installer shows: License Agreement -> Next -> Install path -> Next -> Install -> Finish
    local prefix=$1
    local timeout=300
    local elapsed=0
    local found_any_window=false

    log_info "Automating MT5 installer (will click through wizard)..."

    # List all windows initially for debugging
    log_info "=== Current X11 windows ==="
    local window_list
    window_list=$(xdotool search --name "" 2>/dev/null | head -20) || true
    if [[ -n "$window_list" ]]; then
        while read -r wid; do
            local wname
            wname=$(xdotool getwindowname "$wid" 2>/dev/null) || continue
            [[ -n "$wname" ]] && echo "    $wid: $wname"
        done <<< "$window_list"
    else
        log_warn "No windows found"
    fi
    log_info "==========================="

    while [[ $elapsed -lt $timeout ]]; do
        # Check if MT5 is already installed
        if find_mt5_terminal "$prefix" >/dev/null 2>&1; then
            log_ok "MT5 terminal detected - installation complete"
            return 0
        fi

        # Check if any Wine-related process is running
        local wine_procs
        wine_procs=$(pgrep -f "wine|mt5setup|\.exe" 2>/dev/null | wc -l) || true
        if [[ "$wine_procs" -eq 0 ]]; then
            sleep 2
            if find_mt5_terminal "$prefix" >/dev/null 2>&1; then
                log_ok "MT5 terminal detected - installation complete"
                return 0
            fi
            log_warn "No Wine/installer processes found"
            break
        fi

        # Search for installer window with multiple patterns
        local window_id=""
        local search_patterns=("MetaTrader" "mt5setup" "Setup" "Install" "License" "Installer")

        for pattern in "${search_patterns[@]}"; do
            window_id=$(xdotool search --name "$pattern" 2>/dev/null | head -1) || true
            if [[ -n "$window_id" ]]; then
                if ! $found_any_window; then
                    log_info "Found installer window matching '$pattern' (ID: $window_id)"
                    found_any_window=true
                fi
                break
            fi
        done

        if [[ -n "$window_id" ]]; then
            # Focus the window
            xdotool windowactivate --sync "$window_id" 2>/dev/null || true
            sleep 0.5

            # Send Enter key to click "Next" or "Install" or "Finish" button
            xdotool key --window "$window_id" Return 2>/dev/null || true
            sleep 0.3
        else
            # No window found yet - might still be loading
            if [[ $((elapsed % 15)) -eq 0 ]]; then
                log_info "Waiting for installer window to appear... (${elapsed}s)"
            fi
        fi

        sleep 3
        elapsed=$((elapsed + 3))

        if [[ $((elapsed % 30)) -eq 0 ]]; then
            log_info "MT5 installation in progress... (${elapsed}s/${timeout}s)"
            # Re-list windows for debugging
            log_info "=== Active windows ==="
            local wlist
            wlist=$(xdotool search --name "" 2>/dev/null | head -10) || true
            if [[ -n "$wlist" ]]; then
                while read -r wid; do
                    local wname
                    wname=$(xdotool getwindowname "$wid" 2>/dev/null) || continue
                    [[ -n "$wname" ]] && echo "    $wid: $wname"
                done <<< "$wlist"
            fi
            log_info "====================="
        fi
    done

    # Final check
    if find_mt5_terminal "$prefix" >/dev/null 2>&1; then
        return 0
    fi

    if ! $found_any_window; then
        log_error "MT5 installer window was never detected"
    fi
    return 1
}

wait_for_mt5_installation() {
    local prefix=$1
    local timeout=$2
    local elapsed=0
    local check_interval=5

    log_info "Waiting for MT5 installation to complete..."

    # If xdotool is available, use automated clicking
    if command_exists xdotool; then
        if automate_mt5_installer "$prefix"; then
            return 0
        fi
    fi

    # Fallback: manual waiting with prompts
    log_warn "Please complete the MT5 installation wizard manually:"
    log_warn "  1. Accept the license agreement"
    log_warn "  2. Keep default installation path"
    log_warn "  3. Click 'Next' then 'Finish'"

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

    # Ensure WINEDEBUG is set for MT5 installer as well
    export WINEDEBUG=-all

    # Kill wineserver to ensure fresh start with WINEDEBUG
    wineserver -k 2>/dev/null || true
    sleep 1

    local display_mode
    display_mode=$(detect_display_mode)

    log_info "Display mode: $display_mode"

    if command_exists xdotool; then
        log_info "xdotool detected - installer will be automated"
    else
        log_warn "xdotool not found - you may need to click through the installer manually"
        log_warn "  1. Accept the license agreement"
        log_warn "  2. Keep default installation path"
        log_warn "  3. Click 'Next' then 'Finish'"
    fi

    log_info "DISPLAY=$DISPLAY"

    # Run wine in a subshell with all output suppressed
    case "$display_mode" in
        wayland)
            log_info "Using virtual desktop for Wayland compatibility"
            ( WINEDEBUG=-all WAYLAND_DISPLAY="" wine explorer /desktop=MT5Install,1280x1024 "$temp_dir/mt5setup.exe" ) >/dev/null 2>&1 &
            ;;
        xorg|*)
            # xorg or fallback for any other mode
            if [[ "$display_mode" != "xorg" ]]; then
                log_warn "Unexpected display mode '$display_mode' - attempting standard Wine launch"
            fi
            log_info "Launching: wine $temp_dir/mt5setup.exe"
            ( WINEDEBUG=-all wine "$temp_dir/mt5setup.exe" ) >/dev/null 2>&1 &
            ;;
    esac

    local installer_pid=$!
    log_info "Wine process started (PID: $installer_pid)"

    # Give Wine a moment to start the installer
    sleep 5

    # Verify Wine process is running
    if ! kill -0 "$installer_pid" 2>/dev/null; then
        log_warn "Wine process exited quickly - checking if child process spawned"
        sleep 2
    fi

    # Wait for installation to complete
    if ! wait_for_mt5_installation "$prefix" "$MT5_INSTALL_TIMEOUT"; then
        log_error "MT5 installation did not complete successfully"
        log_error "Please try running the installer manually:"
        log_error "  WINEPREFIX=$prefix wine $temp_dir/mt5setup.exe"
        return 1
    fi

    wineserver --wait 2>/dev/null || true

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

        if wine "C:\\Python312\\python.exe" -c "import rpyc" >/dev/null 2>&1; then
            log_ok "rpyc package installed"
        else
            log_warn "rpyc package not verified"
        fi

        if wine "C:\\Python312\\python.exe" -c "import MetaTrader5" >/dev/null 2>&1; then
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
