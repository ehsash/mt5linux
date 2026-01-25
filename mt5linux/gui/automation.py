"""GUI automation abstraction for mt5linux."""

import shutil
import subprocess
from typing import Literal, Optional, Tuple

try:
    from loguru import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

from mt5linux.detection import DetectionResult


def get_gui_automation_tool(detection_result: DetectionResult) -> Tuple[Literal["xyphir", "xdotool", "none"], Optional[str]]:
    """
    Determine the appropriate GUI automation tool based on environment.

    Args:
        detection_result: Current environment detection results

    Returns:
        Tuple of (tool_name, tool_path) where tool_name is "xyphir", "xdotool", or "none"
        and tool_path is the path to the executable (or None if not found)
    """
    logger.debug("Determining GUI automation tool")

    # Check for Wayland with xyphir
    if detection_result.environment_type == "local" and detection_result.display_system == "wayland":
        if detection_result.xyphir.found and detection_result.xyphir.path:
            logger.info(f"Using xyphir for Wayland GUI automation: {detection_result.xyphir.path}")
            return ("xyphir", detection_result.xyphir.path)
        # Fallback to xdotool if xyphir not available
        xdotool_path = shutil.which("xdotool")
        if xdotool_path:
            logger.info(f"xyphir not available, using xdotool fallback: {xdotool_path}")
            return ("xdotool", xdotool_path)
        logger.warning("Neither xyphir nor xdotool available for Wayland")
        return ("none", None)

    # Check for X11 with xdotool
    if detection_result.display_system == "x11":
        xdotool_path = shutil.which("xdotool")
        if xdotool_path:
            logger.info(f"Using xdotool for X11 GUI automation: {xdotool_path}")
            return ("xdotool", xdotool_path)
        logger.warning("xdotool not available for X11")
        return ("none", None)

    # No display system or unsupported
    logger.warning(f"No GUI automation tool available for display system: {detection_result.display_system}")
    return ("none", None)


def _get_tool_path(tool: Literal["xyphir", "xdotool"], detection_result: Optional[DetectionResult] = None) -> Optional[str]:
    """
    Get the path to the specified GUI automation tool.

    Args:
        tool: Tool name ("xyphir" or "xdotool")
        detection_result: Environment detection results (optional, for xyphir path caching)

    Returns:
        Path to the tool executable, or None if not found
    """
    if tool == "xyphir":
        # Use cached path from detection_result if available
        if detection_result and detection_result.xyphir.found and detection_result.xyphir.path:
            return detection_result.xyphir.path
        return shutil.which("xyphir")
    if tool == "xdotool":
        return shutil.which("xdotool")
    return None


def _execute_gui_command(
    tool: Literal["xyphir", "xdotool"],
    command: list[str],
    tool_path: Optional[str] = None,
    detection_result: Optional[DetectionResult] = None,
    operation_name: str = "operation",
) -> bool:
    """
    Execute a GUI automation command using the specified tool.

    Args:
        tool: Tool name ("xyphir" or "xdotool")
        command: Command arguments (excluding tool name)
        tool_path: Path to tool executable (will look up if not provided)
        detection_result: Environment detection results (for path caching)
        operation_name: Name of the operation for logging

    Returns:
        True if command succeeded, False otherwise
    """
    if tool_path is None:
        tool_path = _get_tool_path(tool, detection_result)

    if not tool_path:
        error_type = "not_found"
        logger.error(f"{tool} not found in PATH for {operation_name}")
        return False

    try:
        result: subprocess.CompletedProcess[str] = subprocess.run(
            [tool_path] + command,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            logger.debug(f"{tool} {operation_name} succeeded")
            return True
        error_type = "command_failed"
        logger.warning(f"{tool} {operation_name} failed (return code {result.returncode}): {result.stderr}")
    except subprocess.TimeoutExpired:
        error_type = "timeout"
        logger.error(f"{tool} {operation_name} timed out")
    except FileNotFoundError:
        error_type = "not_found"
        logger.error(f"{tool} executable not found at {tool_path} for {operation_name}")
    except PermissionError:
        error_type = "permission_denied"
        logger.error(f"Permission denied executing {tool} at {tool_path} for {operation_name}")
    except OSError as e:
        error_type = "os_error"
        logger.error(f"OS error executing {tool} {operation_name}: {e}")

    return False


def _validate_coordinates(x: int, y: int) -> bool:
    """Validate click coordinates are reasonable."""
    if x < 0 or y < 0:
        logger.error(f"Invalid coordinates: x={x}, y={y} (must be non-negative)")
        return False
    # Reasonable upper bound (4K display is ~3840x2160, allow some margin)
    if x > 10000 or y > 10000:
        logger.warning(f"Coordinates seem unusually large: x={x}, y={y}")
    return True


def _validate_text(text: str) -> bool:
    """Validate text input is safe."""
    if not text:
        logger.error("Empty text provided for typing")
        return False
    # Check for potential command injection (basic check)
    if "\n" in text or "\r" in text:
        logger.warning("Text contains newline characters, may cause issues")
    return True


def _validate_keyname(keyname: str) -> bool:
    """Validate key name format."""
    if not keyname:
        logger.error("Empty keyname provided")
        return False
    if not keyname.replace("_", "").replace("-", "").isalnum():
        logger.warning(f"Keyname contains unusual characters: {keyname}")
    return True


def _validate_window_name(window_name: str) -> bool:
    """Validate window name."""
    if not window_name:
        logger.error("Empty window name provided")
        return False
    return True


def click(x: int, y: int, tool: Optional[Literal["xyphir", "xdotool"]] = None, detection_result: Optional[DetectionResult] = None) -> bool:
    """
    Click at the specified coordinates.

    Args:
        x: X coordinate (must be non-negative)
        y: Y coordinate (must be non-negative)
        tool: GUI automation tool to use (auto-detect if not provided)
        detection_result: Environment detection results (required if tool not provided)

    Returns:
        True if click succeeded, False otherwise
    """
    if not _validate_coordinates(x, y):
        return False

    if tool is None:
        if detection_result is None:
            logger.error("Either tool or detection_result must be provided")
            return False
        tool, tool_path = get_gui_automation_tool(detection_result)
        if tool == "none":
            logger.error("No GUI automation tool available")
            return False
    else:
        tool_path = _get_tool_path(tool, detection_result)

    return _execute_gui_command(tool, ["click", str(x), str(y)], tool_path, detection_result, f"click at ({x}, {y})")


def type_text(text: str, tool: Optional[Literal["xyphir", "xdotool"]] = None, detection_result: Optional[DetectionResult] = None) -> bool:
    """
    Type the specified text.

    Args:
        text: Text to type (must not be empty)
        tool: GUI automation tool to use (auto-detect if not provided)
        detection_result: Environment detection results (required if tool not provided)

    Returns:
        True if typing succeeded, False otherwise
    """
    if not _validate_text(text):
        return False

    if tool is None:
        if detection_result is None:
            logger.error("Either tool or detection_result must be provided")
            return False
        tool, tool_path = get_gui_automation_tool(detection_result)
        if tool == "none":
            logger.error("No GUI automation tool available")
            return False
    else:
        tool_path = _get_tool_path(tool, detection_result)

    return _execute_gui_command(tool, ["type", text], tool_path, detection_result, f"type text (length: {len(text)})")


def press_key(keyname: str, tool: Optional[Literal["xyphir", "xdotool"]] = None, detection_result: Optional[DetectionResult] = None) -> bool:
    """
    Press the specified key.

    Args:
        keyname: Key name (e.g., "Return", "Escape", "Tab")
        tool: GUI automation tool to use (auto-detect if not provided)
        detection_result: Environment detection results (required if tool not provided)

    Returns:
        True if key press succeeded, False otherwise
    """
    if not _validate_keyname(keyname):
        return False

    if tool is None:
        if detection_result is None:
            logger.error("Either tool or detection_result must be provided")
            return False
        tool, tool_path = get_gui_automation_tool(detection_result)
        if tool == "none":
            logger.error("No GUI automation tool available")
            return False
    else:
        tool_path = _get_tool_path(tool, detection_result)

    return _execute_gui_command(tool, ["key", keyname], tool_path, detection_result, f"key press: {keyname}")


def window_focus(window_name: str, tool: Optional[Literal["xyphir", "xdotool"]] = None, detection_result: Optional[DetectionResult] = None) -> bool:
    """
    Focus the window with the specified name.

    Args:
        window_name: Window name or title (must not be empty)
        tool: GUI automation tool to use (auto-detect if not provided)
        detection_result: Environment detection results (required if tool not provided)

    Returns:
        True if window focus succeeded, False otherwise
    """
    if not _validate_window_name(window_name):
        return False

    if tool is None:
        if detection_result is None:
            logger.error("Either tool or detection_result must be provided")
            return False
        tool, tool_path = get_gui_automation_tool(detection_result)
        if tool == "none":
            logger.error("No GUI automation tool available")
            return False
    else:
        tool_path = _get_tool_path(tool, detection_result)

    # Different command structure for xdotool
    if tool == "xdotool":
        return _execute_gui_command(tool, ["search", "--name", window_name, "windowfocus"], tool_path, detection_result, f"window focus: {window_name}")
    else:
        return _execute_gui_command(tool, ["window", "focus", window_name], tool_path, detection_result, f"window focus: {window_name}")
