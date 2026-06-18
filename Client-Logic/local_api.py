from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import threading
import uvicorn
import sys
import os

import network_client
import crypto_utils
import config
import watcher
import event_listener

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for local UI
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    print("[OK] Encryption key derived and stored locally.")

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
                print(f"[ERROR] Watcher failed to start: {e}")
                
        def run_sync_engine():
            try:
                import sync_engine
                sync_engine.main()
            except Exception as e:
                print(f"[ERROR] Sync engine failed to start: {e}")
                
        t1 = threading.Thread(target=run_watcher, daemon=True)
        t1.start()
        
        t2 = threading.Thread(target=run_sync_engine, daemon=True)
        t2.start()
        
        print("[INFO] Watcher and Sync Engine daemon started by UI.")


@app.post("/api/auth/login")
def login(req: AuthRequest):
    if not req.email or not req.password:
        raise HTTPException(status_code=400, detail="Email and password required.")
    
    success, msg = network_client.login_user(req.email, req.password)
    if not success:
        raise HTTPException(status_code=401, detail=msg)
        
    token = network_client._get_token()
    if req.passphrase:
        _setup_encryption(req.email, req.passphrase)
        
    _start_watcher_if_needed()
    return {"status": "success", "access_token": token, "message": "Login complete and watcher started."}

@app.post("/api/auth/register")
def register(req: AuthRequest):
    if not req.email or not req.password or not req.username:
        raise HTTPException(status_code=400, detail="Username, email, and password required.")
        
    success, msg = network_client.register_user(req.username, req.email, req.password)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
        
    # Auto-login after registration
    login_ok, login_msg = network_client.login_user(req.email, req.password)
    if not login_ok:
        raise HTTPException(status_code=401, detail="Registration succeeded but auto-login failed: " + login_msg)
        
    token = network_client._get_token()
    if req.passphrase:
        _setup_encryption(req.email, req.passphrase)
        
    _start_watcher_if_needed()
    return {"status": "success", "access_token": token, "message": "Registration complete and watcher started."}

from fastapi import UploadFile, File
import os
import shutil

@app.post("/api/upload")
def handle_ui_upload(file: UploadFile = File(...)):
    """Saves file from UI to the watch_folder so the sync engine picks it up."""
    watch_dir = config.WATCH_DIR
    if not os.path.exists(watch_dir):
        os.makedirs(watch_dir, exist_ok=True)
        
    file_path = os.path.join(watch_dir, file.filename)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return {"status": "success", "message": "File added to local watcher."}

from fastapi.responses import FileResponse
@app.get("/api/download")
def handle_ui_download(file_path: str):
    """Serves the local plaintext file for the UI editor."""
    watch_dir = config.WATCH_DIR
    full_path = os.path.join(watch_dir, file_path)
    if not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found locally. Ensure desktop client has synced it.")
    return FileResponse(full_path)

@app.on_event("startup")
def startup_event():
    import logging_setup
    logging_setup.setup_logging()
    token = network_client._get_token()
    if token:
        print("[INFO] Active token found on startup.")
        key_hex = network_client._get_setting("encryption_key")
        if key_hex:
            config.encryption_key = bytes.fromhex(key_hex)
            print("[INFO] Encryption key loaded from local database.")
        _start_watcher_if_needed()
        event_listener.start()

@app.on_event("shutdown")
def shutdown_event():
    print("[INFO] Initiating graceful shutdown of background services...")
    try:
        import sync_engine
        sync_engine.stop_sync_loop()
    except Exception as e:
        print(f"Error stopping sync engine: {e}")
        
    try:
        import watcher
        watcher.stop()
    except Exception as e:
        print(f"Error stopping watcher: {e}")
    print("[INFO] Graceful shutdown complete.")

if __name__ == "__main__":
    port = int(os.environ.get("API_PORT", 8001))
    uvicorn.run(app, host="127.0.0.1", port=port)
