"""Heartbeat monitoring module for connection health.

This module provides the HeartbeatMonitor class which continuously monitors
the MT5 connection health using periodic heartbeat checks.

Connection health monitoring must detect failures within 45 seconds (NFR12)
with 100% accuracy (NFR15).

Story 4.1 additions:
- HeartbeatConfig dataclass for configuration
- HeartbeatFailureInfo dataclass for typed callbacks
- NFR9 variance tracking (<1 second variance requirement)
- Extended status API methods
"""

import threading
import time
from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class HeartbeatConfig:
    """Configuration for heartbeat monitoring (Story 4.1).

    Configures heartbeat system parameters per FR46, FR47, NFR9, NFR12.

    Attributes:
        interval: Seconds between heartbeat checks (default 30, FR46/NFR9).
        failure_threshold: Seconds before declaring failure (default 45, FR47/NFR12).

    Raises:
        ValueError: If interval >= failure_threshold (invalid configuration).
    """

    interval: float = 30.0
    failure_threshold: float = 45.0

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if self.interval <= 0:
            raise ValueError(f"interval must be positive, got {self.interval}")
        if self.failure_threshold <= 0:
            raise ValueError(
                f"failure_threshold must be positive, got {self.failure_threshold}"
            )
        if self.interval >= self.failure_threshold:
            raise ValueError(
                f"heartbeat_interval ({self.interval}) must be less than "
                f"failure_threshold ({self.failure_threshold})"
            )


@dataclass(frozen=True, slots=True)
class HeartbeatFailureInfo:
    """Information about a heartbeat failure event (Story 4.1).

    Provides typed context for failure callbacks, preparing for
    Story 4.4 Telegram notification integration.

    Attributes:
        last_heartbeat_time: Timestamp of last successful heartbeat (or None).
        consecutive_failures: Count of consecutive failed heartbeats.
        time_since_heartbeat: Seconds since last successful heartbeat.
        monitoring_start_time: Timestamp when monitoring started (or None).
        failure_timestamp: Timestamp when failure was detected.
    """

    last_heartbeat_time: Optional[float]
    consecutive_failures: int
    time_since_heartbeat: float
    monitoring_start_time: Optional[float]
    failure_timestamp: float


class HeartbeatMonitor:
    """Monitors connection health via periodic heartbeats.

    Uses ConnectionManager.verify_connection() for three-level health checks:
    1. Socket-level ping
    2. rpyc layer verification
    3. MT5 command execution

    Detects failures within 45 seconds (NFR12) with 100% accuracy (NFR15).

    Story 4.1 additions:
    - HeartbeatConfig support for typed configuration
    - NFR9 variance tracking (<1 second variance requirement)
    - HeartbeatFailureInfo typed callbacks
    - Extended status API (get_heartbeat_count, get_uptime, get_average_interval)

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
        _heartbeat_count: Total number of heartbeats performed (Story 4.1).
        _total_variance: Sum of variance from expected interval (Story 4.1).
        _previous_heartbeat_time: Timestamp of previous heartbeat (Story 4.1).
        _success_callbacks: Registered success notification callbacks (Story 4.1).

    Example:
        >>> from mt5linux.connection import ConnectionManager
        >>> from mt5linux.monitoring import HeartbeatMonitor, HeartbeatConfig
        >>> conn_mgr = ConnectionManager()
        >>> config = HeartbeatConfig(interval=20.0, failure_threshold=35.0)
        >>> monitor = HeartbeatMonitor(conn_mgr, config=config)
        >>> monitor.start()
        >>> # ... monitoring active ...
        >>> monitor.stop()
    """

    def __init__(
        self,
        connection_manager: "_ConnectionManager",
        heartbeat_interval: float = DEFAULT_HEARTBEAT_INTERVAL,
        failure_threshold: float = DEFAULT_FAILURE_THRESHOLD,
        config: Optional[HeartbeatConfig] = None,
    ) -> None:
        """Initialize HeartbeatMonitor.

        Args:
            connection_manager: ConnectionManager instance to monitor.
            heartbeat_interval: Seconds between heartbeat checks (default 30).
            failure_threshold: Seconds before declaring failure (default 45, NFR12).
            config: Optional HeartbeatConfig for typed configuration (Story 4.1).
                   Explicit interval/threshold params take precedence over config.
        """
        self._connection_manager = connection_manager

        # Determine interval and threshold
        # Priority: explicit params > config > defaults
        if heartbeat_interval != DEFAULT_HEARTBEAT_INTERVAL:
            self._heartbeat_interval = heartbeat_interval
        elif config is not None:
            self._heartbeat_interval = config.interval
        else:
            self._heartbeat_interval = DEFAULT_HEARTBEAT_INTERVAL

        if failure_threshold != DEFAULT_FAILURE_THRESHOLD:
            self._failure_threshold = failure_threshold
        elif config is not None:
            self._failure_threshold = config.failure_threshold
        else:
            self._failure_threshold = DEFAULT_FAILURE_THRESHOLD

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

        # Story 4.1: NFR9 variance tracking
        self._heartbeat_count: int = 0
        self._total_variance: float = 0.0
        self._previous_heartbeat_time: Optional[float] = None
        self._total_actual_interval: float = 0.0  # Sum of actual intervals

        # Story 4.1: Success callbacks
        self._success_callbacks: List[Callable[[], None]] = []

        logger.debug(
            f"HeartbeatMonitor initialized: interval={self._heartbeat_interval}s, "
            f"threshold={self._failure_threshold}s"
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

        Story 4.1: Also tracks NFR9 variance metrics.

        Returns:
            True if heartbeat succeeded, False otherwise.
        """
        current_time = time.time()

        # Story 4.1: NFR9 variance tracking
        with self._lock:
            if self._previous_heartbeat_time is not None:
                actual_interval = current_time - self._previous_heartbeat_time
                variance = abs(actual_interval - self._heartbeat_interval)

                if variance > 1.0:  # NFR9: <1 second variance
                    logger.warning(
                        f"Heartbeat variance exceeded NFR9 limit: {variance:.3f}s",
                        extra={
                            "expected": self._heartbeat_interval,
                            "actual": actual_interval,
                        },
                    )

                self._total_variance += variance
                self._total_actual_interval += actual_interval

            self._previous_heartbeat_time = current_time
            self._heartbeat_count += 1

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

                # Story 4.1: Invoke success callbacks
                for callback in self._success_callbacks:
                    try:
                        callback()
                    except Exception as e:
                        logger.error(f"Success callback error: {e}")
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

    def on_heartbeat_failure(
        self, callback: Callable[[HeartbeatFailureInfo], None]
    ) -> None:
        """Register typed callback for heartbeat failure notifications (Story 4.1).

        Mirrors the on_trade_failure pattern from Story 3.3.
        Prepares for Story 4.4 Telegram notification integration.

        Args:
            callback: Function accepting HeartbeatFailureInfo with failure details.
        """

        def wrapper(ctx: Dict[str, Any]) -> None:
            info = HeartbeatFailureInfo(
                last_heartbeat_time=ctx.get("last_heartbeat_time"),
                consecutive_failures=ctx.get("consecutive_failures", 0),
                time_since_heartbeat=ctx.get("time_since_heartbeat", 0.0),
                monitoring_start_time=ctx.get("monitoring_start_time"),
                failure_timestamp=time.time(),
            )
            callback(info)

        self.register_failure_callback(wrapper)

    def on_heartbeat_success(self, callback: Callable[[], None]) -> None:
        """Register callback for heartbeat success notifications (Story 4.1).

        Used for recovery notifications after a failure episode.

        Args:
            callback: Function to call on successful heartbeat.
        """
        with self._lock:
            if callback not in self._success_callbacks:
                self._success_callbacks.append(callback)
                logger.debug(f"Registered success callback: {callback}")

    def unregister_success_callback(self, callback: Callable[[], None]) -> None:
        """Unregister a previously registered success callback (Story 4.1).

        Args:
            callback: The callback to remove from the success notification list.
        """
        with self._lock:
            if callback in self._success_callbacks:
                self._success_callbacks.remove(callback)
                logger.debug(f"Unregistered success callback: {callback}")

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

    def get_heartbeat_count(self) -> int:
        """Get total number of heartbeats performed (Story 4.1).

        Returns:
            Total heartbeat count since monitor was created.
        """
        with self._lock:
            return self._heartbeat_count

    def get_uptime(self) -> Optional[float]:
        """Get monitoring uptime in seconds (Story 4.1).

        Returns:
            Seconds since monitoring started, or None if not started.
        """
        with self._lock:
            if self._monitoring_start_time is None:
                return None
            return time.time() - self._monitoring_start_time

    def get_average_interval(self) -> Optional[float]:
        """Get average actual interval between heartbeats (Story 4.1).

        Returns:
            Average interval in seconds, or None if insufficient data.
        """
        with self._lock:
            # Need at least 2 heartbeats to calculate interval
            if self._heartbeat_count < 2:
                return None
            # Number of intervals is heartbeat_count - 1
            return self._total_actual_interval / (self._heartbeat_count - 1)

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
                - heartbeat_count: Total heartbeats performed (Story 4.1)
                - average_variance: Average variance from expected interval (Story 4.1)
                - uptime: Seconds since monitoring started (Story 4.1)
        """
        with self._lock:
            # Calculate average variance
            if self._heartbeat_count > 1:
                # Variance is measured between heartbeats, so count - 1 intervals
                avg_variance = self._total_variance / (self._heartbeat_count - 1)
            else:
                avg_variance = 0.0

            return {
                "monitoring_active": (
                    self._monitor_thread is not None and self._monitor_thread.is_alive()
                ),
                "last_heartbeat": self._last_heartbeat_time,
                "consecutive_failures": self._consecutive_failures,
                "is_healthy": self.is_healthy,
                "failure_notified": self._failure_notified,
                "monitoring_start_time": self._monitoring_start_time,
                # Story 4.1 additions
                "heartbeat_count": self._heartbeat_count,
                "average_variance": avg_variance,
                "uptime": self.get_uptime(),
            }
