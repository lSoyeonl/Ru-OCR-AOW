from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Iterable

from runtime_paths import GLOSSARY_PATH, ensure_default_glossary
from services.deepseek_service import DeepSeekService

PROVIDER_LABELS = {
    "azure": "Azure Translator",
    "deepl": "DeepL",
    "gemini": "Gemini",
    "deepseek": "DeepSeek",
}

# Internal OCR language code -> provider language code.
AZURE_LANG = {
    "ch": "zh-Hans",
    "chinese_cht": "zh-Hant",
    "th": "th",
    "vi": "vi",
    "en": "en",
}
DEEPL_LANG = {
    "ch": "ZH",
    "chinese_cht": "ZH",
    "th": "TH",
    "vi": "VI",
    "en": "EN",
}
LANG_NAMES = {
    "ch": "китайский (упрощённый)",
    "chinese_cht": "китайский (традиционный)",
    "th": "тайский",
    "vi": "вьетнамский",
    "en": "английский",
    "auto": "автоматически определённый язык",
}


class TranslationService:
    """Multi-provider translator with automatic fallback.

    Auto priority: Azure -> DeepL -> Gemini -> DeepSeek.
    A provider is skipped when its API key is empty. Any provider/network/quota
    error moves the request to the next configured provider.
    """

    def __init__(self):
        ensure_default_glossary()
        self.deepseek = DeepSeekService()
        self.cache: dict[tuple, tuple[str, str]] = {}
        self.last_provider = ""
        self.last_errors: list[str] = []

    def _glossary(self) -> str:
        try:
            data = json.loads(GLOSSARY_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return "\n".join(f"{k} = {v}" for k, v in list(data.items())[:500])
        except Exception:
            pass
        return "(словарь пуст)"

    def provider_label(self) -> str:
        return PROVIDER_LABELS.get(self.last_provider, self.last_provider or "—")

    @staticmethod
    def _is_configured(provider: str, settings: dict) -> bool:
        key_field = {
            "azure": "azure_translator_key",
            "deepl": "deepl_api_key",
            "gemini": "gemini_api_key",
            "deepseek": "deepseek_api_key",
        }.get(provider)
        return bool(key_field and (settings.get(key_field) or "").strip())

    def has_configured_provider(self, settings: dict) -> bool:
        return any(self._is_configured(p, settings) for p in ("azure", "deepl", "gemini", "deepseek"))

    def configured_provider_names(self, settings: dict) -> list[str]:
        return [PROVIDER_LABELS[p] for p in ("azure", "deepl", "gemini", "deepseek") if self._is_configured(p, settings)]

    @staticmethod
    def _provider_order(settings: dict) -> list[str]:
        mode = (settings.get("translation_mode") or "auto").strip().lower()
        if mode in PROVIDER_LABELS:
            return [mode]
        raw = settings.get("translator_priority", ["azure", "deepl", "gemini", "deepseek"])
        if isinstance(raw, str):
            raw = [x.strip().lower() for x in raw.split(",") if x.strip()]
        order = [p for p in raw if p in PROVIDER_LABELS]
        for p in ("azure", "deepl", "gemini", "deepseek"):
            if p not in order:
                order.append(p)
        return order

    @staticmethod
    def _http_json(url: str, *, headers: dict, payload, timeout: float = 18.0):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                body = ""
            message = body[:600].strip() or str(exc.reason)
            try:
                parsed = json.loads(body)
                if isinstance(parsed, dict):
                    err = parsed.get("error", parsed)
                    if isinstance(err, dict):
                        message = str(err.get("message") or err.get("status") or err.get("code") or message)
                    elif err:
                        message = str(err)
            except Exception:
                pass
            raise RuntimeError(f"HTTP {exc.code}: {message}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Ошибка сети: {exc.reason}") from exc

    def _azure(self, text: str, source_lang: str, settings: dict) -> str:
        key = (settings.get("azure_translator_key") or "").strip()
        region = (settings.get("azure_translator_region") or "").strip()
        endpoint = (settings.get("azure_translator_endpoint") or "https://api.cognitive.microsofttranslator.com").rstrip("/")
        params = {"api-version": "3.0", "to": "ru"}
        src = AZURE_LANG.get(source_lang)
        if src:
            params["from"] = src
        url = endpoint + "/translate?" + urllib.parse.urlencode(params)
        headers = {
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "application/json; charset=UTF-8",
        }
        if region:
            headers["Ocp-Apim-Subscription-Region"] = region
        data = self._http_json(url, headers=headers, payload=[{"Text": text}], timeout=15.0)
        try:
            out = data[0]["translations"][0]["text"].strip()
        except Exception as exc:
            raise RuntimeError("Azure вернул неожиданный ответ.") from exc
        if not out:
            raise RuntimeError("Azure вернул пустой перевод.")
        return out

    def _deepl(self, text: str, source_lang: str, settings: dict) -> str:
        key = (settings.get("deepl_api_key") or "").strip()
        base = "https://api-free.deepl.com" if key.endswith(":fx") else "https://api.deepl.com"
        payload = {
            "text": [text],
            "target_lang": "RU",
            "context": settings.get("game_context", "Age of Wushu / 九阴真经"),
        }
        src = DEEPL_LANG.get(source_lang)
        if src:
            payload["source_lang"] = src
        headers = {
            "Authorization": f"DeepL-Auth-Key {key}",
            "Content-Type": "application/json",
            "User-Agent": "Ru-OCR-AOW/0.7.0",
        }
        data = self._http_json(base + "/v2/translate", headers=headers, payload=payload, timeout=15.0)
        try:
            out = data["translations"][0]["text"].strip()
        except Exception as exc:
            raise RuntimeError("DeepL вернул неожиданный ответ.") from exc
        if not out:
            raise RuntimeError("DeepL вернул пустой перевод.")
        return out

    def _llm_prompt(self, text: str, source_lang: str, settings: dict) -> str:
        src = LANG_NAMES.get(source_lang, source_lang)
        return f"""Ты профессиональный переводчик и локализатор MMORPG Age of Wushu / 九阴真经.
Переведи следующий игровой текст с языка: {src} на естественный русский язык.
Сохраняй цифры, проценты, имена предметов, названия характеристик, квестов и навыков.
Исправляй только очевидные OCR-ошибки и не выдумывай отсутствующий смысл.
Термины из пользовательского словаря имеют приоритет.
Не добавляй комментариев, пояснений, markdown или кавычек. Верни только перевод.
Контекст: {settings.get('game_context', '')}
Словарь:
{self._glossary()}

Текст для перевода:
{text}"""

    def _gemini(self, text: str, source_lang: str, settings: dict) -> str:
        key = (settings.get("gemini_api_key") or "").strip()
        model = (settings.get("gemini_model") or "gemini-3.1-flash-lite").strip()
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            + urllib.parse.quote(model, safe="-._")
            + ":generateContent?key="
            + urllib.parse.quote(key, safe="")
        )
        payload = {
            "contents": [{"role": "user", "parts": [{"text": self._llm_prompt(text, source_lang, settings)}]}],
            "generationConfig": {"temperature": 0.15, "maxOutputTokens": 512},
        }
        data = self._http_json(url, headers={"Content-Type": "application/json"}, payload=payload, timeout=20.0)
        try:
            parts = data["candidates"][0]["content"]["parts"]
            out = "".join(str(p.get("text", "")) for p in parts).strip()
        except Exception as exc:
            raise RuntimeError("Gemini вернул неожиданный ответ.") from exc
        if not out:
            raise RuntimeError("Gemini вернул пустой перевод.")
        return out

    def _run_provider(self, provider: str, text: str, source_lang: str, settings: dict, manual: bool) -> str:
        if provider == "azure":
            return self._azure(text, source_lang, settings)
        if provider == "deepl":
            return self._deepl(text, source_lang, settings)
        if provider == "gemini":
            return self._gemini(text, source_lang, settings)
        if provider == "deepseek":
            return self.deepseek.translate(text, source_lang, settings, manual)
        raise RuntimeError(f"Неизвестный переводчик: {provider}")

    def translate(self, text: str, source_lang: str, settings: dict, manual: bool = False) -> str:
        text = (text or "").strip()
        if not text:
            return ""

        mode = (settings.get("translation_mode") or "auto").strip().lower()
        cache_key = (text, source_lang, mode)
        cached = self.cache.get(cache_key)
        if cached:
            out, provider = cached
            self.last_provider = provider
            self.last_errors = []
            return out

        errors: list[str] = []
        configured = False
        for provider in self._provider_order(settings):
            if not self._is_configured(provider, settings):
                continue
            configured = True
            try:
                out = self._run_provider(provider, text, source_lang, settings, manual).strip()
                if not out:
                    raise RuntimeError("пустой перевод")
                self.last_provider = provider
                self.last_errors = errors
                if len(self.cache) > 300:
                    self.cache.clear()
                self.cache[cache_key] = (out, provider)
                return out
            except Exception as exc:
                errors.append(f"{PROVIDER_LABELS[provider]}: {exc}")
                # Auto mode continues. A forced provider stops immediately.
                if mode in PROVIDER_LABELS:
                    break

        self.last_provider = ""
        self.last_errors = errors
        if not configured:
            raise RuntimeError(
                "Не настроен ни один переводчик. Откройте «Настройки» и добавьте ключ Azure, DeepL, Gemini или DeepSeek."
            )
        raise RuntimeError("Все настроенные переводчики недоступны. " + " | ".join(errors))
