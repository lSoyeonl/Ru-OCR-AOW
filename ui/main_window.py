from __future__ import annotations
import json, threading, webbrowser
from pathlib import Path
from PIL import Image
from PIL.ImageQt import ImageQt
from mss import mss
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QTimer, QRect, QPoint, QSize
from PyQt6.QtGui import QPixmap, QIcon, QCursor, QAction
from PyQt6.QtWidgets import (
    QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QLabel,QPushButton,QComboBox,
    QStackedWidget,QPlainTextEdit,QLineEdit,QFormLayout,QSpinBox,QCheckBox,QMessageBox,QFrame,QSystemTrayIcon,QMenu
)
from config import save_settings
from runtime_paths import resource_path, GLOSSARY_PATH, ensure_default_glossary
from services.license_service import current_license, get_device_code
from ui.region_selector import RegionSelector
from ui.overlay import TranslationOverlay

LANGS=["Китайский (упрощ.)","Китайский (традиц.)","Тайский","Вьетнамский","Английский","Авто"]

class Signals(QObject):
    hotkey=pyqtSignal(str); result=pyqtSignal(object); ocr_result=pyqtSignal(object); failure=pyqtSignal(str); manual_result=pyqtSignal(str); hover_result=pyqtSignal(str,str,QPoint); progress=pyqtSignal(str)

class MainWindow(QMainWindow):
    def __init__(self, settings, ocr, translator):
        super().__init__(); self.settings=settings; self.ocr=ocr; self.translator=translator
        self.signals=Signals(); self.signals.hotkey.connect(self.handle_hotkey); self.signals.result.connect(self.on_result); self.signals.ocr_result.connect(self.on_ocr_result); self.signals.failure.connect(self.on_error); self.signals.manual_result.connect(self.on_manual_result); self.signals.hover_result.connect(self.on_hover_result); self.signals.progress.connect(self.on_progress)
        self.selector=None; self.pending_action=None; self.busy=False; self.hover_busy=False; self.hover_enabled=False; self.last_hover_text=""; self.force_exit=False
        self.setWindowTitle("Ru - OCR AOW"); self.resize(470,690); self.setMinimumSize(440,640)
        self.setWindowIcon(QIcon(str(resource_path("assets/person.webp"))))
        self.build_ui(); self.build_tray(); self.install_hotkeys()
        self.hover_timer=QTimer(self); self.hover_timer.timeout.connect(self.hover_tick); self.hover_timer.start(int(self.settings.get("hover_interval_ms",1300))); QTimer.singleShot(700,self.warmup_ocr)

    def build_ui(self):
        self.setStyleSheet("""
        QMainWindow,QWidget{background:#eeeeff;color:#33334d;font-family:"Segoe UI";} QLabel{background:transparent;}
        QPushButton{background:#726daa;color:white;border:0;border-radius:9px;padding:9px 12px;font-weight:600;} QPushButton:hover{background:#625d9b;}
        QPushButton#nav{background:transparent;color:#58547f;text-align:left;padding:9px;} QPushButton#nav:hover{background:rgba(116,109,170,35);} 
        QComboBox,QLineEdit,QPlainTextEdit,QSpinBox{background:white;border:1px solid #c4c1df;border-radius:7px;padding:6px;color:#2e2d45;}
        QFrame#card{background:rgba(255,255,255,205);border:1px solid rgba(169,164,208,130);border-radius:12px;}
        """)
        central=QWidget(); self.setCentralWidget(central); outer=QHBoxLayout(central); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)
        nav=QFrame(); nav.setFixedWidth(108); nav.setStyleSheet("QFrame{background:#e2e1f7;border-right:1px solid #c8c5e2;}"); nv=QVBoxLayout(nav); nv.setContentsMargins(8,14,8,10)
        logo=QLabel("Ru - OCR\nAOW"); logo.setAlignment(Qt.AlignmentFlag.AlignCenter); logo.setStyleSheet("font-size:16px;font-weight:800;color:#5e5995;padding:8px;"); nv.addWidget(logo)
        self.pages=QStackedWidget()
        labels=[("Главная",0),("Перевод",1),("Настройки",2),("О программе",3)]
        for text,idx in labels:
            b=QPushButton(text); b.setObjectName("nav"); b.clicked.connect(lambda _,i=idx:self.pages.setCurrentIndex(i)); nv.addWidget(b)
        nv.addStretch(); self.hover_badge=QLabel("Наведение: выкл"); self.hover_badge.setAlignment(Qt.AlignmentFlag.AlignCenter); self.hover_badge.setStyleSheet("color:#777398;font-size:10px;"); nv.addWidget(self.hover_badge)
        outer.addWidget(nav); outer.addWidget(self.pages,1)
        self.pages.addWidget(self.home_page()); self.pages.addWidget(self.translate_page()); self.pages.addWidget(self.settings_page()); self.pages.addWidget(self.about_page())

    def home_page(self):
        w=QWidget(); lay=QVBoxLayout(w); lay.setContentsMargins(14,14,14,14); lay.setSpacing(10)
        hero=QFrame(); hero.setObjectName("card"); hero.setMinimumHeight(210); hv=QHBoxLayout(hero); hv.setContentsMargins(16,10,6,0)
        left=QVBoxLayout(); title=QLabel("Ru - OCR AOW"); title.setStyleSheet("font-size:26px;font-weight:800;color:#514c88;"); left.addWidget(title)
        sub=QLabel("OCR + перевод игрового текста\nна русский через DeepSeek"); sub.setStyleSheet("color:#686486;font-size:12px;"); left.addWidget(sub); left.addStretch(); hv.addLayout(left,1)
        person=QLabel(); pix=QPixmap(str(resource_path("assets/person.webp"))); person.setPixmap(pix.scaled(155,190,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)); person.setAlignment(Qt.AlignmentFlag.AlignBottom|Qt.AlignmentFlag.AlignRight); hv.addWidget(person)
        lay.addWidget(hero)
        langrow=QHBoxLayout(); langrow.addWidget(QLabel("Язык текста:")); self.lang=QComboBox(); self.lang.addItems(LANGS); self.lang.setCurrentText(self.settings.get("source_language",LANGS[0])); self.lang.currentTextChanged.connect(self.quick_save_language); langrow.addWidget(self.lang,1); lay.addLayout(langrow)
        grid=QGridLayout(); grid.setSpacing(9)
        actions=[("Перевод по области","F8",self.select_translate),("Перевод при наведении","F9",self.toggle_hover),("Копировать область","F10",self.select_copy),("Перевод внутри программы","",lambda:self.pages.setCurrentIndex(1))]
        for i,(name,key,fn) in enumerate(actions):
            b=QPushButton((name+(f"\n{key}" if key else ""))); b.setMinimumHeight(62); b.clicked.connect(fn); grid.addWidget(b,i//2,i%2)
        lay.addLayout(grid)
        statuscard=QFrame(); statuscard.setObjectName("card"); sv=QVBoxLayout(statuscard); sv.setContentsMargins(11,8,11,8); self.status=QLabel("Готово. Выберите действие."); self.status.setWordWrap(True); sv.addWidget(self.status); lay.addWidget(statuscard); lay.addStretch(); return w

    def translate_page(self):
        w=QWidget(); lay=QVBoxLayout(w); lay.setContentsMargins(16,16,16,16); lay.addWidget(self.page_title("Перевод внутри приложения"))
        self.manual_input=QPlainTextEdit(); self.manual_input.setPlaceholderText("Вставьте китайский, тайский, вьетнамский или английский текст..."); lay.addWidget(QLabel("Исходный текст")); lay.addWidget(self.manual_input,1)
        b=QPushButton("Перевести через DeepSeek"); b.clicked.connect(self.manual_translate); lay.addWidget(b)
        lay.addWidget(QLabel("Русский перевод")); self.manual_output=QPlainTextEdit(); self.manual_output.setReadOnly(True); lay.addWidget(self.manual_output,1); return w

    def settings_page(self):
        w=QWidget(); lay=QVBoxLayout(w); lay.setContentsMargins(16,16,16,16); lay.addWidget(self.page_title("Настройки")); form=QFormLayout()
        self.s_lang=QComboBox(); self.s_lang.addItems(LANGS); self.s_lang.setCurrentText(self.settings.get("source_language",LANGS[0])); form.addRow("Язык OCR",self.s_lang)
        self.api=QLineEdit(self.settings.get("deepseek_api_key","")); self.api.setEchoMode(QLineEdit.EchoMode.Password); form.addRow("DeepSeek API key",self.api)
        self.model=QComboBox(); self.model.addItems(["deepseek-v4-flash","deepseek-v4-pro"]); self.model.setCurrentText(self.settings.get("deepseek_model","deepseek-v4-flash")); form.addRow("Модель",self.model)
        self.interval=QSpinBox(); self.interval.setRange(700,5000); self.interval.setSingleStep(100); self.interval.setValue(int(self.settings.get("hover_interval_ms",1300))); self.interval.setSuffix(" мс"); form.addRow("Наведение: интервал",self.interval)
        self.hw=QSpinBox(); self.hw.setRange(250,1000); self.hw.setValue(int(self.settings.get("hover_width",560))); form.addRow("Наведение: ширина",self.hw)
        self.hh=QSpinBox(); self.hh.setRange(80,500); self.hh.setValue(int(self.settings.get("hover_height",190))); form.addRow("Наведение: высота",self.hh)
        self.author=QLineEdit(self.settings.get("author","Укажите автора")); form.addRow("Автор",self.author)
        self.author_url=QLineEdit(self.settings.get("author_url","https://example.com")); form.addRow("Ссылка",self.author_url)
        lay.addLayout(form); save=QPushButton("Сохранить настройки"); save.clicked.connect(self.save_settings_ui); lay.addWidget(save)
        self.license_label=QLabel(); self.refresh_license_label(); self.license_label.setWordWrap(True); lay.addWidget(self.license_label); lay.addStretch(); return w

    def about_page(self):
        w=QWidget(); lay=QVBoxLayout(w); lay.setContentsMargins(16,16,16,16); lay.addWidget(self.page_title("О программе")); ch=QLabel(); pix=QPixmap(str(resource_path("assets/character_blue.png"))); ch.setPixmap(pix.scaled(300,260,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)); ch.setAlignment(Qt.AlignmentFlag.AlignCenter); lay.addWidget(ch)
        text=QLabel("Ru - OCR AOW\nПереводчик интерфейса и текста Age of Wushu\n\nАвтор: "+self.settings.get("author","Укажите автора")); text.setAlignment(Qt.AlignmentFlag.AlignCenter); text.setWordWrap(True); lay.addWidget(text)
        link=QPushButton("Открыть ссылку автора"); link.clicked.connect(lambda:webbrowser.open(self.settings.get("author_url","https://example.com"))); lay.addWidget(link); lay.addStretch(); return w

    def page_title(self,text):
        l=QLabel(text); l.setStyleSheet("font-size:21px;font-weight:800;color:#514c88;margin-bottom:8px;"); return l

    def build_tray(self):
        self.tray=QSystemTrayIcon(self.windowIcon(),self); menu=QMenu(); show=QAction("Открыть Ru - OCR AOW",self); show.triggered.connect(self.showNormal); area=QAction("Перевести область (F8)",self); area.triggered.connect(self.select_translate); hover=QAction("Вкл/выкл наведение (F9)",self); hover.triggered.connect(self.toggle_hover); quit_a=QAction("Выход",self); quit_a.triggered.connect(self.exit_app); [menu.addAction(a) for a in [show,area,hover,quit_a]]; self.tray.setContextMenu(menu); self.tray.activated.connect(lambda reason:self.showNormal() if reason==QSystemTrayIcon.ActivationReason.Trigger else None); self.tray.show()

    def install_hotkeys(self):
        try:
            import keyboard; keyboard.unhook_all_hotkeys()
            keyboard.add_hotkey(self.settings.get("global_hotkey_area","f8"),lambda:self.signals.hotkey.emit("translate"))
            keyboard.add_hotkey(self.settings.get("global_hotkey_hover","f9"),lambda:self.signals.hotkey.emit("hover"))
            keyboard.add_hotkey(self.settings.get("global_hotkey_copy","f10"),lambda:self.signals.hotkey.emit("copy"))
        except Exception as e: self.status.setText(f"Глобальные клавиши недоступны: {e}")

    def handle_hotkey(self,action):
        if action=="translate": self.select_translate()
        elif action=="hover": self.toggle_hover()
        elif action=="copy": self.select_copy()

    def quick_save_language(self,text):
        self.settings["source_language"]=text; save_settings(self.settings); QTimer.singleShot(100,self.warmup_ocr)

    def select_translate(self): self.start_selector("translate")
    def select_copy(self): self.start_selector("copy")
    def start_selector(self,action):
        if self.busy: return
        self.pending_action=action; self.hide(); self.selector=RegionSelector(); self.selector.selected.connect(self.region_selected); self.selector.cancelled.connect(lambda:self.showNormal())

    def region_selected(self, rect: QRect):
        QTimer.singleShot(150,lambda:self.process_region(rect))

    def capture(self,rect: QRect) -> Image.Image:
        with mss() as sct:
            shot=sct.grab({"left":rect.x(),"top":rect.y(),"width":rect.width(),"height":rect.height()})
            return Image.frombytes("RGB",shot.size,shot.rgb)

    def process_region(self, rect):
        self.showNormal(); image=self.capture(rect)
        if self.pending_action=="copy":
            QApplication.clipboard().setImage(ImageQt(image)); self.status.setText("Выделенная область скопирована как изображение."); return
        self.busy=True; self.status.setText("Распознаю текст…")
        lang=self.settings.get("source_language",self.lang.currentText())
        def work():
            try:
                text,det,conf=self.ocr.recognize(image,lang,lambda m:self.signals.progress.emit(m))
                if not text:
                    raise RuntimeError("Текст не найден. Попробуйте выделить область плотнее.")

                # Show OCR result immediately. DeepSeek must never make the user
                # think OCR itself has frozen.
                self.signals.ocr_result.emit((text,det,conf,rect))

                if not (self.settings.get("deepseek_api_key") or "").strip():
                    self.signals.result.emit((
                        text,
                        "OCR выполнен. Для русского перевода укажите DeepSeek API key в «Настройки».",
                        det,conf,rect
                    ))
                    return

                self.signals.progress.emit("OCR готов. Перевожу через DeepSeek…")
                trans=self.translator.translate(text,det,self.settings)
                self.signals.result.emit((text,trans,det,conf,rect))
            except Exception as e:
                self.signals.failure.emit(str(e))
        threading.Thread(target=work,daemon=True).start()

    def on_progress(self, text):
        self.status.setText(text)

    def warmup_ocr(self):
        lang=self.settings.get("source_language",self.lang.currentText())
        if lang=="Авто":
            return
        def work():
            try:
                self.ocr.warmup(lang,lambda m:self.signals.progress.emit(m))
                self.signals.progress.emit("OCR готов. Можно выделять текст.")
            except Exception as e:
                self.signals.progress.emit("OCR не подготовлен: "+str(e))
        threading.Thread(target=work,daemon=True).start()

    def on_ocr_result(self,data):
        text,det,conf,rect=data
        self.status.setText(f"OCR готов • {det} ~{conf:.0%}. Подготавливаю перевод…")

    def on_result(self,data):
        self.busy=False; text,trans,det,conf,rect=data; self.status.setText(f"Готово • OCR {det} ~{conf:.0%}"); TranslationOverlay(text,trans,int(self.settings.get("overlay_seconds",10)),rect.bottomRight()+QPoint(10,10),self.settings.get("show_source_in_overlay",True))
    def on_error(self,msg): self.busy=False; self.hover_busy=False; self.status.setText("Ошибка: "+msg); QMessageBox.warning(self,"Ru - OCR AOW",msg)

    def toggle_hover(self):
        self.hover_enabled=not self.hover_enabled; self.hover_badge.setText("Наведение: ВКЛ" if self.hover_enabled else "Наведение: выкл"); self.hover_badge.setStyleSheet("color:#3e7c55;font-size:10px;font-weight:700;" if self.hover_enabled else "color:#777398;font-size:10px;"); self.status.setText("Перевод при наведении включён." if self.hover_enabled else "Перевод при наведении выключен.")

    def hover_tick(self):
        if not self.hover_enabled or self.hover_busy or self.busy: return
        pos=QCursor.pos()
        if self.isVisible() and self.frameGeometry().contains(pos): return
        w=int(self.settings.get("hover_width",560)); h=int(self.settings.get("hover_height",190)); rect=QRect(pos.x()-w//2,pos.y()-h//2,w,h); self.hover_busy=True
        lang=self.settings.get("source_language",self.lang.currentText())
        def work():
            try:
                image=self.capture(rect); text,det,conf=self.ocr.recognize(image,lang)
                text=text.strip()
                if len(text)<2 or text==self.last_hover_text: self.hover_busy=False; return
                self.last_hover_text=text; trans=self.translator.translate(text,det,self.settings); self.signals.hover_result.emit(text,trans,pos)
            except Exception: self.hover_busy=False
        threading.Thread(target=work,daemon=True).start()
    def on_hover_result(self,text,trans,pos): self.hover_busy=False; TranslationOverlay(text,trans,5,pos+QPoint(20,20),False)

    def manual_translate(self):
        text=self.manual_input.toPlainText().strip()
        if not text:
            return
        if not (self.settings.get("deepseek_api_key") or "").strip():
            self.manual_output.setPlainText(
                "DeepSeek пока не настроен. Откройте «Настройки», вставьте API key и нажмите «Сохранить настройки»."
            )
            return
        self.manual_output.setPlainText("Перевожу через DeepSeek…")
        lang_map={"Китайский (упрощ.)":"ch","Китайский (традиц.)":"chinese_cht","Тайский":"th","Вьетнамский":"vi","Английский":"en","Авто":"auto"}
        src=lang_map.get(self.settings.get("source_language"),"auto")
        def work():
            try:
                self.signals.manual_result.emit(self.translator.translate(text,src,self.settings,True))
            except Exception as e:
                self.signals.manual_result.emit("Ошибка DeepSeek: "+str(e))
        threading.Thread(target=work,daemon=True).start()
    def on_manual_result(self,text): self.manual_output.setPlainText(text)

    def save_settings_ui(self):
        self.settings.update({"source_language":self.s_lang.currentText(),"deepseek_api_key":self.api.text().strip(),"deepseek_model":self.model.currentText(),"hover_interval_ms":self.interval.value(),"hover_width":self.hw.value(),"hover_height":self.hh.value(),"author":self.author.text().strip() or "Укажите автора","author_url":self.author_url.text().strip() or "https://example.com"}); save_settings(self.settings); self.lang.setCurrentText(self.settings["source_language"]); self.hover_timer.setInterval(self.settings["hover_interval_ms"]); self.status.setText("Настройки сохранены.")

    def refresh_license_label(self):
        ok,msg,p=current_license(); extra=f" Владелец: {p.get('name','—')}" if ok else f" Код устройства: {get_device_code()}"; self.license_label.setText(("✓ " if ok else "⚠ ")+msg+extra)
    def closeEvent(self,e):
        if self.force_exit: e.accept(); return
        e.ignore(); self.hide(); self.tray.showMessage("Ru - OCR AOW","Программа продолжает работать в трее.",QSystemTrayIcon.MessageIcon.Information,1800)
    def exit_app(self):
        self.force_exit=True
        try:
            import keyboard; keyboard.unhook_all_hotkeys()
        except Exception: pass
        QApplication.quit()
