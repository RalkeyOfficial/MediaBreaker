import os
import sqlite3
import logging
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any

from lib.file import check_if_file_exists
from lib.log import logging_group
from lib.url_utils import get_mediadelivery_url_type

log = logging.getLogger(__name__)


"""
============================================
migrations
============================================
"""
MIGRATIONS_DIR = Path(__file__).parent.parent / 'database' / 'migrations'

def _ensure_migrations_table(con: sqlite3.Connection) -> None:
    con.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

def _applied_migrations(con: sqlite3.Connection) -> set[str]:
    rows = con.execute("SELECT id FROM schema_migrations").fetchall()
    return {r[0] for r in rows}

def _run_migrations(con: sqlite3.Connection) -> None:
    log.debug("Ensuring migrations table exists...")
    _ensure_migrations_table(con)

    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    log.debug(f"Available migrations: {[x.stem for x in migration_files]}")

    with logging_group("Retrieving applied migrations...", log, level=logging.DEBUG):
        done = _applied_migrations(con)
        log.debug(f"Existing applied migrations: {done}")

    for path in migration_files:
        mid = path.stem  # "001_init"
        if mid in done:
            log.debug(f"Skipping migrations: {mid}")
            continue

        sql = path.read_text(encoding="utf-8")

        log.debug(f"Applying migrations: {mid}")

        # Atomic per-migration: either applies fully or rolls back
        try:
            con.execute("BEGIN")
            con.executescript(sql)
            con.execute("INSERT INTO schema_migrations(id) VALUES (?)", (mid,))
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            log.error(f"Failed applying migration {mid}.", exc_info=True)
            raise

"""
============================================
database functions
============================================
"""

def _check_if_database_file_exists() -> bool:
    """
    check if the database file exists
    if not, creates it
    """
    Path("./database").mkdir(parents=True, exist_ok=True)
    if not check_if_file_exists("./database/downloads.db"):
        log.debug(f"Creating downloads.db in {os.getcwd()}")
        with open('./database/downloads.db', 'w') as fp:
            pass
        return False
    return True


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dict_factory(cursor, row):
    cols = [col[0] for col in cursor.description]
    return dict(zip(cols, row))


def open_db(db_path: str = "./database/downloads.db") -> sqlite3.Connection:
    # check if DB file exists, if not make it
    _check_if_database_file_exists()

    con = sqlite3.connect(db_path)
    con.execute("PRAGMA journal_mode=WAL;")  # safer with concurrent runs
    con.execute("PRAGMA foreign_keys=ON;")

    # apply migrations
    with logging_group("Running migrations...", log, level=logging.DEBUG):
        _run_migrations(con)

    con.row_factory=_dict_factory

    return con


def save_object(
        con: sqlite3.Connection,
        video_id: str,
        *,  # makes arguments after this keyword only
        account_id: str,
        source_url: str,
        title: Optional[str],
        file_name: Optional[str],
        file_path: Optional[str],
        filesize_bytes: int,
        checksum_sha256: str,
        meta: Optional[dict[str, Any]] = None,
) -> None:
    if not video_id:
        log.error(f"No video_id passed to save_object.")
        return None

    if (one_result := get_one(con, video_id)) is not None:
        # if the source_url in the DB is of higher priority than the given source_url
        # use that one
        if get_mediadelivery_url_type(source_url) > get_mediadelivery_url_type(one_result.get('source_url')):
            source_url = one_result.get('source_url')

    meta_json = json.dumps(meta or {}, ensure_ascii=False)
    now = utcnow_iso()
    # Insert row if new, otherwise keep row but update useful fields
    con.execute(
        """
        INSERT INTO downloads
        (video_id, account_id, source_url, title, file_name, file_path, created_at, filesize_bytes, checksum_sha256,
         meta_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(video_id) DO UPDATE SET source_url      = excluded.source_url,
                                            account_id      = COALESCE(excluded.account_id, downloads.account_id),
                                            title           = COALESCE(excluded.title, downloads.title),
                                            file_name       = COALESCE(excluded.file_name, downloads.file_name),
                                            file_path       = COALESCE(excluded.file_path, downloads.file_path),
                                            meta_json       = COALESCE(excluded.meta_json, downloads.meta_json),
                                            created_at      = COALESCE(excluded.created_at, downloads.created_at),
                                            filesize_bytes  = COALESCE(excluded.filesize_bytes, downloads.filesize_bytes),
                                            checksum_sha256 = COALESCE(excluded.checksum_sha256, downloads.checksum_sha256),
                                            meta_json       = COALESCE(excluded.meta_json, downloads.meta_json)
        """,
        (
            video_id,
            account_id,
            source_url,
            title,
            file_name,
            file_path,
            now,
            filesize_bytes,
            checksum_sha256,
            meta_json,
        ),
    )
    con.commit()
    return None


def is_downloaded(con: sqlite3.Connection, video_id) -> bool:
    return get_one(con, video_id) is not None


def get_one(con: sqlite3.Connection, video_id: str) -> Optional[dict[str, Any]]:
    row = con.execute("""
                      SELECT *
                      FROM downloads
                      WHERE video_id = ?
                      LIMIT 1
                      """, (video_id,)).fetchone()

    return row


def get_all(con: sqlite3.Connection):
    rows = con.execute("""
                       select *
                       from downloads
                       """).fetchall()

    return rows
