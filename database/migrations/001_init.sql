CREATE TABLE IF NOT EXISTS downloads
    (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        video_id        TEXT NOT NULL, -- id of the video
        account_id      TEXT,          -- id of the account (optional as this is only retrievable via generic url)
        source_url      TEXT NOT NULL, -- source url of the video as given by user
        title           TEXT,          -- title of the video
        file_name       TEXT,          -- full file name, (usually title + extension)
        file_path       TEXT NOT NULL, -- path the file is saved to
        filesize_bytes  INTEGER,       -- file size in bytes
        checksum_sha256 TEXT,          -- sha256 hash of the file
        created_at      TEXT NOT NULL, -- file creation time
        meta_json       TEXT           -- extra metadata
    );
CREATE UNIQUE INDEX IF NOT EXISTS ux_download_key ON downloads (video_id);
CREATE INDEX IF NOT EXISTS ix_download_path ON downloads (file_path);