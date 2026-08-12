@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3.11 -m venv .buildvenv
call .buildvenv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements-build.txt
pyinstaller --noconfirm --clean Ru-OCR-AOW.spec
powershell -NoProfile -Command "Compress-Archive -Path 'dist\Ru-OCR-AOW\*' -DestinationPath 'dist\Ru-OCR-AOW-Windows-Portable.zip' -Force"
pause
