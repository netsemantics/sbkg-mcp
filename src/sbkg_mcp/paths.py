"""XDG-compliant path resolution for SBKG data storage."""

from pathlib import Path

from platformdirs import user_data_dir


def get_data_dir() -> Path:
    """Return the XDG-compliant data directory for SBKG."""
    path = Path(user_data_dir("sbkg"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_db_path() -> Path:
    """Return the path to the Oxigraph persistent store directory."""
    path = get_data_dir() / "oxigraph"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_export_path() -> Path:
    """Return the default export directory."""
    path = get_data_dir() / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path
