# -*- mode: python ; coding: utf-8 -*-

import re
from pathlib import Path

# Read the version from __init__.py or main.py
text = Path("lib/__init__.py").read_text()
# math the version string
match = re.search(r'__version__\s*=\s*["\'](.+?)["\']', text)
# sanity check
if not match:
    raise RuntimeError("Could not find __version__ in __init__.py")
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
