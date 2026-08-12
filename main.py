from __future__ import annotations
import sys


def packaged_dependency_self_test() -> int:
    """Used by GitHub Actions after PyInstaller packaging.

    It checks the same PaddleX OCR-extra gate that caused the v0.3 runtime
    error, without downloading OCR models or opening the GUI.
    """
    try:
        from paddlex.utils.deps import is_extra_available
        return 0 if is_extra_available("ocr") else 21
    except Exception:
        return 22


def main():
    # Keep this before Qt/license initialization so CI can test the packaged EXE.
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
