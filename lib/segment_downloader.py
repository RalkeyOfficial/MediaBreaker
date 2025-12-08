"""
Manual m3u8 segment downloading and concatenation.
Replaces FFmpeg-based downloading with manual segment handling.
"""

import requests
import m3u8
from pathlib import Path
from Crypto.Cipher import AES
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock, local
from lib.playlist_parser import get_browser_headers
from lib.url_utils import build_absolute_url, get_base_url


def fetch_encryption_key(key_uri: str, session: requests.Session) -> bytes:
    """
    Download encryption key from URI.
    Return key as bytes.
    """
    try:
        response = session.get(key_uri, timeout=15)
        response.raise_for_status()
        return response.content
    except Exception as e:
        raise RuntimeError(f"Failed to fetch encryption key from {key_uri}: {e}")


def download_segment(segment_url: str, session: requests.Session, max_retries: int = 3) -> bytes:
    """
    Download a single segment from URL.
    Handle HTTP errors and retries.
    Return segment data as bytes.
    """
    for attempt in range(max_retries):
        try:
            response = session.get(segment_url, timeout=15)
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


# Thread-local storage for sessions (one session per worker thread)
_thread_local = local()

def _get_thread_session(headers: dict) -> requests.Session:
    """
    Get or create a session for the current thread.
    Reuses connections within the same thread.
    """
    if not hasattr(_thread_local, 'session'):
        _thread_local.session = requests.Session()
        # Set default headers on the session
        _thread_local.session.headers.update(headers)
    return _thread_local.session


def _download_and_decrypt_segment(args: tuple) -> bytes:
    """
    Download and decrypt a single segment.
    Used for parallel execution with ThreadPoolExecutor.
    Takes a tuple of (segment, idx, base_url, headers, encryption_key, encryption_iv, use_sequence_iv, media_sequence).
    Returns segment data as bytes.
    """
    segment, idx, base_url, headers, encryption_key, encryption_iv, use_sequence_iv, media_sequence = args
    
    # Get thread-local session for connection pooling
    session = _get_thread_session(headers)
    
    segment_url = segment.uri
    
    # Convert relative URL to absolute
    if not segment_url.startswith('http'):
        segment_url = build_absolute_url(base_url, segment_url)
    
    # Download segment
    segment_data = download_segment(segment_url, session)
    
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
    
    return segment_data


def download_all_segments(playlist: m3u8.Playlist, base_url: str, headers: dict, encryption_key: bytes = None, encryption_iv: bytes = None, use_sequence_iv: bool = False) -> list[bytes]:
    """
    Download all segments from playlist in parallel.
    Handle relative URLs (convert to absolute).
    Return list of segment byte data.
    Include progress reporting.
    """
    if not playlist.segments:
        raise ValueError("Playlist has no segments")
    
    total_segments = len(playlist.segments)
    media_sequence = playlist.media_sequence or 0
    
    print(f"Downloading {total_segments} segments in parallel...")
    
    # Prepare arguments for each segment
    segment_args = [
        (segment, idx, base_url, headers, encryption_key, encryption_iv, use_sequence_iv, media_sequence)
        for idx, segment in enumerate(playlist.segments, 1)
    ]
    
    # Download segments in parallel using ThreadPoolExecutor
    # Use submit + as_completed for progress reporting, then reassemble in order
    try:
        completed_count = 0
        completed_lock = Lock()
        results = {}
        
        with ThreadPoolExecutor(max_workers=25) as executor:
            # Submit all tasks with their indices
            future_to_idx = {
                executor.submit(_download_and_decrypt_segment, args): idx
                for idx, args in enumerate(segment_args)
            }
            
            # Process completions as they happen for progress reporting
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    segment_data = future.result()
                    results[idx] = segment_data
                    
                    # Thread-safe progress reporting
                    with completed_lock:
                        completed_count += 1
                        if completed_count % 10 == 0 or completed_count == total_segments:
                            print(f"  Progress: {completed_count}/{total_segments} segments ({completed_count * 100 // total_segments}%)")
                except Exception as e:
                    print(f"ERROR: Failed to download segment {idx + 1}: {e}")
                    raise
        
        # Reassemble results in order
        segments_data = [results[i] for i in range(len(segment_args))]
        
    except Exception as e:
        print(f"ERROR: Failed to download segments: {e}")
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
            for _, segment_data in enumerate(segments, 1):
                f.write(segment_data)
        
        file_size = output_file.stat().st_size
        print(f"Output file size: {file_size / (1024 * 1024):.2f} MB")
        
        return True
    except Exception as e:
        print(f"ERROR: Failed to concatenate segments: {e}")
        return False


def download_video(
        playlist: m3u8.Playlist,
        playlist_url: str,
        output_path: str,
        metadata: dict = None,
        test_run: bool = False) -> bool:
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
                session = requests.Session()
                session.headers.update(headers)
                encryption_key = fetch_encryption_key(key_uri, session)
                session.close()
                
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
    if not test_run:
        success = concatenate_segments(segments_data, output_path)
    else:
        print("[TEST RUN] SKIPPING FILE CREATION")
        success = True
    
    return success

