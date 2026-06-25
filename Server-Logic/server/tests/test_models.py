from app import models
from app.models import UploadStatus


class TestVersionModel:
    def test_version_has_announced_at(self, db_session):
        version = models.Version(
            file_id=1,
            version_num=1,
            hash="abc123",
            size_bytes=100,
            storage_path="test/path",
        )
        assert hasattr(version, "announced_at")
        assert version.announced_at is None

    def test_version_has_file_relationship(self, db_session):
        user = models.User(
            username="reluser", email="rel@test.com", password_hash="pwd"
        )
        db_session.add(user)
        db_session.commit()

        file_record = models.File(user_id=user.id, file_path="reltest.txt")
        db_session.add(file_record)
        db_session.commit()

        version = models.Version(
            file_id=file_record.id,
            version_num=1,
            hash="abc",
            size_bytes=100,
            storage_path="test/path",
        )
        db_session.add(version)
        db_session.commit()

        assert version.file.id == file_record.id
        assert version.file.file_path == "reltest.txt"

    def test_upload_status_exists(self, db_session):
        version = models.Version(
            file_id=1,
            version_num=1,
            hash="abc",
            size_bytes=100,
            storage_path="test/path",
        )
        assert hasattr(version, "upload_status")


class TestFileModel:
    def test_file_has_is_deleted(self, db_session):
        file_record = models.File(
            user_id=1,
            file_path="deletable.txt",
        )
        assert hasattr(file_record, "is_deleted")
        db_session.add(file_record)
        db_session.flush()
        assert file_record.is_deleted is False
