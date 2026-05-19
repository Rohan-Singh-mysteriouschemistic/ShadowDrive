"""
watcher.py — Real-time Operating System Filesystem Hook Listener
Monitors physical directory vectors and schedules debounced event processing tasks.
"""

import time
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import config
from diff_engine import process_single_file, run_full_scan
from sync_engine import start_sync_loop 

DEBOUNCE_DELAY = 2.0

class WatcherHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self._timers = {}
        self._lock = threading.Lock()

    def _schedule(self, event_type, path):
        with self._lock:
            existing = self._timers.get(path)
            if existing:
                existing.cancel()
            timer = threading.Timer(DEBOUNCE_DELAY, self._fire, args=(event_type, path))
            self._timers[path] = timer
            timer.start()

    def _fire(self, event_type, path):
        with self._lock:
            self._timers.pop(path, None)
        process_single_file(path, event_type)

    def on_created(self, event):
        if not event.is_directory: 
            self._schedule("created", event.src_path)

    def on_modified(self, event):
        if not event.is_directory: 
            self._schedule("modified", event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            with self._lock:
                timer = self._timers.pop(event.src_path, None)
                if timer: 
                    timer.cancel()
            process_single_file(event.src_path, "deleted")

    def on_moved(self, event):
        if not event.is_directory:
            with self._lock:
                timer = self._timers.pop(event.src_path, None)
                if timer: 
                    timer.cancel()
            process_single_file(event.src_path, "deleted")
            self._schedule("created", event.dest_path)

def main():
    # Coerce setup strings back into Path abstractions safely
    watch_path = Path(config.WATCH_DIR)
    watch_path.mkdir(parents=True, exist_ok=True)

    print("=" * 50)
    print("  ShadowDrive++ Client Agent (Week 6 Deployment)")
    print("=" * 50)

    print("[STARTUP] Running system structural file-tree scan...")
    run_full_scan()
    
    print("[STARTUP] Spawning Multi-threaded Sync Core Daemon...")
    sync_thread = threading.Thread(target=start_sync_loop, daemon=True)
    sync_thread.start()

    event_handler = WatcherHandler()
    observer = Observer()
    observer.schedule(event_handler, str(watch_path), recursive=True)
    observer.start()
    print(f"[STARTUP] Watcher active on resource path target: {watch_path}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Interrupted captured. Stopping worker handlers cleanly.")
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()