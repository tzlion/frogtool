@echo off
set ver=0.3.0
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
if not exist "venv\Lib\site-packages\PyQt5" (
    venv\Scripts\python -m pip install PyQt5
)
pyinstaller.exe tadpole.py --onefile -F --icon frog.ico --clean --noconsole --version-file versioninfo --add-data="frog.ico;."
copy README.md "dist\readme.md"
copy LICENSE "dist\license.txt"
copy tadpole.py "dist\tadpole.py"
copy frogtool.py "dist\frogtool.py"
copy tadpole_functions.py "dist\tadpole_functions.py"
cd dist
tar -a -cf tadpole-%ver%-win.zip tadpole.exe "readme.md" license.txt
tar -a -cf tadpole-%ver%-py.zip tadpole.py frogtool.py tadpole_functions.py "readme.md" license.txt
cd ../
