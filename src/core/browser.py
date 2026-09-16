"""Opening a link from inside a bundled application.

webbrowser.open() hands the URL to a helper - xdg-open on Linux, which is a
shell script that runs the desktop's own binaries. Those children inherit this
process's environment, and inside a PyInstaller bundle that environment points
at the copies of Qt, libstdc++ and libssl that VEIM ships. KDE's kde-open then
loads the wrong Qt, dies without printing anything, and the click appears to do
nothing at all.

PyInstaller saves what it replaced in <VAR>_ORIG, so a child process that is
not part of the bundle can be handed the environment it would have had. What is
left after that - a bundle path with no saved original, as an AppImage runtime
can leave behind - is filtered out by where it points.
"""
import os
import shutil
import subprocess
import sys
import webbrowser
from typing import Dict, List, Optional

from src.core.logger import log

# Variables that can carry a path into the bundle. Restoring or dropping these
# is the difference between a working xdg-open and a silent one.
BUNDLE_VARS = (
    "LD_LIBRARY_PATH", "LD_PRELOAD", "LD_RUN_PATH",
    "DYLD_LIBRARY_PATH", "DYLD_FRAMEWORK_PATH", "DYLD_INSERT_LIBRARIES",
    "QT_PLUGIN_PATH", "QML2_IMPORT_PATH", "QML_IMPORT_PATH",
    "GIO_MODULE_DIR", "GTK_PATH", "GDK_PIXBUF_MODULE_FILE",
    "GST_PLUGIN_PATH", "GST_PLUGIN_SYSTEM_PATH",
    "PYTHONHOME", "PYTHONPATH", "XDG_DATA_DIRS", "PATH",
)

# Desktop openers, best first. Everything here hands the URL to whatever the
# user has actually chosen as their browser.
LINUX_OPENERS = (
    ["xdg-open"],
    ["gio", "open"],
    ["kde-open"],
    ["gnome-open"],
    ["x-www-browser"],
    ["sensible-browser"],
)


def _bundle_root() -> str:
    """Where this build unpacks itself, or "" when running from a checkout."""
    if not getattr(sys, "frozen", False):
        return ""
    return getattr(sys, "_MEIPASS", "") or os.environ.get("APPDIR", "")


def system_environment() -> Dict[str, str]:
    """This process's environment as a program outside the bundle wants it.

    Restores every <VAR>_ORIG PyInstaller left behind, then strips whatever
    still points inside the bundle - entry by entry, so a list like
    XDG_DATA_DIRS keeps the system directories it also carries.
    """
    env = dict(os.environ)

    for saved in [name for name in env if name.endswith("_ORIG")]:
        original = env.pop(saved)
        name = saved[: -len("_ORIG")]
        if original:
            env[name] = original
        else:
            # The variable did not exist before the bundle invented it.
            env.pop(name, None)

    root = _bundle_root()
    if root:
        for name in BUNDLE_VARS:
            value = env.get(name)
            if not value or root not in value:
                continue
            kept = [part for part in value.split(os.pathsep)
                    if part and not part.startswith(root)]
            if kept:
                env[name] = os.pathsep.join(kept)
            else:
                env.pop(name)

    return env


def _opener(env: Dict[str, str]) -> Optional[List[str]]:
    """The command this desktop opens URLs with, looked up on the real PATH."""
    if sys.platform == "darwin":
        return ["open"]
    if not sys.platform.startswith("linux"):
        # Windows has no environment to repair: os.startfile, which is what
        # webbrowser uses there, does not spawn a child that loads our
        # libraries.
        return None

    path = env.get("PATH") or os.defpath
    for command in LINUX_OPENERS:
        if shutil.which(command[0], path=path):
            return list(command)
    return None


def open_url(url: str) -> bool:
    """Open a URL in the user's browser. True when a helper was launched.

    A launched helper is as far as this can see - whether the browser then
    draws a window is between it and the desktop - but it is the difference
    that matters here, because the bundled environment used to stop anything
    from launching at all.
    """
    env = system_environment()
    command = _opener(env)

    if command:
        try:
            subprocess.Popen(
                command + [url],
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                # Outlive VEIM: closing the app should not close the browser.
                start_new_session=True,
            )
            log.debug(f"Opened {url} with {command[0]}")
            return True
        except OSError as e:
            log.warning(f"{command[0]} could not open {url}: {e}")

    try:
        if webbrowser.open(url):
            return True
    except Exception as e:      # webbrowser raises from whatever it found
        log.warning(f"No browser could be started for {url}: {e}")

    log.error(f"Nothing on this system would open {url}")
    return False
