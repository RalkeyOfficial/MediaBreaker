# MediaBreaker

A Python tool for downloading videos from MediaDelivery\.net. MediaBreaker can handle both direct M3U8 playlist URLs and generic video URLs, automatically extracting the playlist and downloading the video segments.

## Features

- Download videos from M3U8 playlists
- Support for generic URLs (automatically extracts M3U8 playlist from HTML)
- Automatic quality selection (selects highest quality from master playlists)
- Zstandard (zstd) compression support
- Automatic filename extraction from video metadata
- Custom output directory and filename support

## Installation

### Prerequisites

- Python 3.7 or higher
- pip (Python package manager)

### Steps

1. Clone the repository:
```bash
git clone https://github.com/RalkeyOfficial/mediabreaker.git
cd mediabreaker
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Arguments

| Argument | Short | Description | Required |
|----------|-------|-------------|----------|
| `url` | - | M3U8 playlist URL or generic video URL | Yes |
| `--filename` | `-f` | Output filename (without extension) | No |
| `--out-dir` | `-o` | Output directory for downloaded video | No |

### Notes

- If `--filename` is not provided, the tool will attempt to extract the video name from metadata, or use a UUID-based filename
- If `--out-dir` is not provided, videos will be saved to the current working directory
- The output file extension is automatically detected from the playlist metadata (defaults to `.mp4`)

## Usage Examples

### Download from direct M3U8 URL

```bash
python downloader.py "https://.../playlist.m3u8"
```

### Download from generic URL (MediaDelivery\.net)

```bash
python downloader.py "https://iframe.mediadelivery.net/play/479230/[URL]"
```

### Specify custom filename

```bash
python downloader.py "https://.../playlist.m3u8" -f "my_video"
```

### Specify output directory

```bash
python downloader.py "https://.../playlist.m3u8" -o "C:\Videos"
```

### Combine all options

```bash
python downloader.py "https://iframe.mediadelivery.net/play/127378/[UUID]" -f "my_custom_video" -o "C:\Downloads\Videos"
```

## How It Works

1. **URL Detection**: Determines if the URL is a direct M3U8 playlist or a generic URL
2. **Playlist Extraction**: For generic URLs, extracts the M3U8 playlist URL from HTML metadata
3. **Playlist Parsing**: Fetches and parses the M3U8 playlist (with zstd decompression support)
4. **Quality Selection**: If a master playlist is detected, automatically selects the highest quality stream
5. **Metadata Extraction**: Extracts video metadata including encryption info, segment count, and duration
6. **Download**: Downloads all video segments and combines them into a single video file

## Support

I do not plan to support this project long term, though I will probably fix bugs if there is a demand for it.

This project is made to be a base for downloading videos from MediaDelivery,
which others can build upon or fix themselves.

## License

MIT

