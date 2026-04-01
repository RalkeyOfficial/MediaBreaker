import sys
import os
import logging

from lib import url_utils, playlist_parser, metadata_extractor, quality_selector, generic_url_handler, file, \
    segment_downloader, database as db
from lib.file import get_file_bytes, sha256_file
from lib.log import logging_group, logging_start_group, logging_end_group
from lib.url_utils import extract_uuid_from_url


def main(args):
    if __name__ == '__main__':
        return None

    log = logging.getLogger(__name__)

    with logging_group("Opening connection to DB...", log, level=logging.DEBUG):
        con = db.open_db()

    url = args.url
    video_name = None
    playlist_url = url
    extension = None
    uuid = extract_uuid_from_url(url)

    log.info(f"URL: {url}")

    database_data = {
        'url': url
    }

    db_data = None
    with logging_group("Looking up existing data in database", log, level=logging.DEBUG):
        if uuid:
            db_data = db.get_one(con, uuid)
        if db_data:
            with logging_group("Looking up existing data in database", log, level=logging.DEBUG):
                log.debug(f"video_id: {db_data.get('video_id')}")
                log.debug(f"account_id: {db_data.get('account_id')}")
                log.debug(f"file_name: {db_data.get('file_name')}")
                log.debug(f"checksum_sha256: {db_data.get('checksum_sha256')}")
        else:
            log.debug("No data found")

    if args.out_dir:
        output_dir = args.out_dir
    else:
        output_dir = os.getcwd()

    # Step 1: URL Type Detection
    # start logging group (indents the logs)
    url_processing_token = logging_start_group("Processing URL", log, level=logging.DEBUG)

    # Check if the URL is a generic (non m3u8 / HTML) URL
    if generic_url_handler.is_generic_url(url):
        with logging_group("Detected generic URL, extracting m3u8 playlist data...", log, level=logging.DEBUG):
            # resolve the generic URL
            result = generic_url_handler.resolve_generic_url(url)

        # validation - check if the most important information is present
        if result is None or result.get('playlist_url') is None:
            log.error("Failed to resolve generic URL. Please try again later.")
            log.error("If this issue persists, the website structure may have changed.")
            log.error("Please make an issue on the github repository.")
            sys.exit(1)

        log.debug(f"Preparing database data: account_id = {result.get('account_id')}")
        database_data['account_id'] = result.get('account_id')

        playlist_url = result.get('playlist_url')
        video_name = result.get('video_name')
        extension = result.get('extension')

        with logging_group("Extracted data:", log, level=logging.DEBUG):
            log.debug(f"playlist_url: {playlist_url}")
            log.debug(f"video_name: {video_name}")
            log.debug(f"extension: {extension}")

    # Step 2: Parse playlist
    with logging_group("Fetching and parsing playlist...", log, level=logging.DEBUG):
        try:
            playlist = playlist_parser.parse_playlist(playlist_url)
        except Exception as e:
            log.error(f"Failed to parse playlist: {e}")
            sys.exit(1)

    # Step 3: Validate playlist
    log.debug("Validating playlist...")
    if not playlist_parser.validate_playlist(playlist):
        log.error("Invalid playlist")
        sys.exit(1)

    # end logging group
    logging_end_group(url_processing_token)

    # extract file extension
    if not extension:
        if extension := metadata_extractor.extract_file_extension(playlist):
            log.debug(f"Detected file extension: {extension}")
        else:
            log.warning(f"No file extension could be detected, defaulting to mp4")
            extension = 'mp4'
    else:
        log.debug("Skipping file extension extraction, extension already extracted from generic URL")

    # Determine filename
    with logging_group("Determining filename...", log, level=logging.DEBUG):
        # priority 1: filename argument
        if args.filename:
            output_filename = file.sanitize_filename(args.filename) + f'.{extension}'
            database_data['title'] = args.filename
            log.debug("PRIO 1: Use filename passed through args")

        # priority 2: name extracted from generic URL
        elif video_name:
            output_filename = file.sanitize_filename(video_name) + f'.{extension}'
            database_data['title'] = video_name
            log.debug("PRIO 2: Use filename extracted from generic URL")

        # priority 3: use existing data in DB (when re-downloading videos)
        elif db_data and db_data.get('title') != "output":
            output_filename = db_data.get('file_name')
            database_data['title'] = db_data.get('title')
            log.debug("PRIO 3: Use existing name in database")

        # priority 4: UUID
        elif uuid := url_utils.extract_uuid_from_url(playlist_url):
            output_filename = f"{uuid}.{extension}"
            database_data['title'] = uuid
            log.debug("PRIO 4: Use video UUID")

        # priority 5: no name could be found, default to "output"
        else:
            output_filename = f"output.{extension}"
            database_data['title'] = "output"
            log.debug(f"PRIO 5: Defaulting to \"output.{extension}\"")

        log.debug("Final Filename: " + output_filename)

    # check if a file in the specified output directory with the same name already exists
    log.debug("Checking if video file exists in output directory...")
    if os.path.exists(os.path.join(output_dir, output_filename)):
        log.warning(f"File \"{output_filename}\" already exists in \"{output_dir}\"")
        sys.exit(1)

    # Step 4: Type check and quality selection
    playlist_type = playlist_parser.get_playlist_type(playlist)
    log.debug(f"Playlist type: {playlist_type}")

    if playlist_type == 'master':
        log.debug("Master playlist detected, selecting highest quality stream...")
        media_playlist_url = quality_selector.get_highest_quality_stream(playlist)

        if not media_playlist_url:
            log.error("No streams found in master playlist")
            sys.exit(1)

        # Build absolute URL if relative
        if not media_playlist_url.startswith('http'):
            with logging_group("Creating absolute URL...", log, level=logging.DEBUG):
                log.debug(f"Relative URL: {media_playlist_url}")
                base_url = url_utils.get_base_url(playlist_url)
                media_playlist_url = url_utils.build_absolute_url(base_url, media_playlist_url)
                log.debug(f"base_url: {base_url}")
                log.debug(f"media_playlist_url: {media_playlist_url}")

        log.debug(f"Selected media playlist: {media_playlist_url}")

        # Parse the media playlist
        with logging_group("Fetching and parsing media playlist...", log, level=logging.DEBUG):
            try:
                playlist = playlist_parser.parse_playlist(media_playlist_url)
                playlist_url = media_playlist_url
            except Exception as e:
                log.error(f"Failed to parse media playlist: {e}")
                sys.exit(1)

    # Step 5: Extract metadata
    with logging_group("Extracting metadata...", log, level=logging.DEBUG):
        encryption_info = metadata_extractor.extract_encryption_info(playlist)
        segment_info = metadata_extractor.extract_segment_info(playlist)
        log.debug(f"Encryption info: {encryption_info}")
        log.debug(f"Segment info: {segment_info}")

    if segment_info.get('duration'):
        log.info(f"Duration: {segment_info.get('duration'):.2f} seconds")

    # combine output directory and filename
    output_path = os.path.join(output_dir, output_filename)

    # Step 7: Download video
    with logging_group(f"Starting download...", log):
        log.debug(f"Playlist URL: {playlist_url}")
        log.info(f"Output directory: {output_dir}")
        log.info(f"Output file: {output_filename}")

    try:
        encryption_info = segment_downloader.get_encryption_from_playlist(
            playlist=playlist,
            playlist_url=playlist_url,
        )

        segments_data = segment_downloader.download_video(
            playlist=playlist,
            playlist_url=playlist_url,
            encryption=encryption_info,
        )

        if not args.test_run:
            success = segment_downloader.create_file(segments_data=segments_data, output_path=output_path)
        else:
            log.info("[TEST RUN] SKIPPING FILE CREATION")
            success = True

        # updating database
        if success and not args.test_run:
            db.save_object(
                con=con,
                video_id=url_utils.extract_uuid_from_url(playlist_url),
                account_id=database_data.get('account_id') if database_data.get('account_id') else None,
                source_url=database_data.get('url'),
                title=database_data.get('title') if database_data.get('title') else None,
                file_path=output_dir,
                file_name=output_filename,
                filesize_bytes=get_file_bytes(output_path),
                checksum_sha256=sha256_file(output_path),
            )

        if success:
            log.success(f"Download complete: {output_filename}")
            log.info(output_path)
        else:
            log.error("Download failed")
            sys.exit(1)
    except Exception as e:
        log.error(e)
        sys.exit(1)
