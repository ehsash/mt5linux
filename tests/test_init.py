"""Tests for MetaTrader5 automatic initialization sequence (Story 2.7).

This module tests the auto-initialization feature that allows users to
simply instantiate MetaTrader5() and call initialize() without manual
server startup.

Test Classes:
    TestMetaTrader5Init: Instantiation with auto_connect True/False
    TestAutoInitializeSequence: Full auto-initialization flow
    TestHeartbeatMonitorStart: HeartbeatMonitor started after connection
    TestErrorHandling: Error handling for each failure type
    TestShutdown: Cleanup on shutdown
    TestStatusMethods: connection_status() and is_connected()
    TestBackwardCompatibility: Legacy behavior preserved
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
class TestMetaTrader5Init:
    """Tests for MetaTrader5 __init__ with auto_connect parameter."""

    @patch("mt5linux.rpyc.classic.connect")
    def test_init_auto_connect_false_connects_immediately(
        self, mock_rpyc_connect: MagicMock
    ) -> None:
        """auto_connect=False should connect immediately (legacy behavior)."""
        mock_conn = MagicMock()
        mock_rpyc_connect.return_value = mock_conn

        from mt5linux import MetaTrader5

        _mt5 = MetaTrader5(host="localhost", port=18812, auto_connect=False)
        del _mt5  # suppress unused variable warning

        # Should have connected immediately
        mock_rpyc_connect.assert_called_once_with("localhost", 18812)
        mock_conn._config.__setitem__.assert_called()
        mock_conn.execute.assert_any_call("import MetaTrader5 as mt5")
        mock_conn.execute.assert_any_call("import datetime")

    def test_init_auto_connect_true_does_not_connect(self) -> None:
        """auto_connect=True should NOT connect in __init__ (lazy)."""
        with patch("mt5linux.rpyc.classic.connect") as mock_rpyc_connect:
            from mt5linux import MetaTrader5

            _mt5 = MetaTrader5(host="localhost", port=18812, auto_connect=True)
            del _mt5  # suppress unused variable warning

            # Should NOT have connected
            mock_rpyc_connect.assert_not_called()

    def test_init_default_auto_connect_true(self) -> None:
        """Default auto_connect should be True (new behavior)."""
        with patch("mt5linux.rpyc.classic.connect") as mock_rpyc_connect:
            from mt5linux import MetaTrader5

            _mt5 = MetaTrader5()
            del _mt5  # suppress unused variable warning

            # Should NOT have connected (lazy initialization)
            mock_rpyc_connect.assert_not_called()

    def test_init_with_auto_connect_has_lifecycle_manager_attribute(self) -> None:
        """MetaTrader5 with auto_connect=True should have _lifecycle_manager attribute."""
        with patch("mt5linux.rpyc.classic.connect"):
            from mt5linux import MetaTrader5

            mt5 = MetaTrader5(auto_connect=True)

            assert hasattr(mt5, "_lifecycle_manager")
            # Should be None until initialize() is called
            assert mt5._lifecycle_manager is None

    def test_init_with_auto_connect_has_auto_connect_attribute(self) -> None:
        """MetaTrader5 should store the auto_connect setting."""
        with patch("mt5linux.rpyc.classic.connect"):
            from mt5linux import MetaTrader5

            mt5_auto = MetaTrader5(auto_connect=True)
            assert mt5_auto._auto_connect is True

            mt5_legacy = MetaTrader5(auto_connect=False)
            assert mt5_legacy._auto_connect is False

    def test_init_preserves_host_port_parameters(self) -> None:
        """init should preserve host and port parameters."""
        with patch("mt5linux.rpyc.classic.connect"):
            from mt5linux import MetaTrader5

            mt5 = MetaTrader5(host="192.168.1.100", port=19000, auto_connect=True)

            assert mt5._host == "192.168.1.100"
            assert mt5._port == 19000

    def test_init_logs_instantiation(self) -> None:
        """init should log instantiation with configuration."""
        with (
            patch("mt5linux.rpyc.classic.connect"),
            patch("mt5linux.logger") as mock_logger,
        ):
            from mt5linux import MetaTrader5

            _mt5 = MetaTrader5(auto_connect=True)
            del _mt5  # suppress unused variable warning

            # Should have logged instantiation
            mock_logger.debug.assert_called()


@pytest.mark.unit
class TestAutoInitializeSequence:
    """Tests for automatic initialization sequence in initialize()."""

    @patch("mt5linux.lifecycle.LifecycleManager")
    def test_initialize_triggers_auto_sequence(
        self, mock_lifecycle_manager_cls: MagicMock
    ) -> None:
        """initialize() with auto_connect=True should trigger full sequence."""
        mock_lm = MagicMock()
        mock_lifecycle_manager_cls.return_value = mock_lm
        # Mock connection manager from lifecycle manager
        mock_conn_mgr = MagicMock()
        mock_lm._connection_manager = mock_conn_mgr
        mock_conn_mgr._conn = MagicMock()

        with patch("mt5linux.rpyc.classic.connect"):
            from mt5linux import MetaTrader5

            mt5 = MetaTrader5(auto_connect=True)
            _result = mt5.initialize()
            del _result  # suppress unused variable warning

            # Should have called the sequence in correct order
            mock_lm.ensure_server_running.assert_called_once()
            mock_lm.ensure_mt5_running.assert_called_once()
            mock_lm.ensure_connected.assert_called_once()

    @patch("mt5linux.lifecycle.LifecycleManager")
    def test_initialize_sequence_order(
        self, mock_lifecycle_manager_cls: MagicMock
    ) -> None:
        """Sequence should be: server → MT5 → connection."""
        call_order = []
        mock_lm = MagicMock()
        mock_lifecycle_manager_cls.return_value = mock_lm
        mock_conn_mgr = MagicMock()
        mock_lm._connection_manager = mock_conn_mgr
        mock_conn_mgr._conn = MagicMock()

        def record_server_call() -> None:
            call_order.append("server")

        def record_mt5_call() -> None:
            call_order.append("mt5")

        def record_connected_call() -> bool:
            call_order.append("connected")
            return True

        mock_lm.ensure_server_running.side_effect = record_server_call
        mock_lm.ensure_mt5_running.side_effect = record_mt5_call
        mock_lm.ensure_connected.side_effect = record_connected_call

        with patch("mt5linux.rpyc.classic.connect"):
            from mt5linux import MetaTrader5

            mt5 = MetaTrader5(auto_connect=True)
            mt5.initialize()

            assert call_order == ["server", "mt5", "connected"]

    @patch("mt5linux.lifecycle.LifecycleManager")
    def test_initialize_creates_lifecycle_manager_once(
        self, mock_lifecycle_manager_cls: MagicMock
    ) -> None:
        """LifecycleManager should be created on first initialize() only."""
        mock_lm = MagicMock()
        mock_lifecycle_manager_cls.return_value = mock_lm
        mock_conn_mgr = MagicMock()
        mock_lm._connection_manager = mock_conn_mgr
        mock_conn_mgr._conn = MagicMock()

        with patch("mt5linux.rpyc.classic.connect"):
            from mt5linux import MetaTrader5

            mt5 = MetaTrader5(auto_connect=True)

            # First call should create lifecycle manager
            mt5.initialize()
            assert mock_lifecycle_manager_cls.call_count == 1

            # Second call should reuse existing lifecycle manager
            mt5.initialize()
            assert mock_lifecycle_manager_cls.call_count == 1

    @patch("mt5linux.rpyc.classic.connect")
    def test_initialize_with_auto_connect_false_skips_sequence(
        self, mock_rpyc_connect: MagicMock
    ) -> None:
        """initialize() with auto_connect=False should skip auto-sequence."""
        mock_conn = MagicMock()
        mock_rpyc_connect.return_value = mock_conn
        mock_conn.eval.return_value = True

        with patch("mt5linux.lifecycle.LifecycleManager") as mock_lm_cls:
            from mt5linux import MetaTrader5

            mt5 = MetaTrader5(auto_connect=False)
            mt5.initialize()

            # Should NOT create lifecycle manager
            mock_lm_cls.assert_not_called()
            # Should have called the remote initialize
            mock_conn.eval.assert_called()

    @patch("mt5linux.lifecycle.LifecycleManager")
    def test_initialize_passes_through_args_kwargs(
        self, mock_lifecycle_manager_cls: MagicMock
    ) -> None:
        """initialize() should pass args/kwargs to remote mt5.initialize()."""
        mock_lm = MagicMock()
        mock_lifecycle_manager_cls.return_value = mock_lm
        mock_conn_mgr = MagicMock()
        mock_lm._connection_manager = mock_conn_mgr
        mock_conn = MagicMock()
        mock_conn_mgr._conn = mock_conn
        mock_conn.eval.return_value = True

        with patch("mt5linux.rpyc.classic.connect"):
            from mt5linux import MetaTrader5

            mt5 = MetaTrader5(auto_connect=True)
            mt5.initialize(
                "/path/to/mt5.exe",
                login=12345,
                password="secret",
                server="Demo",
            )

            # The eval call should contain the args
            eval_call = mock_conn.eval.call_args
            assert "12345" in str(eval_call) or "'login'" in str(eval_call)

    @patch("mt5linux.lifecycle.LifecycleManager")
    def test_initialize_logs_sequence_steps(
        self, mock_lifecycle_manager_cls: MagicMock
    ) -> None:
        """initialize() should log each sequence step."""
        mock_lm = MagicMock()
        mock_lifecycle_manager_cls.return_value = mock_lm
        mock_conn_mgr = MagicMock()
        mock_lm._connection_manager = mock_conn_mgr
        mock_conn_mgr._conn = MagicMock()

        with (
            patch("mt5linux.rpyc.classic.connect"),
            patch("mt5linux.logger") as mock_logger,
        ):
            from mt5linux import MetaTrader5

            mt5 = MetaTrader5(auto_connect=True)
            mt5.initialize()

            # Should have logged the sequence steps
            assert mock_logger.info.call_count >= 1


@pytest.mark.unit
class TestHeartbeatMonitorStart:
    """Tests for HeartbeatMonitor starting after connection."""

    @patch("mt5linux.monitoring.heartbeat.HeartbeatMonitor")
    @patch("mt5linux.lifecycle.LifecycleManager")
    def test_heartbeat_monitor_started_after_connection(
        self,
        mock_lifecycle_manager_cls: MagicMock,
        mock_heartbeat_cls: MagicMock,
    ) -> None:
        """HeartbeatMonitor should start after successful connection."""
        mock_lm = MagicMock()
        mock_lifecycle_manager_cls.return_value = mock_lm
        mock_conn_mgr = MagicMock()
        mock_lm._connection_manager = mock_conn_mgr
        mock_conn_mgr._conn = MagicMock()

        mock_heartbeat = MagicMock()
        mock_heartbeat_cls.return_value = mock_heartbeat

        with patch("mt5linux.rpyc.classic.connect"):
            from mt5linux import MetaTrader5

            mt5 = MetaTrader5(auto_connect=True)
            mt5.initialize()

            # HeartbeatMonitor should be created and started
            mock_heartbeat_cls.assert_called_once_with(
                mock_conn_mgr,
                heartbeat_interval=30.0,
                failure_threshold=45.0,
            )
            mock_heartbeat.start.assert_called_once()

    @patch("mt5linux.monitoring.heartbeat.HeartbeatMonitor")
    @patch("mt5linux.lifecycle.LifecycleManager")
    def test_heartbeat_monitor_stored_in_lifecycle_manager(
        self,
        mock_lifecycle_manager_cls: MagicMock,
        mock_heartbeat_cls: MagicMock,
    ) -> None:
        """HeartbeatMonitor instance should be stored in LifecycleManager."""
        mock_lm = MagicMock()
        mock_lifecycle_manager_cls.return_value = mock_lm
        mock_conn_mgr = MagicMock()
        mock_lm._connection_manager = mock_conn_mgr
        mock_conn_mgr._conn = MagicMock()
        mock_lm._heartbeat_monitor = None

        mock_heartbeat = MagicMock()
        mock_heartbeat_cls.return_value = mock_heartbeat

        with patch("mt5linux.rpyc.classic.connect"):
            from mt5linux import MetaTrader5

            mt5 = MetaTrader5(auto_connect=True)
            mt5.initialize()

            # Should be stored in lifecycle manager
            assert mock_lm._heartbeat_monitor == mock_heartbeat

    @patch("mt5linux.rpyc.classic.connect")
    def test_heartbeat_not_started_with_auto_connect_false(
        self, mock_rpyc_connect: MagicMock
    ) -> None:
        """HeartbeatMonitor should NOT start with auto_connect=False."""
        mock_conn = MagicMock()
        mock_rpyc_connect.return_value = mock_conn
        mock_conn.eval.return_value = True

        with patch("mt5linux.monitoring.heartbeat.HeartbeatMonitor") as mock_hb_cls:
            from mt5linux import MetaTrader5

            mt5 = MetaTrader5(auto_connect=False)
            mt5.initialize()

            # HeartbeatMonitor should NOT be created
            mock_hb_cls.assert_not_called()


@pytest.mark.unit
class TestErrorHandling:
    """Tests for error handling during initialization sequence."""

    @patch("mt5linux.lifecycle.LifecycleManager")
    def test_rpyc_server_error_raises_initialization_error(
        self, mock_lifecycle_manager_cls: MagicMock
    ) -> None:
        """RpycServerError should raise InitializationError."""
        from mt5linux.process_manager import RpycServerError

        mock_lm = MagicMock()
        mock_lifecycle_manager_cls.return_value = mock_lm
        mock_lm.ensure_server_running.side_effect = RpycServerError("Server failed")

        with patch("mt5linux.rpyc.classic.connect"):
            from mt5linux import InitializationError, MetaTrader5

            mt5 = MetaTrader5(auto_connect=True)

            with pytest.raises(InitializationError) as exc_info:
                mt5.initialize()

            assert "rpyc server" in str(exc_info.value).lower()

    @patch("mt5linux.lifecycle.LifecycleManager")
    def test_mt5_launch_error_raises_initialization_error(
        self, mock_lifecycle_manager_cls: MagicMock
    ) -> None:
        """MT5LaunchError should raise InitializationError."""
        from mt5linux.process_manager import MT5LaunchError

        mock_lm = MagicMock()
        mock_lifecycle_manager_cls.return_value = mock_lm
        mock_lm.ensure_server_running.return_value = MagicMock()
        mock_lm.ensure_mt5_running.side_effect = MT5LaunchError("MT5 failed")

        with patch("mt5linux.rpyc.classic.connect"):
            from mt5linux import InitializationError, MetaTrader5

            mt5 = MetaTrader5(auto_connect=True)

            with pytest.raises(InitializationError) as exc_info:
                mt5.initialize()

            assert "mt5" in str(exc_info.value).lower()

    @patch("mt5linux.lifecycle.LifecycleManager")
    def test_connection_error_raises_initialization_error(
        self, mock_lifecycle_manager_cls: MagicMock
    ) -> None:
        """ConnectionError should raise InitializationError."""
        from mt5linux.connection import ConnectionError

        mock_lm = MagicMock()
        mock_lifecycle_manager_cls.return_value = mock_lm
        mock_lm.ensure_server_running.return_value = MagicMock()
        mock_lm.ensure_mt5_running.return_value = MagicMock()
        mock_lm.ensure_connected.side_effect = ConnectionError("Connection failed")

        with patch("mt5linux.rpyc.classic.connect"):
            from mt5linux import InitializationError, MetaTrader5

            mt5 = MetaTrader5(auto_connect=True)

            with pytest.raises(InitializationError) as exc_info:
                mt5.initialize()

            assert "connection" in str(exc_info.value).lower()

    @patch("mt5linux.lifecycle.LifecycleManager")
    def test_error_logged_before_raising(
        self, mock_lifecycle_manager_cls: MagicMock
    ) -> None:
        """Errors should be logged before raising."""
        from mt5linux.process_manager import RpycServerError

        mock_lm = MagicMock()
        mock_lifecycle_manager_cls.return_value = mock_lm
        mock_lm.ensure_server_running.side_effect = RpycServerError("Server failed")

        with (
            patch("mt5linux.rpyc.classic.connect"),
            patch("mt5linux.logger") as mock_logger,
        ):
            from mt5linux import InitializationError, MetaTrader5

            mt5 = MetaTrader5(auto_connect=True)

            with pytest.raises(InitializationError):
                mt5.initialize()

            mock_logger.error.assert_called()

    @patch("mt5linux.lifecycle.LifecycleManager")
    def test_error_preserves_exception_chain(
        self, mock_lifecycle_manager_cls: MagicMock
    ) -> None:
        """InitializationError should preserve original exception via __cause__."""
        from mt5linux.process_manager import RpycServerError

        original_error = RpycServerError("Original error")
        mock_lm = MagicMock()
        mock_lifecycle_manager_cls.return_value = mock_lm
        mock_lm.ensure_server_running.side_effect = original_error

        with patch("mt5linux.rpyc.classic.connect"):
            from mt5linux import InitializationError, MetaTrader5

            mt5 = MetaTrader5(auto_connect=True)

            with pytest.raises(InitializationError) as exc_info:
                mt5.initialize()

            assert exc_info.value.__cause__ is original_error


@pytest.mark.unit
class TestShutdown:
    """Tests for shutdown() cleanup."""

    @patch("mt5linux.monitoring.heartbeat.HeartbeatMonitor")
    @patch("mt5linux.lifecycle.LifecycleManager")
    def test_shutdown_stops_heartbeat_monitor(
        self,
        mock_lifecycle_manager_cls: MagicMock,
        mock_heartbeat_cls: MagicMock,
    ) -> None:
        """shutdown() should stop HeartbeatMonitor."""
        mock_lm = MagicMock()
        mock_lifecycle_manager_cls.return_value = mock_lm
        mock_conn_mgr = MagicMock()
        mock_lm._connection_manager = mock_conn_mgr
        mock_conn = MagicMock()
        mock_conn_mgr._conn = mock_conn
        mock_conn.eval.return_value = None

        mock_heartbeat = MagicMock()
        mock_heartbeat_cls.return_value = mock_heartbeat
        mock_lm._heartbeat_monitor = mock_heartbeat

        with patch("mt5linux.rpyc.classic.connect"):
            from mt5linux import MetaTrader5

            mt5 = MetaTrader5(auto_connect=True)
            mt5.initialize()
            mt5.shutdown()

            mock_heartbeat.stop.assert_called_once()

    @patch("mt5linux.monitoring.heartbeat.HeartbeatMonitor")
    @patch("mt5linux.lifecycle.LifecycleManager")
    def test_shutdown_disconnects_connection_manager(
        self,
        mock_lifecycle_manager_cls: MagicMock,
        mock_heartbeat_cls: MagicMock,
    ) -> None:
        """shutdown() should disconnect ConnectionManager."""
        mock_lm = MagicMock()
        mock_lifecycle_manager_cls.return_value = mock_lm
        mock_conn_mgr = MagicMock()
        mock_lm._connection_manager = mock_conn_mgr
        mock_conn = MagicMock()
        mock_conn_mgr._conn = mock_conn
        mock_conn.eval.return_value = None

        mock_heartbeat = MagicMock()
        mock_heartbeat_cls.return_value = mock_heartbeat

        with patch("mt5linux.rpyc.classic.connect"):
            from mt5linux import MetaTrader5

            mt5 = MetaTrader5(auto_connect=True)
            mt5.initialize()
            mt5.shutdown()

            mock_conn_mgr.disconnect.assert_called_once()

    @patch("mt5linux.rpyc.classic.connect")
    def test_shutdown_preserves_existing_behavior(
        self, mock_rpyc_connect: MagicMock
    ) -> None:
        """shutdown() should still call remote mt5.shutdown()."""
        mock_conn = MagicMock()
        mock_rpyc_connect.return_value = mock_conn
        mock_conn.eval.return_value = None

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5(auto_connect=False)
        mt5.shutdown()

        # Should have called remote shutdown
        mock_conn.eval.assert_called()
        assert "shutdown" in str(mock_conn.eval.call_args)

    @patch("mt5linux.monitoring.heartbeat.HeartbeatMonitor")
    @patch("mt5linux.lifecycle.LifecycleManager")
    def test_shutdown_logs_sequence(
        self,
        mock_lifecycle_manager_cls: MagicMock,
        mock_heartbeat_cls: MagicMock,
    ) -> None:
        """shutdown() should log the shutdown sequence."""
        mock_lm = MagicMock()
        mock_lifecycle_manager_cls.return_value = mock_lm
        mock_conn_mgr = MagicMock()
        mock_lm._connection_manager = mock_conn_mgr
        mock_conn = MagicMock()
        mock_conn_mgr._conn = mock_conn
        mock_conn.eval.return_value = None

        mock_heartbeat = MagicMock()
        mock_heartbeat_cls.return_value = mock_heartbeat

        with (
            patch("mt5linux.rpyc.classic.connect"),
            patch("mt5linux.logger") as mock_logger,
        ):
            from mt5linux import MetaTrader5

            mt5 = MetaTrader5(auto_connect=True)
            mt5.initialize()
            mt5.shutdown()

            # Should have logged shutdown
            assert any(
                "shutdown" in str(call).lower()
                for call in mock_logger.info.call_args_list
            )


@pytest.mark.unit
class TestStatusMethods:
    """Tests for connection_status() and is_connected property."""

    @patch("mt5linux.lifecycle.LifecycleManager")
    def test_connection_status_returns_dict(
        self, mock_lifecycle_manager_cls: MagicMock
    ) -> None:
        """connection_status() should return a Dict with lifecycle info."""
        mock_lm = MagicMock()
        mock_lifecycle_manager_cls.return_value = mock_lm
        mock_lm.get_status.return_value = {
            "monitoring_active": True,
            "current_pid": 1234,
        }
        mock_conn_mgr = MagicMock()
        mock_lm._connection_manager = mock_conn_mgr
        mock_conn_mgr.connection_info = {"connected": True, "host": "localhost"}
        mock_conn_mgr._conn = MagicMock()

        mock_heartbeat = MagicMock()
        mock_heartbeat.get_status.return_value = {"is_healthy": True}
        mock_lm._heartbeat_monitor = mock_heartbeat

        with patch("mt5linux.rpyc.classic.connect"):
            from mt5linux import MetaTrader5

            mt5 = MetaTrader5(auto_connect=True)
            mt5.initialize()

            status = mt5.connection_status()

            assert isinstance(status, dict)
            assert "lifecycle_status" in status
            assert "connection_info" in status
            assert "heartbeat_status" in status

    @patch("mt5linux.lifecycle.LifecycleManager")
    def test_is_connected_property_true_when_connected(
        self, mock_lifecycle_manager_cls: MagicMock
    ) -> None:
        """is_connected should return True when connected."""
        mock_lm = MagicMock()
        mock_lifecycle_manager_cls.return_value = mock_lm
        mock_conn_mgr = MagicMock()
        mock_lm._connection_manager = mock_conn_mgr
        mock_conn_mgr.is_connected = True
        mock_conn_mgr._conn = MagicMock()

        with patch("mt5linux.rpyc.classic.connect"):
            from mt5linux import MetaTrader5

            mt5 = MetaTrader5(auto_connect=True)
            mt5.initialize()

            assert mt5.is_connected is True

    @patch("mt5linux.lifecycle.LifecycleManager")
    def test_is_connected_property_false_when_not_connected(
        self, mock_lifecycle_manager_cls: MagicMock
    ) -> None:
        """is_connected should return False when not connected."""
        with patch("mt5linux.rpyc.classic.connect"):
            from mt5linux import MetaTrader5

            mt5 = MetaTrader5(auto_connect=True)

            # Before initialize, should be False
            assert mt5.is_connected is False

    def test_is_connected_false_for_legacy_mode_before_init(self) -> None:
        """is_connected should work in legacy mode too."""
        with patch("mt5linux.rpyc.classic.connect") as mock_rpyc_connect:
            mock_conn = MagicMock()
            mock_rpyc_connect.return_value = mock_conn

            from mt5linux import MetaTrader5

            mt5 = MetaTrader5(auto_connect=False)

            # In legacy mode with connection established, should reflect connection state
            # (This tests that the property doesn't crash in legacy mode)
            result = mt5.is_connected
            assert isinstance(result, bool)


@pytest.mark.unit
class TestBackwardCompatibility:
    """Tests for backward compatibility with existing code."""

    @patch("mt5linux.monitoring.heartbeat.HeartbeatMonitor")
    @patch("mt5linux.lifecycle.LifecycleManager")
    def test_existing_code_without_auto_connect_works(
        self,
        mock_lifecycle_manager_cls: MagicMock,
        mock_heartbeat_cls: MagicMock,
    ) -> None:
        """Existing code pattern (no auto_connect param) should work with new default."""
        # Since auto_connect defaults to True, existing code now gets auto-init behavior
        # This test verifies the new behavior works when user doesn't specify auto_connect
        mock_lm = MagicMock()
        mock_lifecycle_manager_cls.return_value = mock_lm
        mock_conn_mgr = MagicMock()
        mock_lm._connection_manager = mock_conn_mgr
        mock_conn = MagicMock()
        mock_conn_mgr._conn = mock_conn
        mock_conn.eval.return_value = True

        mock_heartbeat = MagicMock()
        mock_heartbeat_cls.return_value = mock_heartbeat

        with patch("mt5linux.rpyc.classic.connect"):
            from mt5linux import MetaTrader5

            # Existing code pattern (no auto_connect parameter) - now uses auto_connect=True
            mt5 = MetaTrader5(host="localhost", port=18812)
            result = mt5.initialize()

            # Should trigger auto-sequence (new default behavior)
            mock_lm.ensure_server_running.assert_called_once()
            mock_lm.ensure_mt5_running.assert_called_once()
            mock_lm.ensure_connected.assert_called_once()
            # Result comes from mock connection
            assert result is True or mock_conn.eval.called

    @patch("mt5linux.rpyc.classic.connect")
    def test_manual_server_startup_with_auto_connect_false(
        self, mock_rpyc_connect: MagicMock
    ) -> None:
        """Manual server startup should work with auto_connect=False."""
        mock_conn = MagicMock()
        mock_rpyc_connect.return_value = mock_conn
        mock_conn.eval.return_value = True

        from mt5linux import MetaTrader5

        # Manual mode
        mt5 = MetaTrader5(auto_connect=False)
        mt5.initialize()

        # Should have connected immediately in __init__
        mock_rpyc_connect.assert_called_once()
        mock_conn.eval.assert_called()

    @patch("mt5linux.rpyc.classic.connect")
    def test_all_api_methods_unchanged(self, mock_rpyc_connect: MagicMock) -> None:
        """All existing API methods should still be callable."""
        mock_conn = MagicMock()
        mock_rpyc_connect.return_value = mock_conn
        mock_conn.eval.return_value = "test_result"

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5(auto_connect=False)

        # Test that common API methods exist and are callable
        methods_to_test = [
            "initialize",
            "shutdown",
            "login",
            "version",
            "last_error",
            "terminal_info",
            "account_info",
        ]

        for method_name in methods_to_test:
            assert hasattr(mt5, method_name), f"Missing method: {method_name}"
            method = getattr(mt5, method_name)
            assert callable(method), f"Method not callable: {method_name}"

    @patch("mt5linux.rpyc.classic.connect")
    def test_constants_still_accessible(self, mock_rpyc_connect: MagicMock) -> None:
        """Class constants should still be accessible."""
        mock_conn = MagicMock()
        mock_rpyc_connect.return_value = mock_conn

        from mt5linux import MetaTrader5

        mt5 = MetaTrader5(auto_connect=False)

        # Test some key constants
        assert hasattr(mt5, "TRADE_ACTION_DEAL")
        assert hasattr(mt5, "ORDER_TYPE_BUY")
        assert hasattr(mt5, "ORDER_TYPE_SELL")
        assert hasattr(mt5, "POSITION_TYPE_BUY")
        assert hasattr(mt5, "POSITION_TYPE_SELL")

    @patch("mt5linux.rpyc.classic.connect")
    def test_signature_compatibility(self, mock_rpyc_connect: MagicMock) -> None:
        """__init__ signature should be backward compatible."""
        mock_conn = MagicMock()
        mock_rpyc_connect.return_value = mock_conn

        from mt5linux import MetaTrader5

        # All these should work without errors
        # Use assert to ensure instances are created and satisfy linter
        assert MetaTrader5() is not None
        assert MetaTrader5(host="localhost") is not None
        assert MetaTrader5(port=18812) is not None
        assert MetaTrader5(host="localhost", port=18812) is not None
        assert MetaTrader5("localhost", 18812) is not None

        # No exceptions means compatible


@pytest.mark.unit
class TestInitializationError:
    """Tests for InitializationError exception class."""

    def test_initialization_error_is_exception(self) -> None:
        """InitializationError should be an Exception subclass."""
        from mt5linux import InitializationError

        assert issubclass(InitializationError, Exception)

    def test_initialization_error_has_message(self) -> None:
        """InitializationError should accept a message."""
        from mt5linux import InitializationError

        error = InitializationError("Test message")
        assert str(error) == "Test message"

    def test_initialization_error_inherits_from_mt5linux_error(self) -> None:
        """InitializationError should inherit from MT5LinuxError."""
        from mt5linux import InitializationError
        from mt5linux.process_manager import MT5LinuxError

        assert issubclass(InitializationError, MT5LinuxError)
