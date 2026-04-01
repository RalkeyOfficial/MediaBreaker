# -*- mode: python ; coding: utf-8 -*-

import re
import sys
from pathlib import Path

# ---- Guard: enforce venv + requirements installed BEFORE building ----

def _read_requirements(req_path: str = "requirements.txt") -> list[str]:
    p = Path(req_path)
    if not p.exists():
        return []
    reqs = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # drop inline comments
        line = line.split("#", 1)[0].strip()
        reqs.append(line)
    return reqs

def _ensure_venv():
    # In a venv, sys.prefix != sys.base_prefix
    if getattr(sys, "base_prefix", sys.prefix) == sys.prefix:
        raise RuntimeError(
            "Build must run inside a virtualenv.\n"
            "Create/activate your venv, install requirements, then run PyInstaller "
            "using that venv's Python."
        )

def _ensure_requirements_installed(reqs: list[str]):
    if not reqs:
        return
    try:
        import pkg_resources  # from setuptools
    except Exception as e:
        raise RuntimeError(
            "setuptools/pkg_resources not available in build env; can't validate requirements.\n"
            "Install setuptools in the venv and try again."
        ) from e

    try:
        pkg_resources.require(reqs)
    except (pkg_resources.DistributionNotFound, pkg_resources.VersionConflict) as e:
        raise RuntimeError(
            "Build environment does not satisfy requirements.txt.\n"
            "Install requirements into the build venv, then re-run PyInstaller.\n"
            f"Details: {e}"
        ) from e

_ensure_venv()
_ensure_requirements_installed(_read_requirements("requirements.txt"))

# ---- Continue with the existing code ----

# Read the version from version.py or main.py
text = Path("lib/version.py").read_text()
# math the version string
match = re.search(r'__version__\s*=\s*["\'](.+?)["\']', text)
# sanity check
if not match:
    raise RuntimeError("Could not find __version__ in version.py")
# get first match
version = match.group(1)

exe_name = f"MediaBreaker-{version}"


a = Analysis(
    ['downloader.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
