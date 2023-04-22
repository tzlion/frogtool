@echo off
rem build script for the windows executable version of frogtool
if not exist "venv\" (
    py -m venv venv
)
if not exist "venv\Lib\site-packages\PyInstaller" (
    venv\Scripts\python -m pip install pyinstaller
)
venv\Scripts\python -m PyInstaller frogtool.py  -F --version-file versioninfo --icon frog.ico
copy README.md "dist\readme.txt"
copy LICENSE "dist\license.txt"
