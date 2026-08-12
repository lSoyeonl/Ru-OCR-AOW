# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas=[('assets','assets'),('data','data'),('license','license')]
binaries=[]; hiddenimports=[]
for package in ['PyQt6','paddleocr','paddlex','paddle','openai','mss','keyboard','cryptography']:
    try:
        d,b,h=collect_all(package); datas+=d; binaries+=b; hiddenimports+=h
    except Exception: pass

a=Analysis(['main.py'],pathex=[],binaries=binaries,datas=datas,hiddenimports=hiddenimports,hookspath=[],hooksconfig={},runtime_hooks=[],excludes=[],noarchive=False,optimize=0)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='Ru-OCR-AOW',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False,disable_windowed_traceback=False)
coll=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,upx_exclude=[],name='Ru-OCR-AOW')
