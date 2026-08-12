from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent

RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))


def _stable_user_data_dir() -> Path:
    """
    Store user data outside the portable build folder so updates/re-extraction
    do not generate a new device code or lose the activation/settings.
    """
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "Ru-OCR-AOW"

    # Safe cross-platform fallback for development/testing.
    return Path.home() / ".ru-ocr-aow"


USER_DATA_DIR = _stable_user_data_dir()
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

SETTINGS_PATH = USER_DATA_DIR / "settings.json"
LICENSE_PATH = USER_DATA_DIR / "license.json"
INSTALL_PATH = USER_DATA_DIR / "installation.json"
GLOSSARY_PATH = USER_DATA_DIR / "glossary.json"


def _migrate_legacy_portable_user_data() -> None:
    """
    v0.3-v0.5 stored activation beside the EXE in APP_DIR/user_data.
    On first v0.6 launch, import those files into LocalAppData if the stable
    copies do not already exist.

    This migration works when v0.6 is unpacked over the old program folder.
    If v0.6 is unpacked to a different folder, copy the old `user_data` folder
    next to the new EXE once; the app will import it automatically.
    """
    legacy_dir = APP_DIR / "user_data"
    if not legacy_dir.exists():
        return

    for name in ("installation.json", "license.json", "settings.json", "glossary.json"):
        src = legacy_dir / name
        dst = USER_DATA_DIR / name
        if src.exists() and not dst.exists():
            try:
                shutil.copy2(src, dst)
            except Exception:
                pass


_migrate_legacy_portable_user_data()


def resource_path(relative: str) -> Path:
    return RESOURCE_DIR / relative


def ensure_default_glossary():
    if not GLOSSARY_PATH.exists():
        src = resource_path("data/glossary.json")
        if src.exists():
            shutil.copy2(src, GLOSSARY_PATH)
        else:
            GLOSSARY_PATH.write_text("{}", encoding="utf-8")
