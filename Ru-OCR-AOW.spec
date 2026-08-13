# -*- mode: python ; coding: utf-8 -*-

"""
Ru - OCR AOW PyInstaller spec.

PaddleOCR's official PyInstaller packaging guide dynamically copies metadata
for every installed distribution that PaddleX knows about through
paddlex.utils.deps.BASE_DEP_SPECS (or DEP_SPECS on older builds).

This is important because PaddleX performs runtime dependency checks through
importlib.metadata. Python modules alone are not sufficient in a frozen app.
"""

import importlib.metadata as metadata

import paddlex
from packaging.utils import canonicalize_name
from PyInstaller.utils.hooks import collect_all, copy_metadata


datas = [
    ("assets", "assets"),
    ("data", "data"),
    ("license", "license"),
    ("ocr_models", "ocr_models"),
]
binaries = []
hiddenimports = []


# Keep dynamic package contents available to PyInstaller.
for package in [
    "PyQt6",
    "paddleocr",
    "paddlex",
    "paddle",
    "openai",
    "mss",
    "keyboard",
    "cryptography",
]:
    try:
        d, b, h = collect_all(package)
        datas += d
        binaries += b
        hiddenimports += h
        print(f"[spec] collect_all OK: {package}")
    except Exception as exc:
        print(f"[spec] collect_all skipped for {package!r}: {exc}")


def add_metadata(dist_name: str):
    global datas
    try:
        datas += copy_metadata(dist_name)
        print(f"[spec] metadata included: {dist_name}")
        return True
    except Exception as exc:
        print(f"[spec] metadata skipped for {dist_name!r}: {exc}")
        return False


# Always include metadata for the three central distributions.
for required_dist in ("paddlex", "paddleocr", "paddlepaddle"):
    add_metadata(required_dist)


# Official PaddleOCR packaging approach:
# installed distributions ∩ PaddleX dependency specifications.
deps_module = paddlex.utils.deps
dep_specs = getattr(deps_module, "BASE_DEP_SPECS", None)
if dep_specs is None:
    dep_specs = getattr(deps_module, "DEP_SPECS", {})

known_by_canonical = {
    canonicalize_name(str(name)): str(name)
    for name in dep_specs.keys()
}

installed = []
for dist in metadata.distributions():
    try:
        name = dist.metadata.get("Name")
    except Exception:
        name = None
    if name:
        installed.append(name)

copied = set()
for installed_name in installed:
    canon = canonicalize_name(installed_name)
    if canon in known_by_canonical and canon not in copied:
        if add_metadata(installed_name):
            copied.add(canon)

print(f"[spec] PaddleX dependency metadata copied: {len(copied)} distributions")


a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    [],
    exclude_binaries=True,
    name="Ru-OCR-AOW",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Ru-OCR-AOW",
)
