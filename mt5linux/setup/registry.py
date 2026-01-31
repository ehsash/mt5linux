"""Global registry for MT5 instances."""

import json
import socket
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


REGISTRY_DIR = Path.home() / ".mt5-instances"
REGISTRY_FILE = REGISTRY_DIR / "registry.json"


@dataclass
class InstanceInfo:
    """Information about a registered MT5 instance."""

    project_path: str
    port: int
    service_name: str
    created_at: str


def load_registry() -> list[InstanceInfo]:
    """Load registry from disk."""
    if not REGISTRY_FILE.exists():
        return []

    try:
        data = json.loads(REGISTRY_FILE.read_text())
        return [InstanceInfo(**item) for item in data]
    except (json.JSONDecodeError, TypeError):
        return []


def save_registry(instances: list[InstanceInfo]) -> None:
    """Save registry to disk."""
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    data = [asdict(inst) for inst in instances]
    REGISTRY_FILE.write_text(json.dumps(data, indent=2))


def is_port_in_use(port: int) -> bool:
    """Check if a port is currently in use."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("localhost", port))
            return False
    except OSError:
        return True


def find_available_port(start: int = 18812, end: int = 18899) -> int:
    """Find first available port not in registry and not in use."""
    registry = load_registry()
    used_ports = {inst.port for inst in registry}

    for port in range(start, end + 1):
        if port in used_ports:
            continue
        if is_port_in_use(port):
            continue
        return port

    raise RuntimeError(f"No available ports in range {start}-{end}")


def register_instance(project_path: Path, port: int) -> None:
    """Add or update project in global registry."""
    registry = load_registry()

    # Remove existing entry for this path
    registry = [r for r in registry if r.project_path != str(project_path)]

    # Add new entry
    registry.append(
        InstanceInfo(
            project_path=str(project_path),
            port=port,
            service_name=f"mt5-rpyc-{project_path.name}",
            created_at=datetime.now().isoformat(),
        )
    )

    save_registry(registry)


def unregister_instance(project_path: Path) -> None:
    """Remove project from global registry."""
    registry = load_registry()
    registry = [r for r in registry if r.project_path != str(project_path)]
    save_registry(registry)


def get_instance(project_path: Path) -> Optional[InstanceInfo]:
    """Get registry entry for a project."""
    registry = load_registry()
    for inst in registry:
        if inst.project_path == str(project_path):
            return inst
    return None
