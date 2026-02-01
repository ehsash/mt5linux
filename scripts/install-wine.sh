#!/usr/bin/env bash
# Install Wine Staging and configure Wine prefix for mt5linux
# Handles WineHQ repository setup and Windows Python installation

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
source "$SCRIPT_DIR/lib/detect.sh"

# Configuration
WINE_PYTHON_VERSION="${WINE_PYTHON_VERSION:-3.12.8}"
WINE_PYTHON_URL="https://www.python.org/ftp/python/${WINE_PYTHON_VERSION}/python-${WINE_PYTHON_VERSION}-amd64.exe"

# Default prefix location (local to project, can be overridden)
DEFAULT_WINE_PREFIX=".mt5"

add_winehq_repository() {
    section "Adding WineHQ Repository"

    local keyring_dir="/etc/apt/keyrings"
    local keyring_file="$keyring_dir/winehq-archive.key"
    local sources_file="/etc/apt/sources.list.d/winehq-noble.sources"

    # Check if already configured
    if [[ -f "$sources_file" ]] && [[ -f "$keyring_file" ]]; then
        log_ok "WineHQ repository already configured"
        return 0
    fi

    log_step "Creating keyring directory"
    sudo mkdir -p "$keyring_dir"

    log_step "Downloading WineHQ GPG key"
    sudo wget -q -O "$keyring_file" https://dl.winehq.org/wine-builds/winehq.key

    log_step "Adding WineHQ repository"
    sudo tee "$sources_file" > /dev/null << 'EOF'
Types: deb
URIs: https://dl.winehq.org/wine-builds/ubuntu/
Suites: noble
Components: main
Architectures: amd64 i386
Signed-By: /etc/apt/keyrings/winehq-archive.key
EOF

    log_step "Enabling 32-bit architecture"
    sudo dpkg --add-architecture i386

    log_step "Updating package lists"
    sudo apt-get update

    log_ok "WineHQ repository configured"
}

install_wine_staging() {
    section "Installing Wine Staging"

    if is_wine_staging; then
        log_ok "Wine Staging already installed: $(detect_wine_version)"
        return 0
    fi

    add_winehq_repository

    log_step "Installing Wine Staging (this may take several minutes)"
    sudo apt-get install -y --install-recommends winehq-staging

    # Verify installation
    if ! command_exists wine; then
        die "Wine installation failed"
    fi

    log_ok "Wine Staging installed: $(detect_wine_version)"
}

create_wine_prefix() {
    local prefix=$1

    section "Creating Wine Prefix"

    if is_wine_prefix_valid "$prefix"; then
        log_ok "Wine prefix already exists: $prefix"
        return 0
    fi

    log_step "Initializing Wine prefix at: $prefix"
    ensure_dir "$prefix"

    # Set up environment for Wine
    export WINEPREFIX="$prefix"
    export WINEARCH="win64"

    # On Wayland, we need XWayland for Wine GUI
    if is_wayland; then
        log_info "Wayland detected, using XWayland compatibility"
        unset WAYLAND_DISPLAY
    fi

    log_info "Running wineboot --init (this may take 1-2 minutes)"
    wineboot --init

    # Wait for wineserver to finish
    wineserver --wait

    if ! is_wine_prefix_valid "$prefix"; then
        die "Wine prefix creation failed"
    fi

    log_ok "Wine prefix created successfully"
}

install_python_in_wine() {
    local prefix=$1

    section "Installing Windows Python in Wine"

    export WINEPREFIX="$prefix"
    export WINEARCH="win64"

    # Check if Python already installed
    local python_exe
    if python_exe=$(find_wine_python "$prefix"); then
        log_ok "Windows Python already installed: $python_exe"
        return 0
    fi

    # Check for display availability
    if is_headless; then
        die "Display required for Python installation. Connect via GUI session first."
    fi

    local temp_dir
    temp_dir=$(mktemp -d)
    local installer_path="$temp_dir/python-${WINE_PYTHON_VERSION}-amd64.exe"

    log_step "Downloading Windows Python ${WINE_PYTHON_VERSION}"
    download_file "$WINE_PYTHON_URL" "$installer_path"

    log_step "Installing Python (silent install)"

    # Wayland compatibility
    if is_wayland; then
        unset WAYLAND_DISPLAY
    fi

    # Run silent installer
    wine "$installer_path" /quiet InstallAllUsers=0 PrependPath=1 TargetDir="C:\\Python312" &
    local installer_pid=$!

    # Wait with timeout (5 minutes)
    if ! wait_with_timeout "$installer_pid" 300 "Python installation"; then
        die "Python installation timed out"
    fi

    wineserver --wait
    rm -rf "$temp_dir"

    # Verify installation
    if ! python_exe=$(find_wine_python "$prefix"); then
        die "Python installation failed"
    fi

    log_ok "Windows Python installed: $python_exe"
}

install_python_packages_in_wine() {
    local prefix=$1

    section "Installing Python Packages in Wine"

    export WINEPREFIX="$prefix"
    export WINEARCH="win64"

    local python_exe
    if ! python_exe=$(find_wine_python "$prefix"); then
        die "Python not found in Wine prefix"
    fi

    # Convert Windows path for wine
    local python_path="C:\\Python312\\python.exe"

    log_step "Upgrading pip"
    wine "$python_path" -m pip install --upgrade pip 2>/dev/null || true

    log_step "Installing rpyc"
    wine "$python_path" -m pip install "rpyc>=5.0.1"

    log_step "Installing MetaTrader5"
    wine "$python_path" -m pip install MetaTrader5

    log_ok "Python packages installed"

    # Verify installations
    log_step "Verifying package installations"
    if wine "$python_path" -c "import rpyc; print(f'rpyc {rpyc.__version__}')" 2>/dev/null; then
        log_ok "rpyc verified"
    else
        log_warn "rpyc import verification failed (may still work)"
    fi
}

configure_wine_for_mt5() {
    local prefix=$1

    section "Configuring Wine for MT5"

    export WINEPREFIX="$prefix"
    export WINEARCH="win64"

    log_step "Setting Windows version to Windows 10"

    # Create registry file for Windows 10 compatibility
    local reg_file
    reg_file=$(mktemp --suffix=.reg)

    cat > "$reg_file" << 'EOF'
Windows Registry Editor Version 5.00

[HKEY_LOCAL_MACHINE\Software\Microsoft\Windows NT\CurrentVersion]
"ProductName"="Windows 10"
"CSDVersion"=""
"CurrentBuild"="19041"
"CurrentBuildNumber"="19041"
"CurrentVersion"="6.3"

[HKEY_LOCAL_MACHINE\System\CurrentControlSet\Control\Windows]
"CSDVersion"=dword:00000000
EOF

    wine regedit "$reg_file" 2>/dev/null || true
    rm -f "$reg_file"

    wineserver --wait

    log_ok "Wine configured for MT5 compatibility"
}

show_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Install and configure Wine Staging for mt5linux.

Options:
    --prefix PATH   Wine prefix path (default: ./.mt5 in project folder)
    --wine-only     Only install Wine, skip Python and packages
    --python-only   Only install Python in existing prefix
    --packages      Only install Python packages
    --configure     Only configure Wine for MT5
    --all           Full installation (default)
    -h, --help      Show this help message

Environment Variables:
    WINE_PYTHON_VERSION  Python version to install (default: 3.12.8)

Examples:
    $(basename "$0") --all                           # Full installation
    $(basename "$0") --prefix /path/to/project/.mt5  # Custom prefix
    $(basename "$0") --wine-only                     # Just install Wine
EOF
}

main() {
    local wine_prefix="$DEFAULT_WINE_PREFIX"
    local do_wine=false
    local do_prefix=false
    local do_python=false
    local do_packages=false
    local do_configure=false
    local do_all=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            --prefix)
                wine_prefix="$2"
                shift 2
                ;;
            --wine-only)
                do_wine=true
                shift
                ;;
            --python-only)
                do_python=true
                shift
                ;;
            --packages)
                do_packages=true
                shift
                ;;
            --configure)
                do_configure=true
                shift
                ;;
            --all)
                do_all=true
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

    # Default to full installation if no specific option given
    if ! $do_wine && ! $do_python && ! $do_packages && ! $do_configure; then
        do_all=true
    fi

    section "Wine Installation"
    print_environment_summary

    if ! validate_environment; then
        die "Environment validation failed"
    fi

    start_sudo_keepalive
    trap stop_sudo_keepalive EXIT

    if $do_all || $do_wine; then
        install_wine_staging
    fi

    if $do_all || $do_python; then
        if ! command_exists wine; then
            die "Wine not installed. Run with --wine-only first."
        fi
        create_wine_prefix "$wine_prefix"
        install_python_in_wine "$wine_prefix"
    fi

    if $do_all || $do_packages; then
        if ! is_wine_prefix_valid "$wine_prefix"; then
            die "Wine prefix not found: $wine_prefix"
        fi
        install_python_packages_in_wine "$wine_prefix"
    fi

    if $do_all || $do_configure; then
        if ! is_wine_prefix_valid "$wine_prefix"; then
            die "Wine prefix not found: $wine_prefix"
        fi
        configure_wine_for_mt5 "$wine_prefix"
    fi

    section "Wine Installation Complete"
    log_ok "Wine prefix: $wine_prefix"
    log_ok "Ready for MT5 installation"
}

# Only run main if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
