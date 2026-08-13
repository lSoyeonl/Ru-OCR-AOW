from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from statistics import mean
from typing import Callable, Dict, Optional, Tuple

from PIL import Image, ImageEnhance

from runtime_paths import resource_path

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
        self.models_root = resource_path("ocr_models")
        self.manifest = self._load_manifest()

    def _load_manifest(self) -> dict:
        path = self.models_root / "model_manifest.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                raise RuntimeError(f"Повреждён OCR manifest: {exc}") from exc
        return {}

    @staticmethod
    def _progress(cb: ProgressFn, text: str) -> None:
        if cb:
            try:
                cb(text)
            except Exception:
                pass

    def _local_kwargs(self, lang: str) -> dict:
        if not self.manifest:
            return {}

        det_name = self.manifest.get("det")
        rec_name = (self.manifest.get("rec") or {}).get(lang)
        if not det_name or not rec_name:
            raise RuntimeError(f"В сборке не описана OCR-модель для языка: {lang}")

        det_dir = self.models_root / det_name
        rec_dir = self.models_root / rec_name
        if not det_dir.exists():
            raise RuntimeError(f"В сборке отсутствует OCR detection model: {det_name}")
        if not rec_dir.exists():
            raise RuntimeError(f"В сборке отсутствует OCR recognition model: {rec_name}")

        return {
            "text_detection_model_name": det_name,
            "text_detection_model_dir": str(det_dir),
            "text_recognition_model_name": rec_name,
            "text_recognition_model_dir": str(rec_dir),
        }

    def _get_engine(self, lang: str, progress: ProgressFn = None):
        if lang in self._engines:
            return self._engines[lang]

        self._progress(progress, "Запускаю локальную OCR-модель…")

        with self._engine_lock:
            if lang in self._engines:
                return self._engines[lang]

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
            )

            local = self._local_kwargs(lang)
            if local:
                kwargs.update(local)
            else:
                # Development-only fallback. A released EXE should always have
                # the manifest and local models and should never need the network.
                kwargs["text_detection_model_name"] = "PP-OCRv5_mobile_det"
                if lang in {"ch", "chinese_cht", "en"}:
                    kwargs["text_recognition_model_name"] = "PP-OCRv5_mobile_rec"

            try:
                engine = PaddleOCR(**kwargs)
            except Exception as exc:
                raise RuntimeError(f"Не удалось запустить OCR ({lang}): {exc}") from exc

            self._engines[lang] = engine
            self._progress(progress, "OCR-модель готова.")
            return engine

    def warmup(self, language_label: str, progress: ProgressFn = None) -> None:
        if language_label == "Авто":
            self._progress(
                progress,
                "Для игры выберите язык вручную: «Авто» проверяет несколько моделей."
            )
            return
        lang = LANG_MAP.get(language_label)
        if lang:
            self._get_engine(lang, progress)

    @staticmethod
    def preprocess(image: Image.Image) -> Image.Image:
        img = image.convert("RGB")
        if img.width <= 700 and img.height <= 350:
            img = img.resize(
                (int(img.width * 1.8), int(img.height * 1.8)),
                Image.Resampling.LANCZOS,
            )
        img = ImageEnhance.Contrast(img).enhance(1.25)
        img = ImageEnhance.Sharpness(img).enhance(1.30)
        return img

    @staticmethod
    def _parse_result(result) -> Tuple[str, float]:
        texts, scores = [], []
        for item in result:
            try:
                data = item.json
                if isinstance(data, str):
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
        try:
            result = engine.predict(str(image_path))
        except Exception as exc:
            raise RuntimeError(f"Ошибка OCR inference: {exc}") from exc
        return self._parse_result(result)

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

            candidates = []
            for index, lang in enumerate(AUTO_CANDIDATES, start=1):
                self._progress(
                    progress,
                    f"Автоопределение: модель {index}/{len(AUTO_CANDIDATES)}…"
                )
                try:
                    text, conf = self._run(path, lang, progress)
                    quality = conf + min(len(text), 120) / 1500.0
                    candidates.append((quality, text, lang, conf))
                except Exception:
                    continue

            if not candidates:
                raise RuntimeError("Ни одна OCR-модель не смогла обработать область.")

            candidates.sort(key=lambda x: x[0], reverse=True)
            _, text, lang, conf = candidates[0]
            return text, lang, conf
        finally:
            path.unlink(missing_ok=True)
