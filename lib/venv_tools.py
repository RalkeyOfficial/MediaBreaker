from __future__ import annotations

from pathlib import Path

# get the project root (NON DYNAMIC)
PROJECT_ROOT = Path(__file__).parent.parent


def _activate_venv() -> None:
    """
    Activate virtualenv for current interpreter:

    import runpy
    runpy.run_path(this_file)

    This can be used when you must use an existing Python interpreter, not the virtualenv bin/python.
    """  # noqa: D415

    import os
    import site
    import sys

    venv_dir = PROJECT_ROOT / '.venv'

    # depending on the OS
    if sys.platform == "win32":
        bin_dir = venv_dir / "Scripts"  # str
        site_packages = venv_dir / "Lib" / "site-packages"
        venv_python = bin_dir / "python.exe"
    else:
        bin_dir = venv_dir / "bin"  # str
        pyver = f"python{sys.version_info.major}.{sys.version_info.minor}"
        site_packages = venv_dir / "lib" / pyver / "site-packages"
        venv_python = bin_dir / "python"

    # Optional but useful: fail fast if venv is missing/mis-pointed.
    if not bin_dir.exists():
        raise FileNotFoundError(f"venv bin dir not found: {bin_dir}")
    if not site_packages.exists():
        raise FileNotFoundError(f"venv site-packages not found: {site_packages}")
    if not venv_python.exists():
        raise FileNotFoundError(f"venv python not found: {venv_python}")

    base = os.path.abspath(venv_dir)  # base = venv_dir str

    # prepend bin to PATH (this file is inside the bin directory)
    os.environ["PATH"] = os.pathsep.join([str(bin_dir), *os.environ.get("PATH", "").split(os.pathsep)])
    os.environ["VIRTUAL_ENV"] = base  # virtual env is right above bin directory
    os.environ["VIRTUAL_ENV_PROMPT"] = '' or os.path.basename(base)

    # add the virtual environments libraries to the host python import mechanism
    prev_length = len(sys.path)

    path = os.path.realpath(site_packages)
    site.addsitedir(path.decode("utf-8") if '' else path)

    sys.path[:] = sys.path[prev_length:] + sys.path[0:prev_length]

    sys.real_prefix = sys.prefix
    sys.prefix = base

    # record the venv interpreter path for code that spawns subprocesses.
    # (sys.executable stays the base interpreter.)
    sys._venv_executable = str(venv_python)


def get_venv_python() -> str:
    import sys
    return getattr(sys, "_venv_executable", sys.executable)


def _install_requirements(
        *,
        install_pyinstaller: bool = False,
):
    """
    Install requirements file
    + optional pyinstaller
    """

    import subprocess

    requirements_file = PROJECT_ROOT / 'requirements.txt'

    # Use current Python's pip (which is venv's pip)
    subprocess.run(
        [get_venv_python(), '-m', 'pip', 'install', '-r', str(requirements_file)],
        check=True,
        capture_output=True,
        text=True
    )
    # additionally install pyinstaller
    if install_pyinstaller:
        subprocess.run(
            [get_venv_python(), '-m', 'pip', 'install', 'pyinstaller'],
            check=True,
            capture_output=True,
            text=True
        )


def bootstrap_venv(
        *,
        log = None,
        install_pyinstaller: bool = False,
        is_warmup: bool = False,
):
    """
    Bootstrap virtual environment: check if venv exists, create if needed, activate venv, and install requirements

    `install_pyinstaller: bool` - also installs pyinstaller
    `is_warmup: bool` - just makes the logs prettier 🥰
    """

    import subprocess
    import venv
    import sys
    from lib.log import logging_start_group, logging_end_group

    # Get project root directory (where this script is located)
    venv_path = PROJECT_ROOT / '.venv'
    requirements_file = PROJECT_ROOT / 'requirements.txt'

    # Check if already running in a venv
    in_venv = sys.prefix != sys.base_prefix
    venv_exists = venv_path.exists()

    logging_token = None
    # this is a rather stupid way to have different types of logging, but it is easy to maintain
    if is_warmup and log:
        info_logger = log.info
        error_logger = log.error
        logging_token = logging_start_group("Installing packages:", log)
    else:
        info_logger = print
        error_logger = lambda t: print(f"ERROR: {t}")

    if not in_venv and venv_exists:
        _activate_venv()
        in_venv = sys.prefix != sys.base_prefix

    # If already in venv, ensure requirements are up-to-date and continue
    if in_venv:
        if requirements_file.exists():
            info_logger("Ensuring requirements are installed and up-to-date...")
            try:
                _install_requirements(install_pyinstaller=install_pyinstaller)
                info_logger("Requirements are up-to-date.")
            except subprocess.CalledProcessError as e:
                error_logger(f"Failed to install/update requirements: {e}")
                error_logger(f"pip stderr: {e.stderr}")
                sys.exit(1)

        if logging_token:
            logging_end_group(logging_token)
        return

    # Determine venv paths based on platform
    if sys.platform == 'win32':
        venv_pip = venv_path / 'Scripts' / 'pip.exe'
    else:
        venv_pip = venv_path / 'bin' / 'pip'

    # Create venv if it doesn't exist
    if not venv_path.exists():
        info_logger("Creating virtual environment...")
        try:
            venv.create(venv_path, with_pip=True)
            info_logger("Virtual environment created successfully.")
        except Exception as e:
            error_logger(f"Failed to create virtual environment: {e}")
            sys.exit(1)

    # activate venv after creating venv
    _activate_venv()

    # Verify venv pip exists
    if not venv_pip.exists():
        error_logger(f"Virtual environment pip not found at {venv_pip}")
        sys.exit(1)

    # Always ensure requirements are installed and up-to-date
    # This handles cases where requirements.txt has changed or packages are missing
    if requirements_file.exists():
        info_logger("Installing requirements...")
        try:
            _install_requirements(install_pyinstaller=install_pyinstaller)
            info_logger("Requirements are installed.")
        except subprocess.CalledProcessError as e:
            error_logger(f"Failed to install/update requirements: {e}")
            error_logger(f"pip stderr: {e.stderr}")
            sys.exit(1)

    if logging_token:
        logging_end_group(logging_token)
