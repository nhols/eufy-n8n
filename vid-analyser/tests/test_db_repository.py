import json
from pathlib import Path

from vid_analyser.db import ConfigRepository, ExecutionRepository, ExecutionStatus, NotificationStatus, VideoUploadStatus, init_database


def test_execution_repository_create_update_and_get(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_database(db_path)
    repo = ExecutionRepository(db_path)

    repo.create_execution(
        execution_id="exec-1",
        created_at="2026-03-15T12:00:00Z",
        updated_at="2026-03-15T12:00:00Z",
        status=ExecutionStatus.RECEIVED,
        source="eufy-bridge",
        event_metadata={"storage_path": "abc"},
        input_video_filename="clip.mp4",
        input_video_content_type="video/mp4",
        input_video_size_bytes=123,
        device_serial_number="device-1",
        station_serial_number="station-1",
        event_start_time="2026-03-15T11:59:00Z",
        event_end_time="2026-03-15T12:00:00Z",
        video_upload_status=VideoUploadStatus.NOT_ATTEMPTED,
        notification_status=NotificationStatus.NOT_REQUESTED,
        config_version_id="config-1",
    )

    repo.update_execution(
        "exec-1",
        updated_at="2026-03-15T12:01:00Z",
        status=ExecutionStatus.ANALYSED,
        analysis_result_json={"send_notification": True},
        notification_status=NotificationStatus.PENDING,
        video_upload_status=VideoUploadStatus.STORED,
        video_storage_provider="local",
        video_storage_path="videos/exec-1/clip.mp4",
    )

    record = repo.get_execution("exec-1")
    assert record is not None
    assert record.id == "exec-1"
    assert record.status == "analysed"
    assert record.notification_status == "pending"
    assert record.video_upload_status == "stored"
    assert record.video_storage_provider == "local"
    assert record.video_storage_path == "videos/exec-1/clip.mp4"
    assert record.config_version_id == "config-1"
    assert json.loads(record.event_metadata_json) == {"storage_path": "abc"}
    assert json.loads(record.analysis_result_json or "{}") == {"send_notification": True}


def test_execution_repository_recent_notification_messages_only_returns_sent(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_database(db_path)
    repo = ExecutionRepository(db_path)

    for execution_id, start_time, notification_status, message in [
        ("exec-sent-1", "2026-03-15T10:00:00Z", NotificationStatus.SENT, "First sent"),
        ("exec-unsent", "2026-03-15T10:05:00Z", NotificationStatus.NOT_REQUESTED, "Should not appear"),
        ("exec-sent-2", "2026-03-15T10:10:00Z", NotificationStatus.SENT, "Second sent"),
    ]:
        repo.create_execution(
            execution_id=execution_id,
            created_at=start_time,
            updated_at=start_time,
            status=ExecutionStatus.ANALYSED,
            source="eufy-bridge",
            event_metadata={},
            input_video_filename="clip.mp4",
            input_video_content_type="video/mp4",
            input_video_size_bytes=123,
            device_serial_number="device-1",
            station_serial_number="station-1",
            event_start_time=start_time,
            event_end_time=start_time,
            video_upload_status=VideoUploadStatus.STORED,
            notification_status=notification_status,
            config_version_id="config-1",
        )
        repo.update_execution(
            execution_id,
            updated_at=start_time,
            analysis_result_json={"message_for_user": message},
        )

    messages = repo.get_recent_notification_messages(limit=10)

    assert messages == [
        {"start_time": "2026-03-15T10:00:00Z", "message_for_user": "First sent"},
        {"start_time": "2026-03-15T10:10:00Z", "message_for_user": "Second sent"},
    ]


def test_config_repository_inserts_and_returns_latest_config(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    init_database(db_path)
    repo = ConfigRepository(db_path)

    repo.insert_config_version(
        config={"provider": {"kind": "gemini", "model": "old"}},
        created_at="2026-03-15T09:00:00Z",
        source="test",
    )
    repo.insert_config_version(
        config={"provider": {"kind": "gemini", "model": "new"}},
        created_at="2026-03-15T10:00:00Z",
        source="test",
    )

    latest = repo.get_latest_config()

    assert latest is not None
    assert latest.source == "test"
    assert json.loads(latest.config_json) == {"provider": {"kind": "gemini", "model": "new"}}
    assert repo.get_config(latest.id) is not None
