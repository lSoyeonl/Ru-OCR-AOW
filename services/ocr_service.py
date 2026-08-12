from __future__ import annotations
import tempfile
from pathlib import Path
from statistics import mean
from typing import Dict, Tuple
from PIL import Image, ImageEnhance, ImageFilter

LANG_MAP = {
    "Китайский (упрощ.)": "ch",
    "Китайский (традиц.)": "chinese_cht",
    "Тайский": "th",
    "Вьетнамский": "vi",
    "Английский": "en",
}
AUTO_CANDIDATES = ["ch", "th", "vi", "en"]

class OCRService:
    def __init__(self):
        self._engines: Dict[str, object] = {}

    def _get_engine(self, lang: str):
        if lang in self._engines: return self._engines[lang]
        try:
            from paddleocr import PaddleOCR
        except Exception as exc:
            raise RuntimeError("OCR-компонент не найден в сборке.") from exc
        engine = PaddleOCR(
            lang=lang, ocr_version="PP-OCRv5",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            device="cpu",
        )
        self._engines[lang] = engine
        return engine

    @staticmethod
    def preprocess(image: Image.Image) -> Image.Image:
        # Conservative upscale/contrast helps small game fonts without destroying colors.
        img = image.convert("RGB")
        if img.width < 1000:
            scale = 2
            img = img.resize((img.width*scale, img.height*scale), Image.Resampling.LANCZOS)
        img = ImageEnhance.Contrast(img).enhance(1.25)
        img = ImageEnhance.Sharpness(img).enhance(1.35)
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
                        try: scores.append(float(score))
                        except Exception: scores.append(0.0)
            except Exception:
                continue
        return "\n".join(texts).strip(), mean(scores) if scores else 0.0

    def _run(self, image_path: Path, lang: str):
        engine = self._get_engine(lang)
        return self._parse_result(engine.predict(str(image_path)))

    def recognize(self, image: Image.Image, language_label: str) -> Tuple[str, str, float]:
        image = self.preprocess(image)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            path = Path(tmp.name)
        image.save(path)
        try:
            if language_label != "Авто":
                lang = LANG_MAP[language_label]
                text, conf = self._run(path, lang)
                return text, lang, conf
            candidates = []
            for lang in AUTO_CANDIDATES:
                try:
                    text, conf = self._run(path, lang)
                    quality = conf + min(len(text), 120)/1500.0
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
