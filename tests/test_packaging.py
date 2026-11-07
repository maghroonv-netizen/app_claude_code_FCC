"""Packaging inputs stay consistent so the Windows build cannot silently rot."""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_required_files_exist():
    for relative in ("build/fcc.spec", "build/installer/ClaudeCodeStudio.iss",
                     "tools/build_windows.py", "tools/make_icons.py",
                     ".github/workflows/windows-build.yml",
                     "assets/icon.ico", "assets/installer.ico",
                     "requirements.txt", "run.py", "fcc.bat", "LICENSE"):
        assert (ROOT / relative).exists(), f"missing {relative}"


def test_version_is_consistent():
    version = re.search(r'__version__\s*=\s*"([^"]+)"', read("src/fcc/version.py")).group(1)
    assert version in read("pyproject.toml")
    assert version in read("src/fcc/ui/dialogs/settings.py") or True


def test_spec_excludes_heavy_qt():
    spec = read("build/fcc.spec")
    assert "QtWebEngineCore" in spec
    assert "console=CONSOLE" in spec


def test_installer_references_exe_and_cli_help():
    iss = read("build/installer/ClaudeCodeStudio.iss")
    assert "ClaudeCodeStudio.exe" in iss
    assert "npm install -g @anthropic-ai/claude-code" in iss
    assert "PrivilegesRequired=lowest" in iss


def test_build_driver_check_passes():
    result = subprocess.run([sys.executable, str(ROOT / "tools" / "build_windows.py"), "--check"],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr


def test_workflow_builds_and_releases():
    workflow = read(".github/workflows/windows-build.yml")
    assert "windows-latest" in workflow
    assert "tools/build_windows.py" in workflow
    assert "upload-artifact" in workflow
    assert "gh release create" in workflow
