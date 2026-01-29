"""Connection management module for mt5linux.

This module provides the ConnectionManager class for establishing and managing
connections to the rpyc server that interfaces with MetaTrader5.

Connection establishment must complete within 5 seconds (NFR1) with 100%
availability when MT5 server is available (NFR10).
"""

import builtins
import socket
import threading
import time
from typing import TYPE_CHECKING, Any, Dict, Optional, Union

from mt5linux.process_manager import MT5LinuxError

if TYPE_CHECKING:
    import logging as _logging

    import rpyc as _rpyc
    from loguru import Logger as _LoguruLogger

    LoggerType = Union[_LoguruLogger, _logging.Logger]

try:
    from loguru import logger
except ImportError:
    # Fallback to standard logging if loguru not available
    import logging

    logger: "LoggerType" = logging.getLogger(__name__)  # type: ignore[no-redef]

# Import rpyc for connection (required dependency)
import rpyc

# Import config module for host/port settings
try:
    from mt5linux.config import get_config
except ImportError:
    get_config = None  # type: ignore

# Connection timeout constants
DEFAULT_CONNECTION_TIMEOUT = 5.0  # seconds (NFR1)
SYNC_REQUEST_TIMEOUT = 300  # seconds (5 minutes, existing pattern)
SOCKET_PING_TIMEOUT = 2.0  # seconds

# Alias for built-in ConnectionRefusedError to avoid shadowing
BuiltinConnectionRefusedError = builtins.ConnectionRefusedError


class ConnectionError(MT5LinuxError):
    """Base exception for connection-related errors.

    Raised when connection operations fail due to network issues,
    server unavailability, or other connection problems.

    All connection-specific exceptions inherit from this class.
    """

    pass


class ConnectionTimeoutError(ConnectionError):
    """Raised when connection establishment times out.

    This exception indicates that the connection attempt to the rpyc server
    did not complete within the specified timeout period. The error message
    includes troubleshooting suggestions.

    Example:
        >>> raise ConnectionTimeoutError(
        ...     "Connection to localhost:18812 timed out after 5 seconds. "
        ...     "Ensure rpyc server is running."
        ... )
    """

    pass


class ConnectionRefusedError(ConnectionError):
    """Raised when connection is refused by the server.

    This exception indicates that the rpyc server actively refused the
    connection attempt. This typically means the server is not running
    or is not listening on the expected port.

    Example:
        >>> raise ConnectionRefusedError(
        ...     "Connection to localhost:18812 refused. "
        ...     "Ensure rpyc server is running and listening."
        ... )
    """

    pass


class ConnectionManager:
    """Manages connection to rpyc server for MetaTrader5 access.

    Provides methods to establish, verify, and close connections to the
    rpyc server. All operations are thread-safe using internal locking.

    Connection establishment must complete within 5 seconds (NFR1).

    Attributes:
        _host: Server host address.
        _port: Server port number.
        _timeout: Connection timeout in seconds.
        _conn: rpyc connection object (None if not connected).
        _connected: Flag indicating connection state.
        _connection_time: Timestamp when connection was established.
        _lock: Threading lock for thread-safe operations.

    Example:
        >>> from mt5linux.connection import ConnectionManager
        >>> manager = ConnectionManager(host="localhost", port=18812)
        >>> manager.connect()
        True
        >>> manager.is_connected
        True
        >>> manager.disconnect()
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        timeout: float = DEFAULT_CONNECTION_TIMEOUT,
    ) -> None:
        """Initialize ConnectionManager.

        Args:
            host: Server host address. Defaults to config value or 'localhost'.
            port: Server port number. Defaults to config value or 18812.
            timeout: Connection timeout in seconds. Defaults to 5.0 seconds.
        """
        # Get config values for defaults
        config = get_config() if get_config is not None else None
        if config:
            default_host = config.server.host
            default_port = config.server.port
        else:
            default_host = "localhost"
            default_port = 18812

        self._host = host or default_host
        self._port = port or default_port
        self._timeout = timeout
        self._conn: Optional["_rpyc.Connection"] = None
        self._connected = False
        self._connection_time: Optional[float] = None
        self._lock = threading.Lock()

        logger.debug(
            f"ConnectionManager initialized: host={self._host}, "
            f"port={self._port}, timeout={self._timeout}s"
        )

    def connect(self) -> bool:
        """Establish connection to rpyc server.

        Connects to the rpyc server using the configured host and port.
        Sets up the connection with sync_request_timeout and executes
        initialization commands for MetaTrader5.

        Returns:
            True if connection established successfully.

        Raises:
            ConnectionTimeoutError: If connection times out.
            ConnectionRefusedError: If connection is refused.
            ConnectionError: If connection fails for other reasons.

        Note:
            - Connection must complete within timeout (default 5s, NFR1)
            - Already-connected state returns True immediately
            - Thread-safe: uses internal lock
        """
        with self._lock:
            if self._connected:
                logger.debug("Already connected, returning True")
                return True

            start_time = time.time()
            old_timeout = socket.getdefaulttimeout()

            try:
                # Set temporary socket timeout for connection establishment
                socket.setdefaulttimeout(self._timeout)

                logger.debug(
                    f"Connecting to rpyc server at {self._host}:{self._port}"
                )

                # Establish rpyc connection
                self._conn = rpyc.classic.connect(self._host, self._port)
                self._conn._config["sync_request_timeout"] = SYNC_REQUEST_TIMEOUT

                # Initialize MT5 environment (existing pattern from __init__.py)
                self._conn.execute("import MetaTrader5 as mt5")
                self._conn.execute("import datetime")

                self._connected = True
                self._connection_time = time.time()
                elapsed = self._connection_time - start_time

                logger.info(
                    f"Connected to rpyc server at {self._host}:{self._port} "
                    f"in {elapsed:.2f}s"
                )
                return True

            except socket.timeout as e:
                logger.error(f"Connection timeout after {self._timeout}s")
                raise ConnectionTimeoutError(
                    f"Connection to {self._host}:{self._port} timed out after "
                    f"{self._timeout} seconds. Ensure rpyc server is running."
                ) from e
            except BuiltinConnectionRefusedError as e:
                logger.error(f"Connection refused: {e}")
                raise ConnectionRefusedError(
                    f"Connection to {self._host}:{self._port} refused. "
                    "Ensure rpyc server is running and listening."
                ) from e
            except Exception as e:
                logger.error(f"Connection failed: {e}")
                raise ConnectionError(
                    f"Failed to connect to {self._host}:{self._port}: {e}"
                ) from e
            finally:
                # Restore original socket timeout
                socket.setdefaulttimeout(old_timeout)

    def disconnect(self) -> None:
        """Close connection to rpyc server.

        Gracefully closes the rpyc connection and resets connection state.
        If not connected or connection is already closed, does nothing.

        Note:
            - Thread-safe: uses internal lock
            - Handles close() exceptions gracefully
        """
        with self._lock:
            if not self._connected:
                logger.debug("Already disconnected")
                return

            logger.debug("Disconnecting from rpyc server")

            try:
                if self._conn is not None:
                    self._conn.close()
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")

            self._conn = None
            self._connected = False
            self._connection_time = None

            logger.info("Disconnected from rpyc server")

    def verify_connection(self) -> bool:
        """Verify connection is active and responsive.

        Performs a three-level verification:
        1. Socket-level ping to verify port is listening
        2. rpyc ping to verify RPC layer is responsive
        3. MT5 command to verify MetaTrader5 is working

        Returns:
            True if all verification levels pass, False otherwise.

        Note:
            - Returns False if not connected
            - Returns False if any verification level fails
            - Thread-safe: uses internal lock
        """
        with self._lock:
            if not self._connected or self._conn is None:
                logger.debug("Not connected, cannot verify")
                return False

            # Level 1: Socket-level ping
            if not self._verify_port_listening(self._host, self._port):
                logger.warning("Socket-level verification failed: port not listening")
                return False

            try:
                # Level 2: rpyc ping - verify RPC layer is responsive
                # rpyc's eval() executes on remote server, not local (noqa: S307)
                self._conn.eval("True")  # noqa: S307
                logger.debug("rpyc layer verified")

                # Level 3: MT5 command - verify MetaTrader5 is working
                # Use mt5.version() as a lightweight health check
                # rpyc's eval() executes on remote server, not local (noqa: S307)
                self._conn.eval("mt5.version()")  # noqa: S307
                logger.debug("MT5 layer verified")

                logger.debug("Connection fully verified (socket + rpyc + MT5)")
                return True
            except Exception as e:
                logger.warning(f"Connection verification failed: {e}")
                return False

    def _verify_port_listening(
        self,
        host: str,
        port: int,
        timeout: float = SOCKET_PING_TIMEOUT,
    ) -> bool:
        """Verify that a port is accepting connections.

        Args:
            host: The host address to connect to.
            port: The port number to check.
            timeout: Connection timeout in seconds.

        Returns:
            True if connection successful, False otherwise.
        """
        try:
            with socket.create_connection((host, port), timeout=timeout):
                # Context manager closes socket on exit
                return True
        except (socket.timeout, socket.error, OSError):
            return False

    @property
    def is_connected(self) -> bool:
        """Check if currently connected.

        Returns:
            True if connected, False otherwise.
        """
        with self._lock:
            return self._connected

    @property
    def connection_info(self) -> Dict[str, Any]:
        """Get connection details.

        Returns:
            Dictionary containing:
                - connected: Whether currently connected
                - host: Server host address
                - port: Server port number
                - connection_time: Timestamp of connection (if connected)
                - uptime: Seconds since connection (if connected)
        """
        with self._lock:
            info: Dict[str, Any] = {
                "connected": self._connected,
                "host": self._host,
                "port": self._port,
            }

            if self._connected and self._connection_time is not None:
                info["connection_time"] = self._connection_time
                info["uptime"] = time.time() - self._connection_time

            return info

    @property
    def uptime(self) -> Optional[float]:
        """Get connection uptime in seconds.

        Returns:
            Seconds since connection was established, or None if not connected.
        """
        with self._lock:
            if not self._connected or self._connection_time is None:
                return None
            return time.time() - self._connection_time
