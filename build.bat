@echo off
rem build script for the distributable versions of frogtool
if not exist "venv\" (
    py -m venv venv
)
if not exist "venv\Lib\site-packages\PyInstaller" (
    venv\Scripts\python -m pip install pyinstaller
)
venv\Scripts\python -m PyInstaller frogtool.py  -F --version-file versioninfo --icon frog.ico
copy README.md "dist\readme.txt"
copy LICENSE "dist\license.txt"
copy frogtool.py "dist\frogtool.py"
cd dist
tar -a -cf frogtool-win.zip frogtool.exe readme.txt license.txt
tar -a -cf frogtool-py.zip frogtool.py readme.txt license.txt
cd ../

