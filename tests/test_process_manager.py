"""Tests for mt5linux process manager module."""

import time
from dataclasses import FrozenInstanceError
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from mt5linux.process_manager import ProcessInfo, ProcessManager


# Create mock psutil exceptions for testing
class MockAccessDenied(Exception):
    """Mock psutil.AccessDenied exception."""

    def __init__(self, pid: int = 0) -> None:
        self.pid = pid
        super().__init__(f"AccessDenied(pid={pid})")


class MockNoSuchProcess(Exception):
    """Mock psutil.NoSuchProcess exception."""

    def __init__(self, pid: int = 0) -> None:
        self.pid = pid
        super().__init__(f"NoSuchProcess(pid={pid})")


class MockZombieProcess(Exception):
    """Mock psutil.ZombieProcess exception."""

    def __init__(self, pid: int = 0) -> None:
        self.pid = pid
        super().__init__(f"ZombieProcess(pid={pid})")


@pytest.mark.unit
class TestProcessInfo:
    """Tests for ProcessInfo dataclass."""

    def test_process_info_creation(self) -> None:
        """Test that ProcessInfo can be created with required fields."""
        info = ProcessInfo(pid=1234, name="python.exe", status="running")
        assert info.pid == 1234
        assert info.name == "python.exe"
        assert info.status == "running"
        assert info.cmdline is None

    def test_process_info_with_cmdline(self) -> None:
        """Test that ProcessInfo can be created with optional cmdline."""
        cmdline = ["python.exe", "-c", "import rpyc"]
        info = ProcessInfo(
            pid=5678, name="python.exe", status="running", cmdline=cmdline
        )
        assert info.pid == 5678
        assert info.cmdline == cmdline

    def test_process_info_frozen(self) -> None:
        """Test that ProcessInfo is immutable (frozen)."""
        info = ProcessInfo(pid=1234, name="test", status="running")
        with pytest.raises(FrozenInstanceError):
            info.pid = 9999  # type: ignore

    def test_process_info_slots(self) -> None:
        """Test that ProcessInfo uses slots for memory efficiency."""
        info = ProcessInfo(pid=1234, name="test", status="running")
        assert hasattr(info, "__slots__") or not hasattr(info, "__dict__")


@pytest.mark.unit
class TestProcessManagerInit:
    """Tests for ProcessManager initialization."""

    def test_process_manager_creation(self) -> None:
        """Test that ProcessManager can be instantiated."""
        manager = ProcessManager()
        assert manager is not None

    def test_process_manager_has_required_methods(self) -> None:
        """Test that ProcessManager has required detection methods."""
        manager = ProcessManager()
        assert hasattr(manager, "find_rpyc_server")
        assert hasattr(manager, "find_mt5")
        assert callable(manager.find_rpyc_server)
        assert callable(manager.find_mt5)


@pytest.mark.unit
class TestRpycServerDetection:
    """Tests for rpyc server process detection."""

    def test_find_rpyc_server_found(self) -> None:
        """Test detection when rpyc server process is found."""
        mock_proc = MagicMock()
        mock_proc.info = {
            "pid": 1234,
            "name": "python.exe",
            "status": "running",
            "cmdline": [
                "python.exe",
                "-c",
                "from rpyc.utils.server import ThreadedServer",
            ],
        }

        mock_psutil = MagicMock()
        mock_psutil.process_iter.return_value = [mock_proc]

        with patch("mt5linux.process_manager.psutil", mock_psutil):
            manager = ProcessManager()
            result = manager.find_rpyc_server()

        assert result is not None
        assert result.pid == 1234
        assert result.name == "python.exe"

    def test_find_rpyc_server_not_found(self) -> None:
        """Test detection when rpyc server process is not found."""
        mock_proc = MagicMock()
        mock_proc.info = {
            "pid": 5678,
            "name": "bash",
            "status": "running",
            "cmdline": ["bash"],
        }

        mock_psutil = MagicMock()
        mock_psutil.process_iter.return_value = [mock_proc]

        with patch("mt5linux.process_manager.psutil", mock_psutil):
            manager = ProcessManager()
            result = manager.find_rpyc_server()

        assert result is None

    def test_find_rpyc_server_matches_python_variants(self) -> None:
        """Test detection matches python.exe, pythonw.exe, python3.exe."""
        for python_name in ["python.exe", "pythonw.exe", "python3.exe"]:
            mock_proc = MagicMock()
            mock_proc.info = {
                "pid": 1234,
                "name": python_name,
                "status": "running",
                "cmdline": [python_name, "-m", "rpyc"],
            }

            mock_psutil = MagicMock()
            mock_psutil.process_iter.return_value = [mock_proc]

            with patch("mt5linux.process_manager.psutil", mock_psutil):
                manager = ProcessManager()
                result = manager.find_rpyc_server()

            assert result is not None, f"Should detect {python_name} running rpyc"

    def test_find_rpyc_server_matches_rpyc_patterns(self) -> None:
        """Test detection matches various rpyc command-line patterns."""
        rpyc_patterns = [
            ["python.exe", "-c", "import rpyc"],
            ["python.exe", "-m", "rpyc.utils.server"],
            ["python.exe", "rpyc_server.py"],
            ["python.exe", "-c", "from rpyc import SlaveService"],
        ]
        for cmdline in rpyc_patterns:
            mock_proc = MagicMock()
            mock_proc.info = {
                "pid": 1234,
                "name": "python.exe",
                "status": "running",
                "cmdline": cmdline,
            }

            mock_psutil = MagicMock()
            mock_psutil.process_iter.return_value = [mock_proc]

            with patch("mt5linux.process_manager.psutil", mock_psutil):
                manager = ProcessManager()
                result = manager.find_rpyc_server()

            assert result is not None, f"Should detect rpyc with cmdline: {cmdline}"

    def test_find_rpyc_server_timing(self) -> None:
        """Test that rpyc server detection completes within 2 seconds (NFR8)."""
        # Create many mock processes to simulate real-world scenario
        mock_procs = []
        for i in range(100):
            mock_proc = MagicMock()
            mock_proc.info = {
                "pid": i,
                "name": "other_process",
                "status": "running",
                "cmdline": ["other", "args"],
            }
            mock_procs.append(mock_proc)

        mock_psutil = MagicMock()
        mock_psutil.process_iter.return_value = mock_procs

        with patch("mt5linux.process_manager.psutil", mock_psutil):
            manager = ProcessManager()
            start_time = time.time()
            result = manager.find_rpyc_server()
            elapsed = time.time() - start_time

        assert elapsed < 2.0, f"Detection took {elapsed}s, should be <2s (NFR8)"
        assert result is None


@pytest.mark.unit
class TestMT5Detection:
    """Tests for MT5 process detection."""

    def test_find_mt5_found_terminal64(self) -> None:
        """Test detection when MT5 terminal64.exe is found."""
        mock_proc = MagicMock()
        mock_proc.info = {
            "pid": 2345,
            "name": "terminal64.exe",
            "status": "running",
            "cmdline": ["terminal64.exe"],
        }

        mock_psutil = MagicMock()
        mock_psutil.process_iter.return_value = [mock_proc]

        with patch("mt5linux.process_manager.psutil", mock_psutil):
            manager = ProcessManager()
            result = manager.find_mt5()

        assert result is not None
        assert result.pid == 2345
        assert result.name == "terminal64.exe"

    def test_find_mt5_found_metatrader(self) -> None:
        """Test detection when metatrader5.exe is found."""
        mock_proc = MagicMock()
        mock_proc.info = {
            "pid": 3456,
            "name": "metatrader5.exe",
            "status": "running",
            "cmdline": ["metatrader5.exe"],
        }

        mock_psutil = MagicMock()
        mock_psutil.process_iter.return_value = [mock_proc]

        with patch("mt5linux.process_manager.psutil", mock_psutil):
            manager = ProcessManager()
            result = manager.find_mt5()

        assert result is not None
        assert result.name == "metatrader5.exe"

    def test_find_mt5_not_found(self) -> None:
        """Test detection when MT5 process is not found."""
        mock_proc = MagicMock()
        mock_proc.info = {
            "pid": 5678,
            "name": "bash",
            "status": "running",
            "cmdline": ["bash"],
        }

        mock_psutil = MagicMock()
        mock_psutil.process_iter.return_value = [mock_proc]

        with patch("mt5linux.process_manager.psutil", mock_psutil):
            manager = ProcessManager()
            result = manager.find_mt5()

        assert result is None

    def test_find_mt5_matches_name_variants(self) -> None:
        """Test detection matches various MT5 process name variants."""
        mt5_names = [
            "terminal64.exe",
            "terminal.exe",
            "metatrader5.exe",
            "metatrader.exe",
        ]
        for mt5_name in mt5_names:
            mock_proc = MagicMock()
            mock_proc.info = {
                "pid": 1234,
                "name": mt5_name,
                "status": "running",
                "cmdline": [mt5_name],
            }

            mock_psutil = MagicMock()
            mock_psutil.process_iter.return_value = [mock_proc]

            with patch("mt5linux.process_manager.psutil", mock_psutil):
                manager = ProcessManager()
                result = manager.find_mt5()

            assert result is not None, f"Should detect MT5 with name: {mt5_name}"

    def test_find_mt5_timing(self) -> None:
        """Test that MT5 detection completes within 2 seconds (NFR8)."""
        mock_procs = []
        for i in range(100):
            mock_proc = MagicMock()
            mock_proc.info = {
                "pid": i,
                "name": "other_process",
                "status": "running",
                "cmdline": ["other", "args"],
            }
            mock_procs.append(mock_proc)

        mock_psutil = MagicMock()
        mock_psutil.process_iter.return_value = mock_procs

        with patch("mt5linux.process_manager.psutil", mock_psutil):
            manager = ProcessManager()
            start_time = time.time()
            result = manager.find_mt5()
            elapsed = time.time() - start_time

        assert elapsed < 2.0, f"Detection took {elapsed}s, should be <2s (NFR8)"
        assert result is None

    def test_find_mt5_accuracy(self) -> None:
        """Test that MT5 detection has 100% accuracy (NFR19)."""
        # When MT5 process exists, it must be found
        mock_proc = MagicMock()
        mock_proc.info = {
            "pid": 1234,
            "name": "terminal64.exe",
            "status": "running",
            "cmdline": ["terminal64.exe"],
        }

        mock_psutil = MagicMock()
        mock_psutil.process_iter.return_value = [mock_proc]

        with patch("mt5linux.process_manager.psutil", mock_psutil):
            manager = ProcessManager()

            # Run detection multiple times to verify accuracy
            for _ in range(10):
                result = manager.find_mt5()
                assert result is not None, "MT5 detection must be 100% accurate (NFR19)"
                assert result.pid == 1234


@pytest.mark.unit
class TestMultipleProcessHandling:
    """Tests for handling multiple matching processes."""

    def test_find_rpyc_server_multiple_processes(self) -> None:
        """Test that most relevant process is returned when multiple found."""
        mock_proc1 = MagicMock()
        mock_proc1.info = {
            "pid": 1000,
            "name": "python.exe",
            "status": "running",
            "cmdline": ["python.exe", "-c", "import rpyc"],
        }
        mock_proc2 = MagicMock()
        mock_proc2.info = {
            "pid": 2000,
            "name": "python.exe",
            "status": "running",
            "cmdline": ["python.exe", "-c", "import rpyc"],
        }

        mock_psutil = MagicMock()
        mock_psutil.process_iter.return_value = [mock_proc1, mock_proc2]

        with patch("mt5linux.process_manager.psutil", mock_psutil):
            manager = ProcessManager()
            result = manager.find_rpyc_server()

        assert result is not None
        # Should return one of the matching processes (implementation decides which)
        assert result.pid in [1000, 2000]

    def test_find_mt5_multiple_processes(self) -> None:
        """Test that most relevant MT5 process is returned when multiple found."""
        mock_proc1 = MagicMock()
        mock_proc1.info = {
            "pid": 1000,
            "name": "terminal64.exe",
            "status": "running",
            "cmdline": ["terminal64.exe"],
        }
        mock_proc2 = MagicMock()
        mock_proc2.info = {
            "pid": 2000,
            "name": "terminal64.exe",
            "status": "running",
            "cmdline": ["terminal64.exe"],
        }

        mock_psutil = MagicMock()
        mock_psutil.process_iter.return_value = [mock_proc1, mock_proc2]

        with patch("mt5linux.process_manager.psutil", mock_psutil):
            manager = ProcessManager()
            result = manager.find_mt5()

        assert result is not None
        # Should return one of the matching processes
        assert result.pid in [1000, 2000]


@pytest.mark.unit
class TestErrorHandling:
    """Tests for error handling and resilience."""

    def test_find_rpyc_server_handles_access_denied(self) -> None:
        """Test graceful handling of psutil.AccessDenied."""
        mock_psutil = MagicMock()
        mock_psutil.AccessDenied = MockAccessDenied
        mock_psutil.NoSuchProcess = MockNoSuchProcess
        mock_psutil.ZombieProcess = MockZombieProcess
        mock_psutil.process_iter.side_effect = MockAccessDenied(pid=1234)

        with patch("mt5linux.process_manager.psutil", mock_psutil):
            manager = ProcessManager()
            result = manager.find_rpyc_server()

        assert result is None  # Should return None, not raise exception

    def test_find_mt5_handles_access_denied(self) -> None:
        """Test graceful handling of psutil.AccessDenied for MT5."""
        mock_psutil = MagicMock()
        mock_psutil.AccessDenied = MockAccessDenied
        mock_psutil.NoSuchProcess = MockNoSuchProcess
        mock_psutil.ZombieProcess = MockZombieProcess
        mock_psutil.process_iter.side_effect = MockAccessDenied(pid=1234)

        with patch("mt5linux.process_manager.psutil", mock_psutil):
            manager = ProcessManager()
            result = manager.find_mt5()

        assert result is None  # Should return None, not raise exception

    def test_find_rpyc_server_handles_no_such_process(self) -> None:
        """Test graceful handling of psutil.NoSuchProcess."""
        mock_psutil = MagicMock()
        mock_psutil.AccessDenied = MockAccessDenied
        mock_psutil.NoSuchProcess = MockNoSuchProcess
        mock_psutil.ZombieProcess = MockZombieProcess
        mock_psutil.process_iter.side_effect = MockNoSuchProcess(pid=1234)

        with patch("mt5linux.process_manager.psutil", mock_psutil):
            manager = ProcessManager()
            result = manager.find_rpyc_server()

        assert result is None

    def test_find_mt5_handles_no_such_process(self) -> None:
        """Test graceful handling of psutil.NoSuchProcess for MT5."""
        mock_psutil = MagicMock()
        mock_psutil.AccessDenied = MockAccessDenied
        mock_psutil.NoSuchProcess = MockNoSuchProcess
        mock_psutil.ZombieProcess = MockZombieProcess
        mock_psutil.process_iter.side_effect = MockNoSuchProcess(pid=1234)

        with patch("mt5linux.process_manager.psutil", mock_psutil):
            manager = ProcessManager()
            result = manager.find_mt5()

        assert result is None

    def test_find_rpyc_server_handles_process_disappearing(self) -> None:
        """Test handling when process disappears during iteration."""
        mock_proc = MagicMock()
        # Simulate process disappearing when accessing info
        type(mock_proc).info = PropertyMock(side_effect=MockNoSuchProcess(1234))

        mock_psutil = MagicMock()
        mock_psutil.AccessDenied = MockAccessDenied
        mock_psutil.NoSuchProcess = MockNoSuchProcess
        mock_psutil.ZombieProcess = MockZombieProcess
        mock_psutil.process_iter.return_value = [mock_proc]

        with patch("mt5linux.process_manager.psutil", mock_psutil):
            manager = ProcessManager()
            # Should not raise exception
            result = manager.find_rpyc_server()
            # Result can be None due to the exception
            assert result is None or isinstance(result, ProcessInfo)

    def test_no_exceptions_raised_to_caller(self) -> None:
        """Test that detection methods never raise exceptions to caller."""
        exceptions_to_test = [
            MockAccessDenied(pid=1234),
            MockNoSuchProcess(pid=1234),
            MockZombieProcess(pid=1234),
            RuntimeError("Unexpected error"),
            OSError("System error"),
        ]

        for exc in exceptions_to_test:
            mock_psutil = MagicMock()
            mock_psutil.AccessDenied = MockAccessDenied
            mock_psutil.NoSuchProcess = MockNoSuchProcess
            mock_psutil.ZombieProcess = MockZombieProcess
            mock_psutil.process_iter.side_effect = exc

            with patch("mt5linux.process_manager.psutil", mock_psutil):
                manager = ProcessManager()

                # These should not raise exceptions
                result_rpyc = manager.find_rpyc_server()
                result_mt5 = manager.find_mt5()

                assert result_rpyc is None
                assert result_mt5 is None

    def test_returns_none_when_psutil_unavailable(self) -> None:
        """Test that methods return None when psutil is not available."""
        with patch("mt5linux.process_manager.psutil", None):
            manager = ProcessManager()
            assert manager.find_rpyc_server() is None
            assert manager.find_mt5() is None
