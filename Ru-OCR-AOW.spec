# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Ru - OCR AOW.

Important: PaddleX checks OCR extras at runtime through importlib.metadata.
A normal PyInstaller build can include the Python modules but omit *.dist-info
metadata, which makes PaddleX falsely report that OCR dependencies are absent.
This spec explicitly bundles PaddleX/PaddleOCR metadata and the metadata of
all distributions used by PaddleX's OCR / OCR-core extras.
"""

from importlib.metadata import requires

from packaging.markers import default_environment
from packaging.requirements import Requirement
from PyInstaller.utils.hooks import collect_all, copy_metadata


datas = [('assets', 'assets'), ('data', 'data'), ('license', 'license')]
binaries = []
hiddenimports = []

# Bundle packages that rely heavily on dynamic imports/data files.
for package in [
    'PyQt6', 'paddleocr', 'paddlex', 'paddle', 'openai',
    'mss', 'keyboard', 'cryptography'
]:
    try:
        d, b, h = collect_all(package)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as exc:
        print(f'[spec] collect_all({package!r}) skipped: {exc}')


def add_metadata(dist_name: str, recursive: bool = False):
    global datas
    try:
        datas += copy_metadata(dist_name, recursive=recursive)
        print(f'[spec] metadata included: {dist_name}')
    except Exception as exc:
        print(f'[spec] metadata skipped for {dist_name!r}: {exc}')


# PaddleX reads its own Provides-Extra / Requires-Dist metadata during import.
add_metadata('paddlex')
add_metadata('paddleocr')
add_metadata('paddlepaddle')

# PaddleX's dependency guard calls importlib.metadata.version() for every
# distribution in the OCR extra. Include those *.dist-info folders explicitly.
try:
    env = default_environment()
    for raw in requires('paddlex') or []:
        try:
            req = Requirement(raw)
            include = req.marker is None
            if req.marker is not None:
                for extra in ('ocr', 'ocr-core', 'base'):
                    marker_env = env.copy()
                    marker_env['extra'] = extra
                    if req.marker.evaluate(marker_env):
                        include = True
                        break
            if include:
                add_metadata(req.name, recursive=True)
        except Exception as exc:
            print(f'[spec] failed to process PaddleX requirement {raw!r}: {exc}')
except Exception as exc:
    print(f'[spec] could not enumerate PaddleX requirements: {exc}')


a = Analysis(
    ['main.py'],
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
    name='Ru-OCR-AOW',
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
    name='Ru-OCR-AOW',
)
