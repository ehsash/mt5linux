"""Lifecycle management module for rpyc server.

This module provides the LifecycleManager class which manages:
- Background health monitoring of the rpyc server process
- Automatic restart with exponential backoff on crash detection
- Callback notifications for monitoring system integration
- Thread-safe lifecycle operations

The LifecycleManager uses a daemon thread to periodically check server health
and automatically restart it if a crash is detected. Recovery success rate
target is >95% (NFR13).
"""

import random
import threading
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

try:
    from typing import Protocol
except ImportError:
    from typing_extensions import Protocol  # Python 3.7 compatibility

from mt5linux.process_manager import ProcessError, ProcessInfo, ProcessManager

# TYPE_CHECKING import for ConnectionManager to avoid circular import
if TYPE_CHECKING:
    from mt5linux.connection import ConnectionManager as _ConnectionManager

if TYPE_CHECKING:
    import logging as _logging

    from loguru import Logger as _LoguruLogger

    LoggerType = Union[_LoguruLogger, _logging.Logger]

try:
    from loguru import logger
except ImportError:
    # Fallback to standard logging if loguru not available
    import logging

    logger: "LoggerType" = logging.getLogger(__name__)  # type: ignore[no-redef]


# Lifecycle management constants
DEFAULT_CHECK_INTERVAL = 5.0  # seconds
MIN_CHECK_INTERVAL = 2.0  # seconds (lower bound to prevent CPU overuse)
MAX_CHECK_INTERVAL = 30.0  # seconds (upper bound for timely detection)

# Exponential backoff constants for restart attempts
RESTART_BASE_DELAY = 1.0  # seconds
RESTART_MAX_ATTEMPTS = 5
RESTART_MAX_DELAY = 16.0  # seconds
RESTART_JITTER_MAX = 0.1  # seconds


class LifecycleCallback(Protocol):
    """Protocol defining the callback signature for lifecycle events.

    Callbacks receive three parameters:
    - event: The event type ("crash", "restart", or "failure")
    - pid: The process ID if applicable, None otherwise
    - context: Additional event context as a dictionary
    """

    def __call__(
        self,
        event: str,
        pid: Optional[int],
        context: Dict[str, Any],
    ) -> None:
        """Handle a lifecycle event."""
        ...


class LifecycleError(ProcessError):
    """Base exception for lifecycle management errors.

    Raised when lifecycle operations (monitoring, restart, status) fail.
    All lifecycle-specific exceptions should inherit from this class.
    """

    pass


class ServerRestartError(LifecycleError):
    """Raised when server restart fails after all retry attempts.

    This exception indicates that the system exhausted all restart attempts
    with exponential backoff and was unable to recover the rpyc server.
    Manual intervention is required.
    """

    pass


class MonitoringError(LifecycleError):
    """Raised when monitoring thread encounters a fatal error.

    This exception indicates that the background monitoring thread
    failed unexpectedly and cannot continue monitoring server health.
    """

    pass


class LifecycleManager:
    """Manages rpyc server lifecycle with automatic recovery.

    Provides background health monitoring, automatic restart on crash detection,
    and callback notifications for monitoring system integration.

    The manager uses a daemon thread to periodically check if the rpyc server
    process is running. If a crash is detected, it attempts to restart the
    server using exponential backoff with jitter.

    Attributes:
        _process_manager: ProcessManager instance for server operations.
        _check_interval: Interval between health checks in seconds.
        _monitor_thread: Background monitoring thread (daemon).
        _stop_event: Event to signal monitoring thread to stop.
        _lock: Lock for thread-safe operations.
        _callbacks: List of registered lifecycle event callbacks.
        _current_pid: Currently tracked server process ID.

    Example:
        >>> from mt5linux.process_manager import ProcessManager
        >>> from mt5linux.lifecycle import LifecycleManager
        >>>
        >>> pm = ProcessManager()
        >>> lm = LifecycleManager(pm, check_interval=5.0)
        >>> lm.start_monitoring()
        >>> # ... server is now monitored ...
        >>> lm.stop_monitoring()
    """

    def __init__(
        self,
        process_manager: ProcessManager,
        check_interval: float = DEFAULT_CHECK_INTERVAL,
    ) -> None:
        """Initialize LifecycleManager.

        Args:
            process_manager: ProcessManager instance for server operations.
            check_interval: Interval between health checks in seconds.
                Default is 5.0 seconds. Must be between 2.0 and 30.0 seconds.

        Raises:
            ValueError: If check_interval is outside valid bounds.
        """
        if not (MIN_CHECK_INTERVAL <= check_interval <= MAX_CHECK_INTERVAL):
            raise ValueError(
                f"check_interval must be between {MIN_CHECK_INTERVAL} and "
                f"{MAX_CHECK_INTERVAL} seconds, got {check_interval}"
            )

        self._process_manager = process_manager
        self._check_interval = check_interval
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._callbacks: List[LifecycleCallback] = []
        self._current_pid: Optional[int] = None
        self._mt5_pid: Optional[int] = None
        self._failure_count: int = 0
        self._restart_count: int = 0
        self._last_check_time: Optional[datetime] = None
        self._connection_manager: Optional["_ConnectionManager"] = None
        self._heartbeat_monitor: Optional[Any] = None  # HeartbeatMonitor instance
        self._recovery_manager: Optional[Any] = None  # RecoveryManager instance

        logger.debug(
            f"LifecycleManager initialized with check_interval={check_interval}s"
        )

    def start_monitoring(self) -> None:
        """Start background health monitoring thread.

        Creates and starts a daemon thread that periodically checks if the
        rpyc server is running. If the server crashes, the thread will
        attempt to restart it using exponential backoff.

        If monitoring is already active, this method does nothing.

        Note:
            The monitoring thread is a daemon thread, so it will be
            automatically terminated when the main program exits.
        """
        with self._lock:
            # Check if thread already running
            if self._monitor_thread is not None and self._monitor_thread.is_alive():
                logger.debug("Monitoring already active, skipping start")
                return

            # Clear stop event before starting
            self._stop_event.clear()

            # Create and start monitoring thread
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                name="mt5linux-lifecycle-monitor",
                daemon=True,
            )
            self._monitor_thread.start()

            logger.info("Lifecycle monitoring started")

    def stop_monitoring(self) -> None:
        """Stop background health monitoring with graceful shutdown.

        Signals the monitoring thread to stop and waits for it to terminate.
        If no monitoring thread is running, this method does nothing.

        The method sets the stop event and waits up to 10 seconds for the
        thread to terminate gracefully.
        """
        with self._lock:
            thread_to_stop = self._monitor_thread
            if thread_to_stop is None:
                logger.debug("No monitoring thread to stop")
                return

            # Signal thread to stop
            self._stop_event.set()

        # Wait for thread to terminate (outside lock to avoid deadlock)
        # Use captured reference to avoid race with start_monitoring()
        thread_to_stop.join(timeout=10.0)

        if thread_to_stop.is_alive():
            logger.warning("Monitoring thread did not terminate in time")
        else:
            logger.info("Lifecycle monitoring stopped")

        with self._lock:
            # Only clear if it's still the same thread we stopped
            if self._monitor_thread is thread_to_stop:
                self._monitor_thread = None

    def get_status(self) -> Dict[str, Any]:
        """Get current lifecycle status.

        Returns thread-safe dictionary with current lifecycle state including
        monitoring status, current PID, failure counts, restart counts, and
        connection state.

        Returns:
            Dictionary containing:
                - monitoring_active: True if monitoring thread is running
                - current_pid: PID of currently tracked server process
                - last_check: Timestamp of last health check
                - consecutive_failures: Number of consecutive check failures
                - total_restarts: Total number of restart attempts made
                - connection_active: True if connected to rpyc server
        """
        with self._lock:
            # Determine connection state
            connection_active = False
            if self._connection_manager is not None:
                connection_active = self._connection_manager.is_connected

            # Get heartbeat status if monitor is attached
            heartbeat_status = None
            if self._heartbeat_monitor is not None:
                heartbeat_status = self._heartbeat_monitor.get_status()

            return {
                "monitoring_active": (
                    self._monitor_thread is not None and self._monitor_thread.is_alive()
                ),
                "current_pid": self._current_pid,
                "last_check": self._last_check_time,
                "consecutive_failures": self._failure_count,
                "total_restarts": self._restart_count,
                "connection_active": connection_active,
                "heartbeat_status": heartbeat_status,
            }

    def register_callback(self, callback: LifecycleCallback) -> None:
        """Register callback for lifecycle events.

        Callbacks are invoked when lifecycle events occur:
        - "crash": Server process was detected as crashed
        - "restart": Server was successfully restarted
        - "failure": All restart attempts failed

        Args:
            callback: Callable matching LifecycleCallback protocol.
                Must accept (event: str, pid: Optional[int], context: Dict).
        """
        with self._lock:
            self._callbacks.append(callback)
            logger.debug(f"Registered lifecycle callback: {callback}")

    def unregister_callback(self, callback: LifecycleCallback) -> None:
        """Unregister a previously registered callback.

        Args:
            callback: The callback to remove from the notification list.
        """
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)
                logger.debug(f"Unregistered lifecycle callback: {callback}")

    def ensure_server_running(self) -> ProcessInfo:
        """Ensure rpyc server is running, starting it if needed.

        Checks if the rpyc server is currently running on the configured port.
        If not, starts it and updates the tracked PID.

        Returns:
            ProcessInfo for the running rpyc server.

        Raises:
            RpycServerError: If server cannot be started.
        """
        with self._lock:
            # start_rpyc_server() checks for existing server on correct port
            # and starts a new one only if needed
            result = self._process_manager.start_rpyc_server()
            self._current_pid = result.pid
            return result

    def ensure_mt5_running(self) -> ProcessInfo:
        """Ensure MT5 is running, starting it if needed.

        Checks if the MT5 terminal is currently running. If not, starts it
        via Wine and updates the tracked MT5 PID.

        Returns:
            ProcessInfo for the running MT5 process.

        Raises:
            MT5LaunchError: If MT5 cannot be started.

        Note:
            - Uses ProcessManager.start_mt5() for launching
            - Thread-safe: uses internal lock for PID tracking
            - Logs whether MT5 is reused or newly started
        """
        with self._lock:
            existing = self._process_manager.find_mt5()
            if existing:
                self._mt5_pid = existing.pid
                logger.debug(f"MT5 already running: PID={existing.pid}")
                return existing

            # Start MT5
            logger.info("MT5 not running, starting...")
            result = self._process_manager.start_mt5()
            self._mt5_pid = result.pid
            return result

    def ensure_connected(self) -> bool:
        """Ensure connection to rpyc server is established.

        Ensures rpyc server and MT5 are running before attempting to
        establish the connection. If already connected, returns True
        immediately.

        Returns:
            True if connected successfully.

        Raises:
            RpycServerError: If server cannot be started.
            MT5LaunchError: If MT5 cannot be started.
            ConnectionError: If connection fails.

        Note:
            - Chains: ensure_server_running() → ensure_mt5_running() → connect()
            - Thread-safe: uses internal lock
            - Creates ConnectionManager on first call if not exists
        """
        # Early exit check - avoid unnecessary prerequisite calls if already connected
        with self._lock:
            if self._connection_manager is not None:
                if self._connection_manager.is_connected:
                    logger.debug("Already connected")
                    return True

        # Ensure prerequisites are running (these acquire their own locks)
        self.ensure_server_running()
        self.ensure_mt5_running()

        with self._lock:
            # Re-check connection state after prerequisites (another thread may have connected)
            if self._connection_manager is not None:
                if self._connection_manager.is_connected:
                    logger.debug("Already connected (after prerequisites)")
                    return True

            # Create connection manager if needed
            if self._connection_manager is None:
                from mt5linux.connection import ConnectionManager

                self._connection_manager = ConnectionManager()

            # Establish connection
            logger.info("Establishing connection to rpyc server...")
            return self._connection_manager.connect()

    def _monitor_loop(self) -> None:
        """Background monitoring loop.

        Runs in a separate thread, periodically checking server health.
        If the server crashes, attempts restart with exponential backoff.
        """
        logger.debug("Monitoring loop started")

        while not self._stop_event.is_set():
            try:
                self._perform_health_check()
            except Exception as e:
                logger.error(f"Health check error: {e}")

            # Wait for next check interval or stop event
            self._stop_event.wait(self._check_interval)

        logger.debug("Monitoring loop exiting")

    def _perform_health_check(self) -> None:
        """Perform a single health check on the rpyc server."""
        with self._lock:
            self._last_check_time = datetime.now()

        # Check if server is running
        server = self._process_manager.find_rpyc_server()

        if server:
            with self._lock:
                self._current_pid = server.pid
                self._failure_count = 0
            logger.debug(f"Health check passed: PID={server.pid}")
        else:
            with self._lock:
                self._failure_count += 1
                old_pid = self._current_pid
                self._current_pid = None

            logger.warning(
                f"Health check failed: server not found "
                f"(consecutive failures: {self._failure_count})"
            )

            # Notify crash
            self._notify_callbacks(
                "crash", old_pid, {"consecutive_failures": self._failure_count}
            )

            # Attempt restart
            self._handle_crash()

    def _handle_crash(self) -> None:
        """Handle detected crash with automatic restart."""
        try:
            result = self._restart_with_backoff()
            with self._lock:
                self._current_pid = result.pid
                self._failure_count = 0
            logger.info(f"Server restarted successfully: PID={result.pid}")
        except ServerRestartError as e:
            logger.error(f"Failed to restart server: {e}")

    def _restart_with_backoff(self) -> ProcessInfo:
        """Restart server with exponential backoff and jitter.

        Attempts to restart the server up to RESTART_MAX_ATTEMPTS times,
        using exponential backoff between attempts to avoid overwhelming
        the system.

        Returns:
            ProcessInfo for the restarted server.

        Raises:
            ServerRestartError: If all restart attempts fail.
        """
        from mt5linux.process_manager import RpycServerError

        for attempt in range(RESTART_MAX_ATTEMPTS):
            try:
                with self._lock:
                    self._restart_count += 1

                result = self._process_manager.start_rpyc_server()

                # Notify success
                self._notify_callbacks(
                    "restart",
                    result.pid,
                    {"attempt": attempt + 1, "total_attempts": RESTART_MAX_ATTEMPTS},
                )

                return result

            except RpycServerError as e:
                delay = min(
                    RESTART_BASE_DELAY * (2**attempt),
                    RESTART_MAX_DELAY,
                )
                jitter = random.uniform(0, RESTART_JITTER_MAX)
                total_delay = delay + jitter

                logger.warning(
                    f"Restart attempt {attempt + 1}/{RESTART_MAX_ATTEMPTS} failed: {e}. "
                    f"Retrying in {total_delay:.2f}s"
                )

                if attempt < RESTART_MAX_ATTEMPTS - 1:
                    time.sleep(total_delay)

        # All attempts exhausted
        self._notify_callbacks(
            "failure",
            None,
            {
                "total_attempts": RESTART_MAX_ATTEMPTS,
                "message": "All restart attempts exhausted",
            },
        )

        raise ServerRestartError(
            f"Failed to restart rpyc server after {RESTART_MAX_ATTEMPTS} attempts. "
            "Manual intervention required."
        )

    def _notify_callbacks(
        self,
        event: str,
        pid: Optional[int],
        context: Dict[str, Any],
    ) -> None:
        """Notify all registered callbacks of a lifecycle event.

        Args:
            event: Event type ("crash", "restart", "failure").
            pid: Process ID if applicable.
            context: Additional event context.
        """
        with self._lock:
            callbacks = list(self._callbacks)

        for callback in callbacks:
            try:
                callback(event, pid, context)
            except Exception as e:
                logger.error(f"Callback error for event '{event}': {e}")
