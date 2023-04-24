@echo off
set ver=0.2.0
rem build script for the distributable versions of frogtool
if not exist "venv\" (
    py -m venv venv
)
if not exist "venv\Lib\site-packages\PyInstaller" (
    venv\Scripts\python -m pip install pyinstaller
)
if not exist "venv\Lib\site-packages\PIL" (
    venv\Scripts\python -m pip install Pillow
)
venv\Scripts\python -m PyInstaller frogtool.py  -F --version-file versioninfo --icon frog.ico
copy README.md "dist\readme.md"
rem extremely dirty markdown to txt conversion by stripping out a few non-obvious characters
py -c "open('dist/readme.txt','w').write(open('dist/readme.md','r').read().replace('`','').replace('### ',''))"
copy LICENSE "dist\license.txt"
copy frogtool.py "dist\frogtool.py"
cd dist
tar -a -cf frogtool-%ver%-win.zip frogtool.exe readme.txt license.txt
tar -a -cf frogtool-%ver%-py.zip frogtool.py readme.txt license.txt
cd ../
