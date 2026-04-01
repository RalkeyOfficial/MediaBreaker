#!/usr/bin/env python3
"""
Main entry point for M3U8 video downloader.
"""

# global imports (do not require 3rd party packages)
import sys
import argparse
import logging
from lib.log import setup_logging, get_logger, logging_group
from lib import database as db
from lib.venv_tools import bootstrap_venv


def parse_args():
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
    parser.add_argument('url', nargs='?', help='M3U8 playlist URL or generic video URL')
    parser.add_argument('-f', '--filename', help='filename (optional, without extension)')
    parser.add_argument('-o', '--out-dir', help='output directory (optional)')
    parser.add_argument('--test-run', help='Run the code without outputting a file', action="store_true")
    parser.add_argument('--debug', help='Enable debug logging', action="store_true")
    parser.add_argument('--warmup', help='Prepares the app for usage (not required to run)', action="store_true")

    return parser.parse_args()


def main():
    """
    Main workflow for downloading m3u8 videos.
    """

    from adapters.cli import main as cli_main
    from adapters.webui import main as webui_main
    from lib.version import __version__

    print(f"""
███╗   ███╗███████╗██████╗ ██╗ █████╗ ██████╗ ██████╗ ███████╗ █████╗ ██╗  ██╗███████╗██████╗ 
████╗ ████║██╔════╝██╔══██╗██║██╔══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗██║ ██╔╝██╔════╝██╔══██╗
██╔████╔██║█████╗  ██║  ██║██║███████║██████╔╝██████╔╝█████╗  ███████║█████╔╝ █████╗  ██████╔╝
██║╚██╔╝██║██╔══╝  ██║  ██║██║██╔══██║██╔══██╗██╔══██╗██╔══╝  ██╔══██║██╔═██╗ ██╔══╝  ██╔══██╗
██║ ╚═╝ ██║███████╗██████╔╝██║██║  ██║██████╔╝██║  ██║███████╗██║  ██║██║  ██╗███████╗██║  ██║
╚═╝     ╚═╝╚══════╝╚═════╝ ╚═╝╚═╝  ╚═╝╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝

                              RalkeyOfficial / v{__version__}


""")


    log.info("App started")
    log.debug("Debugging enabled")

    # Print message showing that this is a test run
    if args.test_run:
        log.info("Test run enabled")

    if args.url:
        log.debug("Start CLI application")
        cli_main(args)
    else:
        log.debug("Start WebUI application")
        webui_main(args)


if __name__ in {"__main__", "__mp_main__"}:
    # parse args globally
    args = parse_args()

    # setup logging
    setup_logging(level=logging.DEBUG if args.debug else logging.INFO)
    log = get_logger(__name__)

    # warmup app if needed
    if args.warmup:
        with logging_group("Warming up...", log):
            bootstrap_venv(log=log, is_warmup=True) # is_warmup just makes the warmup logs prettier
            log.info("Initializing database...")
            db.open_db()
            log.info("Database initialized!")
        log.success("Warmup done!")
        sys.exit(0)
    else:
        # bootstrap_venv without custom logging as it is low prio now
        bootstrap_venv(log=log)

    main()
