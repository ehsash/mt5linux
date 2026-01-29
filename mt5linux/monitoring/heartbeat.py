"""Heartbeat monitoring module for connection health.

This module provides the HeartbeatMonitor class which continuously monitors
the MT5 connection health using periodic heartbeat checks.

Connection health monitoring must detect failures within 45 seconds (NFR12)
with 100% accuracy (NFR15).
"""

import threading
import time
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Union

if TYPE_CHECKING:
    import logging as _logging

    from loguru import Logger as _LoguruLogger

    from mt5linux.connection import ConnectionManager as _ConnectionManager

    LoggerType = Union[_LoguruLogger, _logging.Logger]

try:
    from loguru import logger
except ImportError:
    # Fallback to standard logging if loguru not available
    import logging

    logger: "LoggerType" = logging.getLogger(__name__)  # type: ignore[no-redef]


# Heartbeat monitoring constants
DEFAULT_HEARTBEAT_INTERVAL = 30.0  # seconds (architecture requirement)
DEFAULT_FAILURE_THRESHOLD = 45.0  # seconds (NFR12)


class HeartbeatMonitor:
    """Monitors connection health via periodic heartbeats.

    Uses ConnectionManager.verify_connection() for three-level health checks:
    1. Socket-level ping
    2. rpyc layer verification
    3. MT5 command execution

    Detects failures within 45 seconds (NFR12) with 100% accuracy (NFR15).

    Attributes:
        _connection_manager: ConnectionManager instance to monitor.
        _heartbeat_interval: Seconds between heartbeat checks (default 30).
        _failure_threshold: Seconds before declaring failure (default 45).
        _last_heartbeat_time: Timestamp of last successful heartbeat.
        _consecutive_failures: Count of consecutive failed heartbeats.
        _failure_callbacks: Registered failure notification callbacks.
        _failure_notified: Flag to prevent repeated failure notifications.
        _monitoring_start_time: Timestamp when monitoring started.
        _monitor_thread: Background monitoring thread.
        _stop_event: Event to signal thread stop.
        _lock: Threading reentrant lock for thread-safe operations.

    Example:
        >>> from mt5linux.connection import ConnectionManager
        >>> from mt5linux.monitoring import HeartbeatMonitor
        >>> conn_mgr = ConnectionManager()
        >>> monitor = HeartbeatMonitor(conn_mgr)
        >>> monitor.start()
        >>> # ... monitoring active ...
        >>> monitor.stop()
    """

    def __init__(
        self,
        connection_manager: "_ConnectionManager",
        heartbeat_interval: float = DEFAULT_HEARTBEAT_INTERVAL,
        failure_threshold: float = DEFAULT_FAILURE_THRESHOLD,
    ) -> None:
        """Initialize HeartbeatMonitor.

        Args:
            connection_manager: ConnectionManager instance to monitor.
            heartbeat_interval: Seconds between heartbeat checks (default 30).
            failure_threshold: Seconds before declaring failure (default 45, NFR12).
        """
        self._connection_manager = connection_manager
        self._heartbeat_interval = heartbeat_interval
        self._failure_threshold = failure_threshold
        self._last_heartbeat_time: Optional[float] = None
        self._consecutive_failures: int = 0
        self._failure_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._failure_notified: bool = False  # Prevents repeated failure notifications
        self._monitoring_start_time: Optional[float] = (
            None  # Tracks when monitoring began
        )
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()  # RLock allows reentrant acquisition

        logger.debug(
            f"HeartbeatMonitor initialized: interval={heartbeat_interval}s, "
            f"threshold={failure_threshold}s"
        )

    def start(self) -> None:
        """Start background heartbeat monitoring thread.

        Creates and starts a daemon thread that periodically performs
        heartbeat checks. If monitoring is already active, this method
        does nothing.
        """
        with self._lock:
            if self._monitor_thread is not None and self._monitor_thread.is_alive():
                logger.debug("Heartbeat monitoring already active, skipping start")
                return

            self._stop_event.clear()
            self._failure_notified = False  # Reset notification state on start
            self._monitoring_start_time = time.time()  # Track when monitoring began

            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                name="mt5linux-heartbeat-monitor",
                daemon=True,
            )
            self._monitor_thread.start()

            logger.info("Heartbeat monitoring started")

    def stop(self) -> None:
        """Stop background heartbeat monitoring with graceful shutdown.

        Signals the monitoring thread to stop and waits for it to terminate.
        If no monitoring thread is running, this method does nothing.
        """
        with self._lock:
            thread_to_stop = self._monitor_thread
            if thread_to_stop is None:
                logger.debug("No heartbeat monitoring thread to stop")
                return

            self._stop_event.set()

        thread_to_stop.join(timeout=10.0)

        if thread_to_stop.is_alive():
            logger.warning("Heartbeat monitoring thread did not terminate in time")
        else:
            logger.info("Heartbeat monitoring stopped")

        with self._lock:
            if self._monitor_thread is thread_to_stop:
                self._monitor_thread = None

    def _monitor_loop(self) -> None:
        """Background monitoring loop.

        Runs in a separate thread, periodically performing heartbeat checks
        and checking for failure threshold violations.
        """
        logger.debug("Heartbeat monitoring loop started")

        while not self._stop_event.is_set():
            self._perform_heartbeat()
            self._check_failure_threshold()
            self._stop_event.wait(self._heartbeat_interval)

        logger.debug("Heartbeat monitoring loop exiting")

    def _perform_heartbeat(self) -> bool:
        """Perform a single heartbeat check.

        Calls ConnectionManager.verify_connection() to perform three-level
        health verification. Updates internal state based on result.

        Returns:
            True if heartbeat succeeded, False otherwise.
        """
        try:
            result = self._connection_manager.verify_connection()
        except Exception as e:
            logger.warning(f"Heartbeat exception: {e}")
            result = False

        with self._lock:
            if result:
                self._last_heartbeat_time = time.time()
                self._consecutive_failures = 0
                self._failure_notified = False  # Reset on recovery
                logger.debug("Heartbeat succeeded")
            else:
                self._consecutive_failures += 1
                logger.warning(
                    f"Heartbeat failed (consecutive: {self._consecutive_failures})"
                )

        return result

    def _check_failure_threshold(self) -> None:
        """Check if failure threshold has been exceeded.

        If the time since last successful heartbeat exceeds the failure
        threshold, invokes all registered failure callbacks (once per failure
        episode - callbacks are not repeated until recovery occurs).

        If no heartbeat has succeeded yet, uses monitoring start time as the
        reference point to ensure failures are detected even when connection
        was dead from the beginning.
        """
        with self._lock:
            # Already notified for this failure episode - don't spam callbacks
            if self._failure_notified:
                return

            # Use last heartbeat time, or monitoring start time if no heartbeat yet
            reference_time = self._last_heartbeat_time or self._monitoring_start_time
            if reference_time is None:
                return

            time_since_reference = time.time() - reference_time

            if time_since_reference <= self._failure_threshold:
                return

            # Mark as notified to prevent repeated callbacks
            self._failure_notified = True

            context = {
                "last_heartbeat_time": self._last_heartbeat_time,
                "consecutive_failures": self._consecutive_failures,
                "time_since_heartbeat": time_since_reference,
                "monitoring_start_time": self._monitoring_start_time,
            }
            callbacks = list(self._failure_callbacks)

        logger.error(
            f"Failure threshold exceeded: {time_since_reference:.1f}s since "
            f"last heartbeat (threshold: {self._failure_threshold}s)"
        )

        for callback in callbacks:
            try:
                callback(context)
            except Exception as e:
                logger.error(f"Failure callback error: {e}")

    def register_failure_callback(
        self, callback: Callable[[Dict[str, Any]], None]
    ) -> None:
        """Register callback for failure notifications.

        Callbacks are invoked when the failure threshold is exceeded.
        Duplicate registrations are ignored.

        Args:
            callback: Function accepting a context dict with failure details.
        """
        with self._lock:
            if callback in self._failure_callbacks:
                logger.debug(f"Callback already registered, skipping: {callback}")
                return
            self._failure_callbacks.append(callback)
            logger.debug(f"Registered failure callback: {callback}")

    def unregister_failure_callback(
        self, callback: Callable[[Dict[str, Any]], None]
    ) -> None:
        """Unregister a previously registered failure callback.

        Args:
            callback: The callback to remove from the notification list.
        """
        with self._lock:
            if callback in self._failure_callbacks:
                self._failure_callbacks.remove(callback)
                logger.debug(f"Unregistered failure callback: {callback}")

    @property
    def is_healthy(self) -> bool:
        """Check if connection is currently healthy.

        Returns:
            True if last heartbeat was within failure threshold, False otherwise.
        """
        with self._lock:
            if self._last_heartbeat_time is None:
                return False

            time_since_heartbeat = time.time() - self._last_heartbeat_time
            return time_since_heartbeat <= self._failure_threshold

    def get_status(self) -> Dict[str, Any]:
        """Get current heartbeat monitoring status.

        Returns:
            Dictionary containing:
                - monitoring_active: True if monitoring thread is running
                - last_heartbeat: Timestamp of last successful heartbeat
                - consecutive_failures: Count of consecutive failed heartbeats
                - is_healthy: True if within failure threshold
                - failure_notified: True if failure callbacks have been invoked
                - monitoring_start_time: Timestamp when monitoring started
        """
        with self._lock:
            return {
                "monitoring_active": (
                    self._monitor_thread is not None and self._monitor_thread.is_alive()
                ),
                "last_heartbeat": self._last_heartbeat_time,
                "consecutive_failures": self._consecutive_failures,
                "is_healthy": self.is_healthy,
                "failure_notified": self._failure_notified,
                "monitoring_start_time": self._monitoring_start_time,
            }
