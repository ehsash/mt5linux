"""Recovery management module for automatic connection recovery.

This module provides the RecoveryManager class which handles automatic
recovery from connection failures using the sequence:
retry connection → relaunch MT5 → retry connection → notify

Recovery must complete within 30 seconds (NFR5) with >95% success rate (NFR14).
"""

import random
import threading
import time
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Union

if TYPE_CHECKING:
    import logging as _logging

    from loguru import Logger as _LoguruLogger

    from mt5linux.lifecycle import LifecycleManager as _LifecycleManager

    LoggerType = Union[_LoguruLogger, _logging.Logger]

try:
    from loguru import logger
except ImportError:
    # Fallback to standard logging if loguru not available
    import logging

    logger: "LoggerType" = logging.getLogger(__name__)  # type: ignore[no-redef]


# Recovery sequence constants
DEFAULT_MAX_CONNECTION_RETRIES = 3
DEFAULT_MAX_RELAUNCH_RETRIES = 2
DEFAULT_RECOVERY_TIMEOUT = 30.0  # seconds (NFR5)

# Exponential backoff constants (architecture pattern)
RETRY_BASE_DELAY = 1.0  # seconds
RETRY_MAX_DELAY = 10.0  # seconds
RETRY_JITTER_MAX = 0.5  # seconds

# Troubleshooting suggestions for recovery failures (AC#5)
TROUBLESHOOTING_STEPS = [
    "1. Check if MT5 terminal is responding (try opening it manually)",
    "2. Verify Wine is running correctly: 'pgrep -a wine'",
    "3. Check rpyc server status: 'pgrep -af rpyc'",
    "4. Restart the rpyc server manually: 'mt5linux server start'",
    "5. Check system resources (CPU, memory) for resource exhaustion",
    "6. Review logs at ~/.mt5linux/logs/ for detailed error information",
    "7. If persistent, restart MT5 terminal completely",
]


class RecoveryManager:
    """Manages automatic recovery from connection failures.

    Recovery sequence: retry → relaunch → retry → notify
    Target: <30 seconds recovery time (NFR5), >95% success rate (NFR14)

    Attributes:
        _lifecycle_manager: LifecycleManager for process operations.
        _max_connection_retries: Maximum connection retry attempts.
        _max_relaunch_retries: Maximum MT5 relaunch attempts.
        _recovery_timeout: Total recovery timeout in seconds.
        _recovery_in_progress: Flag indicating active recovery.
        _last_recovery_attempt: Timestamp of last recovery attempt.
        _recovery_stats: Dictionary tracking success/failure counts.
        _recovery_callbacks: List of registered callbacks.
        _lock: Threading lock for thread-safe operations.

    Example:
        >>> from mt5linux.lifecycle import LifecycleManager
        >>> from mt5linux.recovery import RecoveryManager
        >>> lm = LifecycleManager(process_manager)
        >>> rm = RecoveryManager(lm)
        >>> rm.attempt_recovery(context)  # Called by HeartbeatMonitor
    """

    def __init__(
        self,
        lifecycle_manager: "_LifecycleManager",
        max_connection_retries: int = DEFAULT_MAX_CONNECTION_RETRIES,
        max_relaunch_retries: int = DEFAULT_MAX_RELAUNCH_RETRIES,
        recovery_timeout: float = DEFAULT_RECOVERY_TIMEOUT,
    ) -> None:
        """Initialize RecoveryManager.

        Args:
            lifecycle_manager: LifecycleManager instance for process operations.
            max_connection_retries: Maximum connection retry attempts (default 3).
            max_relaunch_retries: Maximum MT5 relaunch attempts (default 2).
            recovery_timeout: Total recovery timeout in seconds (default 30, NFR5).
        """
        self._lifecycle_manager = lifecycle_manager
        self._max_connection_retries = max_connection_retries
        self._max_relaunch_retries = max_relaunch_retries
        self._recovery_timeout = recovery_timeout
        self._recovery_in_progress: bool = False
        self._last_recovery_attempt: Optional[float] = None
        self._recovery_stats: Dict[str, int] = {"success": 0, "failure": 0}
        self._recovery_callbacks: List[Callable[[bool, Dict[str, Any]], None]] = []
        self._lock = threading.Lock()

        logger.debug(
            f"RecoveryManager initialized: max_retries={max_connection_retries}, "
            f"max_relaunch={max_relaunch_retries}, timeout={recovery_timeout}s"
        )

    def register_recovery_callback(
        self, callback: Callable[[bool, Dict[str, Any]], None]
    ) -> None:
        """Register callback for recovery completion notifications.

        Callbacks are invoked when recovery completes (success or failure).
        The callback receives two arguments:
        - success: True if recovery succeeded, False otherwise
        - context: Dictionary with recovery details

        Args:
            callback: Function accepting (success: bool, context: dict).
        """
        with self._lock:
            if callback not in self._recovery_callbacks:
                self._recovery_callbacks.append(callback)
                logger.debug(f"Registered recovery callback: {callback}")

    def unregister_recovery_callback(
        self, callback: Callable[[bool, Dict[str, Any]], None]
    ) -> None:
        """Unregister a previously registered recovery callback.

        Args:
            callback: The callback to remove from the notification list.
        """
        with self._lock:
            if callback in self._recovery_callbacks:
                self._recovery_callbacks.remove(callback)
                logger.debug(f"Unregistered recovery callback: {callback}")

    def get_recovery_status(self) -> Dict[str, Any]:
        """Get current recovery status and statistics.

        Returns:
            Dictionary containing:
                - last_recovery_time: Timestamp of last recovery attempt
                - recovery_in_progress: True if recovery is active
                - success_count: Total successful recoveries
                - failure_count: Total failed recoveries
        """
        with self._lock:
            return {
                "last_recovery_time": self._last_recovery_attempt,
                "recovery_in_progress": self._recovery_in_progress,
                "success_count": self._recovery_stats["success"],
                "failure_count": self._recovery_stats["failure"],
            }

    def attempt_recovery(self, context: Dict[str, Any]) -> bool:
        """Main recovery entry point. Called by HeartbeatMonitor failure callback.

        Executes recovery sequence: retry → relaunch → retry → notify.
        Must complete within recovery_timeout (default 30s, NFR5).

        Args:
            context: Failure context from HeartbeatMonitor containing:
                - last_heartbeat_time: Timestamp of last successful heartbeat
                - consecutive_failures: Count of consecutive failures
                - time_since_heartbeat: Seconds since last heartbeat

        Returns:
            True if recovery succeeded, False otherwise.
        """
        # Prevent concurrent recovery attempts
        with self._lock:
            if self._recovery_in_progress:
                logger.warning("Recovery already in progress, skipping")
                return False
            self._recovery_in_progress = True
            self._last_recovery_attempt = time.time()

        start_time = time.time()
        success = False

        try:
            logger.info(
                f"Starting recovery sequence (timeout: {self._recovery_timeout}s)"
            )

            # Step 1: Retry connection
            if self._check_timeout(start_time):
                logger.warning("Recovery timeout exceeded before starting")
                return False

            if self._retry_connection():
                logger.info("Recovery succeeded via connection retry")
                success = True
            else:
                # Step 2: Relaunch MT5
                if self._check_timeout(start_time):
                    logger.warning("Recovery timeout exceeded before MT5 relaunch")
                    return False

                if self._relaunch_mt5():
                    # Step 3: Retry connection after relaunch
                    if self._check_timeout(start_time):
                        logger.warning("Recovery timeout exceeded after MT5 relaunch")
                        return False

                    if self._retry_after_relaunch():
                        logger.info("Recovery succeeded after MT5 relaunch")
                        success = True
                    else:
                        logger.error(
                            "Recovery failed: connection failed after relaunch"
                        )
                else:
                    logger.error("Recovery failed: MT5 relaunch failed")

            return success

        finally:
            # Update stats and notify
            with self._lock:
                self._recovery_in_progress = False
                if success:
                    self._recovery_stats["success"] += 1
                else:
                    self._recovery_stats["failure"] += 1

            # Notify callbacks with context (AC#5: include troubleshooting on failure)
            elapsed = time.time() - start_time
            notification_context: Dict[str, Any] = {
                "elapsed_time": elapsed,
                "original_context": context,
            }

            if not success:
                # AC#5: Provide actionable error message and troubleshooting steps
                notification_context["actionable_message"] = (
                    "Automatic recovery failed after exhausting all retry attempts. "
                    "Manual intervention may be required."
                )
                notification_context["troubleshooting_steps"] = TROUBLESHOOTING_STEPS
                notification_context["suggested_actions"] = [
                    "Check MT5 and rpyc server status",
                    "Review system logs for errors",
                    "Consider manual restart of components",
                ]
                logger.error(
                    f"Recovery failed after {elapsed:.1f}s. "
                    f"Troubleshooting: {TROUBLESHOOTING_STEPS[0]}"
                )

            self._notify_callbacks(success, notification_context)

    def _check_timeout(self, start_time: float) -> bool:
        """Check if recovery timeout has been exceeded.

        Args:
            start_time: When recovery started.

        Returns:
            True if timeout exceeded, False otherwise.
        """
        elapsed = time.time() - start_time
        return elapsed >= self._recovery_timeout

    def _retry_connection(self) -> bool:
        """Step 1: Retry connection with exponential backoff.

        Attempts to reconnect to the rpyc server up to max_connection_retries
        times, using exponential backoff between attempts.

        Returns:
            True if connection succeeded, False otherwise.
        """
        conn_mgr = self._lifecycle_manager._connection_manager
        if conn_mgr is None:
            logger.error("No connection manager available")
            return False

        for attempt in range(self._max_connection_retries):
            try:
                logger.debug(
                    f"Connection retry attempt {attempt + 1}/{self._max_connection_retries}"
                )

                # Disconnect first to clear stale state
                conn_mgr.disconnect()

                # Attempt reconnection
                if conn_mgr.connect():
                    logger.info(f"Connection retry succeeded on attempt {attempt + 1}")
                    return True

            except Exception as e:
                logger.warning(f"Connection retry {attempt + 1} failed: {e}")

            # Backoff before next attempt (except after last attempt)
            if attempt < self._max_connection_retries - 1:
                delay = self._calculate_backoff(attempt)
                logger.debug(f"Waiting {delay:.2f}s before next retry")
                time.sleep(delay)

        logger.warning(f"All {self._max_connection_retries} connection retries failed")
        return False

    def _relaunch_mt5(self) -> bool:
        """Step 2: Relaunch MT5 via LifecycleManager.

        Attempts to restart MT5 up to max_relaunch_retries times.

        Returns:
            True if MT5 relaunch succeeded, False otherwise.
        """
        for attempt in range(self._max_relaunch_retries):
            try:
                logger.debug(
                    f"MT5 relaunch attempt {attempt + 1}/{self._max_relaunch_retries}"
                )

                # Use LifecycleManager to ensure MT5 is running
                self._lifecycle_manager.ensure_mt5_running()
                logger.info(f"MT5 relaunch succeeded on attempt {attempt + 1}")
                return True

            except Exception as e:
                logger.warning(f"MT5 relaunch {attempt + 1} failed: {e}")

            # Backoff before next attempt
            if attempt < self._max_relaunch_retries - 1:
                delay = self._calculate_backoff(attempt)
                time.sleep(delay)

        logger.warning(f"All {self._max_relaunch_retries} MT5 relaunch attempts failed")
        return False

    def _retry_after_relaunch(self) -> bool:
        """Step 3: Retry connection after MT5 relaunch.

        Uses fewer retries than initial retry since MT5 was just restarted.

        Returns:
            True if connection succeeded, False otherwise.
        """
        conn_mgr = self._lifecycle_manager._connection_manager
        if conn_mgr is None:
            logger.error("No connection manager available")
            return False

        # Use half the retries since MT5 was just restarted
        max_retries = max(2, self._max_connection_retries // 2)

        for attempt in range(max_retries):
            try:
                logger.debug(
                    f"Post-relaunch connection attempt {attempt + 1}/{max_retries}"
                )

                if conn_mgr.connect():
                    logger.info(
                        f"Post-relaunch connection succeeded on attempt {attempt + 1}"
                    )
                    return True

            except Exception as e:
                logger.warning(f"Post-relaunch connection {attempt + 1} failed: {e}")

            if attempt < max_retries - 1:
                delay = self._calculate_backoff(attempt)
                time.sleep(delay)

        logger.warning(f"All {max_retries} post-relaunch connection attempts failed")
        return False

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter.

        Pattern: delay = min(base * 2^attempt, max) + jitter

        Args:
            attempt: Zero-indexed attempt number.

        Returns:
            Delay in seconds.
        """
        delay = min(RETRY_BASE_DELAY * (2**attempt), RETRY_MAX_DELAY)
        jitter = random.uniform(0, RETRY_JITTER_MAX)
        return delay + jitter

    def _notify_callbacks(self, success: bool, context: Dict[str, Any]) -> None:
        """Notify all registered callbacks of recovery completion.

        Args:
            success: True if recovery succeeded.
            context: Recovery context including elapsed time.
        """
        with self._lock:
            callbacks = list(self._recovery_callbacks)

        for callback in callbacks:
            try:
                callback(success, context)
            except Exception as e:
                logger.error(f"Recovery callback error: {e}")
