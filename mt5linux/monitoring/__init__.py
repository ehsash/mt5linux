"""Monitoring system package for mt5linux.

This package provides monitoring capabilities for the MT5 connection:
- HeartbeatMonitor: Continuous connection health monitoring

Future modules (per architecture):
- reporter.py: Daily reports
- notifier.py: Notification system (Telegram, etc.)
- latency.py: Latency measurement
"""

from mt5linux.monitoring.heartbeat import HeartbeatMonitor

__all__ = ["HeartbeatMonitor"]
