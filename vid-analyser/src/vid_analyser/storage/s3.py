from pathlib import Path

import boto3

from vid_analyser.storage.base import StorageProvider, VideoReference


class S3StorageProvider(StorageProvider):
    def __init__(self, *, bucket: str) -> None:
        self._bucket = bucket
        self._client = boto3.client("s3")

    def store_video(
        self,
        *,
        execution_id: str,
        filename: str | None,
        source_path: str | Path,
        content_type: str | None,
    ) -> VideoReference:
        key = _build_video_path(execution_id=execution_id, filename=filename)
        extra_args = {"ContentType": content_type} if content_type else None
        if extra_args:
            self._client.upload_file(str(source_path), self._bucket, key, ExtraArgs=extra_args)
        else:
            self._client.upload_file(str(source_path), self._bucket, key)
        return VideoReference(provider="s3", path=f"{self._bucket}/{key}")


def _build_video_path(*, execution_id: str, filename: str | None) -> str:
    safe_filename = filename or "video.mp4"
    return f"videos/{execution_id}/{safe_filename}"
