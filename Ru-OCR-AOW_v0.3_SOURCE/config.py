from __future__ import annotations
import json, os
from runtime_paths import SETTINGS_PATH

DEFAULTS = {
    "source_language": "Китайский (упрощ.)",
    "target_language": "Русский",
    "deepseek_api_key": "",
    "deepseek_model": "deepseek-v4-flash",
    "global_hotkey_area": "f8",
    "global_hotkey_hover": "f9",
    "global_hotkey_copy": "f10",
    "hover_interval_ms": 1300,
    "hover_width": 560,
    "hover_height": 190,
    "overlay_seconds": 10,
    "show_source_in_overlay": True,
    "game_context": "Age of Wushu / 九阴真经: интерфейс, навыки, предметы, квесты, характеристики и диалоги.",
    "author": "Укажите автора",
    "author_url": "https://example.com",
    "license_required": True,
}

def load_settings() -> dict:
    data = DEFAULTS.copy()
    if SETTINGS_PATH.exists():
        try:
            loaded = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict): data.update(loaded)
        except Exception: pass
    env_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if env_key and not data.get("deepseek_api_key"):
        data["deepseek_api_key"] = env_key
    return data

def save_settings(data: dict) -> None:
    SETTINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
