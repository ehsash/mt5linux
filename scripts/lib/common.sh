#!/usr/bin/env bash
# Common utilities for mt5linux installation scripts
# Provides logging, error handling, sudo management, and shared functions

set -euo pipefail

# Colors (only if terminal supports it)
if [[ -t 1 ]] && command -v tput &>/dev/null; then
    RED=$(tput setaf 1)
    GREEN=$(tput setaf 2)
    YELLOW=$(tput setaf 3)
    BLUE=$(tput setaf 4)
    MAGENTA=$(tput setaf 5)
    CYAN=$(tput setaf 6)
    BOLD=$(tput bold)
    RESET=$(tput sgr0)
else
    RED="" GREEN="" YELLOW="" BLUE="" MAGENTA="" CYAN="" BOLD="" RESET=""
fi

# Logging functions
log_info()    { echo "${BLUE}[INFO]${RESET} $*"; }
log_ok()      { echo "${GREEN}[OK]${RESET} $*"; }
log_warn()    { echo "${YELLOW}[WARN]${RESET} $*"; }
log_error()   { echo "${RED}[ERROR]${RESET} $*" >&2; }
log_step()    { echo "${CYAN}${BOLD}==> $*${RESET}"; }
log_substep() { echo "${MAGENTA}  -> $*${RESET}"; }

# Error handler
die() {
    log_error "$*"
    exit 1
}

# Check if running as root (we don't want that)
check_not_root() {
    if [[ $EUID -eq 0 ]]; then
        die "Do not run this script as root. It will use sudo when needed."
    fi
}

# Sudo keepalive - refresh sudo timestamp in background
# Usage: start_sudo_keepalive; trap stop_sudo_keepalive EXIT
SUDO_KEEPALIVE_PID=""

start_sudo_keepalive() {
    log_info "Requesting sudo privileges..."
    sudo -v || die "Failed to obtain sudo privileges"

    # Start background process to keep sudo alive
    (while true; do sudo -n true; sleep 50; done) 2>/dev/null &
    SUDO_KEEPALIVE_PID=$!
}

stop_sudo_keepalive() {
    if [[ -n "${SUDO_KEEPALIVE_PID:-}" ]]; then
        kill "$SUDO_KEEPALIVE_PID" 2>/dev/null || true
        SUDO_KEEPALIVE_PID=""
    fi
}

# Check if a command exists
command_exists() {
    command -v "$1" &>/dev/null
}

# Check if a package is installed (Debian/Ubuntu)
package_installed() {
    dpkg -l "$1" 2>/dev/null | grep -q "^ii"
}

# Wait for a process to complete with timeout
# Usage: wait_with_timeout PID TIMEOUT_SECONDS DESCRIPTION
wait_with_timeout() {
    local pid=$1
    local timeout=$2
    local description=$3
    local elapsed=0
    local interval=5

    while kill -0 "$pid" 2>/dev/null; do
        if [[ $elapsed -ge $timeout ]]; then
            log_error "Timeout waiting for: $description"
            kill "$pid" 2>/dev/null || true
            return 1
        fi
        sleep $interval
        elapsed=$((elapsed + interval))
        log_info "Waiting for $description... (${elapsed}s/${timeout}s)"
    done
    return 0
}

# Check if a port is in use
port_in_use() {
    local port=$1
    if command_exists ss; then
        ss -tuln 2>/dev/null | grep -q ":${port} "
    elif command_exists netstat; then
        netstat -tuln 2>/dev/null | grep -q ":${port} "
    else
        # Fallback: try to connect
        (echo >/dev/tcp/localhost/"$port") 2>/dev/null
    fi
}

# Test if a port responds to connection
test_port_connection() {
    local host=$1
    local port=$2
    local timeout=${3:-5}

    if command_exists nc; then
        nc -z -w "$timeout" "$host" "$port" 2>/dev/null
    elif command_exists timeout; then
        timeout "$timeout" bash -c "echo >/dev/tcp/$host/$port" 2>/dev/null
    else
        (echo >/dev/tcp/"$host"/"$port") 2>/dev/null
    fi
}

# Find available port starting from a base
find_available_port() {
    local start=${1:-18812}
    local end=${2:-18899}

    for ((port=start; port<=end; port++)); do
        if ! port_in_use "$port"; then
            echo "$port"
            return 0
        fi
    done
    return 1
}

# Download file with progress
download_file() {
    local url=$1
    local output=$2

    if command_exists wget; then
        wget -q --show-progress -O "$output" "$url"
    elif command_exists curl; then
        curl -# -L -o "$output" "$url"
    else
        die "Neither wget nor curl found. Install one of them."
    fi
}

# Create directory if not exists
ensure_dir() {
    local dir=$1
    if [[ ! -d "$dir" ]]; then
        mkdir -p "$dir"
        log_substep "Created directory: $dir"
    fi
}

# Backup a file before modifying
backup_file() {
    local file=$1
    if [[ -f "$file" ]]; then
        cp "$file" "${file}.bak.$(date +%Y%m%d_%H%M%S)"
    fi
}

# Parse .mt5env file and export variables
# Usage: source_mt5env /path/to/.mt5env
source_mt5env() {
    local env_file=$1

    if [[ ! -f "$env_file" ]]; then
        log_warn "Config file not found: $env_file"
        return 1
    fi

    # Read and export non-comment, non-empty lines
    while IFS='=' read -r key value; do
        # Skip comments and empty lines
        [[ -z "$key" || "$key" =~ ^# ]] && continue
        # Remove quotes from value
        value="${value%\"}"
        value="${value#\"}"
        value="${value%\'}"
        value="${value#\'}"
        # Export
        export "$key=$value"
    done < "$env_file"
}

# Write .mt5env file
# Usage: write_mt5env /path/to/.mt5env
write_mt5env() {
    local env_file=$1
    local wine_prefix=$2
    local rpyc_port=$3
    local rpyc_host=${4:-localhost}
    local venv_path=$5

    cat > "$env_file" << EOF
# MT5 Linux Configuration
# Auto-generated by mt5linux install script

MT5_WINE_PREFIX="${wine_prefix}"
MT5_RPYC_PORT=${rpyc_port}
MT5_RPYC_HOST="${rpyc_host}"
MT5_VENV="${venv_path}"
EOF
    log_ok "Configuration saved to: $env_file"
}

# Get the script's directory (works even with symlinks)
get_script_dir() {
    local source="${BASH_SOURCE[0]}"
    while [[ -L "$source" ]]; do
        local dir
        dir=$(cd -P "$(dirname "$source")" && pwd)
        source=$(readlink "$source")
        [[ $source != /* ]] && source="$dir/$source"
    done
    cd -P "$(dirname "$source")" && pwd
}

# Get project root (parent of scripts/)
get_project_root() {
    local script_dir
    script_dir=$(get_script_dir)
    dirname "$(dirname "$script_dir")"
}

# Confirm with user
# Usage: confirm "Are you sure?" && do_something
confirm() {
    local prompt="${1:-Continue?}"
    local default="${2:-y}"

    local yn_prompt
    if [[ "$default" == "y" ]]; then
        yn_prompt="[Y/n]"
    else
        yn_prompt="[y/N]"
    fi

    read -r -p "${prompt} ${yn_prompt} " response
    response=${response:-$default}

    [[ "$response" =~ ^[Yy] ]]
}

# Print a separator line
separator() {
    echo "${CYAN}────────────────────────────────────────────────────────────────${RESET}"
}

# Print section header
section() {
    echo
    separator
    echo "${BOLD}${CYAN}$*${RESET}"
    separator
}

