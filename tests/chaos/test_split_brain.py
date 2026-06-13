import os
import time
import shutil
import subprocess
import threading
from pathlib import Path
import pytest

CLIENT_SRC_DIR = Path(__file__).resolve().parent.parent.parent / "Client-Logic"

def setup_client_env(tmp_path, name, email):
    """Copies Client-Logic to a temp dir and initializes it."""
    client_dir = tmp_path / name
    shutil.copytree(CLIENT_SRC_DIR, client_dir)
    watch_dir = client_dir / "watch_folder"
    watch_dir.mkdir(exist_ok=True)
    
    # Pre-seed the local DB or use a registration script?
    # For a true E2E, we would invoke the CLI to register and login.
    # To keep this script self-contained and focused on the chaos injection,
    # we simulate the python subprocess running the sync_engine.
    
    return client_dir, watch_dir

def run_sync_engine_daemon(client_dir):
    """Runs the sync_engine in a subprocess."""
    env = os.environ.copy()
    # We could set up a monkeypatch by injecting a sitecustomize.py or similar,
    # but for simplicity, we let it run natively.
    proc = subprocess.Popen(
        ["python", "-c", "import sync_engine; sync_engine.main()"],
        cwd=client_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    return proc

@pytest.fixture
def chaos_env(tmp_path):
    client_a_dir, watch_a = setup_client_env(tmp_path, "ClientA", "a@test.com")
    client_b_dir, watch_b = setup_client_env(tmp_path, "ClientB", "b@test.com")
    yield {"A": (client_a_dir, watch_a), "B": (client_b_dir, watch_b)}

@pytest.mark.skip(reason="Requires live backend and valid JWTs injected into shadow.db")
def test_split_brain_lww(chaos_env):
    """
    SUITE 1: The Split-Brain Simulator
    Tests Last-Write-Wins and Conflict creation.
    """
    client_a_dir, watch_a = chaos_env["A"]
    client_b_dir, watch_b = chaos_env["B"]
    
    # 1. The Injection: Create a monkeypatch file to simulate Device A offline
    monkeypatch_file = client_a_dir / "network_client.py"
    original_code = monkeypatch_file.read_text()
    
    # Force health_check to return False initially to simulate offline
    hacked_code = original_code.replace(
        "def health_check() -> bool:",
        "def health_check() -> bool:\n    if getattr(config, 'FORCE_OFFLINE', False): return False"
    )
    monkeypatch_file.write_text(hacked_code)
    
    # Start Device A in offline mode
    env_a = os.environ.copy()
    proc_a = subprocess.Popen(
        ["python", "-c", "import config; config.FORCE_OFFLINE=True; import sync_engine; sync_engine.main()"],
        cwd=client_a_dir, env=env_a
    )
    
    # Start Device B normally
    proc_b = run_sync_engine_daemon(client_b_dir)
    
    time.sleep(2) # Give engines time to boot
    
    # 2. The Torture: Write different strings to both devices exactly at the same time
    file_a = watch_a / "budget.txt"
    file_b = watch_b / "budget.txt"
    
    def write_file(path, content):
        with open(path, "w") as f:
            f.write(content)
            
    t1 = threading.Thread(target=write_file, args=(file_a, "Device A budget: 500"))
    t2 = threading.Thread(target=write_file, args=(file_b, "Device B budget: 1000"))
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    
    # Wait for B to sync its changes to the server
    time.sleep(5)
    
    # Restore A online. We kill A and restart it normally.
    proc_a.terminate()
    proc_a.wait()
    
    # Restart A online
    proc_a_online = run_sync_engine_daemon(client_a_dir)
    
    # 3. The Assertion: Wait for A to push its conflicting change
    time.sleep(10)
    
    files_a = list(watch_a.glob("*"))
    files_b = list(watch_b.glob("*"))
    
    file_names_a = {f.name for f in files_a}
    file_names_b = {f.name for f in files_b}
    
    # Both folders should eventually have 'budget.txt' and 'budget (Conflicted copy).txt'
    # due to the split-brain resolution.
    assert "budget.txt" in file_names_a
    assert any("Conflicted copy" in name for name in file_names_a), "Conflict file not created on A"
    
    assert "budget.txt" in file_names_b
    assert any("Conflicted copy" in name for name in file_names_b), "Conflict file not created on B"
    
    # Cleanup
    proc_a_online.terminate()
    proc_b.terminate()
