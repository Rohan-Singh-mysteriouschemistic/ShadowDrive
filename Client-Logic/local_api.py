import os
import shutil
import threading

import config
import crypto_utils
import event_listener
import network_client
import uvicorn
import watcher
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from loguru import logger
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/auth/token")
def get_token():
    token = network_client._get_token()
    if not token:
        raise HTTPException(status_code=404, detail="No active session found.")
    return {"access_token": token}

@app.get("/api/config")
def get_config():
    return {"server_url": config.SERVER_BASE_URL}


class AuthRequest(BaseModel):
    email: str
    password: str
    username: str = ""
    passphrase: str = ""

def _setup_encryption(email: str, passphrase: str):
    key = crypto_utils.derive_key(passphrase, email)
    network_client._save_setting("encryption_key", key.hex())
    network_client._save_setting("user_email", email)
    config.encryption_key = key
    logger.success("Encryption key derived and stored locally.")

_start_lock = threading.Lock()

def _start_watcher_if_needed():
    # Only start watcher if it hasn't been started, protected by a mutex
    with _start_lock:
        if getattr(app.state, "watcher_started", False):
            return
        app.state.watcher_started = True
        config.sync_suspended = False

        def run_watcher():
            try:
                watcher.main()
            except Exception as e:
                logger.error("Watcher failed to start: {}", e)

        def run_sync_engine():
            try:
                import sync_engine
                sync_engine.main()
            except Exception as e:
                logger.error("Sync engine failed to start: {}", e)

        t1 = threading.Thread(target=run_watcher, daemon=True)
        t1.start()

        t2 = threading.Thread(target=run_sync_engine, daemon=True)
        t2.start()

        logger.info("Watcher and Sync Engine daemon started by UI.")


def _restart_services(email: str):
    """Safely shuts down existing background sync/watchers and restarts them under new user paths."""
    import time
    import sync_engine
    import watcher
    import diff_engine
    import event_listener

    logger.info("Restarting background services for user: {}", email)
    
    # 1. Stop existing services
    sync_engine.stop_sync_loop()
    watcher.stop()
    
    # Give threads a brief window to terminate
    time.sleep(1.0)
    
    # 2. Update config paths
    config.update_user_config(email)
    
    # Initialize the schema inside the new SQLite db file
    diff_engine.ensure_db()
    
    # 3. Reset state & start fresh loops
    with _start_lock:
        app.state.watcher_started = False
        
    _start_watcher_if_needed()
    
    # Re-run SSE client connection
    event_listener.start()
    logger.info("Background services successfully restarted under isolated user context.")


@app.post("/api/auth/login")
def login(req: AuthRequest):
    if not req.email or not req.password:
        raise HTTPException(status_code=400, detail="Email and password required.")

    # Initialize config paths and DB first so credentials/device ID go to correct DB
    config.update_user_config(req.email)
    from diff_engine import ensure_db
    ensure_db()

    # Prevent cross-user device conflicts by clearing old device ID on user change
    network_client._clear_device()

    success, msg = network_client.login_user(req.email, req.password)
    if not success:
        raise HTTPException(status_code=401, detail=msg)

    # Persist the active user email securely
    network_client._save_secure_setting("user_email", req.email)

    # Restart services under isolated user context
    _restart_services(req.email)

    token = network_client._get_token()
    if req.passphrase:
        _setup_encryption(req.email, req.passphrase)

    return {"status": "success", "access_token": token, "message": "Login complete and watcher started."}

@app.post("/api/auth/register")
def register(req: AuthRequest):
    if not req.email or not req.password or not req.username:
        raise HTTPException(status_code=400, detail="Username, email, and password required.")

    # Initialize config paths and DB first so credentials/device ID go to correct DB
    config.update_user_config(req.email)
    from diff_engine import ensure_db
    ensure_db()

    network_client._clear_device()

    success, msg = network_client.register_user(req.username, req.email, req.password)
    if not success:
        raise HTTPException(status_code=400, detail=msg)

    # Auto-login after registration
    login_ok, login_msg = network_client.login_user(req.email, req.password)
    if not login_ok:
        raise HTTPException(status_code=401, detail="Registration succeeded but auto-login failed: " + login_msg)

    network_client._save_secure_setting("user_email", req.email)
    _restart_services(req.email)

    token = network_client._get_token()
    if req.passphrase:
        _setup_encryption(req.email, req.passphrase)

    return {"status": "success", "access_token": token, "message": "Registration complete and watcher started."}

@app.post("/api/upload")
def handle_ui_upload(file: UploadFile = File(...)):
    """Saves file from UI to the watch_folder so the sync engine picks it up."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    watch_dir = config.WATCH_DIR
    if not os.path.exists(watch_dir):
        os.makedirs(watch_dir, exist_ok=True)

    file_path = os.path.normpath(os.path.join(watch_dir, file.filename))

    # Suppress watchdog events during the write to avoid 0-byte or partial triggers
    watcher.suppress_path(file_path)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        # After write completes, manually trigger file registration
        from diff_engine import process_single_file
        process_single_file(file_path, "created")

    return {"status": "success", "message": "File added to local watcher."}

@app.get("/api/download")
def handle_ui_download(file_path: str):
    """Serves the local plaintext file for the UI editor."""
    watch_dir = config.WATCH_DIR
    full_path = os.path.join(watch_dir, file_path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found locally. Ensure desktop client has synced it.")
    return FileResponse(full_path)

@app.get("/api/transfers")
def get_transfers():
    """Returns current transfer queue status for the UI."""
    try:
        import sqlite3
        from uploader import get_active_transfers_progress, _in_flight_events

        transfers = []

        conn = sqlite3.connect(config.DB_PATH, timeout=5.0)
        cur = conn.cursor()

        cur.execute("""
            SELECT id, event_type, file_path, hash, is_synced, timestamp 
            FROM events 
            ORDER BY id DESC 
            LIMIT 50
        """)

        progress_map = get_active_transfers_progress()

        for row in cur.fetchall():
            event_id, event_type, file_path, file_hash, is_synced, timestamp = row
            filename = os.path.basename(file_path)
            size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

            if is_synced == 1:
                progress = 100
                status = "complete"
            else:
                job_progress = progress_map.get(event_id)
                if job_progress:
                    progress = job_progress["progress"]
                    status = "active" if event_id in _in_flight_events else "queued"
                else:
                    progress = 0
                    status = "queued"

            transfers.append({
                "id": str(event_id),
                "filename": filename,
                "direction": "upload" if event_type != "deleted" else "delete",
                "progress": progress,
                "speed": "",
                "status": status,
                "size": f"{size / 1024:.1f} KB",
                "transferred": f"{(size * progress / 100) / 1024:.1f} KB" if size > 0 else "0 KB",
            })

        conn.close()
        return {"transfers": transfers}
    except Exception as e:
        return {"transfers": [], "error": str(e)}

@app.post("/api/auth/logout")
def logout():
    logger.info("User requested logout. Shutting down services and clearing session keys...")
    try:
        import sync_engine
        sync_engine.stop_sync_loop()
    except Exception as e:
        logger.error("Error stopping sync engine: {}", e)

    try:
        import watcher
        watcher.stop()
    except Exception as e:
        logger.error("Error stopping watcher: {}", e)

    with _start_lock:
        app.state.watcher_started = False

    # Clear secure token and active user email
    network_client._save_secure_setting("jwt_token", None)
    network_client._save_secure_setting("user_email", None)
    config.encryption_key = None
    config.sync_suspended = True
    return {"status": "success", "message": "Logged out."}

@app.on_event("startup")
def startup_event():
    import logging_setup
    logging_setup.setup_logging()
    
    # Load last active user email on startup to initialize paths correctly
    email = network_client._get_secure_setting("user_email")
    if email:
        logger.info("Initializing configurations on startup for last active user: {}", email)
        config.update_user_config(email)

    token = network_client._get_token()
    if token:
        logger.info("Active token found on startup.")
        key_hex = network_client._get_setting("encryption_key")
        if key_hex:
            config.encryption_key = bytes.fromhex(key_hex)
            logger.info("Encryption key loaded from local database.")
        _start_watcher_if_needed()
        event_listener.start()

@app.on_event("shutdown")
def shutdown_event():
    logger.info("Initiating graceful shutdown of background services...")
    try:
        import sync_engine
        sync_engine.stop_sync_loop()
    except Exception as e:
        logger.error("Error stopping sync engine: {}", e)

    try:
        import watcher
        watcher.stop()
    except Exception as e:
        logger.error("Error stopping watcher: {}", e)
    logger.info("Graceful shutdown complete.")

if __name__ == "__main__":
    port = int(os.environ.get("API_PORT", 8001))
    host = os.environ.get("API_HOST", "127.0.0.1")
    uvicorn.run(app, host=host, port=port)
