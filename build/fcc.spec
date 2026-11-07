# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Claude Code Studio.

Environment switches:
    FCC_ONEFILE=1      build a single self-contained .exe instead of a folder
    FCC_CONSOLE=1      keep a console window (useful while debugging)
    FCC_VERSION=x.y.z  override the version stamped into Windows metadata
"""

import os
import re
import sys

BLOCK = None
ROOT = os.path.dirname(os.path.abspath(SPECPATH))          # <repo>/build
REPO = os.path.dirname(ROOT)                                # <repo>
SRC = os.path.join(REPO, "src")
ASSETS = os.path.join(REPO, "assets")

APP_NAME = "ClaudeCodeStudio"
DISPLAY_NAME = "Claude Code Studio"

_version = "1.0.0"
_version_file = os.path.join(SRC, "fcc", "version.py")
if os.path.exists(_version_file):
    with open(_version_file, "r", encoding="utf-8") as _handle:
        _match = re.search(r'__version__\s*=\s*"([^"]+)"', _handle.read())
        if _match:
            _version = _match.group(1)
_version = os.environ.get("FCC_VERSION", _version)

ONEFILE = os.environ.get("FCC_ONEFILE", "") == "1"
CONSOLE = os.environ.get("FCC_CONSOLE", "") == "1"

_datas = [(ASSETS, "assets"), (os.path.join(REPO, "README.md"), ".")]
if os.path.exists(os.path.join(REPO, "LICENSE")):
    _datas.append((os.path.join(REPO, "LICENSE"), "."))

EXCLUDES = [
    # Qt modules the GUI never touches (big wins on size and startup time)
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtWebChannel", "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtQuickWidgets",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput", "PySide6.Qt3DLogic",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets", "PySide6.QtBluetooth", "PySide6.QtNfc",
    "PySide6.QtPositioning", "PySide6.QtSensors", "PySide6.QtSerialPort",
    "PySide6.QtWebSockets", "PySide6.QtRemoteObjects", "PySide6.QtScxml",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtTest", "PySide6.QtDesigner",
    "PySide6.QtHelp", "PySide6.QtSql", "PySide6.QtXml", "PySide6.QtXmlPatterns",
    "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets", "PySide6.QtDBus",
    # python stdlib not needed by a Qt desktop app
    "tkinter", "unittest", "pydoc", "doctest", "lib2to3", "idlelib",
    "matplotlib", "numpy", "scipy", "pandas", "IPython", "jupyter",
]

a = Analysis(
    [os.path.join(REPO, "run.py")],
    pathex=[SRC],
    binaries=[],
    datas=_datas,

    hiddenimports=[
        "fcc", "fcc.ui", "fcc.ui.widgets", "fcc.ui.dialogs", "fcc.claude",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[item for item in EXCLUDES if item],
    noarchive=False,
)

pyz = PYZ(a.pure)

_exe_kwargs = dict(
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=CONSOLE,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
if sys.platform == "win32":
    _exe_kwargs["icon"] = os.path.join(ASSETS, "icon.ico")
    _version_info = os.path.join(ROOT, "version_info.txt")
    if os.path.exists(_version_info):
        _exe_kwargs["version"] = _version_info
elif sys.platform == "darwin":
    _exe_kwargs["icon"] = os.path.join(ASSETS, "logo.png")

if ONEFILE:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=CONSOLE,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=_exe_kwargs.get("icon"),
        **({"version": _exe_kwargs["version"]} if "version" in _exe_kwargs else {}),
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        **_exe_kwargs,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name=APP_NAME,
    )
