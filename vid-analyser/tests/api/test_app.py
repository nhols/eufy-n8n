import importlib
import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from pytest import MonkeyPatch, raises

from vid_analyser.llm.response_model import AnalyseResponse
from vid_analyser.pipeline import RunConfig

api_module = importlib.import_module("vid_analyser.api.app")
CONFIG_S3_BUCKET_ENV_VAR = api_module.CONFIG_S3_BUCKET_ENV_VAR
CONFIG_S3_KEY_ENV_VAR = api_module.CONFIG_S3_KEY_ENV_VAR
VIDEO_S3_BUCKET_ENV_VAR = api_module.VIDEO_S3_BUCKET_ENV_VAR
VIDEO_S3_PREFIX_ENV_VAR = api_module.VIDEO_S3_PREFIX_ENV_VAR
SQLITE_PATH_ENV_VAR = api_module.SQLITE_PATH_ENV_VAR
TELEGRAM_BOT_TOKEN_ENV_VAR = api_module.TELEGRAM_BOT_TOKEN_ENV_VAR
app = api_module.app


class FakeProvider:
    name = "fake"


def _write_config(tmp_path: Path, *, provider_kind: str = "gemini") -> Path:
    config_path = tmp_path / "run_config.json"
    config_path.write_text(
        (
            "{"
            f'"provider":{{"kind":"{provider_kind}","model":"gemini-3-flash-preview"}},'
            '"overlay_zones":[],"enable_person_id":false'
            "}"
        ),
        encoding="utf-8",
    )
    return config_path


def _config_json(
    *,
    provider_kind: str = "gemini",
    system_prompt: str | None = None,
    user_prompt: str | None = None,
    telegram_chat_id: str | None = None,
    previous_messages_limit: int | None = None,
) -> str:
    body = {
        "provider": {"kind": provider_kind, "model": "gemini-3-flash-preview"},
        "overlay_zones": [],
        "enable_person_id": False,
    }
    if system_prompt is not None:
        body["system_prompt"] = system_prompt
    if user_prompt is not None:
        body["user_prompt"] = user_prompt
    if telegram_chat_id is not None:
        body["telegram_chat_id"] = telegram_chat_id
    if previous_messages_limit is not None:
        body["previous_messages_limit"] = previous_messages_limit
    return json.dumps(body)


def test_run_config_from_json_path(tmp_path: Path) -> None:
    config = RunConfig.from_json_path(_write_config(tmp_path))

    assert config.provider.name == "gemini"
    assert config.overlay is None
    assert config.person_id is None


def test_run_config_from_json_path_rejects_invalid_provider(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path, provider_kind="other")

    with raises(ValueError, match="Unsupported analysis provider"):
        RunConfig.from_json_path(config_path)


def test_run_config_from_json_text_includes_optional_prompts() -> None:
    config = RunConfig.from_json_text(
        _config_json(
            system_prompt="system from s3",
            user_prompt="user from s3",
            telegram_chat_id="1234",
            previous_messages_limit=7,
        )
    )

    assert config.system_prompt == "system from s3"
    assert config.user_prompt == "user from s3"
    assert config.telegram_chat_id == "1234"
    assert config.previous_messages_limit == 7


def test_analyse_video_calls_run_and_cleans_up(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv(CONFIG_S3_BUCKET_ENV_VAR, "test-bucket")
    monkeypatch.setenv(CONFIG_S3_KEY_ENV_VAR, "config/run_config.json")
    monkeypatch.setenv(VIDEO_S3_BUCKET_ENV_VAR, "test-video-bucket")
    monkeypatch.setenv(VIDEO_S3_PREFIX_ENV_VAR, "videos")
    monkeypatch.setenv(SQLITE_PATH_ENV_VAR, str(tmp_path / "app.db"))
    monkeypatch.setattr(
        api_module,
        "_load_json_document_from_s3",
        lambda bucket, key: json.loads(
            _config_json(system_prompt="system from s3", user_prompt="user from s3")
        ),
    )
    monkeypatch.delenv(TELEGRAM_BOT_TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(api_module, "_upload_video_to_s3", lambda **kwargs: None)

    response_model = AnalyseResponse(
        ir_mode="unknown",
        parking_spot_status="unknown",
        number_plate=None,
        events_description="none",
        message_for_user="Nothing relevant happened at your property.",
        send_notification=False,
    )
    captured: dict[str, object] = {}

    async def fake_run(video_path: str | Path, user_prompt: str, system_prompt: str, config: RunConfig):
        captured["video_path"] = Path(video_path)
        captured["user_prompt"] = user_prompt
        captured["system_prompt"] = system_prompt
        captured["config"] = config
        assert Path(video_path).exists()
        return response_model

    monkeypatch.setattr(api_module, "run", fake_run)

    with TestClient(app) as client:
        response = client.post(
            "/analyse-video",
            files={"video": ("clip.mp4", b"video-bytes", "video/mp4")},
            data={"storage_path": "abc", "start_time": "2026-03-15T10:00:00Z"},
        )

    assert response.status_code == 200
    assert response.json() == response_model.model_dump(mode="json")
    assert captured["user_prompt"] == (
        "user from s3\n\n"
        "Event metadata:\n"
        "- storage_path: abc\n"
        "- start_time: 2026-03-15T10:00:00Z"
    )
    assert captured["system_prompt"] == "system from s3"
    assert isinstance(captured["config"], RunConfig)
    assert not Path(captured["video_path"]).exists()


def test_analyse_video_cleans_up_temp_file_on_failure(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv(CONFIG_S3_BUCKET_ENV_VAR, "test-bucket")
    monkeypatch.setenv(VIDEO_S3_BUCKET_ENV_VAR, "test-video-bucket")
    monkeypatch.setenv(SQLITE_PATH_ENV_VAR, str(tmp_path / "app.db"))
    monkeypatch.setattr(api_module, "_load_json_document_from_s3", lambda bucket, key: json.loads(_config_json()))
    monkeypatch.delenv(TELEGRAM_BOT_TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(api_module, "_upload_video_to_s3", lambda **kwargs: None)
    captured: dict[str, object] = {}

    async def fake_run(video_path: str | Path, user_prompt: str, system_prompt: str, config: RunConfig):
        captured["video_path"] = Path(video_path)
        raise RuntimeError("boom")

    monkeypatch.setattr(api_module, "run", fake_run)

    with TestClient(app) as client:
        response = client.post(
            "/analyse-video",
            files={"video": ("clip.mp4", b"video-bytes", "video/mp4")},
            data={"station_serial_number": "homebase-1"},
        )

    assert response.status_code == 500
    assert response.json() == {"detail": "Video analysis failed"}
    assert not Path(captured["video_path"]).exists()


def test_analyse_video_rejects_empty_upload(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv(CONFIG_S3_BUCKET_ENV_VAR, "test-bucket")
    monkeypatch.setenv(VIDEO_S3_BUCKET_ENV_VAR, "test-video-bucket")
    monkeypatch.setenv(SQLITE_PATH_ENV_VAR, str(tmp_path / "app.db"))
    monkeypatch.setattr(api_module, "_load_json_document_from_s3", lambda bucket, key: json.loads(_config_json()))
    monkeypatch.delenv(TELEGRAM_BOT_TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(api_module, "_upload_video_to_s3", lambda **kwargs: None)
    mocked_run = AsyncMock()
    monkeypatch.setattr(api_module, "run", mocked_run)

    with TestClient(app) as client:
        response = client.post(
            "/analyse-video",
            files={"video": ("clip.mp4", b"", "video/mp4")},
            data={"station_serial_number": "homebase-1"},
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Uploaded video is empty"}
    mocked_run.assert_not_awaited()


def test_analyse_video_accepts_request_without_metadata(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv(CONFIG_S3_BUCKET_ENV_VAR, "test-bucket")
    monkeypatch.setenv(VIDEO_S3_BUCKET_ENV_VAR, "test-video-bucket")
    monkeypatch.setenv(SQLITE_PATH_ENV_VAR, str(tmp_path / "app.db"))
    monkeypatch.setattr(api_module, "_load_json_document_from_s3", lambda bucket, key: json.loads(_config_json()))
    monkeypatch.delenv(TELEGRAM_BOT_TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(api_module, "_upload_video_to_s3", lambda **kwargs: None)
    response_model = AnalyseResponse(
        ir_mode="unknown",
        parking_spot_status="unknown",
        number_plate=None,
        events_description="none",
        message_for_user="Nothing relevant happened at your property.",
        send_notification=False,
    )
    captured: dict[str, object] = {}

    async def fake_run(video_path: str | Path, user_prompt: str, system_prompt: str, config: RunConfig):
        captured["user_prompt"] = user_prompt
        return response_model

    monkeypatch.setattr(api_module, "run", fake_run)

    with TestClient(app) as client:
        response = client.post(
            "/analyse-video",
            files={"video": ("clip.mp4", b"video-bytes", "video/mp4")},
        )

    assert response.status_code == 200
    assert captured["user_prompt"] == api_module.DEFAULT_USER_PROMPT


def test_analyse_video_renders_prompt_tokens_lazily(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv(CONFIG_S3_BUCKET_ENV_VAR, "test-bucket")
    monkeypatch.setenv(VIDEO_S3_BUCKET_ENV_VAR, "test-video-bucket")
    monkeypatch.setenv(SQLITE_PATH_ENV_VAR, str(tmp_path / "app.db"))
    monkeypatch.delenv(TELEGRAM_BOT_TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(api_module, "_upload_video_to_s3", lambda **kwargs: None)

    def fake_load_json_document_from_s3(bucket: str, key: str) -> dict:
        if bucket == "test-bucket":
            return json.loads(
                _config_json(
                    system_prompt="system from s3",
                    user_prompt=(
                        "The clip was recorded at: {{time}}\n\n"
                        "Bookings:\n{{bookings}}\n\n"
                        "Previous assistant notifications:\n{{previous_messages}}"
                    ),
                )
            )
        if bucket == "jp-bookings":
            return {"bookings": ["Adam until 24/03/26"]}
        raise AssertionError(f"Unexpected S3 lookup {bucket}/{key}")

    monkeypatch.setattr(api_module, "_load_json_document_from_s3", fake_load_json_document_from_s3)

    response_model = AnalyseResponse(
        ir_mode="unknown",
        parking_spot_status="unknown",
        number_plate=None,
        events_description="none",
        message_for_user="Current notification.",
        send_notification=False,
    )
    captured: dict[str, object] = {}

    async def fake_run(video_path: str | Path, user_prompt: str, system_prompt: str, config: RunConfig):
        captured["user_prompt"] = user_prompt
        captured["system_prompt"] = system_prompt
        return response_model

    monkeypatch.setattr(api_module, "run", fake_run)

    with TestClient(app) as client:
        repo = client.app.state.execution_repository
        repo.create_execution(
            execution_id="older-1",
            created_at="2026-03-15T09:00:00Z",
            updated_at="2026-03-15T09:00:00Z",
            status=api_module.ExecutionStatus.ANALYSED,
            source="eufy-bridge",
            event_metadata={},
            input_video_filename="old-1.mp4",
            input_video_content_type="video/mp4",
            input_video_size_bytes=1,
            device_serial_number="device-1",
            station_serial_number="station-1",
            event_start_time="2026-03-15T09:00:00Z",
            event_end_time="2026-03-15T09:00:10Z",
            video_upload_status=api_module.VideoUploadStatus.STORED,
            notification_status=api_module.NotificationStatus.SENT,
            config_snapshot={},
        )
        repo.update_execution(
            "older-1",
            updated_at="2026-03-15T09:01:00Z",
            analysis_result_json={"message_for_user": "First prior notification."},
        )
        repo.create_execution(
            execution_id="older-2",
            created_at="2026-03-15T10:00:00Z",
            updated_at="2026-03-15T10:00:00Z",
            status=api_module.ExecutionStatus.ANALYSED,
            source="eufy-bridge",
            event_metadata={},
            input_video_filename="old-2.mp4",
            input_video_content_type="video/mp4",
            input_video_size_bytes=1,
            device_serial_number="device-1",
            station_serial_number="station-1",
            event_start_time="2026-03-15T10:00:00Z",
            event_end_time="2026-03-15T10:00:10Z",
            video_upload_status=api_module.VideoUploadStatus.STORED,
            notification_status=api_module.NotificationStatus.SENT,
            config_snapshot={},
        )
        repo.update_execution(
            "older-2",
            updated_at="2026-03-15T10:01:00Z",
            analysis_result_json={"message_for_user": "Second prior notification."},
        )
        repo.create_execution(
            execution_id="older-3",
            created_at="2026-03-15T10:15:00Z",
            updated_at="2026-03-15T10:15:00Z",
            status=api_module.ExecutionStatus.ANALYSED,
            source="eufy-bridge",
            event_metadata={},
            input_video_filename="old-3.mp4",
            input_video_content_type="video/mp4",
            input_video_size_bytes=1,
            device_serial_number="device-1",
            station_serial_number="station-1",
            event_start_time="2026-03-15T10:15:00Z",
            event_end_time="2026-03-15T10:15:10Z",
            video_upload_status=api_module.VideoUploadStatus.STORED,
            notification_status=api_module.NotificationStatus.NOT_REQUESTED,
            config_snapshot={},
        )
        repo.update_execution(
            "older-3",
            updated_at="2026-03-15T10:16:00Z",
            analysis_result_json={"message_for_user": "This should not appear."},
        )

        response = client.post(
            "/analyse-video",
            files={"video": ("clip.mp4", b"video-bytes", "video/mp4")},
            data={"start_time": "2026-03-15T10:30:00Z"},
        )

    assert response.status_code == 200
    assert captured["system_prompt"] == "system from s3"
    assert "The clip was recorded at: 2026-03-15T10:30:00Z" in str(captured["user_prompt"])
    assert '"Adam until 24/03/26"' in str(captured["user_prompt"])
    assert "First prior notification." in str(captured["user_prompt"])
    assert "Second prior notification." in str(captured["user_prompt"])
    assert "This should not appear." not in str(captured["user_prompt"])


def test_analyse_video_does_not_fetch_optional_context_when_tokens_absent(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv(CONFIG_S3_BUCKET_ENV_VAR, "test-bucket")
    monkeypatch.setenv(VIDEO_S3_BUCKET_ENV_VAR, "test-video-bucket")
    monkeypatch.setenv(SQLITE_PATH_ENV_VAR, str(tmp_path / "app.db"))
    monkeypatch.delenv(TELEGRAM_BOT_TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(api_module, "_upload_video_to_s3", lambda **kwargs: None)

    s3_calls: list[tuple[str, str]] = []

    def fake_load_json_document_from_s3(bucket: str, key: str) -> dict:
        s3_calls.append((bucket, key))
        if bucket == "test-bucket":
            return json.loads(_config_json(user_prompt="user from s3"))
        raise AssertionError(f"Unexpected S3 lookup {bucket}/{key}")

    monkeypatch.setattr(api_module, "_load_json_document_from_s3", fake_load_json_document_from_s3)

    previous_messages_called = False

    def fake_get_recent_notification_messages(*, limit: int):
        nonlocal previous_messages_called
        previous_messages_called = True
        return []

    response_model = AnalyseResponse(
        ir_mode="unknown",
        parking_spot_status="unknown",
        number_plate=None,
        events_description="none",
        message_for_user="Nothing relevant happened at your property.",
        send_notification=False,
    )

    async def fake_run(video_path: str | Path, user_prompt: str, system_prompt: str, config: RunConfig):
        return response_model

    monkeypatch.setattr(api_module, "run", fake_run)

    with TestClient(app) as client:
        monkeypatch.setattr(
            client.app.state.execution_repository,
            "get_recent_notification_messages",
            fake_get_recent_notification_messages,
        )
        response = client.post(
            "/analyse-video",
            files={"video": ("clip.mp4", b"video-bytes", "video/mp4")},
            data={"start_time": "2026-03-15T10:00:00Z"},
        )

    assert response.status_code == 200
    assert s3_calls == [("test-bucket", "config/run_config.json")]
    assert previous_messages_called is False


def test_analyse_video_sends_telegram_notification_when_enabled(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv(CONFIG_S3_BUCKET_ENV_VAR, "test-bucket")
    monkeypatch.setenv(VIDEO_S3_BUCKET_ENV_VAR, "test-video-bucket")
    monkeypatch.setenv(VIDEO_S3_PREFIX_ENV_VAR, "videos")
    monkeypatch.setenv(SQLITE_PATH_ENV_VAR, str(tmp_path / "app.db"))
    monkeypatch.setenv(TELEGRAM_BOT_TOKEN_ENV_VAR, "bot-token")
    call_order: list[str] = []
    fake_service = AsyncMock()
    async def fake_send_video(**kwargs):
        call_order.append("notify")
    fake_service.send_video.side_effect = fake_send_video
    monkeypatch.setattr(
        api_module,
        "_load_json_document_from_s3",
        lambda bucket, key: json.loads(_config_json(telegram_chat_id="1234")),
    )
    monkeypatch.setattr(api_module, "_build_notification_service", lambda: fake_service)
    monkeypatch.setattr(api_module, "_upload_video_to_s3", lambda **kwargs: call_order.append("upload"))

    response_model = AnalyseResponse(
        ir_mode="unknown",
        parking_spot_status="unknown",
        number_plate=None,
        events_description="none",
        message_for_user="A car has arrived in your parking spot.",
        send_notification=True,
    )

    async def fake_run(video_path: str | Path, user_prompt: str, system_prompt: str, config: RunConfig):
        return response_model

    monkeypatch.setattr(api_module, "run", fake_run)

    with TestClient(app) as client:
        response = client.post(
            "/analyse-video",
            files={"video": ("clip.mp4", b"video-bytes", "video/mp4")},
        )

    assert response.status_code == 200
    fake_service.send_video.assert_awaited_once()
    kwargs = fake_service.send_video.await_args.kwargs
    assert kwargs["chat_id"] == "1234"
    assert kwargs["caption"] == "A car has arrived in your parking spot."
    assert not Path(kwargs["video_path"]).exists()
    assert call_order == ["notify", "upload"]


def test_analyse_video_persists_execution_record(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv(CONFIG_S3_BUCKET_ENV_VAR, "test-bucket")
    monkeypatch.setenv(VIDEO_S3_BUCKET_ENV_VAR, "test-video-bucket")
    monkeypatch.setenv(VIDEO_S3_PREFIX_ENV_VAR, "videos")
    monkeypatch.setenv(SQLITE_PATH_ENV_VAR, str(tmp_path / "app.db"))
    monkeypatch.setattr(
        api_module,
        "_load_json_document_from_s3",
        lambda bucket, key: json.loads(_config_json(user_prompt="user from s3")),
    )
    monkeypatch.delenv(TELEGRAM_BOT_TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(api_module, "_upload_video_to_s3", lambda **kwargs: None)

    response_model = AnalyseResponse(
        ir_mode="unknown",
        parking_spot_status="occupied",
        number_plate="AB12CDE",
        events_description="A car is parked.",
        message_for_user="A car is parked in your parking spot.",
        send_notification=False,
    )

    async def fake_run(video_path: str | Path, user_prompt: str, system_prompt: str, config: RunConfig):
        return response_model

    monkeypatch.setattr(api_module, "run", fake_run)

    with TestClient(app) as client:
        response = client.post(
            "/analyse-video",
            files={"video": ("clip.mp4", b"video-bytes", "video/mp4")},
            data={"device_serial_number": "device-1", "station_serial_number": "station-1"},
        )
        assert response.status_code == 200
        records = client.app.state.execution_repository

    row = records._connect().execute("SELECT status, device_serial_number, station_serial_number, analysis_result_json, config_snapshot_json, notification_status, input_video_s3_bucket, input_video_s3_key, video_upload_status, video_upload_error FROM executions").fetchone()
    assert row["status"] == "analysed"
    assert row["device_serial_number"] == "device-1"
    assert row["station_serial_number"] == "station-1"
    assert '"parking_spot_status": "occupied"' in row["analysis_result_json"]
    assert json.loads(row["config_snapshot_json"])["user_prompt"] == "user from s3"
    assert row["notification_status"] == "not_requested"
    assert row["input_video_s3_bucket"] == "test-video-bucket"
    assert row["input_video_s3_key"].startswith("videos/")
    assert row["video_upload_status"] == "stored"
    assert row["video_upload_error"] is None


def test_analyse_video_marks_notification_not_configured_when_requested_without_setup(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv(CONFIG_S3_BUCKET_ENV_VAR, "test-bucket")
    monkeypatch.setenv(VIDEO_S3_BUCKET_ENV_VAR, "test-video-bucket")
    monkeypatch.setenv(SQLITE_PATH_ENV_VAR, str(tmp_path / "app.db"))
    monkeypatch.setattr(
        api_module,
        "_load_json_document_from_s3",
        lambda bucket, key: json.loads(_config_json(telegram_chat_id="1234")),
    )
    monkeypatch.delenv(TELEGRAM_BOT_TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(api_module, "_upload_video_to_s3", lambda **kwargs: None)

    response_model = AnalyseResponse(
        ir_mode="unknown",
        parking_spot_status="unknown",
        number_plate=None,
        events_description="none",
        message_for_user="Something happened.",
        send_notification=True,
    )

    async def fake_run(video_path: str | Path, user_prompt: str, system_prompt: str, config: RunConfig):
        return response_model

    monkeypatch.setattr(api_module, "run", fake_run)

    with TestClient(app) as client:
        response = client.post(
            "/analyse-video",
            files={"video": ("clip.mp4", b"video-bytes", "video/mp4")},
        )
        assert response.status_code == 200
        records = client.app.state.execution_repository

    row = records._connect().execute("SELECT notification_status FROM executions").fetchone()
    assert row["notification_status"] == "not_configured"


def test_analyse_video_marks_video_upload_failed_without_overloading_execution_status(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv(CONFIG_S3_BUCKET_ENV_VAR, "test-bucket")
    monkeypatch.setenv(VIDEO_S3_BUCKET_ENV_VAR, "test-video-bucket")
    monkeypatch.setenv(SQLITE_PATH_ENV_VAR, str(tmp_path / "app.db"))
    monkeypatch.setattr(
        api_module,
        "_load_json_document_from_s3",
        lambda bucket, key: json.loads(_config_json()),
    )
    monkeypatch.delenv(TELEGRAM_BOT_TOKEN_ENV_VAR, raising=False)
    monkeypatch.setattr(api_module, "_upload_video_to_s3", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    response_model = AnalyseResponse(
        ir_mode="unknown",
        parking_spot_status="occupied",
        number_plate=None,
        events_description="A car is parked.",
        message_for_user="A car is parked in your parking spot.",
        send_notification=False,
    )

    async def fake_run(video_path: str | Path, user_prompt: str, system_prompt: str, config: RunConfig):
        return response_model

    monkeypatch.setattr(api_module, "run", fake_run)

    with TestClient(app) as client:
        response = client.post(
            "/analyse-video",
            files={"video": ("clip.mp4", b"video-bytes", "video/mp4")},
        )
        assert response.status_code == 200
        records = client.app.state.execution_repository

    row = records._connect().execute("SELECT status, video_upload_status, video_upload_error FROM executions").fetchone()
    assert row["status"] == "analysed"
    assert row["video_upload_status"] == "failed"
    assert row["video_upload_error"] == "Video upload failed"


def test_configure_logging_adds_root_handler(monkeypatch: MonkeyPatch) -> None:
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    original_level = root_logger.level
    try:
        root_logger.handlers = []
        root_logger.setLevel(logging.NOTSET)
        api_module.configure_logging()
        assert root_logger.handlers
        assert root_logger.level == logging.INFO
    finally:
        root_logger.handlers = original_handlers
        root_logger.setLevel(original_level)
