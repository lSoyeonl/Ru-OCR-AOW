from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

os.environ["PADDLE_PDX_MODEL_SOURCE"] = "BOS"

from paddleocr import PaddleOCR

OUT = Path("ocr_models").resolve()
CACHE = Path.home() / ".paddlex" / "official_models"

if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True, exist_ok=True)

COMMON = dict(
    ocr_version="PP-OCRv5",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    device="cpu",
    text_detection_model_name="PP-OCRv5_mobile_det",
)

# We deliberately let PaddleOCR select Thai and Vietnamese recognizers by lang,
# so this stays aligned with the exact installed PaddleOCR/PaddleX version.
REQUESTS = [
    ("ch", {"text_recognition_model_name": "PP-OCRv5_mobile_rec"}),
    ("chinese_cht", {"text_recognition_model_name": "PP-OCRv5_mobile_rec"}),
    ("en", {"text_recognition_model_name": "PP-OCRv5_mobile_rec"}),
    ("th", {}),
    ("vi", {}),
]

manifest = {
    "det": "PP-OCRv5_mobile_det",
    "rec": {},
}

def dirs() -> set[str]:
    if not CACHE.exists():
        return set()
    return {p.name for p in CACHE.iterdir() if p.is_dir()}

for lang, extra in REQUESTS:
    before = dirs()
    print(f"[prefetch] Initializing {lang}...")
    PaddleOCR(lang=lang, **COMMON, **extra)
    after = dirs()
    new_dirs = sorted(after - before)

    if lang in {"ch", "chinese_cht", "en"}:
        manifest["rec"][lang] = "PP-OCRv5_mobile_rec"
    else:
        # PaddleOCR 3.7 may reuse one already-downloaded multilingual recognizer
        # for several languages. Therefore `new_dirs` can legitimately be empty.
        rec_candidates = [n for n in new_dirs if "rec" in n.lower()]
        all_rec = sorted(n for n in after if "rec" in n.lower())

        if not rec_candidates:
            # First prefer an exact / language-prefixed model if Paddle supplies one.
            prefix = lang.lower() + "_"
            rec_candidates = [n for n in all_rec if n.lower().startswith(prefix)]

        if not rec_candidates and lang == "vi":
            # Depending on the installed PaddleOCR/PaddleX release Vietnamese can
            # be routed to a Latin recognizer or the newer shared multilingual rec.
            rec_candidates = [n for n in all_rec if n.lower().startswith("latin_")]

        if not rec_candidates:
            # Current PaddleOCR 3.7/PaddleX 3.7 builds can select the shared
            # PP-OCRv6 multilingual recognizer for both th and vi. It may already
            # have been downloaded while initializing the previous language.
            shared = [
                n for n in all_rec
                if n in {
                    "PP-OCRv6_medium_rec",
                    "PP-OCRv6_small_rec",
                    "PP-OCRv6_tiny_rec",
                }
            ]
            if shared:
                # Prefer medium, then small, then tiny.
                priority = {
                    "PP-OCRv6_medium_rec": 3,
                    "PP-OCRv6_small_rec": 2,
                    "PP-OCRv6_tiny_rec": 1,
                }
                shared.sort(key=lambda n: priority.get(n, 0), reverse=True)
                rec_candidates = [shared[0]]

        if not rec_candidates:
            raise RuntimeError(
                f"Could not determine local recognition model for {lang}. "
                f"New dirs: {new_dirs}; all cache: {sorted(after)}"
            )

        manifest["rec"][lang] = rec_candidates[0]
        print(f"[prefetch] {lang} -> {manifest['rec'][lang]}")

if not CACHE.exists():
    raise RuntimeError(f"PaddleX model cache not found: {CACHE}")

print("[prefetch] Copying official model cache...")
for model_dir in CACHE.iterdir():
    if model_dir.is_dir():
        shutil.copytree(model_dir, OUT / model_dir.name, dirs_exist_ok=True)

(OUT / "model_manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print("[prefetch] Manifest:")
print(json.dumps(manifest, ensure_ascii=False, indent=2))
print("[prefetch] Bundled models:")
for p in sorted(OUT.iterdir()):
    print(" -", p.name)
