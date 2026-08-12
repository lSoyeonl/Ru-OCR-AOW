from __future__ import annotations
from PyQt6.QtCore import Qt, QPoint, QTimer
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout, QApplication

class TranslationOverlay(QFrame):
    def __init__(self, source: str, translated: str, seconds: int=10, pos: QPoint|None=None, show_source=True):
        super().__init__(None)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint|Qt.WindowType.WindowStaysOnTopHint|Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("QFrame{background:rgba(20,22,39,238);border:1px solid rgba(190,184,235,160);border-radius:12px;} QLabel{border:none;background:transparent;}")
        lay=QVBoxLayout(self); lay.setContentsMargins(14,12,14,12); lay.setSpacing(6)
        if show_source:
            s=QLabel(source); s.setWordWrap(True); s.setMaximumWidth(540); s.setStyleSheet("color:#aeb3cf;font-size:11px;"); lay.addWidget(s)
        t=QLabel(translated); t.setWordWrap(True); t.setMaximumWidth(540); t.setStyleSheet("color:white;font-size:15px;font-weight:600;"); lay.addWidget(t)
        self.adjustSize()
        screen=QApplication.screenAt(pos or QCursor.pos()) or QApplication.primaryScreen(); area=screen.availableGeometry()
        p=pos or QCursor.pos()+QPoint(18,18); x=min(max(p.x(),area.left()+8), area.right()-self.width()-8); y=min(max(p.y(),area.top()+8), area.bottom()-self.height()-8)
        self.move(x,y); self.show(); self.raise_()
        if seconds>0: QTimer.singleShot(seconds*1000,self.close)
    def mousePressEvent(self,_): self.close()
