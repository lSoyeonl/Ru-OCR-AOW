from __future__ import annotations
import json
from runtime_paths import GLOSSARY_PATH, ensure_default_glossary

LANG_NAMES = {
    "ch": "китайский (упрощённый)", "chinese_cht": "китайский (традиционный)",
    "th": "тайский", "vi": "вьетнамский", "en": "английский", "auto": "автоматически определённый язык"
}

class DeepSeekService:
    def __init__(self):
        ensure_default_glossary()
        self.cache = {}

    def _glossary(self) -> str:
        try:
            data = json.loads(GLOSSARY_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return "\n".join(f"{k} = {v}" for k,v in list(data.items())[:500])
        except Exception: pass
        return "(словарь пуст)"

    def translate(self, text: str, source_lang: str, settings: dict, manual: bool=False) -> str:
        text = (text or "").strip()
        if not text: return ""
        cache_key = (text, source_lang, settings.get("deepseek_model"))
        if cache_key in self.cache: return self.cache[cache_key]
        api_key = (settings.get("deepseek_api_key") or "").strip()
        if not api_key:
            raise RuntimeError("Не указан DeepSeek API key. Откройте Настройки → DeepSeek.")
        try:
            from openai import OpenAI
        except Exception as exc:
            raise RuntimeError("В сборке отсутствует клиент API.") from exc
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com", timeout=25.0, max_retries=1)
        src = LANG_NAMES.get(source_lang, source_lang)
        context = settings.get("game_context", "")
        system = f"""Ты профессиональный переводчик и локализатор MMORPG Age of Wushu / 九阴真经.
Переводи на естественный русский язык. Исходный язык: {src}.
Сохраняй цифры, проценты, имена предметов, названия характеристик, квестов и навыков.
Исправляй только очевидные OCR-ошибки, не выдумывай отсутствующий смысл.
Термины из пользовательского словаря имеют приоритет.
Не добавляй комментариев, пояснений, markdown и кавычек — верни только перевод.
Контекст: {context}
Словарь:\n{self._glossary()}"""
        resp = client.chat.completions.create(
            model=settings.get("deepseek_model", "deepseek-v4-flash"),
            messages=[{"role":"system","content":system},{"role":"user","content":text}],
            temperature=0.15,
            stream=False,
        )
        out = (resp.choices[0].message.content or "").strip()
        if not out: raise RuntimeError("DeepSeek вернул пустой перевод.")
        if len(self.cache) > 250: self.cache.clear()
        self.cache[cache_key] = out
        return out
