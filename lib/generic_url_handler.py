"""
Handle generic URLs (non-m3u8) and extract playlist URLs from HTML.
"""
import requests
import json
import re
from bs4 import BeautifulSoup
from urllib.parse import urlsplit


def is_generic_url(url: str) -> bool:
    """
    Check if URL is a generic URL (no .m3u8 extension).
    Return True if generic, False if direct m3u8 URL.
    """
    return not url.endswith('.m3u8') and '.m3u8' not in url


def fetch_html(url: str) -> str:
    """
    Fetch HTML content from generic URL.
    Handle network errors.
    Return HTML content as string.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Referer': 'https://iframe.mediadelivery.net/'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Failed to fetch HTML: {e}")


def extract_json_ld(html: str) -> dict | None:
    """
    Parse HTML and find <script type="application/ld+json"> tag.
    Extract and parse JSON-LD content.
    Return parsed JSON object or None.
    """
    soup = BeautifulSoup(html, 'html.parser')
    json_ld_scripts = soup.find_all('script', type='application/ld+json')
    
    for script in json_ld_scripts:
        try:
            json_data = json.loads(script.string)
            if isinstance(json_data, dict) and json_data.get('@type') == 'VideoObject':
                return json_data
        except (json.JSONDecodeError, AttributeError):
            continue
    
    return None


def extract_playlist_url_from_json_ld(json_ld: dict) -> str | None:
    """
    Extract thumbnailUrl from JSON-LD VideoObject.
    Replace thumbnail name with playlist.m3u8.
    Return constructed playlist URL.
    """
    thumbnail_url = json_ld.get('thumbnailUrl')
    if not thumbnail_url:
        return None
    
    # Replace thumbnail name with playlist.m3u8 (The thumbnail is not always called "thumbnail.jpg")
    playlist_url_parts = thumbnail_url.split('/')
    playlist_url_parts[-1] = 'playlist.m3u8'
    playlist_url = '/'.join(playlist_url_parts)
    return playlist_url


def extract_video_name_from_json_ld(json_ld: dict) -> str | None:
    """
    Extract name field from JSON-LD VideoObject.
    Clean filename (remove .mp4 extension if present).
    Return video name string.
    """
    name = json_ld.get('name')
    if not name:
        return None

    # split on .
    name_split = name.split('.')

    # if items in split name array is more than 1, remove the last item (which is the prefix)
    if len(name_split) >= 2:
        del name_split[-1]

    name = '.'.join(name_split)
    
    # Sanitize filename for filesystem
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = name.strip()
    
    return name


def extract_account_id_from_generic_url(url: str) -> str | None:
    """
    Extract account id from a mediadelivery embed URL.

    Examples:
      https://iframe.mediadelivery.net/play/165597/uuid -> "165597"
      http://iframe.mediadelivery.net/play/165597/uuid  -> "165597"
      iframe.mediadelivery.net/play/165597/uuid         -> "165597"
      /play/165597/uuid                                 -> "165597"
    """
    if not url:
        return None

    s = url.strip()

    # urlsplit treats "iframe.mediadelivery.net/..." as a *path* unless there's a scheme.
    # Prefixing '//' makes it parse as a netloc+path without committing to http/https.
    parsed = urlsplit(s if "://" in s else ("//" + s if not s.startswith("/") else s))

    host = (parsed.hostname or "").lower()
    path = parsed.path or ""

    # If it's a full URL and not the expected host, bail (avoid extracting garbage).
    if host and host != "iframe.mediadelivery.net":
        return None

    parts = [p for p in path.split("/") if p]  # remove empty segments from '///'
    # Expect: ["play", "<account_id>", "<video_id>...]
    if len(parts) >= 2 and parts[0] == "play":
        account_id = parts[1]
        return account_id if account_id.isdigit() else None

    return None


def extract_video_extension_from_json_ld(json_ld: dict) -> str | None:
    """
    Extract extension from the name field from JSON-LD VideoObject.
    Return extension string or None if it does not exist.
    """
    name = json_ld.get('name')
    if not name:
        return None

    # split on .
    name_split = name.split('.')

    if len(name_split) >= 2:
        return name_split[-1]
    return None


def resolve_generic_url(url: str) -> dict | None:
    """
    Main function: resolve generic URL to m3u8 playlist URL.
    Returns: {playlist_url: str, video_name: str, metadata: dict} or None
    Handles all error cases and returns None on failure.
    """
    try:
        html = fetch_html(url)
    except ValueError as e:
        return None
    
    json_ld = extract_json_ld(html)
    if not json_ld:
        return None
    
    playlist_url = extract_playlist_url_from_json_ld(json_ld)
    video_name = extract_video_name_from_json_ld(json_ld)
    extension = extract_video_extension_from_json_ld(json_ld)
    account_id = extract_account_id_from_generic_url(url)
    
    return {
        'playlist_url': playlist_url,
        'video_name': video_name,
        'extension': extension,
        'account_id': account_id,
        'metadata': json_ld
    }

