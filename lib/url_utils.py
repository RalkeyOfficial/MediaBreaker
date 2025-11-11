"""
URL parsing and UUID extraction utilities.
"""

import re
from urllib.parse import urljoin, urlparse


def extract_uuid_from_url(url: str) -> str:
    """
    Extract UUID from URL path.
    Pattern: /c1b96916-8302-4c83-9e79-312e344bb6c2/
    """
    uuid_pattern = r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'
    match = re.search(uuid_pattern, url, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def get_base_url(url: str) -> str:
    """
    Extract base URL from full URL.
    Return base URL for relative path resolution.
    """
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rsplit('/', 1)[0]}/"


def build_absolute_url(base_url: str, relative_url: str) -> str:
    """
    Convert relative URLs to absolute.
    Handle base URL resolution.
    """
    return urljoin(base_url, relative_url)

