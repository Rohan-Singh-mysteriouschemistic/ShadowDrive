import time
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from diff_engine import process_single_file, run_full_scan
# NEW: Import the background sync loop
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
        if not event.is_directory: self._schedule("created", event.src_path)

    def on_modified(self, event):
        if not event.is_directory: self._schedule("modified", event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            with self._lock:
                timer = self._timers.pop(event.src_path, None)
                if timer: timer.cancel()
            process_single_file(event.src_path, "deleted")

    def on_moved(self, event):
        if not event.is_directory:
            with self._lock:
                timer = self._timers.pop(event.src_path, None)
                if timer: timer.cancel()
            process_single_file(event.src_path, "deleted")
            self._schedule("created", event.dest_path)

def main():
    watch_dir = Path(__file__).parent.parent / "watch_folder"
    watch_dir.mkdir(exist_ok=True)

    print("=" * 50)
    print("  ShadowDrive++ Client Agent (Week 3)")
    print("=" * 50)

    print("[STARTUP] Running full scan...")
    run_full_scan()
    
    # NEW: Start the Sync Engine in a separate background thread
    # This allows the client to watch files AND talk to the server at once.
    print("[STARTUP] Starting Network Sync Engine...")
    sync_thread = threading.Thread(target=start_sync_loop, daemon=True)
    sync_thread.start()

    event_handler = WatcherHandler()
    observer = Observer()
    observer.schedule(event_handler, str(watch_dir), recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Stopping...")
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()