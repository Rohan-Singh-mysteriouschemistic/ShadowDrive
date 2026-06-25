import os
import sys

import pytest

# Ensure Client-Logic is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


@pytest.fixture(autouse=True)
def temp_environment(tmp_path):
    import config

    _orig_db = config.DB_PATH
    _orig_watch = config.WATCH_DIR

    db_dir = tmp_path / "db"
    watch_dir = tmp_path / "watch"
    db_dir.mkdir(exist_ok=True)
    watch_dir.mkdir(exist_ok=True)

    config.DB_PATH = str(db_dir / "shadow.db")
    config.WATCH_DIR = str(watch_dir)

    yield

    config.DB_PATH = _orig_db
    config.WATCH_DIR = _orig_watch


@pytest.fixture
def sample_file():
    import config

    path = os.path.join(config.WATCH_DIR, "test_sample.txt")
    with open(path, "w") as f:
        f.write("ShadowDrive test content\n")
    return path
