"""
Extract encryption, codec, and segment metadata from playlists.
"""

import m3u8


def extract_encryption_info(playlist: m3u8.Playlist) -> dict:
    """
    Extract #EXT-X-KEY information.
    Return: {method, uri, iv} or None
    """
    if not playlist.segments:
        return None
    
    # Check first segment for encryption info
    first_segment = playlist.segments[0]
    if first_segment.key:
        key_info = first_segment.key
        return {
            'method': key_info.method,
            'uri': key_info.uri,
            'iv': key_info.iv,
            'keyformat': key_info.keyformat,
            'keyformatversions': key_info.keyformatversions
        }
    
    return None


def extract_codec_info(playlist: m3u8.Playlist) -> dict:
    """
    Extract codec information from master playlist.
    Return: {video_codec, audio_codec, resolution, bandwidth}
    """
    if not playlist.is_variant:
        return None
    
    codec_info = {}
    for stream_info in playlist.playlists:
        info = stream_info.stream_info
        if info.codecs:
            codecs = info.codecs.split(',')
            video_codec = None
            audio_codec = None
            
            for codec in codecs:
                codec = codec.strip()
                if codec.startswith('avc1') or codec.startswith('hvc1') or codec.startswith('hev1'):
                    video_codec = codec
                elif codec.startswith('mp4a') or codec.startswith('ac-3'):
                    audio_codec = codec
            
            codec_info[stream_info.uri] = {
                'video_codec': video_codec,
                'audio_codec': audio_codec,
                'resolution': f"{info.resolution[0]}x{info.resolution[1]}" if info.resolution else None,
                'bandwidth': info.bandwidth
            }
    
    return codec_info


def extract_segment_info(playlist: m3u8.Playlist) -> dict:
    """
    Extract segment count, duration, sequence.
    Return: {total_segments, duration, media_sequence, playlist_type}
    """
    if playlist.is_variant:
        return {
            'total_segments': 0,
            'duration': None,
            'media_sequence': None,
            'playlist_type': 'master'
        }
    
    total_duration = sum(segment.duration for segment in playlist.segments)
    
    return {
        'total_segments': len(playlist.segments),
        'duration': total_duration,
        'media_sequence': playlist.media_sequence,
        'playlist_type': playlist.playlist_type or 'VOD'
    }

