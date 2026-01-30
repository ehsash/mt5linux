#!/usr/bin/env bash
#
# mt5_setup.sh - MetaTrader 5 Linux Setup Script
#
# This script automates the installation and configuration of MT5 on Ubuntu 24.04 LTS
# using Wine, Python 3.12, and RPyC for communication between Linux and Windows Python.
#
# Usage:
#   ./mt5_setup.sh --phase=preinstall   # Phase 1: Install dependencies
#   ./mt5_setup.sh --phase=verify       # Phase 3: Verify installation
#
# Between phases, user must manually install MT5 via GUI (desktop or ThinLinc).
#
# Author: Generated for mt5linux project
# License: MIT

set -euo pipefail

# ==============================================================================
# Configuration
# ==============================================================================

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly INSTALL_DIR="$(dirname "$SCRIPT_DIR")"
readonly WINE_PREFIX="${INSTALL_DIR}/.mt5"

# Export WINEPREFIX globally - critical for Wine prefix isolation
export WINEPREFIX="${WINE_PREFIX}"
export WINEARCH="win64"

readonly RPYC_VERSION="5.0.1"
readonly RPYC_PORT="18812"
readonly THINLINC_VERSION="4.17.0"
readonly THINLINC_BUILD="3490"

# Python Windows installer URL (64-bit)
readonly PYTHON_WIN_URL="https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe"
readonly PYTHON_WIN_INSTALLER="python-3.12.8-amd64.exe"

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# ==============================================================================
# Utility Functions
# ==============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

die() {
    log_error "$1"
    exit 1
}

check_ubuntu_version() {
    if [[ ! -f /etc/os-release ]]; then
        die "Cannot detect OS version. This script requires Ubuntu 24.04 LTS."
    fi

    source /etc/os-release

    if [[ "${ID}" != "ubuntu" ]]; then
        die "This script requires Ubuntu. Detected: ${ID}"
    fi

    if [[ "${VERSION_ID}" != "24.04" ]]; then
        die "This script requires Ubuntu 24.04 LTS. Detected: ${VERSION_ID}"
    fi

    log_success "Ubuntu 24.04 LTS detected"
}

detect_display_server() {
    # Check if running on a server (no X server) or desktop
    if [[ -z "${DISPLAY:-}" ]] && [[ -z "${WAYLAND_DISPLAY:-}" ]]; then
        echo "server"
    elif [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
        echo "wayland"
    else
        echo "xorg"
    fi
}

is_server_mode() {
    local display_server
    display_server=$(detect_display_server)
    [[ "$display_server" == "server" ]]
}

is_wayland() {
    local display_server
    display_server=$(detect_display_server)
    [[ "$display_server" == "wayland" ]]
}

command_exists() {
    command -v "$1" &> /dev/null
}

# ==============================================================================
# Sudo Management
# ==============================================================================

SUDO_KEEPALIVE_PID=""

check_sudo_access() {
    log_info "Checking sudo access..."

    if [[ $EUID -eq 0 ]]; then
        die "Do not run this script as root. Run as normal user with sudo privileges."
    fi

    if ! sudo -v 2>/dev/null; then
        die "This script requires sudo privileges. Please ensure you can run sudo."
    fi

    log_success "Sudo access verified"
}

start_sudo_keepalive() {
    # Keep sudo timestamp fresh in the background
    # Refreshes every 50 seconds (default sudo timeout is 5-15 minutes)
    log_info "Starting sudo keepalive..."

    (
        while true; do
            sudo -n true 2>/dev/null
            sleep 50
        done
    ) &
    SUDO_KEEPALIVE_PID=$!

    # Ensure cleanup on script exit
    trap cleanup_sudo_keepalive EXIT INT TERM
}

cleanup_sudo_keepalive() {
    if [[ -n "${SUDO_KEEPALIVE_PID}" ]] && kill -0 "${SUDO_KEEPALIVE_PID}" 2>/dev/null; then
        kill "${SUDO_KEEPALIVE_PID}" 2>/dev/null || true
        wait "${SUDO_KEEPALIVE_PID}" 2>/dev/null || true
        log_info "Sudo keepalive stopped"
    fi
}

# ==============================================================================
# Installation Functions
# ==============================================================================

install_base_dependencies() {
    log_info "Installing base dependencies..."

    sudo apt-get update
    sudo apt-get install -y \
        wget \
        curl \
        gnupg2 \
        software-properties-common \
        apt-transport-https \
        ca-certificates \
        cabextract \
        xdg-utils \
        xvfb \
        x11-utils \
        xdotool \
        netcat-openbsd

    log_success "Base dependencies installed"
}

install_python_linux() {
    log_info "Installing Python 3 on Linux..."

    # Ubuntu 24.04 ships with Python 3.12 by default
    sudo apt-get install -y \
        python3 \
        python3-venv \
        python3-dev \
        python3-pip

    log_success "Python 3 installed on Linux"
}

install_wine_staging() {
    log_info "Installing Wine Staging from WineHQ..."

    # Enable 32-bit architecture
    sudo dpkg --add-architecture i386

    # Add WineHQ GPG key
    sudo mkdir -pm755 /etc/apt/keyrings
    sudo wget -O /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key

    # Add WineHQ repository for Ubuntu 24.04 (noble)
    sudo wget -NP /etc/apt/sources.list.d/ https://dl.winehq.org/wine-builds/ubuntu/dists/noble/winehq-noble.sources

    sudo apt-get update

    # Install Wine Staging
    sudo apt-get install -y --install-recommends winehq-staging

    log_success "Wine Staging installed"
}

setup_wine_prefix() {
    log_info "Setting up Wine prefix at ${WINE_PREFIX}..."

    export WINEPREFIX="${WINE_PREFIX}"
    export WINEARCH="win64"

    # Initialize Wine prefix
    if [[ ! -d "${WINE_PREFIX}" ]]; then
        mkdir -p "${WINE_PREFIX}"
        # Initialize with wineboot, suppress GUI dialogs
        # Temporarily unset WAYLAND_DISPLAY to ensure X11-compatible prefix initialization
        local saved_wayland="${WAYLAND_DISPLAY:-}"
        unset WAYLAND_DISPLAY
        DISPLAY="${DISPLAY:-:0}" wineboot --init 2>/dev/null || true
        if [[ -n "$saved_wayland" ]]; then
            export WAYLAND_DISPLAY="$saved_wayland"
        fi
        log_info "Waiting for Wine prefix initialization..."
        sleep 5
    fi

    log_success "Wine prefix ready at ${WINE_PREFIX}"
}

install_python_wine() {
    log_info "Installing Python 3.12 for Windows via Wine..."

    export WINEPREFIX="${WINE_PREFIX}"
    export WINEARCH="win64"

    local download_dir="${WINE_PREFIX}/downloads"
    mkdir -p "${download_dir}"

    # Download Python installer if not present
    if [[ ! -f "${download_dir}/${PYTHON_WIN_INSTALLER}" ]]; then
        log_info "Downloading Python 3.12 Windows installer..."
        wget -q -O "${download_dir}/${PYTHON_WIN_INSTALLER}" "${PYTHON_WIN_URL}"
    fi

    log_info "Running Python installer (silent mode)..."

    local xvfb_pid=""

    # Run Python installer with silent options
    # Use Xvfb for headless installation if no display
    if [[ -z "${DISPLAY:-}" ]]; then
        log_info "No display detected, using Xvfb..."
        Xvfb :99 -screen 0 1024x768x24 &
        xvfb_pid=$!
        export DISPLAY=:99
        sleep 2
    fi

    # Silent install: /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
    wine "${download_dir}/${PYTHON_WIN_INSTALLER}" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 TargetDir="C:\\Python312" || true

    # Wait for installation to complete
    log_info "Waiting for Python installation to complete..."
    sleep 30

    # Kill Xvfb if we started it
    if [[ -n "${xvfb_pid}" ]]; then
        kill "${xvfb_pid}" 2>/dev/null || true
        unset DISPLAY
    fi

    # Find Python executable
    local python_exe
    python_exe=$(find_wine_python)

    if [[ -n "$python_exe" ]]; then
        log_success "Python for Windows installed at: ${python_exe}"
    else
        log_warn "Python installation may have failed. Will retry detection later."
    fi
}

find_wine_python() {
    export WINEPREFIX="${WINE_PREFIX}"

    local possible_paths=(
        "${WINE_PREFIX}/drive_c/Python312/python.exe"
        "${WINE_PREFIX}/drive_c/users/${USER}/Local Settings/Application Data/Programs/Python/Python312/python.exe"
        "${WINE_PREFIX}/drive_c/users/${USER}/AppData/Local/Programs/Python/Python312/python.exe"
    )

    for path in "${possible_paths[@]}"; do
        if [[ -f "$path" ]]; then
            echo "$path"
            return 0
        fi
    done

    # Search for python.exe
    find "${WINE_PREFIX}/drive_c" -name "python.exe" -path "*Python31*" 2>/dev/null | head -1
}

install_python_packages_linux() {
    log_info "Installing Python packages on Linux..."

    # Create a virtual environment for mt5linux to avoid PEP 668 restrictions
    local venv_dir="${INSTALL_DIR}/.venv"

    # Create or recreate venv if pip is missing
    if [[ ! -x "${venv_dir}/bin/pip" ]]; then
        log_info "Creating virtual environment at ${venv_dir}..."
        rm -rf "${venv_dir}"
        "python3" -m venv "${venv_dir}"
    fi

    # Install packages in the virtual environment
    "${venv_dir}/bin/pip" install --upgrade pip
    "${venv_dir}/bin/pip" install "rpyc==${RPYC_VERSION}"
    "${venv_dir}/bin/pip" install mt5linux

    log_success "Linux Python packages installed in ${venv_dir}"
    log_info "Activate with: source ${venv_dir}/bin/activate"
}

install_python_packages_wine() {
    log_info "Installing Python packages on Windows (via Wine)..."

    export WINEPREFIX="${WINE_PREFIX}"

    local python_exe
    python_exe=$(find_wine_python)

    if [[ -z "$python_exe" ]]; then
        die "Cannot find Python executable in Wine prefix"
    fi

    local xvfb_pid=""

    # Set display for Wine operations
    if [[ -z "${DISPLAY:-}" ]]; then
        Xvfb :99 -screen 0 1024x768x24 &
        xvfb_pid=$!
        export DISPLAY=:99
        sleep 2
    fi

    # Upgrade pip
    log_info "Upgrading pip in Wine Python..."
    wine "$python_exe" -m pip install --upgrade pip 2>/dev/null || true

    # Install rpyc with exact version
    log_info "Installing rpyc==${RPYC_VERSION}..."
    wine "$python_exe" -m pip install "rpyc==${RPYC_VERSION}" 2>/dev/null || true

    # Install MetaTrader5 library
    log_info "Installing MetaTrader5 library..."
    wine "$python_exe" -m pip install --upgrade MetaTrader5 2>/dev/null || true

    # Install mt5linux
    log_info "Installing mt5linux..."
    wine "$python_exe" -m pip install mt5linux 2>/dev/null || true

    # Kill Xvfb if we started it
    if [[ -n "${xvfb_pid}" ]]; then
        kill "${xvfb_pid}" 2>/dev/null || true
        unset DISPLAY
    fi

    log_success "Windows Python packages installed"
}

# ==============================================================================
# Server Mode Setup (ThinLinc + XFCE4)
# ==============================================================================

install_xserver_and_xfce() {
    log_info "Installing X server and XFCE4 desktop environment..."

    sudo apt-get install -y \
        xorg \
        xserver-xorg \
        xfce4 \
        xfce4-goodies \
        lightdm \
        dbus-x11

    # Enable lightdm
    sudo systemctl enable lightdm

    log_success "X server and XFCE4 installed"
}

install_thinlinc_server() {
    log_info "Installing ThinLinc server..."

    local thinlinc_url="https://www.cendio.com/downloads/server/tl-${THINLINC_VERSION}-server.zip"
    local download_dir="/tmp/thinlinc-install"

    mkdir -p "${download_dir}"
    cd "${download_dir}"

    # Download ThinLinc server bundle
    if [[ ! -f "tl-${THINLINC_VERSION}-server.zip" ]]; then
        log_info "Downloading ThinLinc server ${THINLINC_VERSION}..."
        wget -q --show-progress "${thinlinc_url}" -O "tl-${THINLINC_VERSION}-server.zip"
    fi

    # Extract
    log_info "Extracting ThinLinc server..."
    unzip -o -q "tl-${THINLINC_VERSION}-server.zip"

    # Run installer (non-interactive)
    cd "tl-${THINLINC_VERSION}-server"
    log_info "Running ThinLinc installer..."
    sudo ./install-server <<EOF
y
EOF

    # Clean up
    cd /
    rm -rf "${download_dir}"

    # Configure ThinLinc for XFCE
    log_info "Configuring ThinLinc for XFCE desktop..."
    sudo tl-config /vsmagent/default_session startxfce4 2>/dev/null || true

    # Enable and start ThinLinc services
    log_info "Starting ThinLinc services..."
    sudo systemctl enable tlwebadm vsmserver vsmagent 2>/dev/null || true
    sudo systemctl start tlwebadm vsmserver vsmagent 2>/dev/null || true

    # Open firewall ports if ufw is active
    if command_exists ufw && sudo ufw status | grep -q "active"; then
        log_info "Opening firewall ports for ThinLinc..."
        sudo ufw allow 22/tcp comment "SSH/ThinLinc" 2>/dev/null || true
        sudo ufw allow 1010/tcp comment "ThinLinc WebAdmin" 2>/dev/null || true
        sudo ufw allow 300/tcp comment "ThinLinc HTML5" 2>/dev/null || true
    fi

    log_success "ThinLinc server installed and running"
}

# ==============================================================================
# Wayland Configuration
# ==============================================================================

configure_wine_wayland() {
    log_info "Configuring Wine for Wayland..."

    export WINEPREFIX="${WINE_PREFIX}"

    # Create helper scripts for both modes
    local bin_dir="${INSTALL_DIR}/bin"
    mkdir -p "${bin_dir}"

    # Script to run Wine with native Wayland driver
    cat > "${bin_dir}/wine-wayland" << 'EOFWAYLAND'
#!/usr/bin/env bash
# Run Wine with native Wayland driver (Wine 10+)
# Unset DISPLAY to force Wayland mode
export WINEPREFIX="${MT5_WINE_PREFIX:-$HOME/.mt5}"
unset DISPLAY
exec wine "$@"
EOFWAYLAND
    chmod +x "${bin_dir}/wine-wayland"

    # Script to run Wine with XWayland (fallback)
    cat > "${bin_dir}/wine-xwayland" << 'EOFXWAYLAND'
#!/usr/bin/env bash
# Run Wine with XWayland mode
export WINEPREFIX="${MT5_WINE_PREFIX:-$HOME/.mt5}"
# Keep DISPLAY set for XWayland
exec wine "$@"
EOFXWAYLAND
    chmod +x "${bin_dir}/wine-xwayland"

    # Update Wine prefix path in scripts
    sed -i "s|\$HOME/.mt5|${WINE_PREFIX}|g" "${bin_dir}/wine-wayland"
    sed -i "s|\$HOME/.mt5|${WINE_PREFIX}|g" "${bin_dir}/wine-xwayland"

    # Note: We intentionally do NOT configure Wine's graphics driver via registry.
    # Wine's auto-detection works better for both native Wayland and XWayland modes.
    # Forcing "x11,wayland" can cause input issues (no cursor, ignored keystrokes) in XWayland.

    log_success "Wine Wayland configuration complete"
    log_info "Use '${bin_dir}/wine-wayland' for native Wayland mode"
    log_info "Use '${bin_dir}/wine-xwayland' for XWayland fallback"
}

# ==============================================================================
# MT5 Terminal Installation
# ==============================================================================

readonly MT5_SETUP_URL="https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe"
readonly WEBVIEW2_URL="https://go.microsoft.com/fwlink/p/?LinkId=2124703"

install_mt5_terminal() {
    log_info "Installing MetaTrader 5 terminal..."

    export WINEPREFIX="${WINE_PREFIX}"
    export WINEARCH="win64"

    local download_dir="${WINE_PREFIX}/downloads"
    mkdir -p "${download_dir}"

    local display_mode
    display_mode=$(detect_display_server)

    # Check if we have a display
    if [[ "$display_mode" == "server" ]] && [[ -z "${DISPLAY:-}" ]]; then
        die "No display available. Please connect via ThinLinc first, then run this phase."
    fi

    # Download MT5 installer
    if [[ ! -f "${download_dir}/mt5setup.exe" ]]; then
        log_info "Downloading MT5 installer..."
        wget -q --show-progress -O "${download_dir}/mt5setup.exe" "${MT5_SETUP_URL}"
    fi

    # Download WebView2 runtime (required for MT5 web features)
    if [[ ! -f "${download_dir}/MicrosoftEdgeWebView2RuntimeInstallerX64.exe" ]]; then
        log_info "Downloading WebView2 runtime..."
        wget -q --show-progress -O "${download_dir}/MicrosoftEdgeWebView2RuntimeInstallerX64.exe" "${WEBVIEW2_URL}"
    fi

    # Configure Wine to emulate Windows 10 (better compatibility than Win11 for MT5)
    log_info "Configuring Wine for Windows 10 emulation..."
    wine reg add "HKEY_CURRENT_USER\\Software\\Wine" /v Version /t REG_SZ /d "win10" /f 2>/dev/null || true

    # Handle display mode for Wine
    case "$display_mode" in
        wayland)
            install_mt5_wayland
            ;;
        xorg|server)
            install_mt5_xorg
            ;;
        *)
            log_warn "Unknown display mode: ${display_mode}. Attempting standard installation."
            install_mt5_xorg
            ;;
    esac
}

install_mt5_xorg() {
    log_info "Installing MT5 (X11/Xorg mode)..."

    # Ensure Wine prefix is explicitly set for this function
    export WINEPREFIX="${WINE_PREFIX}"
    export WINEARCH="win64"

    local download_dir="${WINE_PREFIX}/downloads"

    # Install WebView2 silently first
    log_info "Installing WebView2 runtime (silent)..."
    wine "${download_dir}/MicrosoftEdgeWebView2RuntimeInstallerX64.exe" /silent /install 2>/dev/null || true
    sleep 5

    # Run MT5 installer
    log_info "Launching MT5 installer..."
    log_info "Please complete the MT5 installation wizard."
    log_warn "DO NOT change the installation path - use the default."
    echo ""

    wine "${download_dir}/mt5setup.exe" 2>/dev/null

    # Wait for user to complete installation
    log_info "Waiting for MT5 installation to complete..."
    wait_for_mt5_installation

    log_success "MT5 installation complete"
}

install_mt5_wayland() {
    log_info "Installing MT5 (Wayland mode)..."

    # Ensure Wine prefix is explicitly set for this function
    export WINEPREFIX="${WINE_PREFIX}"
    export WINEARCH="win64"

    log_info "Wayland detected. You have two options:"
    echo ""
    echo "  1. Native Wayland mode (Wine 10+) - Better integration, may have minor issues"
    echo "  2. XWayland mode - More compatible, uses X11 compatibility layer"
    echo ""

    local choice
    read -rp "Choose mode [1/2] (default: 2): " choice
    choice="${choice:-2}"

    local download_dir="${WINE_PREFIX}/downloads"

    case "$choice" in
        1)
            log_info "Using native Wayland mode..."
            # Unset DISPLAY to force Wine to use Wayland
            local saved_display="${DISPLAY:-}"
            unset DISPLAY

            # Install WebView2
            log_info "Installing WebView2 runtime..."
            wine "${download_dir}/MicrosoftEdgeWebView2RuntimeInstallerX64.exe" /silent /install 2>/dev/null || true
            sleep 5

            # Run MT5 installer
            log_info "Launching MT5 installer (Wayland native)..."
            log_warn "If you experience input issues, restart with XWayland mode (option 2)."
            wine "${download_dir}/mt5setup.exe" 2>/dev/null

            # Restore DISPLAY
            if [[ -n "$saved_display" ]]; then
                export DISPLAY="$saved_display"
            fi
            ;;
        2)
            log_info "Using XWayland mode..."
            # Unset WAYLAND_DISPLAY to force Wine to use X11 driver via XWayland
            # Keep DISPLAY set for XWayland
            local saved_wayland_display="${WAYLAND_DISPLAY:-}"
            unset WAYLAND_DISPLAY

            # Configure Wine for better XWayland compatibility (per ArchWiki recommendations)
            # UseTakeFocus=N helps with keyboard focus issues
            log_info "Configuring Wine for XWayland compatibility..."
            wine reg add "HKEY_CURRENT_USER\\Software\\Wine\\X11 Driver" /v UseTakeFocus /t REG_SZ /d N /f 2>/dev/null || true

            # Install WebView2
            log_info "Installing WebView2 runtime..."
            wine "${download_dir}/MicrosoftEdgeWebView2RuntimeInstallerX64.exe" /silent /install 2>/dev/null || true
            sleep 5

            # Run MT5 installer with virtual desktop to fix cursor/input issues on XWayland
            log_info "Launching MT5 installer (XWayland with virtual desktop)..."
            log_info "Virtual desktop helps fix mouse/keyboard issues on Wayland compositors."
            wine explorer /desktop=MT5Install,1280x1024 "${download_dir}/mt5setup.exe" 2>/dev/null

            # Restore WAYLAND_DISPLAY
            if [[ -n "$saved_wayland_display" ]]; then
                export WAYLAND_DISPLAY="$saved_wayland_display"
            fi
            ;;
        *)
            log_warn "Invalid choice. Using XWayland mode."
            install_mt5_xorg
            return
            ;;
    esac

    wait_for_mt5_installation
    log_success "MT5 installation complete"
}

wait_for_mt5_installation() {
    # Wait for MT5 installation to complete by checking for terminal64.exe
    local max_wait=600  # 10 minutes max
    local wait_interval=5
    local elapsed=0

    log_info "Waiting for MT5 terminal to be installed..."

    while [[ $elapsed -lt $max_wait ]]; do
        # Check if terminal64.exe exists
        if find "${WINE_PREFIX}/drive_c" -name "terminal64.exe" 2>/dev/null | grep -q .; then
            log_success "MT5 terminal detected"
            return 0
        fi

        # Check if installer is still running
        if ! pgrep -f "mt5setup.exe" > /dev/null 2>&1; then
            # Installer finished, check if MT5 was installed
            sleep 3
            if find "${WINE_PREFIX}/drive_c" -name "terminal64.exe" 2>/dev/null | grep -q .; then
                log_success "MT5 terminal detected"
                return 0
            else
                log_warn "MT5 installer closed but terminal not found."
                log_info "You may need to run the installer again."
                return 1
            fi
        fi

        sleep "$wait_interval"
        ((elapsed += wait_interval))
    done

    log_warn "Timeout waiting for MT5 installation."
    return 1
}

create_mt5_launcher() {
    log_info "Creating MT5 launcher script..."

    local bin_dir="${INSTALL_DIR}/bin"
    mkdir -p "${bin_dir}"

    local display_mode
    display_mode=$(detect_display_server)

    # Find MT5 terminal
    local mt5_exe
    mt5_exe=$(find "${WINE_PREFIX}/drive_c" -name "terminal64.exe" 2>/dev/null | head -1)

    if [[ -z "$mt5_exe" ]]; then
        log_warn "MT5 terminal not found. Launcher will search at runtime."
        mt5_exe="\$(find \"${WINE_PREFIX}/drive_c\" -name \"terminal64.exe\" 2>/dev/null | head -1)"
    fi

    # Create launcher based on display mode
    if [[ "$display_mode" == "wayland" ]]; then
        cat > "${bin_dir}/start-mt5.sh" << EOFMT5
#!/usr/bin/env bash
# Start MetaTrader 5 terminal (Wayland-aware)

set -euo pipefail

export WINEPREFIX="${WINE_PREFIX}"
export WINEARCH="win64"

MT5_EXE="\$(find "${WINE_PREFIX}/drive_c" -name "terminal64.exe" 2>/dev/null | head -1)"

if [[ -z "\$MT5_EXE" ]]; then
    echo "Error: Cannot find MT5 terminal. Please install MT5 first."
    exit 1
fi

# Check for Wayland
if [[ -n "\${WAYLAND_DISPLAY:-}" ]]; then
    echo "Wayland detected. Choose mode:"
    echo "  1. Native Wayland (unset DISPLAY)"
    echo "  2. XWayland with virtual desktop (recommended for input compatibility)"
    read -rp "Choice [1/2] (default: 2): " choice
    choice="\${choice:-2}"

    if [[ "\$choice" == "1" ]]; then
        echo "Starting MT5 in native Wayland mode..."
        unset DISPLAY
        echo "Starting MetaTrader 5..."
        wine "\$MT5_EXE" &
    else
        echo "Starting MT5 in XWayland mode with virtual desktop..."
        # Unset WAYLAND_DISPLAY to force X11 driver
        unset WAYLAND_DISPLAY
        # Use virtual desktop to fix cursor/input issues (per ArchWiki)
        wine explorer /desktop=MT5,1920x1080 "\$MT5_EXE" &
    fi
else
    echo "Starting MetaTrader 5..."
    wine "\$MT5_EXE" &
fi
EOFMT5
    else
        cat > "${bin_dir}/start-mt5.sh" << EOFMT5
#!/usr/bin/env bash
# Start MetaTrader 5 terminal

set -euo pipefail

export WINEPREFIX="${WINE_PREFIX}"
export WINEARCH="win64"

MT5_EXE="\$(find "${WINE_PREFIX}/drive_c" -name "terminal64.exe" 2>/dev/null | head -1)"

if [[ -z "\$MT5_EXE" ]]; then
    echo "Error: Cannot find MT5 terminal. Please install MT5 first."
    echo "Download from: https://www.metatrader5.com/en/download"
    exit 1
fi

echo "Starting MetaTrader 5..."
wine "\$MT5_EXE" &
EOFMT5
    fi

    chmod +x "${bin_dir}/start-mt5.sh"
    log_success "MT5 launcher created: ${bin_dir}/start-mt5.sh"
}

# ==============================================================================
# Systemd User Service for RPyC
# ==============================================================================

setup_rpyc_service() {
    log_info "Setting up systemd user service for RPyC server..."

    local service_dir="${HOME}/.config/systemd/user"
    mkdir -p "${service_dir}"

    local python_exe
    python_exe=$(find_wine_python)

    if [[ -z "$python_exe" ]]; then
        log_warn "Cannot find Wine Python. Service setup deferred to verify phase."
        return 0
    fi

    # Convert to Wine path format
    local python_exe_win
    python_exe_win=$(winepath -w "$python_exe" 2>/dev/null || echo "C:\\Python312\\python.exe")

    # Create service file
    cat > "${service_dir}/mt5-rpyc.service" << EOFSERVICE
[Unit]
Description=MT5 RPyC Server (Wine Python)
After=graphical-session.target
Wants=graphical-session.target

[Service]
Type=simple
Environment="WINEPREFIX=${WINE_PREFIX}"
Environment="WINEARCH=win64"
Environment="DISPLAY=:0"
ExecStart=/usr/bin/wine "${python_exe_win}" -m rpyc.bin.rpyc_classic --host localhost --port ${RPYC_PORT}
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
EOFSERVICE

    # Reload systemd user daemon
    systemctl --user daemon-reload

    log_success "RPyC systemd service created"
    log_info "Enable with: systemctl --user enable mt5-rpyc.service"
    log_info "Start with: systemctl --user start mt5-rpyc.service"
}

# ==============================================================================
# Environment Configuration
# ==============================================================================

create_env_file() {
    log_info "Creating environment configuration file..."

    local env_file="${INSTALL_DIR}/.mt5env"
    local python_win_path
    python_win_path=$(find_wine_python 2>/dev/null || echo 'not-found')

    local venv_dir="${INSTALL_DIR}/.venv"

    cat > "${env_file}" << EOFENV
# MT5 Linux Environment Configuration
# Source this file: source ${env_file}

export MT5_WINE_PREFIX="${WINE_PREFIX}"
export WINEPREFIX="${WINE_PREFIX}"
export WINEARCH="win64"
export MT5_RPYC_HOST="localhost"
export MT5_RPYC_PORT="${RPYC_PORT}"

# Python paths
export MT5_VENV="${venv_dir}"
export MT5_PYTHON_LINUX="${venv_dir}/bin/python"
export MT5_PYTHON_WIN="${python_win_path}"

# Activate venv helper
alias mt5-activate='source ${venv_dir}/bin/activate'
alias mt5-server='wine "\${MT5_PYTHON_WIN}" -m rpyc.bin.rpyc_classic --host localhost --port ${RPYC_PORT}'
alias mt5-python='wine "\${MT5_PYTHON_WIN}"'
EOFENV

    log_success "Environment file created: ${env_file}"
    log_info "Source it with: source ${env_file}"
}

create_launch_scripts() {
    log_info "Creating launch scripts..."

    local bin_dir="${INSTALL_DIR}/bin"
    mkdir -p "${bin_dir}"

    # RPyC server launcher
    cat > "${bin_dir}/start-rpyc-server.sh" << EOFRPYC
#!/usr/bin/env bash
# Start the RPyC server for MT5

set -euo pipefail

export WINEPREFIX="${WINE_PREFIX}"
export WINEARCH="win64"

PYTHON_EXE="\$(find "${WINE_PREFIX}/drive_c" -name "python.exe" -path "*Python31*" 2>/dev/null | head -1)"

if [[ -z "\$PYTHON_EXE" ]]; then
    echo "Error: Cannot find Python executable in Wine prefix"
    exit 1
fi

echo "Starting RPyC server on port ${RPYC_PORT}..."
wine "\$PYTHON_EXE" -m rpyc.bin.rpyc_classic --host localhost --port ${RPYC_PORT}
EOFRPYC
    chmod +x "${bin_dir}/start-rpyc-server.sh"

    # MT5 terminal launcher (with Wayland/XWayland support)
    cat > "${bin_dir}/start-mt5.sh" << EOFMT5
#!/usr/bin/env bash
# Start MetaTrader 5 terminal

set -euo pipefail

export WINEPREFIX="${WINE_PREFIX}"
export WINEARCH="win64"

MT5_EXE="\$(find "${WINE_PREFIX}/drive_c" -name "terminal64.exe" 2>/dev/null | head -1)"

if [[ -z "\$MT5_EXE" ]]; then
    echo "Error: Cannot find MT5 terminal. Please install MT5 first."
    echo "Download from: https://www.metatrader5.com/en/download"
    exit 1
fi

# Handle Wayland/XWayland
if [[ -n "\${WAYLAND_DISPLAY:-}" ]]; then
    echo "Wayland detected. Choose mode:"
    echo "  1. Native Wayland (unset DISPLAY)"
    echo "  2. XWayland with virtual desktop (recommended for input compatibility)"
    read -rp "Choice [1/2] (default: 2): " choice
    choice="\${choice:-2}"

    if [[ "\$choice" == "1" ]]; then
        echo "Starting MT5 in native Wayland mode..."
        unset DISPLAY
        wine "\$MT5_EXE" &
    else
        echo "Starting MT5 in XWayland mode with virtual desktop..."
        unset WAYLAND_DISPLAY
        wine explorer /desktop=MT5,1920x1080 "\$MT5_EXE" &
    fi
else
    echo "Starting MetaTrader 5..."
    wine "\$MT5_EXE" &
fi
EOFMT5
    chmod +x "${bin_dir}/start-mt5.sh"

    log_success "Launch scripts created in ${bin_dir}/"
}

# ==============================================================================
# Verification Phase
# ==============================================================================

verify_installation() {
    log_info "Running verification checks..."

    local errors=0

    # Check Wine installation
    log_info "Checking Wine..."
    if command_exists wine; then
        local wine_version
        wine_version=$(wine --version)
        log_success "Wine installed: ${wine_version}"
    else
        log_error "Wine not found"
        ((errors++))
    fi

    # Check Linux Python (venv)
    local venv_python="${INSTALL_DIR}/.venv/bin/python"
    log_info "Checking Linux Python (venv)..."

    if [[ -x "${venv_python}" ]]; then
        local py_version
        py_version=$("${venv_python}" --version)
        log_success "Linux Python (venv): ${py_version}"

        # Check rpyc version
        local rpyc_ver
        rpyc_ver=$("${venv_python}" -c "import rpyc; print(rpyc.__version__)" 2>/dev/null || echo "not installed")
        if [[ "$rpyc_ver" == "${RPYC_VERSION}" ]]; then
            log_success "Linux rpyc: ${rpyc_ver}"
        else
            log_warn "Linux rpyc version mismatch: ${rpyc_ver} (expected ${RPYC_VERSION})"
        fi

        # Check mt5linux
        if "${venv_python}" -c "import mt5linux" 2>/dev/null; then
            log_success "Linux mt5linux: installed"
        else
            log_error "Linux mt5linux: not installed"
            ((errors++))
        fi
    else
        log_error "Linux Python venv not found at ${venv_python}"
        ((errors++))
    fi

    # Check Windows Python
    log_info "Checking Windows Python (via Wine)..."
    export WINEPREFIX="${WINE_PREFIX}"

    local python_exe
    python_exe=$(find_wine_python)

    if [[ -n "$python_exe" ]] && [[ -f "$python_exe" ]]; then
        log_success "Windows Python found: ${python_exe}"

        # Check version
        if [[ -n "${DISPLAY:-}" ]]; then
            local win_py_ver
            win_py_ver=$(wine "$python_exe" --version 2>/dev/null || echo "unknown")
            log_success "Windows Python: ${win_py_ver}"

            # Check rpyc
            local win_rpyc
            win_rpyc=$(wine "$python_exe" -c "import rpyc; print(rpyc.__version__)" 2>/dev/null || echo "not installed")
            if [[ "$win_rpyc" == "${RPYC_VERSION}" ]]; then
                log_success "Windows rpyc: ${win_rpyc}"
            else
                log_warn "Windows rpyc version: ${win_rpyc} (expected ${RPYC_VERSION})"
            fi

            # Check MetaTrader5
            if wine "$python_exe" -c "import MetaTrader5" 2>/dev/null; then
                log_success "Windows MetaTrader5 library: installed"
            else
                log_warn "Windows MetaTrader5 library: not installed (install MT5 first)"
            fi
        else
            log_warn "No display available. Skipping Wine Python version checks."
        fi
    else
        log_error "Windows Python not found in Wine prefix"
        ((errors++))
    fi

    # Check MT5 terminal
    log_info "Checking MT5 terminal..."
    local mt5_exe
    mt5_exe=$(find "${WINE_PREFIX}/drive_c" -name "terminal64.exe" 2>/dev/null | head -1)

    if [[ -n "$mt5_exe" ]]; then
        log_success "MT5 terminal found: ${mt5_exe}"
    else
        log_warn "MT5 terminal not found. Please install MT5 manually."
        log_info "Download from: https://www.metatrader5.com/en/download"
    fi

    # Check systemd service
    log_info "Checking systemd service..."
    if [[ -f "${HOME}/.config/systemd/user/mt5-rpyc.service" ]]; then
        log_success "RPyC systemd service: configured"

        if systemctl --user is-enabled mt5-rpyc.service &>/dev/null; then
            log_success "RPyC service: enabled"
        else
            log_info "RPyC service: not enabled (run: systemctl --user enable mt5-rpyc.service)"
        fi
    else
        log_warn "RPyC systemd service: not configured"
    fi

    # Summary
    echo ""
    echo "=============================================="
    if [[ $errors -eq 0 ]]; then
        log_success "Verification complete: All checks passed!"
    else
        log_error "Verification complete: ${errors} error(s) found"
    fi
    echo "=============================================="

    return $errors
}

test_rpyc_connection() {
    log_info "Testing RPyC connection..."

    # Check if RPyC server is running
    if ! nc -z localhost "${RPYC_PORT}" 2>/dev/null; then
        log_warn "RPyC server is not running on port ${RPYC_PORT}"
        log_info "Start it with: ${INSTALL_DIR}/bin/start-rpyc-server.sh"
        return 1
    fi

    log_success "RPyC server is running on port ${RPYC_PORT}"

    # Test connection from Python (using venv)
    log_info "Testing Python connection..."

    local venv_python="${INSTALL_DIR}/.venv/bin/python"
    "${venv_python}" << EOFTEST
import rpyc
try:
    conn = rpyc.classic.connect('localhost', ${RPYC_PORT})
    # Test basic remote execution
    result = conn.modules.builtins.sum([1, 1])
    if result == 2:
        print('RPyC connection: OK')
        # Try importing MT5
        try:
            conn.execute('import MetaTrader5 as mt5')
            print('MetaTrader5 import: OK')
        except Exception as e:
            print(f'MetaTrader5 import: Failed ({e})')
    conn.close()
except Exception as e:
    print(f'RPyC connection failed: {e}')
    exit(1)
EOFTEST

    log_success "RPyC connection test complete"
}

# ==============================================================================
# Main Phases
# ==============================================================================

phase_preinstall() {
    log_info "=============================================="
    log_info "MT5 Linux Setup - Phase 1: Pre-installation"
    log_info "=============================================="
    echo ""

    # Verify sudo access and start keepalive
    check_sudo_access
    start_sudo_keepalive

    check_ubuntu_version

    local display_mode
    display_mode=$(detect_display_server)
    log_info "Detected display mode: ${display_mode}"

    # Install base dependencies
    install_base_dependencies

    # Install Python 3.12 on Linux
    install_python_linux

    # Install Wine Staging
    install_wine_staging

    # Server mode: install X server, XFCE4, ThinLinc
    if [[ "$display_mode" == "server" ]]; then
        log_info "Server mode detected. Installing graphical environment..."
        install_xserver_and_xfce
        install_thinlinc_server
    fi

    # Setup Wine prefix
    setup_wine_prefix

    # Install Python in Wine
    install_python_wine

    # Install Python packages
    install_python_packages_linux
    install_python_packages_wine

    # Configure Wayland if applicable
    if [[ "$display_mode" == "wayland" ]]; then
        configure_wine_wayland
    fi

    # Setup systemd service
    setup_rpyc_service

    # Create environment file and launch scripts
    create_env_file
    create_launch_scripts

    echo ""
    log_info "=============================================="
    log_success "Phase 1 (Pre-installation) complete!"
    log_info "=============================================="
    echo ""
    echo "==============================================================================="
    echo "                         INSTALLATION WORKFLOW"
    echo "==============================================================================="
    echo ""
    echo "  CURRENT STATUS: Pre-installation complete"
    echo ""
    echo "  NEXT STEP: Install MetaTrader 5 terminal"
    echo ""

    if [[ "$display_mode" == "server" ]]; then
        local server_ip
        server_ip=$(hostname -I | awk '{print $1}')

        echo "  You are on a SERVER. Follow these steps:"
        echo ""
        echo "==============================================================================="
        echo "                    THINLINC CONNECTION INSTRUCTIONS"
        echo "==============================================================================="
        echo ""
        echo "  STEP A: Download and install ThinLinc Client on your local machine"
        echo ""
        echo "    Download from: https://www.cendio.com/thinlinc/download"
        echo ""
        echo "    Available for:"
        echo "      - Windows: ThinLinc Client for Windows (.exe)"
        echo "      - macOS:   ThinLinc Client for macOS (.dmg)"
        echo "      - Linux:   ThinLinc Client for Linux (.deb or .rpm)"
        echo ""
        echo "  STEP B: Connect to this server using ThinLinc Client"
        echo ""
        echo "    Connection settings:"
        echo "    +-------------------------------------------------+"
        echo "    |  Server:     ${server_ip}"
        echo "    |  Username:   ${USER}"
        echo "    |  Password:   <your Linux user password>"
        echo "    +-------------------------------------------------+"
        echo ""
        echo "    Alternative: Use web browser (HTML5 client)"
        echo "      URL: https://${server_ip}:300/"
        echo ""
        echo "  STEP C: Once connected to the XFCE desktop, open a terminal and run:"
        echo ""
        echo "      cd ${INSTALL_DIR}"
        echo "      ./bin/mt5_setup.sh --phase=install-mt5"
        echo ""
        echo "-------------------------------------------------------------------------------"
        echo "  THINLINC ADMIN (optional)"
        echo "-------------------------------------------------------------------------------"
        echo ""
        echo "    Web Admin URL: https://${server_ip}:1010/"
        echo "    Default credentials: Set during first login"
        echo ""
    else
        echo "  Run the following command to install MT5:"
        echo ""
        echo "    cd ${INSTALL_DIR}"
        echo "    ./bin/mt5_setup.sh --phase=install-mt5"
        echo ""
    fi

    echo "-------------------------------------------------------------------------------"
    echo "  FULL WORKFLOW REFERENCE:"
    echo "-------------------------------------------------------------------------------"
    echo ""
    echo "    Phase 1: ./bin/mt5_setup.sh --phase=preinstall   [DONE]"
    echo "    Phase 2: ./bin/mt5_setup.sh --phase=install-mt5  <-- YOU ARE HERE"
    echo "    Phase 3: ./bin/mt5_setup.sh --phase=verify"
    echo ""
    echo "==============================================================================="
    echo ""
    log_info "Environment file: ${INSTALL_DIR}/.mt5env"
    log_info "Launch scripts:   ${INSTALL_DIR}/bin/"
}

phase_install_mt5() {
    log_info "=============================================="
    log_info "MT5 Linux Setup - Phase 2: Install MT5 Terminal"
    log_info "=============================================="
    echo ""

    local display_mode
    display_mode=$(detect_display_server)
    log_info "Detected display mode: ${display_mode}"

    # Install MT5 terminal
    install_mt5_terminal

    # Create/update MT5 launcher
    create_mt5_launcher

    echo ""
    log_info "=============================================="
    log_success "Phase 2 (MT5 Installation) complete!"
    log_info "=============================================="
    echo ""
    echo "==============================================================================="
    echo "                         INSTALLATION WORKFLOW"
    echo "==============================================================================="
    echo ""
    echo "  CURRENT STATUS: MT5 terminal installed"
    echo ""
    echo "  NEXT STEP: Verify the installation"
    echo ""
    echo "    Run the following command:"
    echo ""
    echo "      cd ${INSTALL_DIR}"
    echo "      ./bin/mt5_setup.sh --phase=verify"
    echo ""
    echo "-------------------------------------------------------------------------------"
    echo "  FULL WORKFLOW REFERENCE:"
    echo "-------------------------------------------------------------------------------"
    echo ""
    echo "    Phase 1: ./bin/mt5_setup.sh --phase=preinstall   [DONE]"
    echo "    Phase 2: ./bin/mt5_setup.sh --phase=install-mt5  [DONE]"
    echo "    Phase 3: ./bin/mt5_setup.sh --phase=verify       <-- YOU ARE HERE"
    echo ""
    echo "==============================================================================="
    echo ""
    echo "  QUICK START COMMANDS (after verification):"
    echo ""
    echo "    Start MT5 terminal:    ${INSTALL_DIR}/bin/start-mt5.sh"
    echo "    Start RPyC server:     ${INSTALL_DIR}/bin/start-rpyc-server.sh"
    echo "    Load environment:      source ${INSTALL_DIR}/.mt5env"
    echo ""
}

phase_verify() {
    log_info "=============================================="
    log_info "MT5 Linux Setup - Phase 3: Verification"
    log_info "=============================================="
    echo ""

    # Update systemd service with correct Python path
    setup_rpyc_service

    # Run verification
    verify_installation

    echo ""
    echo "==============================================================================="
    echo "                         INSTALLATION COMPLETE!"
    echo "==============================================================================="
    echo ""
    echo "  WORKFLOW STATUS:"
    echo ""
    echo "    Phase 1: ./bin/mt5_setup.sh --phase=preinstall   [DONE]"
    echo "    Phase 2: ./bin/mt5_setup.sh --phase=install-mt5  [DONE]"
    echo "    Phase 3: ./bin/mt5_setup.sh --phase=verify       [DONE]"
    echo ""
    echo "-------------------------------------------------------------------------------"
    echo "  HOW TO USE MT5 ON LINUX"
    echo "-------------------------------------------------------------------------------"
    echo ""
    echo "  STEP 1: Start the RPyC server (in one terminal)"
    echo ""
    echo "      ${INSTALL_DIR}/bin/start-rpyc-server.sh"
    echo ""
    echo "  STEP 2: Start MT5 terminal (in another terminal or keep RPyC running)"
    echo ""
    echo "      ${INSTALL_DIR}/bin/start-mt5.sh"
    echo ""
    echo "  STEP 3: Use MT5 from Python (in another terminal)"
    echo ""
    echo "      source ${INSTALL_DIR}/.venv/bin/activate"
    echo "      python"
    echo "      >>> from mt5linux import MetaTrader5"
    echo "      >>> mt5 = MetaTrader5(host='localhost', port=${RPYC_PORT})"
    echo "      >>> mt5.initialize()"
    echo "      >>> print(mt5.terminal_info())"
    echo ""
    echo "-------------------------------------------------------------------------------"
    echo "  OPTIONAL: Enable RPyC server auto-start"
    echo "-------------------------------------------------------------------------------"
    echo ""
    echo "      systemctl --user enable mt5-rpyc.service"
    echo "      systemctl --user start mt5-rpyc.service"
    echo ""
    echo "-------------------------------------------------------------------------------"
    echo "  OPTIONAL: Test RPyC connection"
    echo "-------------------------------------------------------------------------------"
    echo ""
    echo "      # Make sure RPyC server is running, then:"
    echo "      ./bin/mt5_setup.sh --phase=test-rpyc"
    echo ""
    echo "==============================================================================="
}

phase_test_rpyc() {
    log_info "=============================================="
    log_info "MT5 Linux Setup - RPyC Connection Test"
    log_info "=============================================="
    echo ""

    test_rpyc_connection
}

show_help() {
    cat << EOF
MT5 Linux Setup Script

Usage: $0 --phase=<phase>

Phases:
  preinstall    Install all dependencies (Wine, Python, packages)
  install-mt5   Install MetaTrader 5 terminal (handles Wayland/X11)
  verify        Verify installation
  test-rpyc     Test RPyC connection (requires running server)

Options:
  --help, -h    Show this help message

Installation workflow:
  1. Run: $0 --phase=preinstall
  2. If on server: Connect via ThinLinc client
  3. Run: $0 --phase=install-mt5
  4. Run: $0 --phase=verify

Environment variables:
  MT5_WINE_PREFIX    Override Wine prefix location
  MT5_RPYC_PORT      Override RPyC port (default: ${RPYC_PORT})

EOF
}

# ==============================================================================
# Entry Point
# ==============================================================================

main() {
    local phase=""

    # Parse arguments
    for arg in "$@"; do
        case $arg in
            --phase=*)
                phase="${arg#*=}"
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                die "Unknown argument: $arg. Use --help for usage."
                ;;
        esac
    done

    if [[ -z "$phase" ]]; then
        show_help
        exit 1
    fi

    case $phase in
        preinstall)
            phase_preinstall
            ;;
        install-mt5)
            phase_install_mt5
            ;;
        verify)
            phase_verify
            ;;
        test-rpyc)
            phase_test_rpyc
            ;;
        *)
            die "Unknown phase: $phase. Use --help for available phases."
            ;;
    esac
}

main "$@"
