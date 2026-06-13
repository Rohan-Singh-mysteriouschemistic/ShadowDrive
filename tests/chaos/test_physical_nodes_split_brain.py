import os
import time
import shutil
import subprocess
import threading
import pytest
from pathlib import Path
from sqlalchemy import create_engine, text

CLIENT_SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../Client-Logic"))
DB_URL = "postgresql://user:SDrive516477%23@localhost/shadowdrive"

@pytest.fixture
def dual_physical_env(tmp_path):
    client_a_dir = tmp_path / "ClientA"
    client_b_dir = tmp_path / "ClientB"
    shutil.copytree(CLIENT_SRC_DIR, client_a_dir)
    shutil.copytree(CLIENT_SRC_DIR, client_b_dir)
    
    watch_a = client_a_dir / "watch_folder"
    watch_b = client_b_dir / "watch_folder"
    watch_a.mkdir(exist_ok=True)
    watch_b.mkdir(exist_ok=True)
    
    yield (client_a_dir, watch_a), (client_b_dir, watch_b)

@pytest.mark.skip(reason="Requires live backend and valid PostgreSQL instance")
def test_physical_split_brain(dual_physical_env):
    """
    Simulates a physical split-brain scenario.
    Both devices edit the same file simultaneously while A is offline.
    Verifies that upon reconnection, a '(Conflicted copy)' is physically
    written to BOTH watch folders, and the DB reflects the conflict copy.
    """
    (client_a_dir, watch_a), (client_b_dir, watch_b) = dual_physical_env
    
    import socket
    def get_free_port():
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind(("",0))
        p = s.getsockname()[1]
        s.close()
        return str(p)

    env_a = os.environ.copy()
    env_a["WATCH_DIR"] = str(watch_a)
    env_a["DB_PATH"] = str(client_a_dir / "shadow.db")
    env_a["API_PORT"] = get_free_port()

    env_b = os.environ.copy()
    env_b["WATCH_DIR"] = str(watch_b)
    env_b["DB_PATH"] = str(client_b_dir / "shadow.db")
    env_b["API_PORT"] = get_free_port()

    username = "split_user_" + str(int(time.time()))
    email = f"{username}@test.com"
    password = "password123"

    # 1. Register User via Client A
    setup_script = client_a_dir / "setup_test_user.py"
    setup_script.write_text(f'''
import network_client, crypto_utils, config, sys, diff_engine
diff_engine.ensure_db()
username = sys.argv[1]
email = sys.argv[2]
password = sys.argv[3]
ok, msg = network_client.register_user(username, email, password)
if not ok: print(f"Register Failed: {{msg}}"); sys.exit(1)
ok, msg = network_client.login_user(email, password)
if not ok: print(f"Login Failed: {{msg}}"); sys.exit(1)
key = crypto_utils.derive_key("passphrase", email)
network_client._save_setting("encryption_key", key.hex())
network_client._save_setting("user_email", email)
print("Registered successfully")
''')
    proc_reg = subprocess.run(
        ["python", "setup_test_user.py", username, email, password],
        cwd=client_a_dir, env=env_a, text=True, capture_output=True
    )
    print("REGISTRATION A STDOUT:", proc_reg.stdout)
    assert proc_reg.returncode == 0, f"Registration A failed: {proc_reg.stdout} {proc_reg.stderr}"
    
    # Login via Client B
    setup_script_b = client_b_dir / "setup_test_user.py"
    setup_script_b.write_text(f'''
import network_client, crypto_utils, config, sys, diff_engine
diff_engine.ensure_db()
email = sys.argv[1]
password = sys.argv[2]
ok, msg = network_client.login_user(email, password)
if not ok: print(msg); sys.exit(1)
key = crypto_utils.derive_key("passphrase", email)
network_client._save_setting("encryption_key", key.hex())
network_client._save_setting("user_email", email)
print("Login successfully")
''')
    proc_login = subprocess.run(
        ["python", "setup_test_user.py", email, password],
        cwd=client_b_dir, env=env_b, text=True, capture_output=True
    )
    print("LOGIN B STDOUT:", proc_login.stdout)
    assert proc_login.returncode == 0, f"Login B failed: {proc_login.stdout} {proc_login.stderr}"

    b_log = open(client_b_dir / "b.log", "w")
    proc_b = subprocess.Popen(["python", "-u", "local_api.py"], cwd=client_b_dir, env=env_b, stdout=b_log, stderr=b_log, text=True)
    time.sleep(3)
    if proc_b.poll() is not None:
        out, err = proc_b.communicate()
        pytest.fail(f"API B crashed: {err} | {out}") # Wait for B to boot

    # Seed the initial file via B
    file_b = watch_b / "shared.txt"
    file_b.write_text("Base version")
    time.sleep(10) # Let it sync to server

    a_log = open(client_a_dir / "a.log", "w")
    proc_a = subprocess.Popen(["python", "-u", "local_api.py"], cwd=client_a_dir, env=env_a, stdout=a_log, stderr=a_log, text=True)
    time.sleep(10) # A boots and downloads
    file_a = watch_a / "shared.txt"
    
    if not file_a.exists():
        a_log.flush()
        b_log.flush()
        with open(client_a_dir / "a.log", "r") as f:
            a_out = f.read()
        with open(client_b_dir / "b.log", "r") as f:
            b_out = f.read()
        pytest.fail(f"A failed to download initial file.\nClient A log:\n{a_out}\n\nClient B log:\n{b_out}")
    
    # 2. Kill A, inject offline monkeypatch, restart A
    proc_a.terminate()
    proc_a.wait()
    
    network_client_path = client_a_dir / "network_client.py"
    code = network_client_path.read_text()
    hacked_code = code.replace(
        "def health_check() -> bool:",
        "def health_check() -> bool:\n    return False\n"
    )
    if "return False" not in hacked_code:
        pytest.fail("Monkeypatch for offline simulation failed to apply!")
    network_client_path.write_text(hacked_code)
    
    proc_a_offline = subprocess.Popen(["python", "local_api.py"], cwd=client_a_dir, env=env_a, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3) # A is now offline

    # 3. SPLIT BRAIN TORTURE
    def write_a():
        file_a.write_text("Edit from offline A")
        print(f"TEST: A wrote at {time.time()}")
    def write_b():
        file_b.write_text("Edit from online B")
        print(f"TEST: B wrote at {time.time()}")

    t1 = threading.Thread(target=write_a)
    t2 = threading.Thread(target=write_b)
    t1.start(); t2.start()
    t1.join(); t2.join()
    print(f"TEST: Wrote both at {time.time()}")
    
    time.sleep(10) # B syncs its edit. A sits offline with pending event.
    print(f"TEST: Sleep finished at {time.time()}")

    # 4. Reconnect A (Restore original code and restart)
    try:
        proc_a_offline.terminate()
        proc_a_offline.wait(timeout=2)
    except:
        pass
    
    network_client_path.write_text(code) # RESTORE ORIGINAL CODE

    a_online_log = open(client_a_dir / "a_online.log", "w")
    proc_a_online = subprocess.Popen(["python", "-u", "local_api.py"], cwd=client_a_dir, env=env_a, stdout=a_online_log, stderr=a_online_log, text=True)
    
    time.sleep(5)
    if proc_a_online.poll() is not None:
        a_online_log.flush()
        with open(client_a_dir / "a_online.log", "r") as f:
            out = f.read()
        pytest.fail(f"API A (online) crashed:\n{out}")

    try:
        # Wait for sync to propagate
        time.sleep(15)

        # 5. Assertions
        files_a = set(f.name for f in watch_a.iterdir() if f.is_file())
        files_b = set(f.name for f in watch_b.iterdir() if f.is_file())

        print("Client A files:", files_a)
        print("Client B files:", files_b)

        assert "shared.txt" in files_a
        assert "shared.txt" in files_b

        # Verify conflict copy exists
        conflict_files_a = [f for f in files_a if "(Conflicted copy)" in f]
        conflict_files_b = [f for f in files_b if "(Conflicted copy)" in f]

        if len(conflict_files_a) != 1 or len(conflict_files_b) != 1:
            a_online_log.flush()
            b_log.flush()
            with open(client_a_dir / "a_online.log", "r") as f:
                a_out = f.read()
            with open(client_b_dir / "b.log", "r") as f:
                b_out = f.read()
            pytest.fail(f"Conflict copy missing!\n\nClient A files: {files_a}\nClient B files: {files_b}\n\nA online log:\n{a_out}\n\nB log:\n{b_out}")
        engine = create_engine(DB_URL)
        with engine.connect() as conn:
            user_res = conn.execute(text(f"SELECT id FROM users WHERE email='{email}'")).fetchone()
            user_id = user_res[0]
            
            # Check that there is a file record for the conflicted copy
            conflict_name = conflict_files_a[0]
            db_res = conn.execute(text(f"SELECT id FROM files WHERE user_id={user_id} AND file_path='{conflict_name}'")).fetchone()
            assert db_res is not None, "Conflict copy missing from database"
            
            # Verify the version has is_conflict_copy = True
            file_id = db_res[0]
            v_res = conn.execute(text(f"SELECT is_conflict_copy FROM versions WHERE file_id={file_id} ORDER BY version_num DESC LIMIT 1")).fetchone()
            assert v_res[0] is True, "is_conflict_copy flag not set in database"

    finally:
        proc_b.terminate()
        proc_a_online.terminate()
        proc_b.wait()
        proc_a_online.wait()
