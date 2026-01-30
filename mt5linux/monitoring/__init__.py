"""Monitoring system package for mt5linux.

This package provides monitoring capabilities for the MT5 connection:
- HeartbeatMonitor: Continuous connection health monitoring (Story 2.6, 4.1)
- DailyReporter: Scheduled daily reports with account status and metrics (Story 4.2)
- LatencyMonitor: End-to-end latency measurement (Story 4.3)
- TelegramNotifier: Telegram notification system (Story 4.4)
- NotificationConfigManager: Notification configuration management (Story 4.5)
- BaseNotifier: Abstract notification channel interface (Story 4.6)
- NotificationType: Notification type enumeration (Story 4.6)
- ConsoleNotifier: Console notification channel (Story 4.6)
- NotificationRouter: Multi-channel notification router (Story 4.6)
- AnalyticsEngine: Analytics and insights aggregation (Story 4.7)
- AnalyticsReport: Complete analytics report dataclass (Story 4.7)
- LatencyAnalytics: Latency statistics dataclass (Story 4.7)
- SystemHealthAnalytics: System health statistics dataclass (Story 4.7)
- TradingAnalytics: Trading statistics dataclass (Story 4.7)
"""

from mt5linux.monitoring.analytics import (
    AnalyticsEngine,
    AnalyticsReport,
    LatencyAnalytics,
    SystemHealthAnalytics,
    TradingAnalytics,
)
from mt5linux.monitoring.base_notifier import BaseNotifier, NotificationType
from mt5linux.monitoring.config_manager import NotificationConfigManager
from mt5linux.monitoring.console_notifier import ConsoleNotifier, ConsoleNotifierConfig
from mt5linux.monitoring.heartbeat import HeartbeatMonitor
from mt5linux.monitoring.latency import LatencyAlert, LatencyMeasurement, LatencyMonitor
from mt5linux.monitoring.notification_router import NotificationRouter
from mt5linux.monitoring.notifier import NotificationMessage, TelegramNotifier
from mt5linux.monitoring.reporter import DailyReport, DailyReporter, PositionInfo

__all__ = [
    "HeartbeatMonitor",
    "DailyReporter",
    "DailyReport",
    "PositionInfo",
    "LatencyMonitor",
    "LatencyMeasurement",
    "LatencyAlert",
    "TelegramNotifier",
    "NotificationMessage",
    "NotificationConfigManager",
    # Story 4.6: Alternative Notification Channels
    "BaseNotifier",
    "NotificationType",
    "ConsoleNotifier",
    "ConsoleNotifierConfig",
    "NotificationRouter",
    # Story 4.7: Advanced Analytics and Insights
    "AnalyticsEngine",
    "AnalyticsReport",
    "LatencyAnalytics",
    "SystemHealthAnalytics",
    "TradingAnalytics",
]
