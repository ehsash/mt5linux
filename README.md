# MetaTrader 5 for GNU/Linux

A package that uses [Wine](https://www.winehq.org), [RPyC](https://github.com/tomerfiliba-org/rpyc) and a Windows Python version to allow using [MetaTrader5](https://pypi.org/project/MetaTrader5) on GNU/Linux.

## Quick Start (Automated Installation)

The fastest way to get started on Ubuntu 24.04 (Desktop or Server):

```bash
git clone https://github.com/lucas-campagna/mt5linux.git
cd mt5linux
./scripts/install.sh full
```

This installs everything needed: Wine Staging, Windows Python, MetaTrader 5 terminal, and the RPyC bridge. All files are stored locally in the project folder.

After installation:

```bash
# Start MT5 and RPyC server
./bin/start-system.sh

# In Python
from mt5linux import MetaTrader5
mt5 = MetaTrader5(port=18812)
mt5.initialize()
mt5.terminal_info()

# When done
./bin/stop-system.sh
```

## Installation

### Automated Installation (Recommended)

The `scripts/` folder contains bash scripts that automate the entire installation process.

#### Supported Environments

| Environment                | Display    | Installation                          |
| -------------------------- | ---------- | ------------------------------------- |
| Ubuntu Desktop (X11)       | Native X11 | Standard                              |
| Ubuntu Desktop (Wayland)   | XWayland   | Standard (auto-detected)              |
| Ubuntu Server (headless)   | ThinLinc   | Auto-installs ThinLinc for remote GUI |

#### What Gets Installed

The installer sets up:

- **Wine Staging** - Windows compatibility layer (from WineHQ repository)
- **Windows Python 3.12** - Runs inside Wine prefix
- **MetaTrader 5 packages** - `MetaTrader5` and `rpyc` Python packages (Windows side)
- **MT5 Terminal** - Downloaded and installed automatically
- **Development tools** - `pipx`, `hatch`, `uv` for Python development
- **Chromium browser** - Default browser on server installations

#### File Locations

All files are stored locally in the project folder (fully isolated):

```text
project/
├── .mt5/                    # Wine prefix (contains MT5, Windows Python)
├── .mt5env                  # Configuration file
├── .mt5-install-state       # Installation progress tracker
└── bin/                     # Launcher scripts
    ├── start-system.sh      # Start MT5 + RPyC server
    ├── stop-system.sh       # Stop everything
    ├── start-mt5.sh         # Start MT5 terminal only
    ├── start-rpyc-server.sh # Start RPyC server only
    └── system-status.sh     # Show system status
```

### Ubuntu Desktop Installation

```bash
# Clone the repository
git clone https://github.com/lucas-campagna/mt5linux.git
cd mt5linux

# Run the installer
./scripts/install.sh full
```

The installer will:

1. Install base dependencies (wget, curl, Python, pipx, hatch, uv)
2. Add WineHQ repository and install Wine Staging
3. Create a Wine prefix with Windows Python
4. Download and install MetaTrader 5
5. Configure RPyC server and create launcher scripts

### Ubuntu Server Installation (Headless)

On headless servers, the installer automatically installs [ThinLinc](https://www.cendio.com/thinlinc) for remote GUI access:

```bash
# Clone the repository
git clone https://github.com/lucas-campagna/mt5linux.git
cd mt5linux

# Run the installer (ThinLinc auto-installed on headless)
./scripts/install.sh full
```

After ThinLinc installation completes:

1. Download the [ThinLinc client](https://www.cendio.com/thinlinc/download)
2. Connect to your server (port 22)
3. Login with your Ubuntu credentials
4. Resume installation:

```bash
cd mt5linux
./scripts/install.sh resume
```

If you prefer X server without remote access:

```bash
./scripts/install.sh full --xserver
```

### Installation Options

```text
./scripts/install.sh [OPTIONS] [COMMAND]

Commands:
    full            Full installation (default)
    resume          Resume from last incomplete phase
    phase PHASE     Run specific phase only (base, wine, mt5, rpyc, verify)
    verify          Verify installation
    status          Show current installation state

Options:
    --prefix PATH   Wine prefix path (default: ./.mt5)
    --port PORT     RPyC port (default: 18812)
    --host HOST     RPyC host (default: localhost)
    --name NAME     Instance name (default: directory name)
    --xserver       Install X server only (no ThinLinc)
    --thinlinc      Force ThinLinc installation
    -y, --yes       Non-interactive mode
```

### Manual Installation

For manual installation without the scripts:

1. Install [Wine](https://wiki.winehq.org/Download)
2. Install [Python for Windows](https://www.python.org/downloads/windows/) via Wine
3. Install MT5 packages on Windows Python:

```bash
wine python.exe -m pip install MetaTrader5 rpyc
```

1. Install this package on Linux:

```bash
pip install mt5linux
```

## Usage

### Starting the System

```bash
# Start both MT5 terminal and RPyC server
./bin/start-system.sh

# Start MT5 terminal only (useful for initial broker login)
./bin/start-mt5.sh

# Start RPyC server only (if MT5 already running)
./bin/start-rpyc-server.sh
```

### Connecting from Python

```python
from mt5linux import MetaTrader5

# Connect to the RPyC server
mt5 = MetaTrader5(
    host='localhost',  # default
    port=18812         # default, or your custom port
)

# Initialize connection to MT5 terminal
mt5.initialize()

# Check terminal info
print(mt5.terminal_info())

# Get market data
rates = mt5.copy_rates_from_pos('EURUSD', mt5.TIMEFRAME_M1, 0, 1000)

# Place orders, manage positions, etc.
# See: https://www.mql5.com/en/docs/integration/python_metatrader5/

# Shutdown when done
mt5.shutdown()
```

### Stopping the System

```bash
# Stop everything (MT5 + RPyC server)
./bin/stop-system.sh

# Check status
./bin/system-status.sh
```

### Using as a Git Submodule (Recommended for Projects)

For trading projects managed with git, add mt5linux as a submodule:

```bash
# Create your trading project
mkdir ~/trading/my-strategy
cd ~/trading/my-strategy
git init

# Add mt5linux as a submodule
git submodule add https://github.com/lucas-campagna/mt5linux.git
git submodule update --init --recursive

# Install to the project root (not inside the submodule)
./mt5linux/scripts/install.sh full --project .
```

This creates the following structure:

```text
my-strategy/
├── mt5linux/                # Git submodule (tracked by git)
│   ├── scripts/
│   ├── mt5linux/
│   └── README.md
├── .mt5/                    # Wine prefix (gitignored)
├── .mt5env                  # Configuration (gitignored)
├── bin/                     # Launcher scripts
│   ├── start-system.sh
│   └── stop-system.sh
├── .gitignore
└── my_strategy.py           # Your trading code
```

Add to your `.gitignore`:

```gitignore
# MT5 Linux files
.mt5/
.mt5env
.mt5-install-state
```

After cloning your project on a new machine:

```bash
git clone --recurse-submodules https://github.com/you/my-strategy.git
cd my-strategy
./mt5linux/scripts/install.sh full --project .
git submodule update --init --recursive
```

### Running Multiple Instances

Each project folder is a fully isolated instance with its own Wine prefix and port:

```bash
# Strategy A (port 18812)
cd ~/trading/strategy-a
./mt5linux/scripts/install.sh full --project . --port 18812
./bin/start-system.sh

# Strategy B (port 18813)
cd ~/trading/strategy-b
./mt5linux/scripts/install.sh full --project . --port 18813
./bin/start-system.sh
```

Connect to each instance:

```python
mt5_a = MetaTrader5(port=18812)
mt5_b = MetaTrader5(port=18813)
```

Each instance has:

- Separate Wine prefix (different MT5 installations, broker accounts)
- Separate RPyC port (no conflicts)
- Separate configuration (`.mt5env`)

## Troubleshooting

### Diagnostics

Run the diagnostic script to check your installation:

```bash
./scripts/diagnose.sh
```

This reports:

- System information
- Display environment (X11/Wayland/headless)
- Wine installation status
- Wine prefix contents
- MT5 terminal location
- RPyC server status
- Network/port status
- Running processes

### Common Issues

#### Wine GUI Not Displaying on Wayland

The scripts automatically handle Wayland by using XWayland. If you still have issues:

```bash
# Force X11 session (logout and select "Ubuntu on Xorg" at login)
# Or run with virtual desktop:
./bin/start-system.sh --virtual-desktop
```

#### Port Already in Use

```bash
# Check what's using the port
ss -tuln | grep 18812

# Use a different port
./scripts/setup-rpyc.sh --port 18813 setup
```

#### MT5 Terminal Not Starting

```bash
# Check Wine prefix is valid
ls -la .mt5/drive_c/

# Try starting MT5 manually
WINEPREFIX=$(pwd)/.mt5 wine .mt5/drive_c/Program\ Files/MetaTrader\ 5/terminal64.exe
```

#### RPyC Connection Refused

```bash
# Check if server is running
./bin/system-status.sh

# Start the server
./bin/start-rpyc-server.sh

# Test connection
./scripts/setup-rpyc.sh test
```

## Uninstallation

```bash
# Full uninstall (removes Wine prefix, scripts, config)
./scripts/uninstall.sh all

# Keep Wine prefix (only remove scripts and config)
./scripts/uninstall.sh all --keep-wine

# Just kill running processes
./scripts/uninstall.sh processes

# Remove launcher scripts only
./scripts/uninstall.sh scripts
```

Note: System packages (Wine, Python) are not removed. To remove Wine:

```bash
sudo apt remove winehq-staging
```

## Script Reference

| Script                     | Purpose                                            |
| -------------------------- | -------------------------------------------------- |
| `scripts/install.sh`       | Main installation orchestrator                     |
| `scripts/install-base.sh`  | Install base dependencies (Python, pipx, hatch, uv)|
| `scripts/install-wine.sh`  | Install Wine Staging and Windows Python            |
| `scripts/install-mt5.sh`   | Install MetaTrader 5 terminal                      |
| `scripts/setup-rpyc.sh`    | Configure RPyC and create launcher scripts         |
| `scripts/start-system.sh`  | Start MT5 and RPyC server                          |
| `scripts/stop-system.sh`   | Stop MT5 and RPyC server                           |
| `scripts/diagnose.sh`      | Run diagnostic checks                              |
| `scripts/uninstall.sh`     | Uninstall components                               |

### Library Scripts

| Script                     | Purpose                                            |
| -------------------------- | -------------------------------------------------- |
| `scripts/lib/common.sh`    | Shared utilities (logging, sudo management, ports) |
| `scripts/lib/detect.sh`    | Environment detection (display, Wine, MT5 paths)   |

## Configuration

The `.mt5env` file stores instance configuration:

```bash
# MT5 Linux Configuration
MT5_WINE_PREFIX="/path/to/project/.mt5"
MT5_RPYC_PORT=18812
MT5_RPYC_HOST="localhost"
MT5_VENV="/path/to/project/.venv"
MT5_INSTANCE_NAME="mt5linux"
```

## Requirements

- Ubuntu 24.04 LTS (Desktop or Server)
- 64-bit system
- ~2GB disk space for Wine prefix
- Internet connection for downloads

## License

MIT License
