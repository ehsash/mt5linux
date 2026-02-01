#!/usr/bin/env bash
# Environment detection utilities for mt5linux installation
# Detects display server, OS version, architecture, and installed components

set -euo pipefail

# Source common utilities if not already loaded
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
[[ -z "${COMMON_LOADED:-}" ]] && source "$SCRIPT_DIR/common.sh"
DETECT_LOADED=1

# Detect display server type
# Returns: wayland, xorg, or headless
detect_display_mode() {
    if [[ -n "${WAYLAND_DISPLAY:-}" ]]; then
        echo "wayland"
    elif [[ -n "${DISPLAY:-}" ]]; then
        echo "xorg"
    else
        echo "headless"
    fi
}

# Check if we're running in a graphical session
has_display() {
    local mode
    mode=$(detect_display_mode)
    [[ "$mode" != "headless" ]]
}

# Check if Wayland is the display server
is_wayland() {
    [[ -n "${WAYLAND_DISPLAY:-}" ]]
}

# Check if X11/Xorg is the display server
is_xorg() {
    [[ -z "${WAYLAND_DISPLAY:-}" && -n "${DISPLAY:-}" ]]
}

# Check if running headless (no display)
is_headless() {
    [[ -z "${WAYLAND_DISPLAY:-}" && -z "${DISPLAY:-}" ]]
}

# Detect Ubuntu version
# Returns version number (e.g., 24.04) or empty if not Ubuntu
detect_ubuntu_version() {
    if [[ -f /etc/os-release ]]; then
        # shellcheck source=/dev/null
        source /etc/os-release
        if [[ "${ID:-}" == "ubuntu" ]]; then
            echo "${VERSION_ID:-}"
            return 0
        fi
    fi
    return 1
}

# Check if running Ubuntu 24.04 LTS
is_ubuntu_2404() {
    local version
    version=$(detect_ubuntu_version) || return 1
    [[ "$version" == "24.04" ]]
}

# Get OS description
get_os_info() {
    if [[ -f /etc/os-release ]]; then
        # shellcheck source=/dev/null
        source /etc/os-release
        echo "${PRETTY_NAME:-Unknown}"
    else
        uname -a
    fi
}

# Detect architecture
detect_arch() {
    local arch
    arch=$(uname -m)
    case "$arch" in
        x86_64|amd64) echo "amd64" ;;
        aarch64|arm64) echo "arm64" ;;
        *) echo "$arch" ;;
    esac
}

# Check if running on 64-bit system
is_64bit() {
    [[ "$(detect_arch)" == "amd64" ]]
}

# Check if Wine is installed and get version
detect_wine_version() {
    if command_exists wine; then
        wine --version 2>/dev/null | head -1
    else
        return 1
    fi
}

# Check if Wine Staging is installed
is_wine_staging() {
    local version
    version=$(detect_wine_version) || return 1
    [[ "$version" == *"staging"* ]] || [[ "$version" == *"Staging"* ]]
}

# Check if a Wine prefix exists and is initialized
is_wine_prefix_valid() {
    local prefix=$1
    [[ -d "$prefix/drive_c" ]]
}

# Find Python executable in Wine prefix
find_wine_python() {
    local prefix=$1
    local python_exe="$prefix/drive_c/Python312/python.exe"

    if [[ -f "$python_exe" ]]; then
        echo "$python_exe"
        return 0
    fi

    # Search for any Python installation
    for py_dir in "$prefix/drive_c"/Python3*/; do
        if [[ -f "${py_dir}python.exe" ]]; then
            echo "${py_dir}python.exe"
            return 0
        fi
    done

    return 1
}

# Find MT5 terminal executable
find_mt5_terminal() {
    local prefix=$1
    local search_paths=(
        "$prefix/drive_c/Program Files/MetaTrader 5/terminal64.exe"
        "$prefix/drive_c/Program Files (x86)/MetaTrader 5/terminal64.exe"
    )

    for path in "${search_paths[@]}"; do
        if [[ -f "$path" ]]; then
            echo "$path"
            return 0
        fi
    done

    # Fallback: search for terminal64.exe
    local found
    found=$(find "$prefix/drive_c" -name "terminal64.exe" 2>/dev/null | head -1)
    if [[ -n "$found" ]]; then
        echo "$found"
        return 0
    fi

    return 1
}

# Check if X server is installed
is_xserver_installed() {
    command_exists Xorg || command_exists X
}

# Check if a desktop environment is installed
detect_desktop_environment() {
    if command_exists startxfce4; then
        echo "xfce"
    elif command_exists gnome-session; then
        echo "gnome"
    elif command_exists startplasma-x11 || command_exists startplasma-wayland; then
        echo "kde"
    else
        echo "none"
    fi
}

# Check if ThinLinc server is installed
is_thinlinc_installed() {
    command_exists tlwebadm || [[ -d /opt/thinlinc ]]
}

# Check if lightdm is active
is_lightdm_active() {
    systemctl is-active --quiet lightdm 2>/dev/null
}

# Get server IP address (first non-localhost)
get_server_ip() {
    hostname -I 2>/dev/null | awk '{print $1}'
}

# Check if running in WSL
is_wsl() {
    grep -qi microsoft /proc/version 2>/dev/null
}

# Check if running in Docker
is_docker() {
    [[ -f /.dockerenv ]] || grep -q docker /proc/1/cgroup 2>/dev/null
}

# Check if running in a VM
is_virtual_machine() {
    if command_exists systemd-detect-virt; then
        local virt
        virt=$(systemd-detect-virt 2>/dev/null)
        [[ "$virt" != "none" ]]
    else
        # Fallback: check DMI
        grep -qiE "virtual|vmware|qemu|kvm|xen|hyperv" /sys/class/dmi/id/product_name 2>/dev/null
    fi
}

# Print environment summary
print_environment_summary() {
    section "Environment Detection"

    log_info "OS: $(get_os_info)"
    log_info "Architecture: $(detect_arch)"

    local display_mode
    display_mode=$(detect_display_mode)
    case "$display_mode" in
        wayland) log_info "Display: Wayland (${WAYLAND_DISPLAY:-})" ;;
        xorg)    log_info "Display: X11/Xorg (${DISPLAY:-})" ;;
        headless) log_warn "Display: Headless (no display detected)" ;;
    esac

    if command_exists wine; then
        log_info "Wine: $(detect_wine_version)"
    else
        log_warn "Wine: Not installed"
    fi

    local desktop
    desktop=$(detect_desktop_environment)
    if [[ "$desktop" != "none" ]]; then
        log_info "Desktop: $desktop"
    fi

    if is_wsl; then
        log_warn "Running in WSL"
    elif is_docker; then
        log_warn "Running in Docker"
    elif is_virtual_machine; then
        log_info "Running in virtual machine"
    fi
}

# Validate that environment meets requirements
validate_environment() {
    local errors=0

    # Check Ubuntu 24.04
    if ! is_ubuntu_2404; then
        log_error "Ubuntu 24.04 LTS required. Found: $(detect_ubuntu_version 2>/dev/null || echo 'Not Ubuntu')"
        ((errors++))
    fi

    # Check 64-bit
    if ! is_64bit; then
        log_error "64-bit system required. Found: $(detect_arch)"
        ((errors++))
    fi

    # Check not root
    if [[ $EUID -eq 0 ]]; then
        log_error "Do not run as root"
        ((errors++))
    fi

    return $errors
}
