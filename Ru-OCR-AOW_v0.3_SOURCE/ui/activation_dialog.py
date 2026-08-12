from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QLabel,QPushButton,QPlainTextEdit,QHBoxLayout,QApplication,QMessageBox
from services.license_service import get_device_code, verify_token, save_token

class ActivationDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent); self.setWindowTitle("Ru - OCR AOW — активация"); self.setFixedWidth(520)
        self.setStyleSheet("QDialog{background:#f0f0ff;} QLabel{color:#30304b;} QPlainTextEdit{background:white;border:1px solid #b9b6dc;border-radius:6px;padding:6px;} QPushButton{background:#6662a8;color:white;border:0;border-radius:7px;padding:9px 14px;font-weight:600;} QPushButton:hover{background:#575396;}")
        lay=QVBoxLayout(self); lay.setContentsMargins(22,22,22,22); lay.setSpacing(10)
        title=QLabel("Активация Ru - OCR AOW"); title.setStyleSheet("font-size:20px;font-weight:700;"); lay.addWidget(title)
        lay.addWidget(QLabel("Отправьте автору код устройства. В ответ получите персональный код активации."))
        self.device=get_device_code(); code=QLabel(self.device); code.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); code.setStyleSheet("font-size:18px;font-weight:700;color:#5d579c;padding:8px;background:white;border-radius:6px;"); lay.addWidget(code)
        copy=QPushButton("Копировать код устройства"); copy.clicked.connect(lambda: QApplication.clipboard().setText(self.device)); lay.addWidget(copy)
        lay.addWidget(QLabel("Код активации:")); self.token=QPlainTextEdit(); self.token.setPlaceholderText("Вставьте полученный код..."); self.token.setFixedHeight(110); lay.addWidget(self.token)
        row=QHBoxLayout(); cancel=QPushButton("Закрыть"); activate=QPushButton("Активировать"); row.addWidget(cancel); row.addStretch(); row.addWidget(activate); lay.addLayout(row)
        cancel.clicked.connect(self.reject); activate.clicked.connect(self.activate)
    def activate(self):
        token=self.token.toPlainText().strip(); ok,msg,_=verify_token(token,self.device)
        if ok: save_token(token); QMessageBox.information(self,"Готово",msg); self.accept()
        else: QMessageBox.warning(self,"Активация",msg)
