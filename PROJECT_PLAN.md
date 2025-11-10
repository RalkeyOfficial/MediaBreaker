# M3U8 Video Downloader - Project Plan
### Codename: MediaDelivery-cracker

## Overview
Automated tool to download videos from m3u8 playlists with support for master playlists, quality selection, encryption handling, and project-local ffmpeg installation.

## Project Structure

```
MEDIA CRACKER/
├── lib/
│   ├── __init__.py
│   ├── playlist_parser.py      # Parse and validate m3u8 playlists
│   ├── quality_selector.py      # Select highest quality from master playlist
│   ├── metadata_extractor.py    # Extract encryption, codec, and segment info
│   ├── ffmpeg_handler.py        # Interface with ffmpeg for downloading
│   ├── url_utils.py             # URL parsing and UUID extraction
│   └── generic_url_handler.py   # Handle generic URLs and extract m3u8 from HTML
├── downloader.py                # Main entry point
├── fetch_m3u8.py               # Debugging script (not part of main implementation)
├── requirements.txt
├── PROJECT_PLAN.md
└── ffmpeg/                      # Project-local ffmpeg (if possible)
    ├── bin/
    └── ...
```

## Library Modules

### 1. `lib/playlist_parser.py`
**Purpose**: Parse and validate m3u8 playlists

**Functions**:
- `parse_playlist(url: str) -> m3u8.Playlist`
  - Fetch playlist (handle zstd decompression)
  - Parse with m3u8 library
  - Return parsed playlist object
  
- `validate_playlist(playlist: m3u8.Playlist) -> bool`
  - Check if playlist is valid
  - Verify required tags exist
  - Return validation result

- `get_playlist_type(playlist: m3u8.Playlist) -> str`
  - Return 'master' or 'media'
  - Determine playlist type

**Dependencies**: `m3u8`, `requests`, `zstandard`

---

### 2. `lib/quality_selector.py`
**Purpose**: Select highest quality stream from master playlist

**Functions**:
- `get_highest_quality_stream(playlist: m3u8.Playlist) -> m3u8.Playlist`
  - Find stream with highest bandwidth
  - Return media playlist URL
  - Handle resolution/bandwidth comparison

- `get_stream_info(playlist: m3u8.Playlist) -> dict`
  - Extract bandwidth, resolution, codecs
  - Return metadata dict

**Dependencies**: `m3u8`

---

### 3. `lib/metadata_extractor.py`
**Purpose**: Extract encryption, codec, and segment metadata

**Functions**:
- `extract_encryption_info(playlist: m3u8.Playlist) -> dict`
  - Extract `#EXT-X-KEY` information
  - Return: `{method, uri, iv}` or `None`
  
- `extract_codec_info(playlist: m3u8.Playlist) -> dict`
  - Extract codec information from master playlist
  - Return: `{video_codec, audio_codec, resolution, bandwidth}`
  
- `extract_segment_info(playlist: m3u8.Playlist) -> dict`
  - Extract segment count, duration, sequence
  - Return: `{total_segments, duration, media_sequence, playlist_type}`

**Dependencies**: `m3u8`

---

### 4. `lib/url_utils.py`
**Purpose**: URL parsing and UUID extraction

**Functions**:
- `extract_uuid_from_url(url: str) -> str`
  - Extract UUID from URL path
  - Pattern: `/c1b96916-8302-4c83-9e79-312e344bb6c2/`
  - Return UUID string
  
- `build_absolute_url(base_url: str, relative_url: str) -> str`
  - Convert relative URLs to absolute
  - Handle base URL resolution
  
- `get_base_url(url: str) -> str`
  - Extract base URL from full URL
  - Return base URL for relative path resolution

**Dependencies**: `urllib.parse`

---

### 5. `lib/generic_url_handler.py`
**Purpose**: Handle generic URLs (non-m3u8) and extract playlist URLs from HTML

**Functions**:
- `is_generic_url(url: str) -> bool`
  - Check if URL is a generic URL (no .m3u8 extension)
  - Return True if generic, False if direct m3u8 URL
  
- `fetch_html(url: str) -> str`
  - Fetch HTML content from generic URL
  - Handle network errors
  - Return HTML content as string
  
- `extract_json_ld(html: str) -> dict`
  - Parse HTML and find `<script type="application/ld+json">` tag
  - Extract and parse JSON-LD content
  - Return parsed JSON object or None
  
- `extract_playlist_url_from_json_ld(json_ld: dict) -> str`
  - Extract `thumbnailUrl` from JSON-LD VideoObject
  - Replace `thumbnail.jpg` with `playlist.m3u8`
  - Return constructed playlist URL
  
- `extract_video_name_from_json_ld(json_ld: dict) -> str`
  - Extract `name` field from JSON-LD VideoObject
  - Clean filename (remove .mp4 extension if present)
  - Return video name string
  
- `resolve_generic_url(url: str) -> dict`
  - Main function: resolve generic URL to m3u8 playlist URL
  - Returns: `{playlist_url: str, video_name: str, metadata: dict}` or None
  - Handles all error cases and returns None on failure

**Dependencies**: `requests`, `beautifulsoup4`, `json`

**Error Handling**:
- Network errors during HTML fetch
- Missing or malformed JSON-LD script tag
- Missing required fields in JSON-LD (thumbnailUrl, name)
- Invalid URL construction
- All errors should be caught and return None with informative error messages

---

### 6. `lib/ffmpeg_handler.py`
**Purpose**: Interface with ffmpeg for downloading and processing

**Functions**:
- `find_ffmpeg() -> str`
  - Check for project-local ffmpeg first
  - Fallback to system ffmpeg
  - Return path to ffmpeg executable
  
- `download_video(m3u8_url: str, output_path: str, metadata: dict) -> bool`
  - Build ffmpeg command with proper flags
  - Handle encryption automatically
  - Use codec copy when possible
  - Return success status
  
- `get_ffmpeg_version() -> str`
  - Check ffmpeg availability
  - Return version string or None

**Dependencies**: `subprocess`, `os`, `pathlib`

---

## Main Workflow

### `downloader.py` - Main Entry Point

**Flow**:
1. **Input**: Master playlist URL, media playlist URL, or generic URL (e.g., `https://iframe.mediadelivery.net/play/479907/[UUID]`)
2. **URL Type Detection**: 
   - Use `generic_url_handler.is_generic_url()` to check if input is generic URL
   - If generic → use `generic_url_handler.resolve_generic_url()` to extract m3u8 URL and video name
   - If resolution fails → inform user and exit with error
   - If direct m3u8 URL → continue with original URL
3. **Parse**: Use `playlist_parser.parse_playlist()` to fetch and parse m3u8 playlist
4. **Validate**: Use `playlist_parser.validate_playlist()` to check validity
5. **Type Check**: 
   - If master playlist → use `quality_selector.get_highest_quality_stream()`
   - If media playlist → continue
6. **Extract Metadata**: Use `metadata_extractor` functions to get all info
7. **Extract UUID/Filename**: 
   - If video name from JSON-LD exists → use that (sanitize for filesystem)
   - Otherwise → use `url_utils.extract_uuid_from_url()` for filename
8. **Download**: Use `ffmpeg_handler.download_video()` with m3u8 URL
9. **Output**: Save as `{video_name}.mp4` or `{uuid}.mp4`

**Example Usage**:
```python
# Direct m3u8 URL
python downloader.py "https://.../playlist.m3u8"

# Generic URL (will extract m3u8 from HTML)
python downloader.py "https://iframe.mediadelivery.net/play/479907/[UUID]"
```

---

## FFmpeg Integration

### Command Structure
```bash
ffmpeg -i "{m3u8_url}" \
       -c copy \
       -bsf:a aac_adtstoasc \
       "{output_filename}.mp4"
```

**Flags Explanation**:
- `-i`: Input m3u8 URL
- `-c copy`: Stream copy (no re-encoding, faster)
- `-bsf:a aac_adtstoasc`: Bitstream filter for AAC audio (handles ADTS headers)

### Project-Local FFmpeg

**Download FFmpeg Binary:**
- Download platform-specific ffmpeg binary
- Store in `ffmpeg/bin/` directory
- Add to `.gitignore`
- Check platform (Windows/Linux/Mac) and download appropriate binary
- Use `lib/ffmpeg_handler.find_ffmpeg()` to locate

**Submodule/Download Script:**
- Create `scripts/download_ffmpeg.py`
- Downloads ffmpeg on first run
- Stores in project directory

**Implementation Plan**:
1. Create `lib/ffmpeg_handler.py` with `find_ffmpeg()`
2. Check `ffmpeg/bin/ffmpeg.exe` (Windows) or `ffmpeg/bin/ffmpeg` (Unix)
3. If not found, check system PATH
4. If still not found, prompt user or auto-download

---

## Metadata Usage

### Encryption Handling
- FFmpeg automatically handles `#EXT-X-KEY` tags
- No manual decryption needed
- FFmpeg fetches key from URI and decrypts segments

### Codec Information
- Use `-c copy` when codecs are compatible
- Metadata extracted for logging/info display
- FFmpeg handles codec compatibility automatically

### Segment Information
- Used for progress estimation
- Display total duration, segment count
- Not needed for ffmpeg command (handles automatically)

---

## Error Handling

### Scenarios to Handle:
1. **Invalid URL**: Return clear error message
2. **Network Errors**: Retry logic for playlist fetch
3. **Invalid Playlist**: Validation errors
4. **FFmpeg Not Found**: Clear instructions for installation
5. **Download Failures**: Partial download handling
6. **Encryption Errors**: Key fetch failures
7. **Generic URL Resolution Failures**: 
   - HTML fetch failures
   - Missing or malformed JSON-LD script tag
   - Missing required fields in JSON-LD (thumbnailUrl, name)
   - Invalid playlist URL construction
   - Website structure changes (inform user this is error-prone)

---

## Dependencies

### Python Packages:
```
requests>=2.31.0
zstandard>=0.22.0
m3u8>=3.5.0
beautifulsoup4>=4.12.0
```

### External:
- FFmpeg (project-local or system-wide)

---

## Implementation Steps

### Phase 1: Core Infrastructure
1. ✅ Create project structure
2. ✅ Set up `lib/` modules with function stubs
3. ✅ Implement `url_utils.py` (UUID extraction)
4. ✅ Implement `playlist_parser.py` (integrate existing zstd logic)
5. ✅ Implement `generic_url_handler.py` (generic URL resolution)

### Phase 2: Playlist Handling
6. ✅ Implement `quality_selector.py`
7. ✅ Implement `metadata_extractor.py`
8. ✅ Test master playlist → media playlist flow

### Phase 3: FFmpeg Integration
9. ✅ Implement `ffmpeg_handler.py`
10. ✅ Add project-local ffmpeg detection
11. ✅ Create download function

### Phase 4: Main Downloader
12. ✅ Create `downloader.py` main script
13. ✅ Integrate all modules (including generic URL handler)
14. ✅ Add error handling and logging

### Phase 5: Polish
15. ✅ Add progress indicators
16. ✅ Add command-line arguments
17. ✅ Add output formatting
18. ✅ Testing and bug fixes

---

## File Naming Convention

**Output Format**: `{video_name}.mp4` or `{uuid}.mp4`

**Priority**:
1. If video name extracted from JSON-LD → use `{video_name}.mp4` (sanitized for filesystem)
2. Otherwise → use `{uuid}.mp4` extracted from URL

**Examples**:
- Generic URL: `https://iframe.mediadelivery.net/play/479907/c1b96916-8302-4c83-9e79-312e344bb6c2`
  - JSON-LD name: `"My Video.mp4"`
  - Output: `My Video.mp4`
- Direct m3u8 URL: `https://.../c1b96916-8302-4c83-9e79-312e344bb6c2/playlist.m3u8`
  - UUID: `c1b96916-8302-4c83-9e79-312e344bb6c2`
  - Output: `c1b96916-8302-4c83-9e79-312e344bb6c2.mp4`

---

## Future Enhancements

1. **Progress Bar**: Show download progress
2. **Quality Selection**: Allow user to choose quality instead of auto-selecting highest
3. **Resume Support**: Resume interrupted downloads
4. **Batch Download**: Download multiple playlists
5. **Config File**: Store preferences (output directory, quality, etc.)
6. **Logging**: Detailed logging for debugging

---

## Notes

- FFmpeg handles all the complex parts (decryption, concatenation, remuxing)
- m3u8 library is used for parsing and validation only
- Project-local ffmpeg is possible but requires platform-specific binaries
- UUID extraction assumes consistent URL structure
- `fetch_m3u8.py` is a debugging/testing script and should not be used in the main implementation
- **Generic URL handling is error-prone**: Website structure may change at any time. All generic URL resolution steps must be tested before proceeding, and failures must inform the user clearly. The JSON-LD extraction method relies on specific HTML structure that may break if the website updates.

