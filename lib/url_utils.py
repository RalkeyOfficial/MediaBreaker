"""
URL parsing and UUID extraction utilities.
"""

import re
from enum import Enum
from functools import total_ordering
from urllib.parse import urljoin, urlparse


def extract_uuid_from_url(url: str) -> str | None:
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


@total_ordering
class MediaDeliveryUrlType(Enum):
    GENERIC  = ("generic", 1)
    PLAYLIST = ("playlist", 2)
    STREAM   = ("stream", 3)

    def __init__(self, label: str, priority: int) -> None:
        self.label = label
        self.priority = priority

    def __str__(self) -> str:
        return self.label

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, MediaDeliveryUrlType):
            return NotImplemented
        return self.priority < other.priority

def get_mediadelivery_url_type(url: str) -> MediaDeliveryUrlType | None:
    """
    returns the type of the url.

    example:
        https://iframe.mediadelivery.net/play/[account_id]/[uuid] -> generic  - 1
        https://vz-f6fedefb-132.b-cdn.net/[uuid]/playlist.m3u8    -> playlist - 2
        https://vz-f6fedefb-132.b-cdn.net/[uuid]/720p/video.m3u8  -> stream   - 3
    """

    u = url.lower()

    if "iframe.mediadelivery.net/play/" in u:
        return MediaDeliveryUrlType.GENERIC

    if u.endswith("/playlist.m3u8"):
        return MediaDeliveryUrlType.PLAYLIST

    if u.endswith("/video.m3u8"):
        return MediaDeliveryUrlType.STREAM

    return None

