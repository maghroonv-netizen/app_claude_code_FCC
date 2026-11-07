import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("FCC_DATA_DIR", os.path.join(tempfile.gettempdir(), "fcc-test-data"))
os.environ.setdefault("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1")


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return ROOT


def _qt_hygiene() -> None:
    """Destroy Qt objects deterministically while the QApplication still lives.

    Windows aborts the whole process — silently, with no Python traceback —
    when a parentless QThread or widget is garbage-collected during interpreter
    shutdown.  After every test (and after the session) we therefore join any
    stray CLI-probe threads and delete every top-level widget.
    """
    try:
        from PySide6.QtCore import QCoreApplication, QEvent
        from PySide6.QtWidgets import QApplication
    except Exception:  # pragma: no cover - Qt missing
        return
    app = QApplication.instance()
    if app is None:
        return
    try:
        from fcc.ui.main_window import drain_probes

        drain_probes(10000)
    except Exception:
        pass
    for widget in list(app.topLevelWidgets()):
        try:
            widget.close()
            widget.deleteLater()
        except RuntimeError:  # C++ object already deleted
            pass
    try:
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
    except RuntimeError:  # pragma: no cover
        pass


@pytest.fixture(autouse=True)
def _qt_state_hygiene():
    yield
    _qt_hygiene()


@pytest.fixture(scope="session", autouse=True)
def _qt_session_hygiene():
    yield
    _qt_hygiene()


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    """Record a machine-readable marker once the session has fully concluded.

    PySide6 can hard-crash during interpreter shutdown on Windows even after a
    completely green session; CI uses this marker to tell that apart from real
    test failures.  It is written to a side file (flush + fsync) so neither
    pytest's capture nor a later crash can lose it.
    """
    try:
        marker = ROOT / "pytest_session_marker.txt"
        with open(marker, "w", encoding="utf-8") as handle:
            handle.write(f"FCC_SESSION_COMPLETE exitstatus={int(exitstatus)}\n")
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:  # pragma: no cover
        pass


@pytest.fixture()
def tmp_config(tmp_path):
    from fcc import config as config_module
    from fcc import paths

    os.environ["FCC_DATA_DIR"] = str(tmp_path / "data")
    paths._current = None  # type: ignore[attr-defined]
    config_module._current = None
    config = config_module.load()
    yield config
    config_module._current = None
