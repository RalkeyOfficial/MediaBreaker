#!/usr/bin/env python3
"""
Main entry point for M3U8 video downloader.
"""

import sys
import os
import argparse
from pathlib import Path

from lib import playlist_parser
from lib import quality_selector
from lib import metadata_extractor
from lib import url_utils
from lib import generic_url_handler
from lib import segment_downloader

from lib import __version__


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
        description='Download videos from MediaDelivery.net',
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
    parser.add_argument('-f', '--filename', help='filename (optional, without extension)')
    parser.add_argument('-o', '--out-dir', help='output directory (optional)')

    args = parser.parse_args()

    print(f"""
███╗   ███╗███████╗██████╗ ██╗ █████╗ ██████╗ ██████╗ ███████╗ █████╗ ██╗  ██╗███████╗██████╗ 
████╗ ████║██╔════╝██╔══██╗██║██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗██║ ██╔╝██╔════╝██╔══██╗
██╔████╔██║█████╗  ██║  ██║██║███████║██████╔╝██████╔╝█████╗  ███████║█████╔╝ █████╗  ██████╔╝
██║╚██╔╝██║██╔══╝  ██║  ██║██║██╔══██║██╔══██╗██╔══██╗██╔══╝  ██╔══██║██╔═██╗ ██╔══╝  ██╔══██╗
██║ ╚═╝ ██║███████╗██████╔╝██║██║  ██║██████╔╝██║  ██║███████╗██║  ██║██║  ██╗███████╗██║  ██║
╚═╝     ╚═╝╚══════╝╚═════╝ ╚═╝╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝

                               RalkeyOfficial / v{__version__}


""")

    url = args.url
    video_name = None
    playlist_url = url
    output_dir = None
    file_extension = None

    if args.out_dir:
        output_dir = args.out_dir
    else:
        output_dir = os.getcwd()

    # Step 1: URL Type Detection
    print(f"Processing URL: {url}")

    if generic_url_handler.is_generic_url(url):
        print("Detected generic URL, extracting m3u8 playlist...")
        result = generic_url_handler.resolve_generic_url(url)
        if not result:
            print("ERROR: Failed to resolve generic URL. Please try again later.\n")
            print("If this issue persists, the website structure may have changed.")
            print("Please make an issue on the github repository.")
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


    # extract file extension
    if (extension := metadata_extractor.extract_file_extension(playlist)):
        print(f"Detected file extension: {extension}")
        file_extension = extension
    else:
        print("No file extension detected, defaulting to mp4")
        file_extension = 'mp4'

    # Determine filename
    if args.filename:
        output_filename = sanitize_filename(args.filename) + f'.{file_extension}'
    elif video_name:
        output_filename = sanitize_filename(video_name) + f'.{file_extension}'
    else:
        uuid = url_utils.extract_uuid_from_url(playlist_url)
        if uuid:
            output_filename = f"{uuid}.{file_extension}"
        else:
            output_filename = f"output.{file_extension}"
    
    # check if a file in the specified output directory with the same name already exists
    if os.path.exists(os.path.join(output_dir, output_filename)):
        print(f"ERROR: File \"{output_filename}\" already exists in \"{output_dir}\"")
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

    
    print(f"\nOutput filename: {output_filename}")

    # combine output directory and filename
    output_path = os.path.join(output_dir, output_filename)

    # Step 7: Download video
    print(f"\nStarting download...")
    print(f"Playlist URL: {playlist_url}")
    print(f"Output directory: {output_dir}")
    print(f"Output: {output_filename}")
    print("-" * 80)
    
    try:
        success = segment_downloader.download_video(playlist, playlist_url, output_path, segment_info)
        if success:
            print("-" * 80)
            print(f"✓ Download complete: {output_filename}")
            print(f"✓ {output_path}")
        else:
            print("-" * 80)
            print("ERROR: Download failed")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

