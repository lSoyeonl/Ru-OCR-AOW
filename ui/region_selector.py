from __future__ import annotations
from PyQt6.QtCore import Qt, QRect, pyqtSignal, QPoint
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget, QApplication

class RegionSelector(QWidget):
    selected = pyqtSignal(QRect)
    cancelled = pyqtSignal()
    def __init__(self):
        super().__init__()
        self.start = QPoint(); self.end = QPoint(); self.dragging = False
        screens = QApplication.screens()
        geo = screens[0].geometry()
        for s in screens[1:]: geo = geo.united(s.geometry())
        self.setGeometry(geo)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.show(); self.raise_(); self.activateWindow()

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(5,8,18,115))
        if self.dragging:
            r = QRect(self.start,self.end).normalized()
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear); p.fillRect(r, Qt.GlobalColor.transparent)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            p.setPen(QPen(QColor(230,225,255), 2)); p.drawRect(r)

    def mousePressEvent(self,e):
        if e.button()==Qt.MouseButton.LeftButton:
            self.start=e.position().toPoint(); self.end=self.start; self.dragging=True; self.update()
    def mouseMoveEvent(self,e):
        if self.dragging: self.end=e.position().toPoint(); self.update()
    def mouseReleaseEvent(self,e):
        if e.button()==Qt.MouseButton.LeftButton and self.dragging:
            self.end=e.position().toPoint(); r=QRect(self.start,self.end).normalized(); self.close()
            if r.width()>8 and r.height()>8:
                top_left=self.mapToGlobal(r.topLeft()); self.selected.emit(QRect(top_left,r.size()))
            else: self.cancelled.emit()
    def keyPressEvent(self,e):
        if e.key()==Qt.Key.Key_Escape: self.close(); self.cancelled.emit()
