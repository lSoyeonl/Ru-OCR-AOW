from __future__ import annotations
import sys, shutil
from pathlib import Path

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent

RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
USER_DATA_DIR = APP_DIR / "user_data"
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
SETTINGS_PATH = USER_DATA_DIR / "settings.json"
LICENSE_PATH = USER_DATA_DIR / "license.json"
INSTALL_PATH = USER_DATA_DIR / "installation.json"
GLOSSARY_PATH = USER_DATA_DIR / "glossary.json"

def resource_path(relative: str) -> Path:
    return RESOURCE_DIR / relative

def ensure_default_glossary():
    if not GLOSSARY_PATH.exists():
        src = resource_path("data/glossary.json")
        if src.exists():
            shutil.copy2(src, GLOSSARY_PATH)
        else:
            GLOSSARY_PATH.write_text("{}", encoding="utf-8")
