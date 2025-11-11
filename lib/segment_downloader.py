"""
Manual m3u8 segment downloading and concatenation.
Replaces FFmpeg-based downloading with manual segment handling.
"""

import requests
import m3u8
from pathlib import Path
from Crypto.Cipher import AES
from lib.playlist_parser import get_browser_headers
from lib.url_utils import build_absolute_url, get_base_url


def fetch_encryption_key(key_uri: str, headers: dict) -> bytes:
    """
    Download encryption key from URI.
    Return key as bytes.
    """
    try:
        response = requests.get(key_uri, headers=headers, timeout=30)
        response.raise_for_status()
        return response.content
    except Exception as e:
        raise RuntimeError(f"Failed to fetch encryption key from {key_uri}: {e}")


def download_segment(segment_url: str, headers: dict, max_retries: int = 3) -> bytes:
    """
    Download a single segment from URL.
    Handle HTTP errors and retries.
    Return segment data as bytes.
    """
    for attempt in range(max_retries):
        try:
            response = requests.get(segment_url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.content
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                raise RuntimeError(f"Failed to download segment after {max_retries} attempts: {e}")
            continue
    raise RuntimeError("Failed to download segment")


def decrypt_segment(segment_data: bytes, key: bytes, iv: bytes = None) -> bytes:
    """
    Decrypt segment if encryption is present.
    Handle AES-128 encryption (most common).
    Return decrypted segment data.
    """
    if len(key) != 16:
        raise ValueError(f"Invalid key length: {len(key)} bytes (expected 16)")
    
    # If IV is not provided, use zero IV (common for AES-128)
    if iv is None:
        iv = b'\x00' * 16
    elif isinstance(iv, str):
        # Handle hex string IV
        if iv.startswith('0x') or iv.startswith('0X'):
            iv = bytes.fromhex(iv[2:])
        else:
            iv = bytes.fromhex(iv)
    
    # Ensure IV is 16 bytes
    if len(iv) != 16:
        raise ValueError(f"Invalid IV length: {len(iv)} bytes (expected 16)")
    
    try:
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted = cipher.decrypt(segment_data)
        
        # Remove PKCS7 padding if present
        padding_length = decrypted[-1]
        if padding_length <= 16:
            # Check if padding is valid
            if all(decrypted[-i] == padding_length for i in range(1, padding_length + 1)):
                decrypted = decrypted[:-padding_length]
        
        return decrypted
    except Exception as e:
        raise RuntimeError(f"Decryption failed: {e}")


def download_all_segments(playlist: m3u8.Playlist, base_url: str, headers: dict, encryption_key: bytes = None, encryption_iv: bytes = None, use_sequence_iv: bool = False) -> list[bytes]:
    """
    Download all segments from playlist.
    Handle relative URLs (convert to absolute).
    Return list of segment byte data.
    Include progress reporting.
    """
    if not playlist.segments:
        raise ValueError("Playlist has no segments")
    
    segments_data = []
    total_segments = len(playlist.segments)
    media_sequence = playlist.media_sequence or 0
    
    print(f"Downloading {total_segments} segments...")
    
    for idx, segment in enumerate(playlist.segments, 1):
        segment_url = segment.uri
        
        # Convert relative URL to absolute
        if not segment_url.startswith('http'):
            segment_url = build_absolute_url(base_url, segment_url)
        
        # Download segment
        try:
            segment_data = download_segment(segment_url, headers)
            
            # Decrypt if encryption is present
            if encryption_key:
                # Check if this segment has its own IV
                segment_iv = encryption_iv
                
                # Check segment-specific IV first
                if segment.key and segment.key.iv:
                    iv_str = segment.key.iv
                    if iv_str.startswith('0x') or iv_str.startswith('0X'):
                        segment_iv = bytes.fromhex(iv_str[2:])
                    else:
                        segment_iv = bytes.fromhex(iv_str)
                elif use_sequence_iv:
                    # If no IV specified, use segment sequence number as IV
                    # IV is the segment sequence number as a 16-byte big-endian integer
                    sequence_number = media_sequence + idx - 1
                    segment_iv = sequence_number.to_bytes(16, byteorder='big')
                
                segment_data = decrypt_segment(segment_data, encryption_key, segment_iv)
            
            segments_data.append(segment_data)
            
            # Progress reporting
            if idx % 10 == 0 or idx == total_segments:
                print(f"  Progress: {idx}/{total_segments} segments ({idx * 100 // total_segments}%)")
        
        except Exception as e:
            print(f"ERROR: Failed to download segment {idx}: {e}")
            raise
    
    return segments_data


def concatenate_segments(segments: list[bytes], output_path: str) -> bool:
    """
    Concatenate all segment bytes into single file.
    Write to output file.
    Return success status.
    """
    try:
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"Concatenating {len(segments)} segments to {output_path}...")
        
        with open(output_file, 'wb') as f:
            for idx, segment_data in enumerate(segments, 1):
                f.write(segment_data)
                if idx % 10 == 0 or idx == len(segments):
                    print(f"  Progress: {idx}/{len(segments)} segments written")
        
        file_size = output_file.stat().st_size
        print(f"Output file size: {file_size / (1024 * 1024):.2f} MB")
        
        return True
    except Exception as e:
        print(f"ERROR: Failed to concatenate segments: {e}")
        return False


def download_video(playlist: m3u8.Playlist, playlist_url: str, output_path: str, metadata: dict = None) -> bool:
    """
    Main function: orchestrate download and concatenation.
    Handle encryption keys.
    Download all segments.
    Decrypt if needed.
    Concatenate to output file.
    Return success status.
    """
    if not playlist.segments:
        print("ERROR: Playlist has no segments")
        return False
    
    # Get base URL for relative segment URLs
    base_url = get_base_url(playlist_url)
    
    # Get headers
    headers = get_browser_headers()
    
    # Handle encryption
    encryption_key = None
    encryption_iv = None
    use_sequence_iv = False
    
    if playlist.segments:
        first_segment = playlist.segments[0]
        if first_segment.key and first_segment.key.method != 'NONE':
            encryption_method = first_segment.key.method
            key_uri = first_segment.key.uri
            
            if encryption_method == 'AES-128':
                print(f"Encryption detected: {encryption_method}")
                
                # Convert relative key URI to absolute if needed
                if not key_uri.startswith('http'):
                    key_uri = build_absolute_url(base_url, key_uri)
                
                print(f"Fetching encryption key from {key_uri}...")
                encryption_key = fetch_encryption_key(key_uri, headers)
                
                # Get IV if present
                if first_segment.key.iv:
                    iv_str = first_segment.key.iv
                    if iv_str.startswith('0x') or iv_str.startswith('0X'):
                        encryption_iv = bytes.fromhex(iv_str[2:])
                    else:
                        encryption_iv = bytes.fromhex(iv_str)
                else:
                    # No IV specified - use segment sequence number as IV
                    use_sequence_iv = True
                    print("No IV specified in playlist, using segment sequence numbers as IV")
                
                print(f"Encryption key fetched: {len(encryption_key)} bytes")
            else:
                print(f"WARNING: Unsupported encryption method: {encryption_method}")
                return False
    
    # Download all segments
    try:
        segments_data = download_all_segments(
            playlist,
            base_url,
            headers,
            encryption_key,
            encryption_iv,
            use_sequence_iv
        )
    except Exception as e:
        print(f"ERROR: Failed to download segments: {e}")
        return False
    
    # Concatenate segments
    success = concatenate_segments(segments_data, output_path)
    
    return success

