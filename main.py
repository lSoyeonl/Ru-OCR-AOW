from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path


def _self_test_report_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "ocr_self_test.json"
    return Path.cwd() / "ocr_self_test.json"


def packaged_dependency_self_test() -> int:
    """CI diagnostic for PaddleX OCR dependencies inside the packaged EXE."""
    report = {
        "ok": False,
        "frozen": bool(getattr(sys, "frozen", False)),
        "python": sys.version,
        "executable": sys.executable,
    }

    try:
        import importlib.metadata as md
        import paddle
        import paddleocr
        import paddlex
        from paddlex.utils import deps

        report["versions"] = {}
        for dist_name in ("paddlepaddle", "paddleocr", "paddlex"):
            try:
                report["versions"][dist_name] = md.version(dist_name)
            except Exception as exc:
                report["versions"][dist_name] = f"ERROR: {type(exc).__name__}: {exc}"

        extras = getattr(deps, "EXTRAS", {})
        report["extra_keys"] = sorted(str(k) for k in extras.keys())

        ocr_deps = list(extras.get("ocr", []))
        report["ocr_dependencies"] = [str(x) for x in ocr_deps]

        dep_status = {}
        is_dep_available = getattr(deps, "is_dep_available", None)
        if is_dep_available is not None:
            for dep in ocr_deps:
                key = str(dep)
                try:
                    dep_status[key] = {
                        "available": bool(is_dep_available(dep)),
                    }
                except Exception as exc:
                    dep_status[key] = {
                        "available": False,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
        report["dependency_status"] = dep_status

        try:
            report["ocr_extra_available"] = bool(deps.is_extra_available("ocr"))
        except Exception as exc:
            report["ocr_extra_available"] = False
            report["is_extra_available_error"] = (
                f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
            )

        report["ok"] = bool(report.get("ocr_extra_available"))
        code = 0 if report["ok"] else 21

    except Exception as exc:
        report["fatal_error"] = f"{type(exc).__name__}: {exc}"
        report["traceback"] = traceback.format_exc()
        code = 22

    try:
        _self_test_report_path().write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
    except Exception:
        pass

    return code


def main():
    # Must run before Qt / licensing, so GitHub Actions can test the packaged EXE.
    if "--self-test-deps" in sys.argv:
        return packaged_dependency_self_test()

    from PyQt6.QtWidgets import QApplication, QDialog
    from config import load_settings
    from services.ocr_service import OCRService
    from services.deepseek_service import DeepSeekService
    from services.license_service import current_license
    from ui.activation_dialog import ActivationDialog
    from ui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Ru - OCR AOW")
    app.setQuitOnLastWindowClosed(False)

    settings = load_settings()

    if settings.get("license_required", True):
        ok, _, _ = current_license()
        if not ok:
            dlg = ActivationDialog()
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return 0

    win = MainWindow(settings, OCRService(), DeepSeekService())
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
