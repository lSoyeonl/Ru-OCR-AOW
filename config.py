from __future__ import annotations
import json, os
from runtime_paths import SETTINGS_PATH

DEFAULTS = {
    "source_language": "Китайский (упрощ.)",
    "target_language": "Русский",
    "translation_mode": "auto",
    "translator_priority": ["azure", "deepl", "gemini", "deepseek"],
    "azure_translator_key": "",
    "azure_translator_region": "",
    "azure_translator_endpoint": "https://api.cognitive.microsofttranslator.com",
    "deepl_api_key": "",
    "gemini_api_key": "",
    "gemini_model": "gemini-3.1-flash-lite",
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
    env_map = {
        "AZURE_TRANSLATOR_KEY": "azure_translator_key",
        "AZURE_TRANSLATOR_REGION": "azure_translator_region",
        "DEEPL_API_KEY": "deepl_api_key",
        "GEMINI_API_KEY": "gemini_api_key",
        "DEEPSEEK_API_KEY": "deepseek_api_key",
    }
    for env_name, setting_name in env_map.items():
        value = os.getenv(env_name, "").strip()
        if value and not data.get(setting_name):
            data[setting_name] = value
    return data

def save_settings(data: dict) -> None:
    SETTINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
