#!/bin/bash
# ThinLinc diagnostics script

echo "======================================================================="
echo "ThinLinc Diagnostics"
echo "======================================================================="
echo ""

echo "1. Checking ThinLinc services status:"
echo "--------------------------------------"
for service in tlwebadm vsmserver vsmagent; do
    if systemctl is-active --quiet $service; then
        echo "✓ $service is running"
    else
        echo "✗ $service is NOT running"
        systemctl status $service --no-pager | tail -5
    fi
done
echo ""

echo "2. Checking ThinLinc configuration:"
echo "-----------------------------------"
if [ -f /opt/thinlinc/etc/conf.d/vsmagent.hconf ]; then
    echo "Default session: $(grep 'default_session' /opt/thinlinc/etc/conf.d/vsmagent.hconf || echo 'not set')"
else
    echo "✗ Configuration file not found"
fi
echo ""

echo "3. Checking XFCE installation:"
echo "------------------------------"
if command -v startxfce4 &> /dev/null; then
    echo "✓ XFCE is installed: $(which startxfce4)"
else
    echo "✗ XFCE is NOT installed"
fi
echo ""

echo "4. Recent ThinLinc agent logs (last 20 lines):"
echo "----------------------------------------------"
if [ -f /var/log/vsmagent.log ]; then
    tail -20 /var/log/vsmagent.log
else
    echo "✗ Agent log not found at /var/log/vsmagent.log"
    echo "Checking alternative location:"
    if [ -f /opt/thinlinc/var/log/vsmagent.log ]; then
        tail -20 /opt/thinlinc/var/log/vsmagent.log
    fi
fi
echo ""

echo "5. Checking authentication logs:"
echo "--------------------------------"
journalctl -u vsmagent -n 20 --no-pager
echo ""

echo "6. Network connectivity:"
echo "-----------------------"
netstat -tlnp 2>/dev/null | grep -E ':(22|300|3389|9000|9001)' || ss -tlnp | grep -E ':(22|300|3389|9000|9001)'
echo ""

echo "7. User session directory:"
echo "-------------------------"
if [ -d "$HOME/.thinlinc" ]; then
    echo "✓ ThinLinc user directory exists"
    ls -la "$HOME/.thinlinc/" 2>/dev/null || echo "Cannot read directory"
else
    echo "✗ No ThinLinc user directory"
fi
echo ""

echo "======================================================================="
echo "Diagnostics complete"
echo "======================================================================="
