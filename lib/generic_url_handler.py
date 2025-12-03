"""
Handle generic URLs (non-m3u8) and extract playlist URLs from HTML.
"""

import requests
import json
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin


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


def extract_json_ld(html: str) -> dict:
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


def extract_playlist_url_from_json_ld(json_ld: dict) -> str:
    """
    Extract thumbnailUrl from JSON-LD VideoObject.
    Replace thumbnail.jpg with playlist.m3u8.
    Return constructed playlist URL.
    """
    thumbnail_url = json_ld.get('thumbnailUrl')
    if not thumbnail_url:
        return None
    
    # Replace thumbnail.jpg with playlist.m3u8 (The thumbnail is not always called "thumbnail.jpg")
    playlist_url_parts = thumbnail_url.split('/')
    playlist_url_parts[-1] = 'playlist.m3u8'
    playlist_url = '/'.join(playlist_url_parts)
    return playlist_url


def extract_video_name_from_json_ld(json_ld: dict) -> str:
    """
    Extract name field from JSON-LD VideoObject.
    Clean filename (remove .mp4 extension if present).
    Return video name string.
    """
    name = json_ld.get('name')
    if not name:
        return None
    
    # Remove .mp4 extension if present
    if name.endswith('.mp4'):
        name = name[:-4]
    
    # Sanitize filename for filesystem
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    name = name.strip()
    
    return name


def resolve_generic_url(url: str) -> dict:
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
    if not playlist_url:
        return None
    
    video_name = extract_video_name_from_json_ld(json_ld)
    
    return {
        'playlist_url': playlist_url,
        'video_name': video_name,
        'metadata': json_ld
    }

