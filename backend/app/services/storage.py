import hashlib
from abc import ABC, abstractmethod
from pathlib import Path, PurePosixPath
from typing import Any

from app.core.config import Settings


class StorageError(RuntimeError):
    pass


class StorageProvider(ABC):
    @abstractmethod
    def put(self, user_id: int, object_key: str, content: bytes) -> None:
        raise NotImplementedError

    @abstractmethod
    def get(self, user_id: int, object_key: str) -> bytes:
        raise NotImplementedError

    @abstractmethod
    def delete(self, user_id: int, object_key: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def exists(self, user_id: int, object_key: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def generate_download_url(self, user_id: int, object_key: str) -> str | None:
        raise NotImplementedError

    @abstractmethod
    def healthcheck(self) -> bool:
        raise NotImplementedError

    @staticmethod
    def validate_key(user_id: int, object_key: str) -> None:
        path = PurePosixPath(object_key)
        expected = ("users", str(user_id), "resume-exports")
        if (
            path.is_absolute()
            or ".." in path.parts
            or path.parts[:3] != expected
            or len(path.parts) != 4
            or not path.name
        ):
            raise StorageError("Object key is outside the user's storage namespace")


class LocalStorageProvider(StorageProvider):
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def put(self, user_id: int, object_key: str, content: bytes) -> None:
        path = self._path(user_id, object_key)
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_bytes(content)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    def get(self, user_id: int, object_key: str) -> bytes:
        path = self._path(user_id, object_key)
        try:
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise StorageError("Stored object does not exist") from exc

    def delete(self, user_id: int, object_key: str) -> None:
        self._path(user_id, object_key).unlink(missing_ok=True)

    def exists(self, user_id: int, object_key: str) -> bool:
        return self._path(user_id, object_key).is_file()

    def generate_download_url(self, user_id: int, object_key: str) -> None:
        self.validate_key(user_id, object_key)
        return None

    def healthcheck(self) -> bool:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            return self.root.is_dir()
        except OSError:
            return False

    def _path(self, user_id: int, object_key: str) -> Path:
        self.validate_key(user_id, object_key)
        extension = PurePosixPath(object_key).suffix.lower()
        digest = hashlib.sha256(object_key.encode("utf-8")).hexdigest()
        candidate = (self.root / f"{digest}{extension}").resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise StorageError("Object path escaped the storage root") from exc
        return candidate


class S3CompatibleStorageProvider(StorageProvider):
    def __init__(
        self,
        settings: Settings,
        client: Any | None = None,
    ) -> None:
        self.bucket = settings.s3_bucket
        self.presigned_seconds = settings.s3_presigned_url_seconds
        if client is None:
            import boto3

            client = boto3.client(
                "s3",
                endpoint_url=settings.s3_endpoint_url or None,
                region_name=settings.s3_region,
                aws_access_key_id=settings.s3_access_key_id,
                aws_secret_access_key=settings.s3_secret_access_key,
            )
        self.client = client

    def put(self, user_id: int, object_key: str, content: bytes) -> None:
        self.validate_key(user_id, object_key)
        self.client.put_object(Bucket=self.bucket, Key=object_key, Body=content)

    def get(self, user_id: int, object_key: str) -> bytes:
        self.validate_key(user_id, object_key)
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=object_key)
            return response["Body"].read()
        except Exception as exc:
            raise StorageError("Stored object could not be read") from exc

    def delete(self, user_id: int, object_key: str) -> None:
        self.validate_key(user_id, object_key)
        self.client.delete_object(Bucket=self.bucket, Key=object_key)

    def exists(self, user_id: int, object_key: str) -> bool:
        self.validate_key(user_id, object_key)
        try:
            self.client.head_object(Bucket=self.bucket, Key=object_key)
            return True
        except Exception:
            return False

    def generate_download_url(self, user_id: int, object_key: str) -> str:
        self.validate_key(user_id, object_key)
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": object_key},
            ExpiresIn=self.presigned_seconds,
        )

    def healthcheck(self) -> bool:
        try:
            self.client.head_bucket(Bucket=self.bucket)
            return True
        except Exception:
            return False


def build_storage_provider(settings: Settings) -> StorageProvider:
    if settings.storage_backend == "s3":
        return S3CompatibleStorageProvider(settings)
    return LocalStorageProvider(settings.resume_export_dir)


# Backward-compatible internal name used by the Phase 5A test fixtures.
S3StorageProvider = S3CompatibleStorageProvider
