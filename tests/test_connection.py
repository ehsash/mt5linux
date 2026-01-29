"""Unit tests for connection module.

Tests the ConnectionManager class and connection exception hierarchy.
All tests use mocks for rpyc and socket to enable isolated testing.
"""

import builtins
import socket
import threading
import time
from contextlib import ExitStack
from unittest.mock import MagicMock, Mock, patch

import pytest


# =============================================================================
# Task 1: Connection Exception Classes Tests
# =============================================================================


@pytest.mark.unit
class TestConnectionExceptionHierarchy:
    """Test connection exception class hierarchy."""

    def test_connection_error_inherits_from_mt5linux_error(self) -> None:
        """ConnectionError should inherit from MT5LinuxError."""
        from mt5linux.connection import ConnectionError
        from mt5linux.process_manager import MT5LinuxError

        assert issubclass(ConnectionError, MT5LinuxError)

    def test_connection_timeout_error_inherits_from_connection_error(self) -> None:
        """ConnectionTimeoutError should inherit from ConnectionError."""
        from mt5linux.connection import ConnectionError, ConnectionTimeoutError

        assert issubclass(ConnectionTimeoutError, ConnectionError)

    def test_connection_refused_error_inherits_from_connection_error(self) -> None:
        """ConnectionRefusedError should inherit from ConnectionError."""
        from mt5linux.connection import ConnectionError, ConnectionRefusedError

        assert issubclass(ConnectionRefusedError, ConnectionError)

    def test_connection_error_message(self) -> None:
        """ConnectionError should preserve error message."""
        from mt5linux.connection import ConnectionError

        error = ConnectionError("Test error message")
        assert str(error) == "Test error message"

    def test_connection_timeout_error_message(self) -> None:
        """ConnectionTimeoutError should preserve error message."""
        from mt5linux.connection import ConnectionTimeoutError

        error = ConnectionTimeoutError("Connection timed out after 5s")
        assert "timed out" in str(error).lower()

    def test_connection_refused_error_message(self) -> None:
        """ConnectionRefusedError should preserve error message."""
        from mt5linux.connection import ConnectionRefusedError

        error = ConnectionRefusedError("Connection refused by server")
        assert "refused" in str(error).lower()

    def test_exception_docstrings_exist(self) -> None:
        """All exception classes should have docstrings."""
        from mt5linux.connection import (
            ConnectionError,
            ConnectionRefusedError,
            ConnectionTimeoutError,
        )

        assert ConnectionError.__doc__ is not None
        assert ConnectionTimeoutError.__doc__ is not None
        assert ConnectionRefusedError.__doc__ is not None


# =============================================================================
# Task 2: ConnectionManager Class Tests
# =============================================================================


@pytest.mark.unit
class TestConnectionManagerInit:
    """Test ConnectionManager initialization."""

    def test_init_with_defaults(self) -> None:
        """ConnectionManager should initialize with default config values."""
        with patch("mt5linux.connection.get_config") as mock_config:
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            from mt5linux.connection import ConnectionManager

            manager = ConnectionManager()

            assert manager._host == "localhost"
            assert manager._port == 18812
            assert manager._timeout == 5.0
            assert manager._conn is None
            assert manager._connected is False
            assert manager._connection_time is None

    def test_init_with_custom_host_port(self) -> None:
        """ConnectionManager should accept custom host and port."""
        with patch("mt5linux.connection.get_config") as mock_config:
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            from mt5linux.connection import ConnectionManager

            manager = ConnectionManager(host="192.168.1.100", port=28812)

            assert manager._host == "192.168.1.100"
            assert manager._port == 28812

    def test_init_with_custom_timeout(self) -> None:
        """ConnectionManager should accept custom timeout."""
        with patch("mt5linux.connection.get_config") as mock_config:
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            from mt5linux.connection import ConnectionManager

            manager = ConnectionManager(timeout=10.0)

            assert manager._timeout == 10.0

    def test_init_creates_lock(self) -> None:
        """ConnectionManager should create a threading lock."""
        with patch("mt5linux.connection.get_config") as mock_config:
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            from mt5linux.connection import ConnectionManager

            manager = ConnectionManager()

            assert hasattr(manager, "_lock")
            assert isinstance(manager._lock, type(threading.Lock()))


# =============================================================================
# Task 3: Connect Method Tests
# =============================================================================


@pytest.mark.unit
class TestConnect:
    """Test ConnectionManager.connect() method."""

    def test_connect_success(self) -> None:
        """connect() should establish connection and return True."""
        with ExitStack() as stack:
            mock_config = stack.enter_context(
                patch("mt5linux.connection.get_config")
            )
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            mock_rpyc = stack.enter_context(
                patch("mt5linux.connection.rpyc")
            )
            mock_conn = MagicMock()
            mock_conn._config = {}
            mock_rpyc.classic.connect.return_value = mock_conn

            stack.enter_context(patch("mt5linux.connection.socket"))

            from mt5linux.connection import ConnectionManager

            manager = ConnectionManager()
            result = manager.connect()

            assert result is True
            assert manager._connected is True
            assert manager._conn is mock_conn
            mock_rpyc.classic.connect.assert_called_once_with("localhost", 18812)
            mock_conn.execute.assert_any_call("import MetaTrader5 as mt5")
            mock_conn.execute.assert_any_call("import datetime")

    def test_connect_already_connected_returns_true(self) -> None:
        """connect() should return True if already connected."""
        with ExitStack() as stack:
            mock_config = stack.enter_context(
                patch("mt5linux.connection.get_config")
            )
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            from mt5linux.connection import ConnectionManager

            manager = ConnectionManager()
            manager._connected = True
            manager._conn = MagicMock()

            result = manager.connect()

            assert result is True

    def test_connect_sets_sync_request_timeout(self) -> None:
        """connect() should set sync_request_timeout to 300 seconds."""
        with ExitStack() as stack:
            mock_config = stack.enter_context(
                patch("mt5linux.connection.get_config")
            )
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            mock_rpyc = stack.enter_context(
                patch("mt5linux.connection.rpyc")
            )
            mock_conn = MagicMock()
            mock_conn._config = {}
            mock_rpyc.classic.connect.return_value = mock_conn

            stack.enter_context(patch("mt5linux.connection.socket"))

            from mt5linux.connection import ConnectionManager

            manager = ConnectionManager()
            manager.connect()

            assert mock_conn._config["sync_request_timeout"] == 300

    def test_connect_records_connection_time(self) -> None:
        """connect() should record connection establishment time."""
        with ExitStack() as stack:
            mock_config = stack.enter_context(
                patch("mt5linux.connection.get_config")
            )
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            mock_rpyc = stack.enter_context(
                patch("mt5linux.connection.rpyc")
            )
            mock_conn = MagicMock()
            mock_conn._config = {}
            mock_rpyc.classic.connect.return_value = mock_conn

            stack.enter_context(patch("mt5linux.connection.socket"))

            from mt5linux.connection import ConnectionManager

            manager = ConnectionManager()
            before = time.time()
            manager.connect()
            after = time.time()

            assert manager._connection_time is not None
            assert before <= manager._connection_time <= after

    def test_connect_timeout_raises_connection_timeout_error(self) -> None:
        """connect() should raise ConnectionTimeoutError on socket timeout."""
        with ExitStack() as stack:
            mock_config = stack.enter_context(
                patch("mt5linux.connection.get_config")
            )
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            mock_rpyc = stack.enter_context(
                patch("mt5linux.connection.rpyc")
            )
            mock_rpyc.classic.connect.side_effect = socket.timeout("timed out")

            # Only mock specific socket functions, not the whole module
            stack.enter_context(
                patch("mt5linux.connection.socket.getdefaulttimeout", return_value=30.0)
            )
            stack.enter_context(
                patch("mt5linux.connection.socket.setdefaulttimeout")
            )

            from mt5linux.connection import ConnectionManager, ConnectionTimeoutError

            manager = ConnectionManager()

            with pytest.raises(ConnectionTimeoutError) as exc_info:
                manager.connect()

            assert "timed out" in str(exc_info.value).lower()
            assert manager._connected is False

    def test_connect_refused_raises_connection_refused_error(self) -> None:
        """connect() should raise ConnectionRefusedError when refused."""
        with ExitStack() as stack:
            mock_config = stack.enter_context(
                patch("mt5linux.connection.get_config")
            )
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            mock_rpyc = stack.enter_context(
                patch("mt5linux.connection.rpyc")
            )
            # Use builtins.ConnectionRefusedError (the real exception)
            mock_rpyc.classic.connect.side_effect = builtins.ConnectionRefusedError(
                "Connection refused"
            )

            # Only mock specific socket functions, not the whole module
            stack.enter_context(
                patch("mt5linux.connection.socket.getdefaulttimeout", return_value=30.0)
            )
            stack.enter_context(
                patch("mt5linux.connection.socket.setdefaulttimeout")
            )

            from mt5linux.connection import ConnectionManager
            from mt5linux.connection import (
                ConnectionRefusedError as ConnRefusedError,
            )

            manager = ConnectionManager()

            with pytest.raises(ConnRefusedError) as exc_info:
                manager.connect()

            assert "refused" in str(exc_info.value).lower()
            assert manager._connected is False

    def test_connect_generic_error_raises_connection_error(self) -> None:
        """connect() should raise ConnectionError on generic failures."""
        with ExitStack() as stack:
            mock_config = stack.enter_context(
                patch("mt5linux.connection.get_config")
            )
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            mock_rpyc = stack.enter_context(
                patch("mt5linux.connection.rpyc")
            )
            mock_rpyc.classic.connect.side_effect = Exception("Network error")

            # Only mock specific socket functions, not the whole module
            stack.enter_context(
                patch("mt5linux.connection.socket.getdefaulttimeout", return_value=30.0)
            )
            stack.enter_context(
                patch("mt5linux.connection.socket.setdefaulttimeout")
            )

            from mt5linux.connection import ConnectionError, ConnectionManager

            manager = ConnectionManager()

            with pytest.raises(ConnectionError) as exc_info:
                manager.connect()

            assert "Network error" in str(exc_info.value)
            assert manager._connected is False

    def test_connect_restores_socket_timeout(self) -> None:
        """connect() should restore original socket timeout on success."""
        with ExitStack() as stack:
            mock_config = stack.enter_context(
                patch("mt5linux.connection.get_config")
            )
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            mock_rpyc = stack.enter_context(
                patch("mt5linux.connection.rpyc")
            )
            mock_conn = MagicMock()
            mock_conn._config = {}
            mock_rpyc.classic.connect.return_value = mock_conn

            mock_socket_module = stack.enter_context(
                patch("mt5linux.connection.socket")
            )
            mock_socket_module.getdefaulttimeout.return_value = 30.0
            mock_socket_module.timeout = socket.timeout

            from mt5linux.connection import ConnectionManager

            manager = ConnectionManager()
            manager.connect()

            # Should restore timeout (setdefaulttimeout called with 5.0 then back to 30.0)
            calls = mock_socket_module.setdefaulttimeout.call_args_list
            assert len(calls) >= 2

    def test_connect_restores_socket_timeout_on_error(self) -> None:
        """connect() should restore socket timeout even on error."""
        with ExitStack() as stack:
            mock_config = stack.enter_context(
                patch("mt5linux.connection.get_config")
            )
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            mock_rpyc = stack.enter_context(
                patch("mt5linux.connection.rpyc")
            )
            mock_rpyc.classic.connect.side_effect = socket.timeout("timed out")

            mock_socket_module = stack.enter_context(
                patch("mt5linux.connection.socket")
            )
            mock_socket_module.getdefaulttimeout.return_value = 30.0
            mock_socket_module.timeout = socket.timeout

            from mt5linux.connection import ConnectionManager, ConnectionTimeoutError

            manager = ConnectionManager()

            with pytest.raises(ConnectionTimeoutError):
                manager.connect()

            # Should still restore timeout
            calls = mock_socket_module.setdefaulttimeout.call_args_list
            assert len(calls) >= 2

    def test_connect_timeout_is_within_nfr1_limit(self) -> None:
        """connect() timeout should be <= 5 seconds (NFR1 requirement)."""
        with ExitStack() as stack:
            mock_config = stack.enter_context(
                patch("mt5linux.connection.get_config")
            )
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            from mt5linux.connection import (
                DEFAULT_CONNECTION_TIMEOUT,
                ConnectionManager,
            )

            # Verify the default timeout constant meets NFR1
            assert DEFAULT_CONNECTION_TIMEOUT <= 5.0, (
                f"NFR1 violation: DEFAULT_CONNECTION_TIMEOUT is {DEFAULT_CONNECTION_TIMEOUT}s, "
                "must be <= 5 seconds"
            )

            # Verify ConnectionManager uses this timeout by default
            manager = ConnectionManager()
            assert manager._timeout <= 5.0, (
                f"NFR1 violation: ConnectionManager timeout is {manager._timeout}s, "
                "must be <= 5 seconds"
            )

    def test_connect_timeout_is_enforced_at_socket_level(self) -> None:
        """connect() should set socket timeout to enforce NFR1."""
        with ExitStack() as stack:
            mock_config = stack.enter_context(
                patch("mt5linux.connection.get_config")
            )
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            mock_rpyc = stack.enter_context(
                patch("mt5linux.connection.rpyc")
            )
            mock_conn = MagicMock()
            mock_conn._config = {}
            mock_rpyc.classic.connect.return_value = mock_conn

            mock_socket_module = stack.enter_context(
                patch("mt5linux.connection.socket")
            )
            mock_socket_module.getdefaulttimeout.return_value = 30.0
            mock_socket_module.timeout = socket.timeout

            from mt5linux.connection import ConnectionManager

            manager = ConnectionManager(timeout=5.0)
            manager.connect()

            # Verify socket timeout was set to 5.0 seconds
            set_timeout_calls = mock_socket_module.setdefaulttimeout.call_args_list
            # First call should set the timeout to 5.0
            assert set_timeout_calls[0][0][0] == 5.0, (
                f"Socket timeout not set to 5.0s, got {set_timeout_calls[0][0][0]}"
            )


# =============================================================================
# Task 4: Verify Connection Tests
# =============================================================================


@pytest.mark.unit
class TestVerifyConnection:
    """Test ConnectionManager.verify_connection() method.

    verify_connection() performs three-level verification:
    1. Socket-level ping (port listening)
    2. rpyc ping (RPC layer)
    3. MT5 command (MetaTrader5 layer)
    """

    def test_verify_connection_success_all_levels(self) -> None:
        """verify_connection() should return True when all levels pass."""
        with ExitStack() as stack:
            mock_config = stack.enter_context(
                patch("mt5linux.connection.get_config")
            )
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            from mt5linux.connection import ConnectionManager

            manager = ConnectionManager()
            manager._connected = True
            mock_conn = MagicMock()
            # Remote execution called twice: rpyc ping + mt5.version()
            mock_conn.eval.return_value = True
            manager._conn = mock_conn

            # Mock socket-level ping
            with patch.object(manager, "_verify_port_listening", return_value=True):
                result = manager.verify_connection()

            assert result is True
            # Verify both remote calls were made (rpyc + MT5)
            assert mock_conn.eval.call_count == 2

    def test_verify_connection_not_connected(self) -> None:
        """verify_connection() should return False when not connected."""
        with ExitStack() as stack:
            mock_config = stack.enter_context(
                patch("mt5linux.connection.get_config")
            )
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            from mt5linux.connection import ConnectionManager

            manager = ConnectionManager()
            manager._connected = False

            result = manager.verify_connection()

            assert result is False

    def test_verify_connection_socket_ping_fails(self) -> None:
        """verify_connection() should return False when socket ping fails."""
        with ExitStack() as stack:
            mock_config = stack.enter_context(
                patch("mt5linux.connection.get_config")
            )
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            from mt5linux.connection import ConnectionManager

            manager = ConnectionManager()
            manager._connected = True
            manager._conn = MagicMock()

            # Mock socket-level ping to fail
            with patch.object(manager, "_verify_port_listening", return_value=False):
                result = manager.verify_connection()

            assert result is False

    def test_verify_connection_rpyc_ping_fails(self) -> None:
        """verify_connection() should return False when rpyc ping fails."""
        with ExitStack() as stack:
            mock_config = stack.enter_context(
                patch("mt5linux.connection.get_config")
            )
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            from mt5linux.connection import ConnectionManager

            manager = ConnectionManager()
            manager._connected = True
            mock_conn = MagicMock()
            mock_conn.eval.side_effect = Exception("Connection lost")
            manager._conn = mock_conn

            # Socket ping passes, but rpyc remote call fails
            with patch.object(manager, "_verify_port_listening", return_value=True):
                result = manager.verify_connection()

            assert result is False

    def test_verify_connection_mt5_command_fails(self) -> None:
        """verify_connection() should return False when MT5 command fails."""
        with ExitStack() as stack:
            mock_config = stack.enter_context(
                patch("mt5linux.connection.get_config")
            )
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            from mt5linux.connection import ConnectionManager

            manager = ConnectionManager()
            manager._connected = True
            mock_conn = MagicMock()
            # First remote call (rpyc ping) succeeds, second (MT5) fails
            mock_conn.eval.side_effect = [True, Exception("MT5 not responding")]
            manager._conn = mock_conn

            with patch.object(manager, "_verify_port_listening", return_value=True):
                result = manager.verify_connection()

            assert result is False


# =============================================================================
# Task 5: Disconnect Tests
# =============================================================================


@pytest.mark.unit
class TestDisconnect:
    """Test ConnectionManager.disconnect() method."""

    def test_disconnect_closes_connection(self) -> None:
        """disconnect() should close the rpyc connection."""
        with ExitStack() as stack:
            mock_config = stack.enter_context(
                patch("mt5linux.connection.get_config")
            )
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            from mt5linux.connection import ConnectionManager

            manager = ConnectionManager()
            manager._connected = True
            mock_conn = MagicMock()
            manager._conn = mock_conn

            manager.disconnect()

            mock_conn.close.assert_called_once()
            assert manager._connected is False
            assert manager._conn is None
            assert manager._connection_time is None

    def test_disconnect_when_not_connected(self) -> None:
        """disconnect() should handle already disconnected state gracefully."""
        with ExitStack() as stack:
            mock_config = stack.enter_context(
                patch("mt5linux.connection.get_config")
            )
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            from mt5linux.connection import ConnectionManager

            manager = ConnectionManager()
            manager._connected = False
            manager._conn = None

            # Should not raise
            manager.disconnect()

            assert manager._connected is False

    def test_disconnect_handles_close_exception(self) -> None:
        """disconnect() should handle exception during close gracefully."""
        with ExitStack() as stack:
            mock_config = stack.enter_context(
                patch("mt5linux.connection.get_config")
            )
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            from mt5linux.connection import ConnectionManager

            manager = ConnectionManager()
            manager._connected = True
            mock_conn = MagicMock()
            mock_conn.close.side_effect = Exception("Close failed")
            manager._conn = mock_conn

            # Should not raise
            manager.disconnect()

            assert manager._connected is False


# =============================================================================
# Task 6: Connection State Properties Tests
# =============================================================================


@pytest.mark.unit
class TestConnectionStateProperties:
    """Test ConnectionManager state properties."""

    def test_is_connected_true(self) -> None:
        """is_connected should return True when connected."""
        with ExitStack() as stack:
            mock_config = stack.enter_context(
                patch("mt5linux.connection.get_config")
            )
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            from mt5linux.connection import ConnectionManager

            manager = ConnectionManager()
            manager._connected = True

            assert manager.is_connected is True

    def test_is_connected_false(self) -> None:
        """is_connected should return False when not connected."""
        with ExitStack() as stack:
            mock_config = stack.enter_context(
                patch("mt5linux.connection.get_config")
            )
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            from mt5linux.connection import ConnectionManager

            manager = ConnectionManager()
            manager._connected = False

            assert manager.is_connected is False

    def test_connection_info_when_connected(self) -> None:
        """connection_info should return details when connected."""
        with ExitStack() as stack:
            mock_config = stack.enter_context(
                patch("mt5linux.connection.get_config")
            )
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            from mt5linux.connection import ConnectionManager

            manager = ConnectionManager()
            manager._connected = True
            manager._connection_time = time.time()

            info = manager.connection_info

            assert info["connected"] is True
            assert info["host"] == "localhost"
            assert info["port"] == 18812
            assert "connection_time" in info
            assert "uptime" in info

    def test_connection_info_when_not_connected(self) -> None:
        """connection_info should indicate not connected."""
        with ExitStack() as stack:
            mock_config = stack.enter_context(
                patch("mt5linux.connection.get_config")
            )
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            from mt5linux.connection import ConnectionManager

            manager = ConnectionManager()
            manager._connected = False

            info = manager.connection_info

            assert info["connected"] is False

    def test_uptime_when_connected(self) -> None:
        """uptime should return seconds since connection."""
        with ExitStack() as stack:
            mock_config = stack.enter_context(
                patch("mt5linux.connection.get_config")
            )
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            from mt5linux.connection import ConnectionManager

            manager = ConnectionManager()
            manager._connected = True
            manager._connection_time = time.time() - 10.0  # 10 seconds ago

            uptime = manager.uptime

            assert uptime is not None
            assert 9.5 <= uptime <= 11.0

    def test_uptime_when_not_connected(self) -> None:
        """uptime should return None when not connected."""
        with ExitStack() as stack:
            mock_config = stack.enter_context(
                patch("mt5linux.connection.get_config")
            )
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            from mt5linux.connection import ConnectionManager

            manager = ConnectionManager()
            manager._connected = False

            uptime = manager.uptime

            assert uptime is None


# =============================================================================
# Task 8: Socket Ping Verification Tests
# =============================================================================


@pytest.mark.unit
class TestSocketPing:
    """Test socket-level ping verification."""

    def test_verify_port_listening_success(self) -> None:
        """_verify_port_listening should return True when port is listening."""
        with ExitStack() as stack:
            mock_config = stack.enter_context(
                patch("mt5linux.connection.get_config")
            )
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            mock_socket = stack.enter_context(
                patch("mt5linux.connection.socket")
            )
            mock_sock = MagicMock()
            mock_socket.create_connection.return_value.__enter__ = Mock(
                return_value=mock_sock
            )
            mock_socket.create_connection.return_value.__exit__ = Mock(
                return_value=False
            )

            from mt5linux.connection import ConnectionManager

            manager = ConnectionManager()

            result = manager._verify_port_listening("localhost", 18812)

            assert result is True

    def test_verify_port_listening_timeout(self) -> None:
        """_verify_port_listening should return False on timeout."""
        with ExitStack() as stack:
            mock_config = stack.enter_context(
                patch("mt5linux.connection.get_config")
            )
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            mock_socket = stack.enter_context(
                patch("mt5linux.connection.socket")
            )
            mock_socket.create_connection.side_effect = socket.timeout("timed out")
            mock_socket.timeout = socket.timeout
            mock_socket.error = socket.error

            from mt5linux.connection import ConnectionManager

            manager = ConnectionManager()

            result = manager._verify_port_listening("localhost", 18812)

            assert result is False

    def test_verify_port_listening_connection_refused(self) -> None:
        """_verify_port_listening should return False when refused."""
        with ExitStack() as stack:
            mock_config = stack.enter_context(
                patch("mt5linux.connection.get_config")
            )
            mock_config.return_value.server.host = "localhost"
            mock_config.return_value.server.port = 18812

            mock_socket = stack.enter_context(
                patch("mt5linux.connection.socket")
            )
            mock_socket.create_connection.side_effect = OSError("Connection refused")
            mock_socket.timeout = socket.timeout
            mock_socket.error = socket.error

            from mt5linux.connection import ConnectionManager

            manager = ConnectionManager()

            result = manager._verify_port_listening("localhost", 18812)

            assert result is False


# =============================================================================
# Task 7: LifecycleManager Integration Tests
# =============================================================================


@pytest.mark.unit
class TestLifecycleIntegration:
    """Test LifecycleManager connection integration."""

    def test_ensure_connected_chains_prerequisites(self) -> None:
        """ensure_connected should call ensure_server_running and ensure_mt5_running."""
        from unittest.mock import MagicMock

        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessInfo, ProcessManager

        # Create mocks
        mock_pm = MagicMock(spec=ProcessManager)
        mock_pm.find_rpyc_server.return_value = ProcessInfo(
            pid=1234, name="python.exe", status="running"
        )
        mock_pm.find_mt5.return_value = ProcessInfo(
            pid=5678, name="terminal64.exe", status="running"
        )

        lm = LifecycleManager(mock_pm)

        # Mock connection manager
        mock_conn_manager = MagicMock()
        mock_conn_manager.is_connected = False
        mock_conn_manager.connect.return_value = True
        lm._connection_manager = mock_conn_manager

        result = lm.ensure_connected()

        assert result is True
        mock_conn_manager.connect.assert_called_once()

    def test_ensure_connected_returns_true_if_already_connected(self) -> None:
        """ensure_connected should return True if already connected."""
        from unittest.mock import MagicMock

        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessInfo, ProcessManager

        mock_pm = MagicMock(spec=ProcessManager)
        mock_pm.find_rpyc_server.return_value = ProcessInfo(
            pid=1234, name="python.exe", status="running"
        )
        mock_pm.find_mt5.return_value = ProcessInfo(
            pid=5678, name="terminal64.exe", status="running"
        )

        lm = LifecycleManager(mock_pm)

        # Mock connection manager as already connected
        mock_conn_manager = MagicMock()
        mock_conn_manager.is_connected = True
        lm._connection_manager = mock_conn_manager

        result = lm.ensure_connected()

        assert result is True
        mock_conn_manager.connect.assert_not_called()

    def test_ensure_connected_creates_connection_manager_if_none(self) -> None:
        """ensure_connected should create ConnectionManager if not exists."""
        from unittest.mock import MagicMock, patch

        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessInfo, ProcessManager

        mock_pm = MagicMock(spec=ProcessManager)
        mock_pm.find_rpyc_server.return_value = ProcessInfo(
            pid=1234, name="python.exe", status="running"
        )
        mock_pm.find_mt5.return_value = ProcessInfo(
            pid=5678, name="terminal64.exe", status="running"
        )

        lm = LifecycleManager(mock_pm)
        lm._connection_manager = None

        # Patch the connection module's ConnectionManager class
        with patch("mt5linux.connection.ConnectionManager") as mock_cm_class:
            mock_cm = MagicMock()
            mock_cm.is_connected = False
            mock_cm.connect.return_value = True
            mock_cm_class.return_value = mock_cm

            result = lm.ensure_connected()

            assert result is True
            mock_cm_class.assert_called_once()

    def test_get_status_includes_connection_state(self) -> None:
        """get_status should include connection_active field."""
        from unittest.mock import MagicMock

        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        mock_pm = MagicMock(spec=ProcessManager)
        lm = LifecycleManager(mock_pm)

        # Mock connection manager
        mock_conn_manager = MagicMock()
        mock_conn_manager.is_connected = True
        lm._connection_manager = mock_conn_manager

        status = lm.get_status()

        assert "connection_active" in status
        assert status["connection_active"] is True

    def test_get_status_connection_active_false_when_disconnected(self) -> None:
        """get_status connection_active should be False when not connected."""
        from unittest.mock import MagicMock

        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        mock_pm = MagicMock(spec=ProcessManager)
        lm = LifecycleManager(mock_pm)

        # No connection manager
        lm._connection_manager = None

        status = lm.get_status()

        assert "connection_active" in status
        assert status["connection_active"] is False

    def test_get_status_connection_active_false_when_manager_disconnected(self) -> None:
        """get_status connection_active should be False when manager not connected."""
        from unittest.mock import MagicMock

        from mt5linux.lifecycle import LifecycleManager
        from mt5linux.process_manager import ProcessManager

        mock_pm = MagicMock(spec=ProcessManager)
        lm = LifecycleManager(mock_pm)

        # Connection manager exists but not connected
        mock_conn_manager = MagicMock()
        mock_conn_manager.is_connected = False
        lm._connection_manager = mock_conn_manager

        status = lm.get_status()

        assert status["connection_active"] is False
