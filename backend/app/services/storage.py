"""Object storage abstraction (local filesystem or S3/MinIO).

Uploads, rendered slide images, and export artifacts go through this layer so
the app can run on disk in dev/tests and on MinIO/S3 in production without
touching call sites. ``materialize`` yields a local path for libraries that
need a real file (python-pptx, PyMuPDF).
"""
from __future__ import annotations

import shutil
import tempfile
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Iterator

from app.core.config import get_settings


class Storage:
    def save_bytes(self, key: str, data: bytes) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def save_file(self, key: str, path: str | Path) -> None:  # pragma: no cover
        raise NotImplementedError

    def read_bytes(self, key: str) -> bytes:  # pragma: no cover
        raise NotImplementedError

    def exists(self, key: str) -> bool:  # pragma: no cover
        raise NotImplementedError

    def delete(self, key: str) -> None:  # pragma: no cover
        raise NotImplementedError

    @contextmanager
    def materialize(self, key: str) -> Iterator[Path]:  # pragma: no cover
        raise NotImplementedError


class LocalStorage(Storage):
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / key

    def save_bytes(self, key: str, data: bytes) -> None:
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)

    def save_file(self, key: str, path: str | Path) -> None:
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)

    def read_bytes(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    @contextmanager
    def materialize(self, key: str) -> Iterator[Path]:
        yield self._path(key)


class S3Storage(Storage):
    def __init__(self, settings) -> None:
        import boto3  # imported lazily so local mode needs no boto3

        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint or None,
            aws_access_key_id=settings.s3_access_key or None,
            aws_secret_access_key=settings.s3_secret_key or None,
            region_name=settings.s3_region,
            use_ssl=settings.s3_secure,
        )

    def save_bytes(self, key: str, data: bytes) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)

    def save_file(self, key: str, path: str | Path) -> None:
        self.client.upload_file(str(path), self.bucket, key)

    def read_bytes(self, key: str) -> bytes:
        obj = self.client.get_object(Bucket=self.bucket, Key=key)
        return obj["Body"].read()

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    @contextmanager
    def materialize(self, key: str) -> Iterator[Path]:
        data = self.read_bytes(key)
        suffix = Path(key).suffix
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        try:
            tmp.write(data)
            tmp.close()
            yield Path(tmp.name)
        finally:
            Path(tmp.name).unlink(missing_ok=True)


@lru_cache
def get_storage() -> Storage:
    settings = get_settings()
    if settings.storage_backend == "s3":
        return S3Storage(settings)
    base = Path("tests_tmp" if settings.environment == "test" else settings.storage_dir)
    return LocalStorage(base / "objects")
