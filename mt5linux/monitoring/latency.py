"""Latency monitoring module (Story 4.3).

This module provides the LatencyMonitor class for measuring end-to-end latency
from order submission to execution confirmation.
"""

import time
from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)  # type: ignore[assignment]

from mt5linux.config import LatencyConfig


@dataclass(frozen=True, slots=True)
class LatencyMeasurement:
    """A single latency measurement (Story 4.3).

    Contains timing data for one order execution cycle.

    Attributes:
        order_ticket: MT5 order ticket number.
        symbol: Trading symbol (e.g., "EURUSD").
        order_type: Order type ("buy" or "sell").
        send_timestamp: Unix timestamp when order was sent.
        execution_timestamp: Unix timestamp when execution confirmed.
        latency_ms: End-to-end latency in milliseconds.
        is_high_latency: True if latency exceeded threshold.
    """

    order_ticket: int
    symbol: str
    order_type: str
    send_timestamp: float
    execution_timestamp: float
    latency_ms: float
    is_high_latency: bool


@dataclass(frozen=True, slots=True)
class LatencyAlert:
    """High latency alert (Story 4.3).

    Generated when measured latency exceeds configured threshold.

    Attributes:
        measurement: The LatencyMeasurement that triggered the alert.
        threshold_ms: Configured threshold in milliseconds.
        alert_timestamp: Unix timestamp when alert was generated.
        message: Human-readable alert message.
    """

    measurement: LatencyMeasurement
    threshold_ms: float
    alert_timestamp: float
    message: str


class LatencyMonitor:
    """Monitors trading order latency (Story 4.3).

    Measures end-to-end latency from order submission to execution
    confirmation per FR52, NFR2, NFR3.

    Example:
        >>> monitor = LatencyMonitor()
        >>> monitor.on_high_latency(send_telegram_alert)
        >>> monitor.start()
        >>> # In trading code:
        >>> monitor.record_order_sent(12345, "EURUSD", "buy")
        >>> # ... order executes ...
        >>> measurement = monitor.record_order_executed(12345)
        >>> if measurement:
        ...     print(f"Latency: {measurement.latency_ms}ms")

    Attributes:
        _enabled: Whether monitoring is enabled.
        _threshold_ms: Latency threshold in milliseconds.
        _warning_delivery_secs: Max seconds to deliver warning.
        _pending_orders: Dict mapping order_ticket to (symbol, order_type, timestamp).
        _measurements: List of completed LatencyMeasurement objects.
        _high_latency_callbacks: List of callbacks for high latency alerts.
        _lock: RLock for thread-safe operations.
        _high_latency_count: Number of high latency events.
        _start_time: Timestamp when monitor was started.
    """

    def __init__(self, config: Optional[LatencyConfig] = None) -> None:
        """Initialize LatencyMonitor.

        Args:
            config: Optional LatencyConfig. Uses defaults if not provided.
        """
        if config is None:
            config = LatencyConfig()

        self._enabled = config.enabled
        self._threshold_ms = config.threshold_ms
        self._warning_delivery_secs = config.warning_delivery_secs

        # Pending orders awaiting execution: order_ticket -> (symbol, order_type, send_timestamp)
        self._pending_orders: Dict[int, Tuple[str, str, float]] = {}

        # Completed measurements
        self._measurements: List[LatencyMeasurement] = []

        # Callbacks for high latency alerts
        self._high_latency_callbacks: List[Callable[[LatencyAlert], None]] = []

        # Thread safety
        self._lock = RLock()

        # Statistics
        self._high_latency_count = 0
        self._start_time: Optional[float] = None

        logger.debug(
            f"LatencyMonitor initialized: enabled={self._enabled}, "
            f"threshold_ms={self._threshold_ms}"
        )

    def start(self) -> None:
        """Start the latency monitor."""
        with self._lock:
            self._start_time = time.time()
            logger.info("LatencyMonitor started")

    def stop(self) -> None:
        """Stop the latency monitor."""
        with self._lock:
            self._start_time = None
            logger.info("LatencyMonitor stopped")

    @property
    def is_running(self) -> bool:
        """Return whether the monitor is running."""
        return self._start_time is not None

    @property
    def is_enabled(self) -> bool:
        """Return whether monitoring is enabled."""
        return self._enabled

    def record_order_sent(
        self,
        order_ticket: int,
        symbol: str,
        order_type: str,
    ) -> None:
        """Record that an order was sent for latency tracking.

        Args:
            order_ticket: MT5 order ticket number.
            symbol: Trading symbol (e.g., "EURUSD").
            order_type: Order type ("buy" or "sell").
        """
        if not self._enabled:
            return

        with self._lock:
            self._pending_orders[order_ticket] = (
                symbol,
                order_type,
                time.time(),
            )
            logger.debug(
                f"Recording order sent: {order_ticket} ({symbol} {order_type})"
            )

    def record_order_executed(
        self,
        order_ticket: int,
    ) -> Optional[LatencyMeasurement]:
        """Record that an order was executed and calculate latency.

        Args:
            order_ticket: MT5 order ticket number.

        Returns:
            LatencyMeasurement if order was found in pending, None otherwise.
        """
        if not self._enabled:
            return None

        execution_time = time.time()

        with self._lock:
            if order_ticket not in self._pending_orders:
                logger.warning(f"Order {order_ticket} not found in pending orders")
                return None

            symbol, order_type, send_time = self._pending_orders.pop(order_ticket)
            latency_ms = (execution_time - send_time) * 1000
            is_high = latency_ms > self._threshold_ms

            measurement = LatencyMeasurement(
                order_ticket=order_ticket,
                symbol=symbol,
                order_type=order_type,
                send_timestamp=send_time,
                execution_timestamp=execution_time,
                latency_ms=latency_ms,
                is_high_latency=is_high,
            )

            self._measurements.append(measurement)

            if is_high:
                self._high_latency_count += 1
                self._handle_high_latency(measurement)

            logger.debug(f"Order {order_ticket} latency: {latency_ms:.2f}ms")
            return measurement

    def _handle_high_latency(self, measurement: LatencyMeasurement) -> None:
        """Handle high latency detection.

        Args:
            measurement: The high latency measurement.
        """
        alert = LatencyAlert(
            measurement=measurement,
            threshold_ms=self._threshold_ms,
            alert_timestamp=time.time(),
            message=(
                f"High latency detected: {measurement.latency_ms:.2f}ms "
                f"(threshold: {self._threshold_ms}ms) for {measurement.symbol}"
            ),
        )

        logger.warning(
            f"High latency: {measurement.latency_ms:.2f}ms for order "
            f"{measurement.order_ticket} ({measurement.symbol})"
        )

        for callback in self._high_latency_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"High latency callback error: {e}", exc_info=True)

    def on_high_latency(self, callback: Callable[[LatencyAlert], None]) -> None:
        """Register callback for high latency alerts.

        Args:
            callback: Function to call with LatencyAlert when high latency detected.
        """
        with self._lock:
            self._high_latency_callbacks.append(callback)
            logger.debug(f"Registered high latency callback: {callback}")

    def unregister_high_latency_callback(
        self, callback: Callable[[LatencyAlert], None]
    ) -> None:
        """Unregister a previously registered high latency callback.

        Args:
            callback: The callback to unregister.
        """
        with self._lock:
            if callback in self._high_latency_callbacks:
                self._high_latency_callbacks.remove(callback)
                logger.debug(f"Unregistered high latency callback: {callback}")

    def get_status(self) -> Dict[str, Any]:
        """Get current monitor status.

        Returns:
            Dictionary containing monitor status information.
        """
        with self._lock:
            latencies = [m.latency_ms for m in self._measurements]

            avg_latency: Optional[float] = None
            max_latency: Optional[float] = None
            min_latency: Optional[float] = None

            if latencies:
                avg_latency = sum(latencies) / len(latencies)
                max_latency = max(latencies)
                min_latency = min(latencies)

            return {
                "enabled": self._enabled,
                "threshold_ms": self._threshold_ms,
                "measurement_count": len(self._measurements),
                "average_latency_ms": avg_latency,
                "max_latency_ms": max_latency,
                "min_latency_ms": min_latency,
                "high_latency_count": self._high_latency_count,
                "last_measurement_time": (
                    self._measurements[-1].execution_timestamp
                    if self._measurements
                    else None
                ),
                "pending_orders_count": len(self._pending_orders),
            }

    def get_average_latency(self) -> Optional[float]:
        """Get average latency in milliseconds.

        Returns:
            Average latency in ms, or None if no measurements.
        """
        with self._lock:
            if not self._measurements:
                return None
            latencies = [m.latency_ms for m in self._measurements]
            return sum(latencies) / len(latencies)

    def get_latency_percentile(self, percentile: float) -> Optional[float]:
        """Get latency at specified percentile.

        Args:
            percentile: Percentile value (0-100).

        Returns:
            Latency in ms at the specified percentile, or None if no measurements.

        Raises:
            ValueError: If percentile is not in range [0, 100].
        """
        if not 0.0 <= percentile <= 100.0:
            raise ValueError(f"percentile must be between 0 and 100, got {percentile}")

        with self._lock:
            if not self._measurements:
                return None

            latencies = sorted(m.latency_ms for m in self._measurements)
            # Linear interpolation for percentile
            index = (percentile / 100.0) * (len(latencies) - 1)
            lower_idx = int(index)
            upper_idx = min(lower_idx + 1, len(latencies) - 1)
            fraction = index - lower_idx

            return latencies[lower_idx] + fraction * (
                latencies[upper_idx] - latencies[lower_idx]
            )

    def get_recent_measurements(self, count: int) -> List[LatencyMeasurement]:
        """Get most recent measurements.

        Args:
            count: Maximum number of measurements to return. Must be non-negative.

        Returns:
            List of most recent LatencyMeasurement objects.

        Raises:
            ValueError: If count is negative.
        """
        if count < 0:
            raise ValueError(f"count must be non-negative, got {count}")
        with self._lock:
            return list(self._measurements[-count:]) if count > 0 else []

    def clear_measurements(self) -> int:
        """Clear all stored measurements and reset statistics.

        Useful for long-running sessions to prevent memory growth.

        Returns:
            Number of measurements that were cleared.
        """
        with self._lock:
            count = len(self._measurements)
            self._measurements.clear()
            self._high_latency_count = 0
            logger.info(f"Cleared {count} latency measurements")
            return count

    def clear_pending_orders(self) -> int:
        """Clear all pending orders that were never executed.

        Useful for cleaning up stale orders (cancelled, timed out, etc.).

        Returns:
            Number of pending orders that were cleared.
        """
        with self._lock:
            count = len(self._pending_orders)
            if count > 0:
                logger.warning(
                    f"Clearing {count} pending orders that were never executed"
                )
            self._pending_orders.clear()
            return count
