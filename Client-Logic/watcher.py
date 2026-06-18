"""
watcher.py — Real-time Operating System Filesystem Hook Listener
Monitors physical directory vectors and schedules debounced event processing tasks.
"""

import time
import os
import threading
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import config
from diff_engine import process_single_file, run_full_scan

DEBOUNCE_DELAY = 2.0

# Thread-safe set of paths to suppress.
_suppressed_paths: set[str] = set()
_suppression_lock = threading.Lock()
_suppression_ttl: dict[str, float] = {}

SUPPRESSION_WINDOW_SECONDS = 5.0

def suppress_path(path: str):
    """Mark a path for suppression. The watchdog will ignore events
    for this path for the next SUPPRESSION_WINDOW_SECONDS seconds."""
    normalized = os.path.normpath(path)
    with _suppression_lock:
        _suppressed_paths.add(normalized)
        _suppression_ttl[normalized] = time.time() + SUPPRESSION_WINDOW_SECONDS

def is_suppressed(path: str) -> bool:
    """Check if a path is currently suppressed."""
    normalized = os.path.normpath(path)
    with _suppression_lock:
        if normalized not in _suppressed_paths:
            return False
        if time.time() > _suppression_ttl.get(normalized, 0):
            _suppressed_paths.discard(normalized)
            _suppression_ttl.pop(normalized, None)
            return False
        return True


class DebounceScheduler(threading.Thread):
    """
    A single-threaded scheduler that manages debouncing of filesystem events,
    completely replacing the resource-heavy threading.Timer (OS thread per event) model.
    """
    def __init__(self):
        super().__init__(daemon=True, name="watcher-debounce-scheduler")
        self._events = {}
        self._lock = threading.Lock()
        self._wakeup = threading.Event()
        self._running = True

    def schedule(self, path: str, event_type: str, delay: float = 2.0):
        normalized = os.path.normpath(path)
        fire_time = time.time() + delay
        with self._lock:
            self._events[normalized] = (fire_time, event_type)
        self._wakeup.set()

    def cancel(self, path: str):
        normalized = os.path.normpath(path)
        with self._lock:
            self._events.pop(normalized, None)

    def stop(self):
        self._running = False
        self._wakeup.set()

    def run(self):
        while self._running:
            now = time.time()
            next_wake = None
            events_to_fire = []
            
            with self._lock:
                for path, (fire_time, event_type) in list(self._events.items()):
                    if now >= fire_time:
                        events_to_fire.append((path, event_type))
                        self._events.pop(path)
                    else:
                        if next_wake is None or fire_time < next_wake:
                            next_wake = fire_time
            
            # Fire any events that are due
            for path, event_type in events_to_fire:
                try:
                    process_single_file(path, event_type)
                except Exception as e:
                    print(f"[WATCHER ERROR] Error processing event for {path}: {e}")
            
            # Sleep until the next event is due, or until nudged
            if next_wake is not None:
                sleep_time = max(0.01, next_wake - time.time())
                self._wakeup.wait(timeout=sleep_time)
            else:
                self._wakeup.wait()
                
            self._wakeup.clear()


class WatcherHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self._scheduler = DebounceScheduler()
        self._scheduler.start()

    def _schedule(self, event_type, path):
        self._scheduler.schedule(path, event_type, DEBOUNCE_DELAY)

    def on_created(self, event):
        if not event.is_directory: 
            if is_suppressed(event.src_path):
                return
            self._schedule("created", event.src_path)

    def on_modified(self, event):
        if not event.is_directory: 
            if is_suppressed(event.src_path):
                return
            self._schedule("modified", event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            if is_suppressed(event.src_path):
                return
            self._scheduler.cancel(event.src_path)
            process_single_file(event.src_path, "deleted")

    def on_moved(self, event):
        if not event.is_directory:
            if is_suppressed(event.src_path) or is_suppressed(event.dest_path):
                return
            self._scheduler.cancel(event.src_path)
            process_single_file(event.src_path, "deleted")
            self._schedule("created", event.dest_path)


_observer = None
_event_handler = None

def stop():
    global _observer, _event_handler
    print("[WATCHER] Stopping filesystem observer...")
    if _event_handler and _event_handler._scheduler:
        _event_handler._scheduler.stop()
    if _observer:
        _observer.stop()
        try:
            _observer.join(timeout=3.0)
        except Exception:
            pass

def main():
    global _observer, _event_handler
    # Coerce setup strings back into Path abstractions safely
    watch_path = Path(config.WATCH_DIR)
    watch_path.mkdir(parents=True, exist_ok=True)

    print("=" * 50)
    print("  ShadowDrive++ Client Agent (Week 6 Deployment)")
    print("=" * 50)

    # Phase 2: Shift bootstrapping full scan to a background thread to prevent startup freezes
    print("[STARTUP] Spawning system structural file-tree scan in background...")
    scan_thread = threading.Thread(target=run_full_scan, daemon=True, name="BootstrapScanner")
    scan_thread.start()
    
    # Sync Core Daemon is now spawned by local_api.py to avoid duplicate runs
    _event_handler = WatcherHandler()
    _observer = Observer()
    _observer.schedule(_event_handler, str(watch_path), recursive=True)
    _observer.start()
    print(f"[STARTUP] Watcher active on resource path target: {watch_path}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Interrupted captured. Stopping worker handlers cleanly.")
        stop()

if __name__ == "__main__":
    main()