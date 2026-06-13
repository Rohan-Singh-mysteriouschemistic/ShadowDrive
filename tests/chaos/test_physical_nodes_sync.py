import os
import time
import shutil
import subprocess
import pytest
import sqlite3
from sqlalchemy import create_engine, text
import boto3

CLIENT_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../Client-Logic"))
DB_URL = "postgresql://user:SDrive516477%23@localhost/shadowdrive"
MINIO_URL = "http://localhost:9000"
MINIO_KEY = "admin"
MINIO_SECRET = "password"
MINIO_BUCKET = "shadowdrive"

@pytest.fixture
def physical_env(tmp_path):
    client_a_dir = tmp_path / "ClientA"
    shutil.copytree(CLIENT_SRC_DIR, client_a_dir)
    watch_a = client_a_dir / "watch_folder"
    watch_a.mkdir(exist_ok=True)
    db_path_a = client_a_dir / "shadow.db"
    
    yield client_a_dir, watch_a, db_path_a
    
    # Force kill any lingering processes from these dirs just in case
    # (In a real CI this would use psutil, but terminate() is usually enough)

def test_physical_sync_lifecycle(physical_env):
    """
    Physically tests User Registration, File Creation, and validates state 
    directly against Local SQLite, PostgreSQL, and MinIO.
    """
    client_a_dir, watch_a, db_path_a = physical_env
    env = os.environ.copy()
    env["WATCH_DIR"] = str(watch_a)
    env["DB_PATH"] = str(db_path_a)

    # 1. Register User A via a direct script to bypass getpass hanging on Windows
    username = "phys_user_" + str(int(time.time()))
    email = f"{username}@test.com"
    setup_script = client_a_dir / "setup_test_user.py"
    setup_script.write_text(f'''
import network_client, crypto_utils, config, sys, diff_engine
diff_engine.ensure_db()
username = sys.argv[1]
email = sys.argv[2]
password = sys.argv[3]
ok, msg = network_client.register_user(username, email, password)
if not ok: print(msg); sys.exit(1)
network_client.login_user(email, password)
key = crypto_utils.derive_key("passphrase", email)
network_client._save_setting("encryption_key", key.hex())
network_client._save_setting("user_email", email)
print("Registered successfully")
''')
    proc_reg = subprocess.run(
        ["python", "setup_test_user.py", username, email, "password123"],
        cwd=client_a_dir, env=env, text=True, capture_output=True
    )
    assert proc_reg.returncode == 0, f"Registration failed: {proc_reg.stdout} {proc_reg.stderr}"
    assert "Registered successfully" in proc_reg.stdout

    # 2. Start Local Agent (API + Watcher + Sync)
    # The local_api.py starts everything needed when booted
    proc_api = subprocess.Popen(
        ["python", "local_api.py"],
        cwd=client_a_dir, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    time.sleep(4) # Boot time
    if proc_api.poll() is not None:
        stdout, stderr = proc_api.communicate()
        pytest.fail(f"API crashed on boot: {stderr} | {stdout}")

    # 3. Create File
    file_path = watch_a / "test_phys.txt"
    file_content = "Physical content test."
    file_path.write_text(file_content)
    
    # Wait for watchdog debounce and sync engine processing
    time.sleep(12)

    try:
        # 4. Verify Local SQLite
        print(f"DB Path A: {db_path_a}")
        print(f"Files in Client A: {list(client_a_dir.glob('*'))}")
        conn = sqlite3.connect(db_path_a)
        c = conn.cursor()
        print("Tables:", c.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall())
        c.execute("SELECT hash FROM files WHERE file_path=?", (str(file_path),))
        row = c.fetchone()
        assert row is not None, "File not tracked in local shadow.db"
        conn.close()

        # 5. Verify PostgreSQL Database
        engine = create_engine(DB_URL)
        with engine.connect() as conn_pg:
            user_res = conn_pg.execute(text(f"SELECT id FROM users WHERE email='{email}'")).fetchone()
            assert user_res is not None, "User missing from Postgres"
            user_id = user_res[0]

            file_res = conn_pg.execute(text(f"SELECT id FROM files WHERE user_id={user_id} AND file_path='test_phys.txt' AND is_deleted=False")).fetchone()
            assert file_res is not None, "File missing from Postgres"
            file_id = file_res[0]

            version_res = conn_pg.execute(text(f"SELECT storage_path, upload_status FROM versions WHERE file_id={file_id} ORDER BY version_num DESC LIMIT 1")).fetchone()
            assert version_res is not None
            storage_path, status = version_res
            assert status == "complete", f"Upload status in DB is {status}"

        # 6. Verify MinIO Physical Bytes
        s3 = boto3.client(
            "s3", endpoint_url=MINIO_URL, aws_access_key_id=MINIO_KEY,
            aws_secret_access_key=MINIO_SECRET, config=boto3.session.Config(signature_version="s3v4")
        )
        try:
            response = s3.get_object(Bucket=MINIO_BUCKET, Key=storage_path)
            data = response["Body"].read()
            assert len(data) > 0, "MinIO object is empty"
        except Exception as e:
            pytest.fail(f"MinIO verification failed: {e}")
            
    finally:
        proc_api.terminate()
        proc_api.wait()
