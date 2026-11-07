#!/usr/bin/env python3
"""Build no-op stub copies of system libraries some headless Linux containers lack.

Qt's GUI libraries declare a *load-time* dependency on libGL / libEGL /
libxkbcommon / libdbus even when the app renders with the "offscreen" platform
and never calls a single one of their functions. Minimal CI containers (and
this project's dev sandbox) often ship without them, which makes
`import PySide6.QtGui` fail before a single test runs.

This script compiles empty shared objects carrying the right sonames and the
exact versioned symbol table Qt expects, so the dynamic loader is satisfied.
The real symbols are resolved lazily and are never touched by an offscreen Qt
app. Windows and macOS never need this; real Linux desktops never need it.

    python tools/make_stublibs.py                 # writes ~/.cache/fcc-stublibs
    LD_LIBRARY_PATH=~/.cache/fcc-stublibs python -m pytest
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

STUBS = ["libGL.so.1", "libEGL.so.1", "libxkbcommon.so.0", "libdbus-1.so.3"]
SYSTEM_VERSION = re.compile(r"^(GLIBC|GLIBCXX|CXXABI|GCC|LIBC|LIBM|ITM|ZLIB|OPENSSL)")
DYN_SYM_LINE = re.compile(r"^\s*\d+:\s+\S+\s+\S+\s+(\w+)\s+(\w+)\s+\S+\s+(\S+)\s+(\S+)$")


def qt_shared_objects(pyside_dir: Path) -> list[Path]:
    roots = [pyside_dir / "Qt" / "lib", pyside_dir / "Qt" / "plugins"]
    found = []
    for root in roots:
        if root.exists():
            found.extend(sorted(p for p in root.rglob("*") if p.is_file() and ".so" in p.name))
    return found


def provider(symbol: str) -> str:
    if symbol.startswith("dbus_"):
        return "libdbus-1.so.3"
    if symbol.startswith("egl") or symbol.startswith("glEGL"):
        return "libEGL.so.1"
    if symbol.startswith(("glX", "glx")) or re.match(r"^gl[A-Z]", symbol):
        return "libGL.so.1"
    if symbol.startswith("xkb"):
        return "libxkbcommon.so.0"
    return ""


def collect(pyside_dir: Path) -> dict[str, list[list[str]]]:
    defined: set[str] = set()
    undefined: dict[tuple[str, str], int] = collections.defaultdict(int)
    for library in qt_shared_objects(pyside_dir):
        output = subprocess.run(["readelf", "--dyn-syms", "-W", str(library)],
                                capture_output=True, text=True).stdout
        for line in output.splitlines():
            parts = line.split()
            if len(parts) < 8 or not parts[0].rstrip(":").isdigit():
                continue
            bind, section = parts[4], parts[6]
            name = " ".join(parts[7:])
            if bind not in ("GLOBAL", "WEAK"):
                continue
            version = ""
            if "@" in name:
                name, version = name.split("@", 1)
            name = name.split()[0] if name.split() else name
            version = version.split()[0] if version.split() else version
            if section == "UND":
                undefined[(name, version)] += 1
            else:
                defined.add(name)
    wanted: dict[str, set[tuple[str, str]]] = collections.defaultdict(set)
    for (symbol, version), _count in undefined.items():
        if symbol in defined or SYSTEM_VERSION.match(version or ""):
            continue
        target = provider(symbol)
        if target:
            wanted[target].add((symbol, version))
    return {lib: sorted(pairs) for lib, pairs in wanted.items()}


def build(wanted: dict[str, list[list[str]]], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if compiler is None:
        raise SystemExit("a C compiler is required to build the stub libraries")
    for lib, pairs in wanted.items():
        symbols = [pair[0] for pair in pairs]
        source = output / f"gen_{lib}.c"
        source.write_text("\n".join(
            ["int fcc_stub_marker(void) { return 0; }"] +
            [f"int {symbol}(void) {{ return 0; }}" for symbol in symbols]), encoding="utf-8")
        groups: dict[str, list[str]] = collections.defaultdict(list)
        for symbol, version in pairs:
            groups[version or ""].append(symbol)
        blocks = []
        for version, names in groups.items():
            body = "\n".join(f"    {name};" for name in names)
            if version:
                blocks.append(f"{version} {{\nglobal:\n{body}\nlocal: *;\n}};")
            else:
                blocks.append(f"{{\nglobal:\n{body}\nlocal: *;\n}};")
        map_file = output / f"gen_{lib}.map"
        map_file.write_text("\n".join(blocks), encoding="utf-8")
        subprocess.run([compiler, "-shared", "-fPIC", "-o", str(output / lib), str(source),
                        f"-Wl,-soname,{lib}", f"-Wl,--version-script={map_file}"],
                       check=True)
        print(f"built {output / lib} with {len(symbols)} stub symbols")


def pyside_location() -> Path | None:
    try:
        import PySide6  # noqa: F401

        return Path(PySide6.__file__).parent
    except Exception:
        for candidate in Path(sys.prefix).glob("lib/python3.*/site-packages/PySide6"):
            return candidate
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(Path.home() / ".cache" / "fcc-stublibs"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if sys.platform != "linux":
        print("stub libraries are only needed on Linux")
        return 0
    location = pyside_location()
    if location is None:
        print("PySide6 is not installed")
        return 1
    wanted = collect(location)
    if not wanted and not args.force:
        print("nothing missing — no stubs needed")
        return 0
    output = Path(args.output).expanduser().resolve()
    build(wanted, output)
    print(json.dumps({lib: len(pairs) for lib, pairs in wanted.items()}))
    print(f"\nexport LD_LIBRARY_PATH={output}:$LD_LIBRARY_PATH")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
