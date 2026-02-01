#!/usr/bin/env bash
# Install base system dependencies for mt5linux
# This script installs common packages needed before Wine and MT5

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/common.sh"
source "$SCRIPT_DIR/lib/detect.sh"

# Base packages needed for the installation process
BASE_PACKAGES=(
    wget
    curl
    gnupg2
    software-properties-common
    ca-certificates
    apt-transport-https
    xdg-utils
)

# X11 and display utilities
DISPLAY_PACKAGES=(
    xvfb
    x11-utils
    xdotool
    netcat-openbsd
)

# Python packages (for Linux side)
PYTHON_PACKAGES=(
    python3
    python3-venv
    python3-dev
    python3-pip
    pipx
)

# Server-only packages (X server and desktop for headless)
SERVER_XSERVER_PACKAGES=(
    xorg
    xserver-xorg
    xserver-xorg-video-dummy
    x11-xserver-utils
)

SERVER_DESKTOP_PACKAGES=(
    xfce4
    xfce4-goodies
    xfce4-terminal
    lightdm
    lightdm-gtk-greeter
    dbus-x11
    chromium-browser
)

install_packages() {
    local packages=("$@")
    local to_install=()

    for pkg in "${packages[@]}"; do
        if ! package_installed "$pkg"; then
            to_install+=("$pkg")
        fi
    done

    if [[ ${#to_install[@]} -eq 0 ]]; then
        log_ok "All packages already installed"
        return 0
    fi

    log_info "Installing: ${to_install[*]}"
    sudo apt-get install -y "${to_install[@]}"
}

install_base_dependencies() {
    section "Installing Base Dependencies"

    log_step "Updating package lists"
    sudo apt-get update

    log_step "Installing base packages"
    install_packages "${BASE_PACKAGES[@]}"

    log_step "Installing display utilities"
    install_packages "${DISPLAY_PACKAGES[@]}"

    log_step "Installing Python packages"
    install_packages "${PYTHON_PACKAGES[@]}"

    log_ok "Base dependencies installed"
}

install_python_tools() {
    section "Installing Python Development Tools"

    # Ensure pipx path is available
    log_step "Ensuring pipx is on PATH"
    pipx ensurepath 2>/dev/null || true

    # Add pipx bin to current PATH for this session
    export PATH="$HOME/.local/bin:$PATH"

    log_step "Installing hatch (Python project manager)"
    if command_exists hatch; then
        log_ok "hatch already installed: $(hatch --version 2>/dev/null || echo 'unknown version')"
    else
        pipx install hatch
        log_ok "hatch installed"
    fi

    log_step "Installing uv (fast Python package installer)"
    if command_exists uv; then
        log_ok "uv already installed: $(uv --version 2>/dev/null || echo 'unknown version')"
    else
        pipx install uv
        log_ok "uv installed"
    fi

    log_ok "Python development tools installed"
    log_info "You may need to restart your shell or run: source ~/.bashrc"
}

install_xserver_for_headless() {
    section "Installing X Server for Headless Environment"

    if has_display; then
        log_info "Display already available, skipping X server installation"
        return 0
    fi

    log_step "Installing X server packages"
    install_packages "${SERVER_XSERVER_PACKAGES[@]}"

    log_step "Installing XFCE desktop environment"
    install_packages "${SERVER_DESKTOP_PACKAGES[@]}"

    log_step "Enabling lightdm service"
    sudo systemctl enable lightdm || log_warn "Could not enable lightdm"

    log_step "Configuring Chromium as default browser"
    configure_default_browser

    log_ok "X server and desktop environment installed"
    log_warn "A reboot may be required to start the graphical environment"
}

configure_default_browser() {
    # Set Chromium as default browser using xdg-settings
    # This works for XFCE and other XDG-compliant desktops

    local chromium_desktop="chromium-browser.desktop"

    # Check if chromium desktop file exists
    if [[ -f "/usr/share/applications/$chromium_desktop" ]]; then
        # Set as default web browser
        xdg-settings set default-web-browser "$chromium_desktop" 2>/dev/null || true

        # Set MIME types for web content
        xdg-mime default "$chromium_desktop" x-scheme-handler/http 2>/dev/null || true
        xdg-mime default "$chromium_desktop" x-scheme-handler/https 2>/dev/null || true
        xdg-mime default "$chromium_desktop" text/html 2>/dev/null || true
        xdg-mime default "$chromium_desktop" application/xhtml+xml 2>/dev/null || true

        # Also set in XFCE settings if available
        if command_exists xfconf-query; then
            xfconf-query -c exo -p /exo-helper/Web-Browser -s chromium-browser 2>/dev/null || true
        fi

        log_ok "Chromium configured as default browser"
    else
        log_warn "Chromium desktop file not found, skipping default browser configuration"
    fi
}

# ThinLinc installation for remote access to headless servers
install_thinlinc_server() {
    section "Installing ThinLinc Server"

    if is_thinlinc_installed; then
        log_ok "ThinLinc already installed"
        return 0
    fi

    local thinlinc_version="4.17.0"
    local thinlinc_url="https://www.cendio.com/downloads/server/tl-${thinlinc_version}-server.zip"
    local temp_dir
    temp_dir=$(mktemp -d)

    log_step "Downloading ThinLinc ${thinlinc_version}"
    download_file "$thinlinc_url" "$temp_dir/thinlinc.zip"

    log_step "Extracting ThinLinc"
    cd "$temp_dir"
    unzip -q thinlinc.zip

    log_step "Running ThinLinc installer (interactive)"
    log_warn "You will be prompted for configuration options"
    sudo "./tl-${thinlinc_version}-server/install-server"

    log_step "Configuring ThinLinc for XFCE"
    if command_exists tl-config; then
        sudo tl-config /vsmagent/default_session startxfce4
    fi

    log_step "Enabling ThinLinc services"
    for service in tlwebadm vsmserver vsmagent; do
        sudo systemctl enable "$service" 2>/dev/null || true
        sudo systemctl start "$service" 2>/dev/null || true
    done

    cd - >/dev/null
    rm -rf "$temp_dir"

    log_ok "ThinLinc installed and configured"

    local server_ip
    server_ip=$(get_server_ip)
    echo
    separator
    echo "${BOLD}ThinLinc Connection Instructions:${RESET}"
    echo
    echo "1. Download ThinLinc client from: https://www.cendio.com/thinlinc/download"
    echo "2. Connect to: ${server_ip}:22"
    echo "3. Login with your Ubuntu user credentials"
    echo "4. After connecting, run this installer again to continue MT5 setup"
    separator
}

show_usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS]

Install base system dependencies for mt5linux.

Options:
    --all           Install all base dependencies
    --xserver       Also install X server (for headless systems)
    --thinlinc      Also install ThinLinc server (for remote access)
    --check         Only check what would be installed
    -h, --help      Show this help message

Examples:
    $(basename "$0") --all                  # Install base dependencies
    $(basename "$0") --all --xserver        # Include X server for headless
    $(basename "$0") --all --thinlinc       # Include ThinLinc for remote access
EOF
}

main() {
    local install_all=false
    local install_xserver=false
    local install_thinlinc_flag=false
    local check_only=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            --all) install_all=true ;;
            --xserver) install_xserver=true ;;
            --thinlinc) install_thinlinc_flag=true ;;
            --check) check_only=true ;;
            -h|--help) show_usage; exit 0 ;;
            *) die "Unknown option: $1" ;;
        esac
        shift
    done

    check_not_root

    section "Base Dependencies Installation"
    print_environment_summary

    if ! validate_environment; then
        die "Environment validation failed"
    fi

    if $check_only; then
        log_info "Check mode: would install base packages"
        exit 0
    fi

    if ! $install_all; then
        show_usage
        exit 1
    fi

    start_sudo_keepalive
    trap stop_sudo_keepalive EXIT

    install_base_dependencies
    install_python_tools

    if $install_xserver || is_headless; then
        install_xserver_for_headless
    fi

    if $install_thinlinc_flag; then
        install_thinlinc_server
    fi

    section "Base Installation Complete"
    log_ok "All base dependencies installed successfully"
}

# Only run main if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
