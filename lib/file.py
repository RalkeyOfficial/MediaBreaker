"""
Handle file based functions
"""

import hashlib
import os
from pathlib import Path


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for filesystem use.
    """
    import re
    # Remove or replace invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = filename.strip()
    # Remove leading/trailing dots and spaces
    filename = filename.strip('. ')
    return filename


def check_if_file_exists(path: str) -> bool:
    my_file = Path(path)
    return my_file.is_file()


def sha256_file(path: str) -> str:
    file = Path(path)
    h = hashlib.sha256()
    with file.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def get_file_bytes(path: str) -> int:
    file = Path(path)
    return os.path.getsize(file)
