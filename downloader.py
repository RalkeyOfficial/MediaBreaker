#!/usr/bin/env python3
"""
Main entry point for M3U8 video downloader.
"""

import sys
import argparse
from pathlib import Path

from lib import playlist_parser
from lib import quality_selector
from lib import metadata_extractor
from lib import url_utils
from lib import generic_url_handler
from lib import segment_downloader


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


def main():
    """
    Main workflow for downloading m3u8 videos.
    """
    parser = argparse.ArgumentParser(
        description='Download videos from m3u8 playlists',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Direct m3u8 URL
  python downloader.py "https://.../playlist.m3u8"
  
  # Generic URL (will extract m3u8 from HTML)
  python downloader.py "https://iframe.mediadelivery.net/play/479907/[UUID]"
        """
    )
    parser.add_argument('url', help='M3U8 playlist URL or generic video URL')
    parser.add_argument('-o', '--output', help='Output filename (optional)')
    parser.add_argument('-q', '--quality', action='store_true', 
                       help='Show available quality options and exit')
    
    args = parser.parse_args()
    
    url = args.url
    video_name = None
    playlist_url = url
    
    # Step 1: URL Type Detection
    print(f"Processing URL: {url}")
    
    if generic_url_handler.is_generic_url(url):
        print("Detected generic URL, extracting m3u8 playlist...")
        result = generic_url_handler.resolve_generic_url(url)
        if not result:
            print("ERROR: Failed to resolve generic URL. The website structure may have changed.")
            sys.exit(1)
        
        playlist_url = result['playlist_url']
        video_name = result.get('video_name')
        print(f"Extracted playlist URL: {playlist_url}")
        if video_name:
            print(f"Extracted video name: {video_name}")
    
    # Step 2: Parse playlist
    print("\nFetching and parsing playlist...")
    try:
        playlist = playlist_parser.parse_playlist(playlist_url)
    except Exception as e:
        print(f"ERROR: Failed to parse playlist: {e}")
        sys.exit(1)
    
    # Step 3: Validate playlist
    if not playlist_parser.validate_playlist(playlist):
        print("ERROR: Invalid playlist")
        sys.exit(1)
    
    # Step 4: Type check and quality selection
    playlist_type = playlist_parser.get_playlist_type(playlist)
    print(f"Playlist type: {playlist_type}")
    
    if playlist_type == 'master':
        print("Master playlist detected, selecting highest quality stream...")
        media_playlist_url = quality_selector.get_highest_quality_stream(playlist)
        
        if not media_playlist_url:
            print("ERROR: No streams found in master playlist")
            sys.exit(1)
        
        # Build absolute URL if relative
        if not media_playlist_url.startswith('http'):
            base_url = url_utils.get_base_url(playlist_url)
            media_playlist_url = url_utils.build_absolute_url(base_url, media_playlist_url)
        
        print(f"Selected media playlist: {media_playlist_url}")
        
        # Parse the media playlist
        try:
            playlist = playlist_parser.parse_playlist(media_playlist_url)
            playlist_url = media_playlist_url
        except Exception as e:
            print(f"ERROR: Failed to parse media playlist: {e}")
            sys.exit(1)
    
    # Step 5: Extract metadata
    print("\nExtracting metadata...")
    encryption_info = metadata_extractor.extract_encryption_info(playlist)
    segment_info = metadata_extractor.extract_segment_info(playlist)
    
    if encryption_info:
        print(f"Encryption: {encryption_info.get('method', 'None')}")
    print(f"Total segments: {segment_info.get('total_segments', 0)}")
    if segment_info.get('duration'):
        print(f"Duration: {segment_info.get('duration'):.2f} seconds")
    
    # Step 6: Determine output filename
    if args.output:
        output_filename = args.output
    elif video_name:
        output_filename = sanitize_filename(video_name) + '.mp4'
    else:
        uuid = url_utils.extract_uuid_from_url(playlist_url)
        if uuid:
            output_filename = f"{uuid}.mp4"
        else:
            output_filename = "output.mp4"
    
    # Ensure .mp4 extension
    if not output_filename.endswith('.mp4'):
        output_filename += '.mp4'
    
    print(f"\nOutput filename: {output_filename}")

    # Step 7: Download video
    print(f"\nStarting download...")
    print(f"Playlist URL: {playlist_url}")
    print(f"Output: {output_filename}")
    print("-" * 80)
    
    try:
        success = segment_downloader.download_video(playlist, playlist_url, output_filename, segment_info)
        if success:
            print("-" * 80)
            print(f"✓ Download complete: {output_filename}")
        else:
            print("-" * 80)
            print("ERROR: Download failed")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

