# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build. The same spec produces all three platforms' bundles.

    pyinstaller packaging/veim.spec

Output is a one-directory bundle in dist/VEIM (dist/VEIM.app on macOS), which
the release workflow then wraps in an installer, an AppImage or a disk image.
"""
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(SPECPATH, os.pardir))
BRANDING = os.path.join(ROOT, "src", "assets", "branding")

# The definitions VEIM falls back on: the definitions/ submodule, shipped as
# files rather than compiled in. src/core/definitions.py imports them by
# location, and a downloaded copy has to be able to take their place.
DEFINITIONS = os.path.join(ROOT, "definitions")
DEFINITIONS_PACKAGE = os.path.join(DEFINITIONS, "veim_definitions")
if not os.path.isfile(os.path.join(DEFINITIONS_PACKAGE, "registry.py")):
    raise SystemExit("definitions/ is empty: run `git submodule update --init` first")


def definitions_files():
    """Source and logos only: no bytecode left behind by a test run."""
    for dirpath, dirnames, filenames in os.walk(DEFINITIONS_PACKAGE):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            if name.endswith((".py", ".png")):
                full = os.path.join(dirpath, name)
                yield full, os.path.relpath(dirpath, ROOT)


def definitions_version_file():
    """The bundled copy's version, in the form a published release is named:
    when its commit was made, and never later than now. A release is named
    for when it was published, so every release since this commit is newer
    and an installed VEIM takes it."""
    committed = int(subprocess.run(
        ["git", "-C", DEFINITIONS, "log", "-1", "--format=%ct"],
        capture_output=True, text=True, check=True).stdout.strip())
    stamp = datetime.fromtimestamp(min(committed, time.time()), timezone.utc)
    path = os.path.join(ROOT, "build", "definitions", "VERSION")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(stamp.strftime("%Y.%m.%d.%H%M%S"))
    return path


def definitions_stdlib():
    """The standard library definitions may import: an installed VEIM holds
    only the modules it was built with."""
    namespace = {}
    with open(os.path.join(DEFINITIONS_PACKAGE, "__init__.py"), encoding="utf-8") as handle:
        exec(handle.read(), namespace)
    return list(namespace["STDLIB"])

datas = [
    (BRANDING, os.path.join("src", "assets", "branding")),
    # The distribution logos and the dropdown chevron. Without the chevron the
    # stylesheet draws every QComboBox with no arrow; without the logos every
    # catalog row waits on a network fetch that may never succeed.
    (os.path.join(ROOT, "src", "assets", "icons"),
     os.path.join("src", "assets", "icons")),
    (os.path.join(ROOT, "src", "assets", "fonts"),
     os.path.join("src", "assets", "fonts")),
    *definitions_files(),
    (definitions_version_file(), "definitions"),
]

# Nothing in the app imports what only the definitions use.
hiddenimports = [
    "src.core.recipe_base", "src.core.logger", "requests.adapters", "urllib3.util.retry",
    *definitions_stdlib(),
]

# Qt ships far more than a desktop form needs, and every module left in costs
# tens of megabytes in the installer.
excludes = [
    "tkinter", "unittest", "pydoc_data", "pytest",
    # Pulled in by hooks for optional paths this app never takes.
    "numpy", "cryptography", "yaml", "scipy", "pandas", "matplotlib",
    "IPython", "docutils", "jinja2",
    "PySide6.Qt3DAnimation", "PySide6.Qt3DCore", "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DRender",
    "PySide6.QtBluetooth", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets", "PySide6.QtNetworkAuth", "PySide6.QtNfc",
    "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtPdf",
    "PySide6.QtPdfWidgets", "PySide6.QtPositioning", "PySide6.QtQml",
    "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQuickControls2",
    "PySide6.QtQuickWidgets", "PySide6.QtRemoteObjects", "PySide6.QtScxml",
    "PySide6.QtSensors", "PySide6.QtSerialBus", "PySide6.QtSerialPort",
    "PySide6.QtSpatialAudio", "PySide6.QtSql", "PySide6.QtStateMachine",
    "PySide6.QtTest", "PySide6.QtTextToSpeech", "PySide6.QtUiTools",
    "PySide6.QtVirtualKeyboard", "PySide6.QtWebChannel", "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineQuick", "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets", "PySide6.QtXml",
]

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=excludes,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    exclude_binaries=True,
    name="VEIM",
    console=False,
    icon=os.path.join(BRANDING, "veim.ico" if sys.platform == "win32" else "veim.icns"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="VEIM",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="VEIM.app",
        icon=os.path.join(BRANDING, "veim.icns"),
        bundle_identifier="com.github.cir0cuit.veim",
        info_plist={
            "CFBundleName": "VEIM",
            "CFBundleDisplayName": "VEIM",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "NSRemovableVolumesUsageDescription":
                "VEIM reads and writes the ISO files on your Ventoy USB drive.",
        },
    )
