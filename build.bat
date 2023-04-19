py -m venv venv
venv\Scripts\python -m pip install pyinstaller
venv\Scripts\python -m PyInstaller frogtool.py  -F --version-file versioninfo --icon frog.ico
