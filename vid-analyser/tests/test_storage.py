from pathlib import Path

from vid_analyser.storage.local import LocalStorageProvider
from vid_analyser.storage.s3 import S3StorageProvider


def test_local_storage_provider_stores_video_under_fixed_videos_path(tmp_path: Path) -> None:
    source_path = tmp_path / "source.mp4"
    source_path.write_bytes(b"video-bytes")
    provider = LocalStorageProvider(root=tmp_path / "storage")

    reference = provider.store_video(
        execution_id="exec-1",
        filename="clip.mp4",
        source_path=source_path,
        content_type="video/mp4",
    )

    assert reference.provider == "local"
    assert reference.path == "videos/exec-1/clip.mp4"
    assert (tmp_path / "storage" / "videos" / "exec-1" / "clip.mp4").read_bytes() == b"video-bytes"


def test_s3_storage_provider_stores_video_under_fixed_videos_path(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeClient:
        def upload_file(self, filename, bucket, key, ExtraArgs=None):
            captured["filename"] = filename
            captured["bucket"] = bucket
            captured["key"] = key
            captured["extra_args"] = ExtraArgs

    monkeypatch.setattr("boto3.client", lambda service: FakeClient())
    provider = S3StorageProvider(bucket="video-bucket")

    reference = provider.store_video(
        execution_id="exec-1",
        filename="clip.mp4",
        source_path="/tmp/source.mp4",
        content_type="video/mp4",
    )

    assert reference.provider == "s3"
    assert reference.path == "video-bucket/videos/exec-1/clip.mp4"
    assert captured == {
        "filename": "/tmp/source.mp4",
        "bucket": "video-bucket",
        "key": "videos/exec-1/clip.mp4",
        "extra_args": {"ContentType": "video/mp4"},
    }
