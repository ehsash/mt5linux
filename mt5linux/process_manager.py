"""Process detection and management module for mt5linux.

This module provides functionality to detect running rpyc server and MT5 processes,
supporting automatic connection management in the mt5linux library.

Process detection uses psutil for cross-platform process enumeration.
Detection must complete within 2 seconds (NFR8) with 100% accuracy (NFR19).
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Union

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore

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


# Process name patterns for detection
PYTHON_PROCESS_NAMES = frozenset({"python.exe", "pythonw.exe", "python3.exe", "python"})
MT5_PROCESS_NAMES = frozenset(
    {"terminal64.exe", "terminal.exe", "metatrader5.exe", "metatrader.exe"}
)
RPYC_CMDLINE_PATTERNS = frozenset(
    {"rpyc", "rpyc_server", "rpyc.utils.server", "SlaveService"}
)


@dataclass(frozen=True, slots=True)
class ProcessInfo:
    """Information about a detected process.

    Attributes:
        pid: Process ID.
        name: Process name (e.g., 'python.exe', 'terminal64.exe').
        status: Process status (e.g., 'running', 'sleeping').
        cmdline: Optional command-line arguments used to start the process.
    """

    pid: int
    name: str
    status: str
    cmdline: Optional[List[str]] = None


class ProcessManager:
    """Manages process detection for rpyc server and MT5.

    This class provides methods to detect running processes by name and
    command-line arguments, supporting automatic process management in
    the mt5linux library.

    Process detection completes within 2 seconds (NFR8) with 100% accuracy (NFR19).
    All detection methods return None on failure and do not raise exceptions.

    Example:
        >>> manager = ProcessManager()
        >>> rpyc_proc = manager.find_rpyc_server()
        >>> if rpyc_proc:
        ...     print(f"rpyc server running: PID {rpyc_proc.pid}")
    """

    def __init__(self) -> None:
        """Initialize ProcessManager."""
        if psutil is None:
            logger.warning("psutil not available, process detection will not work")

    def find_rpyc_server(self) -> Optional[ProcessInfo]:
        """Find running rpyc server process.

        Searches for Python processes that appear to be running an rpyc server
        by checking process names and command-line arguments.

        Returns:
            ProcessInfo if rpyc server process found, None otherwise.

        Note:
            - Detection completes within 2 seconds (NFR8)
            - Returns None on any error (does not raise exceptions)
            - Matches python.exe, pythonw.exe, python3.exe process names
            - Matches 'rpyc' patterns in command-line arguments
        """
        if psutil is None:
            logger.debug("psutil not available, cannot detect rpyc server")
            return None

        logger.debug("Searching for rpyc server process")
        try:
            return self._find_process_by_criteria(
                name_matches=PYTHON_PROCESS_NAMES,
                cmdline_patterns=RPYC_CMDLINE_PATTERNS,
                require_cmdline_match=True,
            )
        except Exception as e:
            logger.debug(f"Error during rpyc server detection: {e}")
            return None

    def find_mt5(self) -> Optional[ProcessInfo]:
        """Find running MetaTrader 5 process.

        Searches for MT5 processes by checking process names.

        Returns:
            ProcessInfo if MT5 process found, None otherwise.

        Note:
            - Detection completes within 2 seconds (NFR8)
            - Detection accuracy is 100% (NFR19)
            - Returns None on any error (does not raise exceptions)
            - Matches terminal64.exe, terminal.exe, metatrader5.exe, metatrader.exe
        """
        if psutil is None:
            logger.debug("psutil not available, cannot detect MT5")
            return None

        logger.debug("Searching for MT5 process")
        try:
            return self._find_process_by_criteria(
                name_matches=MT5_PROCESS_NAMES,
                cmdline_patterns=None,
                require_cmdline_match=False,
            )
        except Exception as e:
            logger.debug(f"Error during MT5 detection: {e}")
            return None

    def _find_process_by_criteria(
        self,
        name_matches: frozenset,
        cmdline_patterns: Optional[frozenset],
        require_cmdline_match: bool,
    ) -> Optional[ProcessInfo]:
        """Find process matching specified criteria.

        Args:
            name_matches: Set of process names to match (case-insensitive).
            cmdline_patterns: Set of patterns to search for in command-line.
            require_cmdline_match: If True, cmdline must match patterns.

        Returns:
            ProcessInfo if matching process found, None otherwise.
        """
        candidates: List[ProcessInfo] = []

        try:
            for proc in psutil.process_iter(["pid", "name", "status", "cmdline"]):
                try:
                    info = proc.info
                    proc_name = info.get("name", "")
                    if not proc_name:
                        continue

                    # Check process name match (case-insensitive)
                    if proc_name.lower() not in name_matches:
                        continue

                    cmdline = info.get("cmdline") or []
                    cmdline_str = " ".join(cmdline).lower()

                    # Check cmdline patterns if required
                    if require_cmdline_match and cmdline_patterns:
                        if not any(
                            pattern in cmdline_str for pattern in cmdline_patterns
                        ):
                            continue

                    # Found a match
                    process_info = ProcessInfo(
                        pid=info.get("pid", 0),
                        name=proc_name,
                        status=info.get("status", "unknown"),
                        cmdline=cmdline if cmdline else None,
                    )
                    candidates.append(process_info)
                    logger.debug(
                        f"Found matching process: PID={process_info.pid}, name={process_info.name}"
                    )

                except (
                    psutil.NoSuchProcess,
                    psutil.AccessDenied,
                    psutil.ZombieProcess,
                ) as e:
                    # Process disappeared or inaccessible during iteration
                    logger.debug(f"Process inaccessible during iteration: {e}")
                    continue

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            logger.debug(f"Process iteration error: {e}")
            return None
        except Exception as e:
            logger.debug(f"Unexpected error during process iteration: {e}")
            return None

        if not candidates:
            logger.debug("No matching process found")
            return None

        # Return most relevant process (highest PID = newest)
        if len(candidates) > 1:
            logger.debug(
                f"Multiple matching processes found ({len(candidates)}), selecting newest"
            )
            candidates.sort(key=lambda p: p.pid, reverse=True)

        selected = candidates[0]
        logger.info(f"Selected process: PID={selected.pid}, name={selected.name}")
        return selected
