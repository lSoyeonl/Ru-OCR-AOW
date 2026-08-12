from __future__ import annotations
import sys
from PyQt6.QtWidgets import QApplication, QDialog
from config import load_settings
from services.ocr_service import OCRService
from services.deepseek_service import DeepSeekService
from services.license_service import current_license
from ui.activation_dialog import ActivationDialog
from ui.main_window import MainWindow

def main():
    app=QApplication(sys.argv); app.setApplicationName("Ru - OCR AOW"); app.setQuitOnLastWindowClosed(False)
    settings=load_settings()
    if settings.get("license_required",True):
        ok,_,_=current_license()
        if not ok:
            dlg=ActivationDialog()
            if dlg.exec()!=QDialog.DialogCode.Accepted: return 0
    win=MainWindow(settings,OCRService(),DeepSeekService()); win.show(); return app.exec()
if __name__=="__main__": raise SystemExit(main())
