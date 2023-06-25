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
pyinstaller.exe --onefile -F tadpole.py --icon frog.ico --clean --noconsole --version-file versioninfo
copy README.md "dist\readme.md"
copy LICENSE "dist\license.txt"
copy tadpole.py "dist\tadpole.py"
copy frogtool.py "dist\frogtool.py"
copy tadpole_functions.py "dist\tadpole_functions.py"
cd dist
tar -a -cf tadpole-%ver%-win.zip tadpole.exe readme.txt license.txt
tar -a -cf tadpole-%ver%-py.zip tadpole.py frogtool.py tadpole_functions.py readme.txt license.txt
cd ../
