"""Where VEIM reads its own files from, and where it is allowed to write.

An installed build runs from a read-only bundle inside Program Files, /usr or
an .app, so anything written at runtime -- the logo cache, the log -- has to go
to a per-user directory instead. Running from a checkout keeps both in the
working tree, where .gitignore already covers them.
"""
import os
import sys

APP_NAME = "VEIM"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def resource_dir() -> str:
    """The directory `src/` sits in."""
    if is_frozen():
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def user_data_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser(r"~\AppData\Local")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, APP_NAME)


def icon_cache_dir() -> str:
    if is_frozen():
        path = os.path.join(user_data_dir(), "icons")
    else:
        path = os.path.join(resource_dir(), "src", "assets", "icons")
    os.makedirs(path, exist_ok=True)
    return path


def log_path() -> str:
    if not is_frozen():
        return "veim.log"
    directory = user_data_dir()
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, "veim.log")


def state_path(filename: str) -> str:
    directory = user_data_dir()
    os.makedirs(directory, exist_ok=True)
    return os.path.join(directory, filename)
