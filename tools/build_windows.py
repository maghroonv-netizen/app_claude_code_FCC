#!/usr/bin/env python3
"""Package Claude Code Studio into a Windows .exe + installer.

Typical use on Windows (from the repository root):

    python tools/build_windows.py                      # folder app + portable zip
    python tools/build_windows.py --installer          # also build the setup .exe
    python tools/build_windows.py --onefile --clean    # single-file build

On other platforms the script verifies everything and explains the two ways to
produce Windows binaries (locally on a Windows machine, or via the included
GitHub Actions workflow).
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
SPEC = BUILD / "fcc.spec"
ISS = BUILD / "installer" / "ClaudeCodeStudio.iss"
VERSION_FILE = ROOT / "src" / "fcc" / "version.py"
APP = "ClaudeCodeStudio"

ISCC_CANDIDATES = [
    r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    r"C:\Program Files\Inno Setup 6\ISCC.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"),
]


def read_version() -> str:
    try:
        text = VERSION_FILE.read_text(encoding="utf-8")
        match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
        return match.group(1) if match else "1.0.0"
    except OSError:
        return "1.0.0"


def write_version_info(version: str) -> Path:
    """Windows version metadata embedded into the .exe."""
    parts = (version.split(".") + ["0", "0", "0"])[:4]
    numbers = ",".join(str(int(p) if p.isdigit() else 0) for p in parts)
    dotted = ".".join(str(int(p) if p.isdigit() else 0) for p in parts)
    content = f"""# UTF-8
#
# PyInstaller version resource for {APP}
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({numbers}),
    prodvers=({numbers}),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'FCC'),
         StringStruct(u'FileDescription', u'Claude Code Studio — desktop GUI for the Claude Code CLI'),
         StringStruct(u'FileVersion', u'{dotted}'),
         StringStruct(u'InternalName', u'{APP}'),
         StringStruct(u'LegalCopyright', u'MIT — independent community project'),
         StringStruct(u'OriginalFilename', u'{APP}.exe'),
         StringStruct(u'ProductName', u'Claude Code Studio'),
         StringStruct(u'ProductVersion', u'{dotted}')])
    ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""
    target = BUILD / "version_info.txt"
    target.write_text(content, encoding="utf-8")
    return target


def find_iscc(explicit: str = "") -> str:
    if explicit:
        return explicit if Path(explicit).exists() else ""
    found = shutil.which("ISCC") or shutil.which("iscc")
    if found:
        return found
    for candidate in ISCC_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return ""


def run(command: list[str], cwd: Path, env: dict | None = None, on_line=None) -> int:
    printable = " ".join(str(c) for c in command)
    print(f"\n$ {printable}")
    process = subprocess.Popen(
        command, cwd=str(cwd), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        line = line.rstrip()
        if line:
            print(f"  {line}")
            if on_line:
                on_line(line)
    process.wait()
    return process.returncode


def ensure_venv(output: Path, skip_install: bool) -> Path | None:
    """A throw-away venv keeps the packaged build reproducible."""
    venv_dir = BUILD / ".build-venv"
    python = Path(sys.executable)
    if skip_install:
        return python
    if not venv_dir.exists():
        print(f"\ncreating build venv at {venv_dir}")
        code = run([sys.executable, "-m", "venv", str(venv_dir)], ROOT)
        if code != 0:
            print("venv creation failed — falling back to the current interpreter")
            return python
    if sys.platform == "win32":
        venv_python = venv_dir / "Scripts" / "python.exe"
    else:
        venv_python = venv_dir / "bin" / "python"
    if not venv_python.exists():
        return python
    print("\ninstalling build dependencies into the build venv…")
    code = run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], ROOT)
    if code != 0:
        return python
    code = run([str(venv_python), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt"),
                "pyinstaller>=6.6", "pillow>=10"], ROOT)
    if code != 0:
        print("dependency install failed — falling back to the current interpreter")
        return python
    return venv_python


def zip_directory(source: Path, target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for file_path in sorted(source.rglob("*")):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(source.parent).as_posix())
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(BUILD / "output"), help="artifact directory")
    parser.add_argument("--onefile", action="store_true", help="single-file .exe")
    parser.add_argument("--installer", action="store_true", help="compile the Inno Setup installer")
    parser.add_argument("--iscc", default="", help="path to ISCC.exe")
    parser.add_argument("--clean", action="store_true", help="delete previous build artifacts")
    parser.add_argument("--skip-install", action="store_true", help="use the current interpreter")
    parser.add_argument("--console", action="store_true", help="keep a console window")
    parser.add_argument("--check", action="store_true", help="verify inputs only, then exit")
    args = parser.parse_args()

    version = read_version()
    output = Path(args.output).expanduser().resolve()
    print(f"Claude Code Studio {version} — packaging driver")
    print(f"platform : {sys.platform} ({platform.machine()})")
    print(f"python   : {sys.version.split()[0]}")
    print(f"repo     : {ROOT}")
    print(f"output   : {output}")

    problems = []
    for label, path in (("spec", SPEC), ("installer script", ISS),
                        ("windows icon", ROOT / "assets" / "icon.ico")):
        state = "ok" if path.exists() else "MISSING"
        print(f"  [{state:>7}] {path.relative_to(ROOT)}")
        if not path.exists() and state == "MISSING" and label != "windows icon":
            problems.append(str(path))
    if problems:
        print("\nmissing required files; cannot package.")
        return 2
    if args.check:
        print("\nall packaging inputs are present.")
        return 0

    write_version_info(version)

    if args.clean:
        for target in (BUILD / "work", output):
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
                print(f"removed {target}")

    output.mkdir(parents=True, exist_ok=True)

    if sys.platform != "win32":
        print("\n⚠  Packaging must run on Windows. Two supported routes:")
        print("   1. Copy this repository to a Windows machine and run:")
        print(f"         python tools/build_windows.py --output {output} --installer")
        print("   2. Push a version tag (for example v%s) — the included GitHub Actions" % version)
        print("      workflow (.github/workflows/windows-build.yml) builds the .exe and the")
        print("      installer in the cloud and attaches them to a GitHub Release.")
        return 3

    python = ensure_venv(output, args.skip_install)
    env = os.environ.copy()
    env["FCC_VERSION"] = version
    if args.onefile:
        env["FCC_ONEFILE"] = "1"
    if args.console:
        env["FCC_CONSOLE"] = "1"

    started = time.time()
    code = run([str(python), "-m", "PyInstaller", "--noconfirm", "--clean",
                "--distpath", str(output), "--workpath", str(BUILD / "work"),
                str(SPEC)], ROOT, env=env)
    if code != 0:
        print("\nPyInstaller failed.")
        return code
    elapsed = time.time() - started

    artifacts = []
    app_dir = output / APP
    app_exe = output / f"{APP}.exe"
    if args.onefile and app_exe.exists():
        artifacts.append(app_exe)
    elif app_dir.exists():
        artifacts.append(app_dir)
        portable = zip_directory(app_dir, output / f"{APP}-{version}-win64-portable.zip")
        artifacts.append(portable)

    if args.installer:
        iscc = find_iscc(args.iscc)
        if not iscc:
            print("\nInno Setup (ISCC.exe) was not found — skipping the installer.")
            print("Install it from https://jrsoftware.org/isinfo.php, or re-run with --iscc.")
        else:
            print(f"\nusing Inno Setup at {iscc}")
            code = run([iscc, f"/DAPPVERSION={version}", f"/DSourceDir={app_dir}",
                        f"/DOutputDir={output}", str(ISS)], ROOT)
            if code == 0:
                setup = output / f"{APP}-Setup-{version}-x64.exe"
                if setup.exists():
                    artifacts.append(setup)
            else:
                print("\nInno Setup compilation failed.")
                return code

    print(f"\npackaging finished in {elapsed:.0f}s")
    print("artifacts:")
    for artifact in artifacts:
        size = artifact.stat().st_size if artifact.is_file() else sum(
            f.stat().st_size for f in artifact.rglob("*") if f.is_file())
        print(f"  {artifact}  ({size / 1_000_000:.1f} MB)")
    print("\nNext steps on any Windows device:")
    print(f"  • run the installer: {output / f'{APP}-Setup-{version}-x64.exe'}")
    print(f"  • or unpack the portable zip: {output / f'{APP}-{version}-win64-portable.zip'}")
    print("  • first launch shows the setup screen; install the CLI with")
    print("      npm install -g @anthropic-ai/claude-code")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
