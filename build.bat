@echo off
set ver=0.1.1
rem build script for the distributable versions of tadpole
if not exist "venv\" (
    py -m venv venv
)
if not exist "venv\Lib\site-packages\PyInstaller" (
    venv\Scripts\python -m pip install pyinstaller
)
if not exist "venv\Lib\site-packages\PIL" (
    venv\Scripts\python -m pip install Pillow
)
venv\Scripts\python -m PyInstaller --onefile tadpole.py --icon frog.ico
copy README.md "dist\readme.md"
copy LICENSE "dist\license.txt"
copy tadpole.py "dist\tadpole.py"
cd dist
tar -a -cf tadpole-%ver%-win.zip tadpole.exe readme.txt license.txt
tar -a -cf tadpole-%ver%-py.zip tadpole.py readme.txt license.txt
cd ../
