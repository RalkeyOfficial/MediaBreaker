#!/usr/bin/env python3
"""
Script to fetch and display m3u8 playlist content with browser-like headers.
"""

import requests
from urllib.parse import urljoin, urlparse
import binascii
import sys

try:
    import zstandard as zstd
    ZSTD_AVAILABLE = True
except ImportError:
    ZSTD_AVAILABLE = False


def fetch_m3u8_playlist(url):
    """
    Fetch m3u8 playlist with browser-like headers to mimic a valid browser session.
    """
    headers = {
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
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        # Disable automatic encoding to get raw bytes
        response.encoding = None
        return response
    except requests.exceptions.RequestException as e:
        print(f"Error fetching playlist: {e}")
        return None


def safe_print(text):
    """
    Safely print text that may contain non-printable characters.
    """
    try:
        print(text)
    except UnicodeEncodeError:
        # Fallback: encode with errors='replace' or use repr for problematic strings
        try:
            print(text.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))
        except (UnicodeEncodeError, AttributeError):
            print(repr(text))


def decompress_content(raw_bytes):
    """
    Detect and decompress content if it's compressed with zstd.
    Returns (decompressed_bytes, compression_info)
    """
    # Check for zstd magic bytes: 0x28 0xB5 0x2F 0xFD
    if len(raw_bytes) >= 4 and raw_bytes[:4] == b'\x28\xb5\x2f\xfd':
        if not ZSTD_AVAILABLE:
            return raw_bytes, 'zstd (library not available)'
        try:
            dctx = zstd.ZstdDecompressor()
            # Use decompress_stream for cases where content size isn't known
            decompressed = dctx.decompress(raw_bytes, max_output_size=1024*1024)  # 1MB max
            return decompressed, 'zstd (decompressed)'
        except Exception as e:
            # Try alternative method with streaming
            try:
                dctx = zstd.ZstdDecompressor()
                decompressed = bytearray()
                with dctx.stream_reader(raw_bytes) as reader:
                    while True:
                        chunk = reader.read(8192)
                        if not chunk:
                            break
                        decompressed.extend(chunk)
                return bytes(decompressed), 'zstd (decompressed via stream)'
            except Exception as e2:
                return raw_bytes, f'zstd (decompression failed: {e}, stream failed: {e2})'
    
    return raw_bytes, 'none'


def decode_content(raw_bytes):
    """
    Try to decode content with multiple encodings, fallback to raw bytes.
    """
    encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1', 'utf-16', 'utf-16le', 'utf-16be']
    
    for encoding in encodings:
        try:
            decoded = raw_bytes.decode(encoding)
            return decoded, encoding
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    # Fallback: use latin-1 which can decode any byte sequence
    return raw_bytes.decode('latin-1', errors='replace'), 'latin-1 (fallback)'


def parse_m3u8_content(content, base_url):
    """
    Parse m3u8 content and extract relevant information.
    """
    lines = content.strip().split('\n')
    parsed_data = {
        'playlist_type': None,
        'version': None,
        'target_duration': None,
        'media_sequence': None,
        'segments': [],
        'playlists': [],
        'tags': []
    }
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if not line or line.startswith('#'):
            if line.startswith('#EXTM3U'):
                parsed_data['playlist_type'] = 'Master' if '#EXT-X-STREAM-INF' in content else 'Media'
            elif line.startswith('#EXT-X-VERSION:'):
                parsed_data['version'] = line.split(':')[1]
            elif line.startswith('#EXT-X-TARGETDURATION:'):
                parsed_data['target_duration'] = line.split(':')[1]
            elif line.startswith('#EXT-X-MEDIA-SEQUENCE:'):
                parsed_data['media_sequence'] = line.split(':')[1]
            elif line.startswith('#EXT-X-STREAM-INF:'):
                # Master playlist variant
                if i + 1 < len(lines):
                    variant_url = lines[i + 1].strip()
                    if variant_url and not variant_url.startswith('#'):
                        parsed_data['playlists'].append({
                            'info': line,
                            'url': urljoin(base_url, variant_url)
                        })
                        i += 1
            elif line.startswith('#EXTINF:'):
                # Media segment
                if i + 1 < len(lines):
                    segment_url = lines[i + 1].strip()
                    if segment_url and not segment_url.startswith('#'):
                        parsed_data['segments'].append({
                            'info': line,
                            'url': urljoin(base_url, segment_url)
                        })
                        i += 1
            else:
                parsed_data['tags'].append(line)
        elif not line.startswith('#'):
            # URL line without preceding tag
            if i > 0 and not lines[i - 1].strip().startswith('#'):
                parsed_data['segments'].append({
                    'info': 'Direct URL',
                    'url': urljoin(base_url, line)
                })
        
        i += 1
    
    return parsed_data


def display_results(response, parsed_data, decoded_text, encoding_used, decompressed_bytes=None):
    """
    Display the relevant results from the m3u8 call.
    """
    print("=" * 80)
    print("M3U8 PLAYLIST RESULTS")
    print("=" * 80)
    print()
    
    # Response information
    print("HTTP Response:")
    print(f"  Status Code: {response.status_code}")
    print(f"  Content-Type: {response.headers.get('Content-Type', 'N/A')}")
    print(f"  Content-Length (compressed): {len(response.content)} bytes")
    if decompressed_bytes and len(decompressed_bytes) != len(response.content):
        print(f"  Content-Length (decompressed): {len(decompressed_bytes)} bytes")
    print(f"  Content-Encoding: {response.headers.get('Content-Encoding', 'N/A')}")
    print(f"  Compression: {parsed_data.get('compression_info', 'N/A')}")
    print(f"  Text Encoding Used: {encoding_used}")
    print()
    
    # Playlist information
    print("Playlist Information:")
    print(f"  Type: {parsed_data['playlist_type'] or 'Unknown'}")
    if parsed_data['version']:
        print(f"  Version: {parsed_data['version']}")
    if parsed_data['target_duration']:
        print(f"  Target Duration: {parsed_data['target_duration']} seconds")
    if parsed_data['media_sequence']:
        print(f"  Media Sequence: {parsed_data['media_sequence']}")
    print()
    
    # Master playlist variants
    if parsed_data['playlists']:
        print(f"Stream Variants ({len(parsed_data['playlists'])}):")
        for idx, playlist in enumerate(parsed_data['playlists'], 1):
            safe_print(f"  [{idx}] {playlist['info']}")
            safe_print(f"      URL: {playlist['url']}")
        print()
    
    # Media segments
    if parsed_data['segments']:
        print(f"Media Segments ({len(parsed_data['segments'])}):")
        for idx, segment in enumerate(parsed_data['segments'][:10], 1):  # Show first 10
            safe_print(f"  [{idx}] {segment['info']}")
            safe_print(f"      URL: {segment['url']}")
        if len(parsed_data['segments']) > 10:
            print(f"  ... and {len(parsed_data['segments']) - 10} more segments")
        print()
    
    # Other tags
    if parsed_data['tags']:
        print("Other Tags:")
        for tag in parsed_data['tags'][:20]:  # Show first 20 tags
            safe_print(f"  {tag}")
        if len(parsed_data['tags']) > 20:
            print(f"  ... and {len(parsed_data['tags']) - 20} more tags")
        print()
    
    # Raw bytes hex dump (decompressed if available)
    bytes_to_dump = decompressed_bytes if decompressed_bytes else response.content
    print("Raw Bytes (Hex Dump - Decompressed Content, first 512 bytes):")
    print("-" * 80)
    hex_dump = binascii.hexlify(bytes_to_dump[:512]).decode('ascii')
    for i in range(0, len(hex_dump), 64):
        hex_line = hex_dump[i:i+64]
        formatted_hex = ' '.join(hex_line[j:j+2] for j in range(0, len(hex_line), 2))
        ascii_repr = ''.join(chr(int(hex_line[k:k+2], 16)) if 32 <= int(hex_line[k:k+2], 16) <= 126 else '.' 
                            for k in range(0, len(hex_line), 2))
        print(f"  {i//2:04x}: {formatted_hex:<48} |{ascii_repr}|")
    if len(bytes_to_dump) > 512:
        print(f"  ... ({len(bytes_to_dump) - 512} more bytes)")
    print()
    
    # Raw content as text
    print("Raw Content (Decoded Text - Full):")
    print("-" * 80)
    safe_print(decoded_text)
    print()
    
    # Raw content preview (first 500 chars)
    print("Raw Content Preview (first 500 characters):")
    print("-" * 80)
    safe_print(decoded_text[:500])
    if len(decoded_text) > 500:
        print(f"\n... ({len(decoded_text) - 500} more characters)")
    print()
    
    # Raw bytes representation (decompressed if available)
    bytes_to_repr = decompressed_bytes if decompressed_bytes else response.content
    print("Raw Bytes (Python repr - Decompressed Content, first 200 bytes):")
    print("-" * 80)
    print(repr(bytes_to_repr[:200]))
    if len(bytes_to_repr) > 200:
        print(f"... ({len(bytes_to_repr) - 200} more bytes)")
    print()
    
    # Show decompressed m3u8 content in readable format
    print("=" * 80)
    print("DECOMPRESSED M3U8 CONTENT")
    print("=" * 80)
    print()
    safe_print(decoded_text)
    print()


def main():
    """
    Main function to fetch and display m3u8 playlist.
    """
    # Set UTF-8 encoding for stdout on Windows
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except (AttributeError, ValueError):
            pass
    
    url = ""
    
    print(f"Fetching m3u8 playlist from: {url}")
    print()
    
    response = fetch_m3u8_playlist(url)
    
    if response is None:
        print("Failed to fetch playlist.")
        return
    
    # Decompress content if needed (zstd)
    decompressed_bytes, compression_info = decompress_content(response.content)
    
    # Decode content with multiple encoding attempts
    decoded_text, encoding_used = decode_content(decompressed_bytes)
    
    parsed_data = parse_m3u8_content(decoded_text, url)
    parsed_data['compression_info'] = compression_info
    display_results(response, parsed_data, decoded_text, encoding_used, decompressed_bytes)


if __name__ == "__main__":
    main()

