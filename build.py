from __future__ import annotations
import os, platform, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).parent; sep=";" if platform.system()=="Windows" else ":"
environment=os.environ.copy(); environment.setdefault("PYINSTALLER_CONFIG_DIR",str(Path(tempfile.gettempdir())/"jobradar-pyinstaller"))
icon=ROOT/"assets"/("app-icon.ico" if platform.system()=="Windows" else "app-icon.icns")
subprocess.run([sys.executable,"-m","PyInstaller","--noconfirm","--clean","--windowed","--name","JobRadar AI","--icon",str(icon),
    "--add-data",f"{ROOT/'jobradar'/'style.qss'}{sep}jobradar","--add-data",f"{ROOT/'assets'}{sep}assets",str(ROOT/"run.py")],cwd=ROOT,check=True,env=environment)
print(f"Built JobRadar AI for {platform.system()} in {ROOT/'dist'}")
