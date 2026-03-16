from pathlib import Path
import sqlite3


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS executions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    status TEXT NOT NULL,
    error_message TEXT,

    source TEXT NOT NULL,

    video_storage_provider TEXT,
    video_storage_path TEXT,
    input_video_filename TEXT,
    input_video_content_type TEXT,
    input_video_size_bytes INTEGER,
    video_upload_status TEXT,
    video_upload_error TEXT,

    notification_status TEXT,
    notification_channel TEXT,
    notification_target TEXT,
    notification_sent_at TEXT,
    notification_error TEXT,

    event_type TEXT,
    device_serial_number TEXT,
    station_serial_number TEXT,
    event_start_time TEXT,
    event_end_time TEXT,

    config_version_id TEXT,
    event_metadata_json TEXT NOT NULL,
    analysis_result_json TEXT
);

CREATE TABLE IF NOT EXISTS config_versions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    source TEXT,
    config_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_executions_created_at ON executions(created_at);
CREATE INDEX IF NOT EXISTS idx_executions_status ON executions(status);
CREATE INDEX IF NOT EXISTS idx_executions_device_serial_number ON executions(device_serial_number);
CREATE INDEX IF NOT EXISTS idx_executions_event_start_time ON executions(event_start_time);
CREATE INDEX IF NOT EXISTS idx_executions_notification_status ON executions(notification_status);
CREATE INDEX IF NOT EXISTS idx_executions_video_upload_status ON executions(video_upload_status);
CREATE INDEX IF NOT EXISTS idx_config_versions_created_at ON config_versions(created_at);
"""


def init_database(db_path: str | Path) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA_SQL)
        _migrate_legacy_schema(conn)


def _migrate_legacy_schema(conn: sqlite3.Connection) -> None:
    columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(executions)")
    }
    if "video_storage_provider" not in columns:
        conn.execute("ALTER TABLE executions ADD COLUMN video_storage_provider TEXT")
    if "video_storage_path" not in columns:
        conn.execute("ALTER TABLE executions ADD COLUMN video_storage_path TEXT")
    if "config_version_id" not in columns:
        conn.execute("ALTER TABLE executions ADD COLUMN config_version_id TEXT")
