#!/bin/bash
# Diagnostic script for Ubuntu server MT5 setup

echo "======================================================================="
echo "MT5 Linux Server Environment Diagnostics"
echo "======================================================================="
echo ""

echo "1. Current Session Environment:"
echo "------------------------------"
echo "DISPLAY: ${DISPLAY:-not set}"
echo "WAYLAND_DISPLAY: ${WAYLAND_DISPLAY:-not set}"
echo "XDG_SESSION_TYPE: ${XDG_SESSION_TYPE:-not set}"
echo "USER: $USER"
echo "Current directory: $(pwd)"
echo ""

echo "2. Wine Prefix Location:"
echo "-----------------------"
if [ -d ".mt5" ]; then
    echo "✓ Wine prefix found: $(pwd)/.mt5"
    echo "  MT5 terminal: $(find .mt5 -name terminal64.exe 2>/dev/null | head -1)"
else
    echo "✗ No .mt5 directory found in current directory"
fi
echo ""

echo "3. RPyC Service Status:"
echo "----------------------"
SERVICE_NAME="mt5-rpyc-$(basename $(pwd))"
if systemctl --user is-active --quiet "$SERVICE_NAME"; then
    echo "✓ Service $SERVICE_NAME is running"
    echo ""
    echo "Service environment variables:"
    systemctl --user show "$SERVICE_NAME" -p Environment | sed 's/Environment=/  /'
    echo ""
    echo "Service process info:"
    systemctl --user status "$SERVICE_NAME" --no-pager | grep -A 5 "Main PID"
else
    echo "✗ Service $SERVICE_NAME is NOT running"
fi
echo ""

echo "4. Running Wine Processes:"
echo "-------------------------"
pgrep -a wine || echo "No wine processes found"
echo ""

echo "5. MT5 Terminal Process:"
echo "-----------------------"
pgrep -a terminal64 || echo "MT5 terminal not running"
echo ""

echo "6. RPyC Port Accessibility:"
echo "--------------------------"
if command -v nc >/dev/null 2>&1; then
    timeout 2 nc -zv localhost 18812 2>&1 || echo "Cannot connect to port 18812"
elif command -v telnet >/dev/null 2>&1; then
    timeout 2 telnet localhost 18812 2>&1 | head -5 || echo "Cannot connect to port 18812"
else
    echo "nc/telnet not available, checking with ss:"
    ss -tlnp | grep 18812 || echo "Port 18812 not listening"
fi
echo ""

echo "7. X Server Accessibility:"
echo "-------------------------"
if [ -n "$DISPLAY" ]; then
    if command -v xdpyinfo >/dev/null 2>&1; then
        if xdpyinfo >/dev/null 2>&1; then
            echo "✓ X server accessible on $DISPLAY"
        else
            echo "✗ X server NOT accessible on $DISPLAY"
        fi
    else
        echo "xdpyinfo not installed, cannot test X server"
    fi
else
    echo "✗ DISPLAY not set"
fi
echo ""

echo "======================================================================="
echo "Diagnostics complete"
echo "======================================================================="
