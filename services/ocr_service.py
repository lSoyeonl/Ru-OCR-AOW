from __future__ import annotations

import os
import tempfile
import threading
from pathlib import Path
from statistics import mean
from typing import Callable, Dict, Optional, Tuple

from PIL import Image, ImageEnhance

# PaddleOCR 3.x downloads official models from HuggingFace by default.
# For the Windows portable build we prefer Paddle's BOS mirror, which avoids
# long "silent" waits when HuggingFace is slow or unavailable.
os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", "BOS")

LANG_MAP = {
    "Китайский (упрощ.)": "ch",
    "Китайский (традиц.)": "chinese_cht",
    "Тайский": "th",
    "Вьетнамский": "vi",
    "Английский": "en",
}

AUTO_CANDIDATES = ["ch", "th", "vi", "en"]

ProgressFn = Optional[Callable[[str], None]]


class OCRService:
    def __init__(self):
        self._engines: Dict[str, object] = {}
        self._engine_lock = threading.Lock()

    @staticmethod
    def _progress(cb: ProgressFn, text: str) -> None:
        if cb:
            try:
                cb(text)
            except Exception:
                pass

    def _get_engine(self, lang: str, progress: ProgressFn = None):
        if lang in self._engines:
            return self._engines[lang]

        # Prevent hover + F8 from trying to initialize/download the same model twice.
        with self._engine_lock:
            if lang in self._engines:
                return self._engines[lang]

            self._progress(
                progress,
                "Подготавливаю OCR-модель… При первом запуске язык может загружаться 20–90 секунд."
            )

            try:
                from paddleocr import PaddleOCR
            except Exception as exc:
                raise RuntimeError("OCR-компонент не найден в сборке.") from exc

            kwargs = dict(
                lang=lang,
                ocr_version="PP-OCRv5",
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
                device="cpu",
                # Mobile detection is much better suited to an interactive game overlay.
                text_detection_model_name="PP-OCRv5_mobile_det",
            )

            # The unified mobile recognizer supports Simplified Chinese,
            # Traditional Chinese and English and is much lighter than server_rec.
            if lang in {"ch", "chinese_cht", "en"}:
                kwargs["text_recognition_model_name"] = "PP-OCRv5_mobile_rec"

            try:
                engine = PaddleOCR(**kwargs)
            except TypeError:
                # Compatibility fallback if a future/older PaddleOCR build rejects
                # the explicit mobile detector argument.
                kwargs.pop("text_detection_model_name", None)
                kwargs.pop("text_recognition_model_name", None)
                engine = PaddleOCR(**kwargs)

            self._engines[lang] = engine
            self._progress(progress, "OCR-модель готова.")
            return engine

    def warmup(self, language_label: str, progress: ProgressFn = None) -> None:
        """
        Prepare the selected language in the background shortly after app start.
        Auto mode is intentionally NOT preloaded because it would initialize
        four language engines and can take several minutes on a fresh PC.
        """
        if language_label == "Авто":
            self._progress(
                progress,
                "Режим «Авто» загружает несколько языков. Для игры быстрее выбрать язык вручную."
            )
            return
        lang = LANG_MAP.get(language_label)
        if lang:
            self._get_engine(lang, progress)

    @staticmethod
    def preprocess(image: Image.Image) -> Image.Image:
        img = image.convert("RGB")

        # Game UI text is often small. Upscale only genuinely small captures;
        # avoid turning a large capture into millions of extra pixels.
        if img.width <= 700 and img.height <= 350:
            img = img.resize(
                (int(img.width * 1.6), int(img.height * 1.6)),
                Image.Resampling.LANCZOS,
            )

        img = ImageEnhance.Contrast(img).enhance(1.20)
        img = ImageEnhance.Sharpness(img).enhance(1.25)
        return img

    @staticmethod
    def _parse_result(result) -> Tuple[str, float]:
        texts, scores = [], []
        for item in result:
            try:
                data = item.json
                if isinstance(data, str):
                    import json
                    data = json.loads(data)
                res = data.get("res", data)
                rec_texts = res.get("rec_texts", []) or []
                rec_scores = res.get("rec_scores", []) or [0.0] * len(rec_texts)
                for text, score in zip(rec_texts, rec_scores):
                    text = str(text).strip()
                    if text:
                        texts.append(text)
                        try:
                            scores.append(float(score))
                        except Exception:
                            scores.append(0.0)
            except Exception:
                continue
        return "\n".join(texts).strip(), mean(scores) if scores else 0.0

    def _run(self, image_path: Path, lang: str, progress: ProgressFn = None):
        engine = self._get_engine(lang, progress)
        self._progress(progress, "Распознаю текст…")
        return self._parse_result(engine.predict(str(image_path)))

    def recognize(
        self,
        image: Image.Image,
        language_label: str,
        progress: ProgressFn = None,
    ) -> Tuple[str, str, float]:
        image = self.preprocess(image)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            path = Path(tmp.name)

        image.save(path)

        try:
            if language_label != "Авто":
                lang = LANG_MAP[language_label]
                text, conf = self._run(path, lang, progress)
                return text, lang, conf

            self._progress(
                progress,
                "Автоопределение: проверяю несколько языков. Это медленнее ручного выбора."
            )
            candidates = []

            for index, lang in enumerate(AUTO_CANDIDATES, start=1):
                try:
                    self._progress(
                        progress,
                        f"Автоопределение языка: {index}/{len(AUTO_CANDIDATES)}…"
                    )
                    text, conf = self._run(path, lang, progress)
                    quality = conf + min(len(text), 120) / 1500.0
                    candidates.append((quality, text, lang, conf))
                except Exception:
                    continue

            if not candidates:
                raise RuntimeError("Не удалось запустить OCR-модели.")

            candidates.sort(key=lambda x: x[0], reverse=True)
            _, text, lang, conf = candidates[0]
            return text, lang, conf

        finally:
            path.unlink(missing_ok=True)
