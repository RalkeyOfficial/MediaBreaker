"""
Select highest quality stream from master playlist.
"""

import m3u8


def get_highest_quality_stream(playlist: m3u8.Playlist) -> str:
    """
    Find stream with highest bandwidth.
    Return media playlist URL.
    Handle resolution/bandwidth comparison.
    """
    if not playlist.is_variant:
        return None
    
    highest_bandwidth = 0
    best_stream = None
    
    for stream_info in playlist.playlists:
        bandwidth = stream_info.stream_info.bandwidth or 0
        if bandwidth > highest_bandwidth:
            highest_bandwidth = bandwidth
            best_stream = stream_info
    
    if best_stream:
        return best_stream.uri
    
    return None


def get_stream_info(playlist: m3u8.Playlist) -> dict:
    """
    Extract bandwidth, resolution, codecs.
    Return metadata dict.
    """
    if not playlist.is_variant:
        return None
    
    streams = []
    for stream_info in playlist.playlists:
        info = stream_info.stream_info
        streams.append({
            'bandwidth': info.bandwidth,
            'resolution': f"{info.resolution[0]}x{info.resolution[1]}" if info.resolution else None,
            'codecs': info.codecs,
            'uri': stream_info.uri
        })
    
    return streams

