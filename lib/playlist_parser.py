"""
Parse and validate m3u8 playlists with zstd decompression support.
"""

import requests
import m3u8

try:
    import zstandard as zstd
    ZSTD_AVAILABLE = True
except ImportError:
    ZSTD_AVAILABLE = False


def get_browser_headers():
    """
    Get browser-like headers for playlist requests.
    """
    return {
        'accept': '*/*',
        'accept-encoding': 'gzip, deflate, br, zstd',
        'accept-language': 'en-US,en;q=0.9,nl-NL;q=0.8,nl;q=0.7',
        'cache-control': 'no-cache',
        'dnt': '1',
        'origin': 'https://iframe.mediadelivery.net',
        'pragma': 'no-cache',
        'priority': 'u=1, i',
        'referer': 'https://iframe.mediadelivery.net/',
        'sec-ch-ua': '"Not?A_Brand";v="99", "Chromium";v="130"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'cross-site',
        'sec-gpc': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'
    }


def decompress_zstd(raw_bytes: bytes) -> bytes:
    """
    Decompress zstd-compressed content.
    Check for zstd magic bytes: 0x28 0xB5 0x2F 0xFD
    """
    if len(raw_bytes) < 4 or raw_bytes[:4] != b'\x28\xb5\x2f\xfd':
        return raw_bytes
    
    if not ZSTD_AVAILABLE:
        raise ValueError("zstd compression detected but zstandard library not available")
    
    try:
        dctx = zstd.ZstdDecompressor()
        decompressed = dctx.decompress(raw_bytes, max_output_size=10*1024*1024)  # 10MB max
        return decompressed
    except Exception as e:
        try:
            dctx = zstd.ZstdDecompressor()
            decompressed = bytearray()
            with dctx.stream_reader(raw_bytes) as reader:
                while True:
                    chunk = reader.read(8192)
                    if not chunk:
                        break
                    decompressed.extend(chunk)
            return bytes(decompressed)
        except Exception as e2:
            raise ValueError(f"Failed to decompress zstd content: {e}, stream failed: {e2}")


def parse_playlist(url: str) -> m3u8.Playlist:
    """
    Fetch playlist (handle zstd decompression) and parse with m3u8 library.
    """
    headers = get_browser_headers()
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    
    # Disable automatic encoding to get raw bytes
    response.encoding = None
    raw_bytes = response.content
    
    # Decompress if zstd-compressed
    try:
        decompressed = decompress_zstd(raw_bytes)
        content = decompressed.decode('utf-8')
    except (ValueError, UnicodeDecodeError):
        # Not zstd-compressed or decompression failed, try regular decoding
        content = raw_bytes.decode('utf-8')
    
    # Parse with m3u8 library
    playlist = m3u8.loads(content, uri=url)
    return playlist


def validate_playlist(playlist: m3u8.Playlist) -> bool:
    """
    Check if playlist is valid.
    Verify required tags exist.
    """
    if playlist is None:
        return False
    
    if not playlist.segments and not playlist.playlists:
        return False
    
    return True


def get_playlist_type(playlist: m3u8.Playlist) -> str:
    """
    Return 'master' or 'media'.
    Determine playlist type.
    """
    if playlist.is_variant:
        return 'master'
    return 'media'

