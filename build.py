import subprocess

from lib.venv_tools import bootstrap_venv, get_venv_python

# activate VENV
bootstrap_venv(install_pyinstaller=True)

# build the .exe
subprocess.run(
    [get_venv_python(), '-m', 'PyInstaller', '.\\downloader.spec'],
)
