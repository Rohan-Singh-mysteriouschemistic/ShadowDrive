"""
watcher.py — Real-time Operating System Filesystem Hook Listener
Monitors physical directory vectors and schedules debounced event processing tasks.
"""

import os
import threading
import time
from pathlib import Path

import config
import pathspec
from diff_engine import process_single_file, run_full_scan
from loguru import logger
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# Load .shadowignore patterns
_ignore_spec = None

def _load_ignore_patterns():
    """Load .shadowignore patterns from watch_folder root."""
    global _ignore_spec
    ignore_file = os.path.join(config.WATCH_DIR, '.shadowignore')
    if os.path.exists(ignore_file):
        with open(ignore_file) as f:
            _ignore_spec = pathspec.PathSpec.from_lines('gitwildmatch', f)
    else:
        _ignore_spec = None

def is_ignored(path: str) -> bool:
    """Check if a path matches .shadowignore patterns."""
    if _ignore_spec is None:
        return False
    try:
        rel_path = os.path.relpath(path, config.WATCH_DIR)
        return _ignore_spec.match_file(rel_path)
    except ValueError:
        return False

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
                    logger.error("Error processing event for {}: {}", path, e)

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
            if is_ignored(event.src_path) or is_suppressed(event.src_path):
                return
            self._schedule("created", event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            if is_ignored(event.src_path) or is_suppressed(event.src_path):
                return
            self._schedule("modified", event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            if is_ignored(event.src_path) or is_suppressed(event.src_path):
                return
            self._scheduler.cancel(event.src_path)
            process_single_file(event.src_path, "deleted")

    def on_moved(self, event):
        if not event.is_directory:
            if is_ignored(event.src_path) or is_ignored(event.dest_path) or is_suppressed(event.src_path) or is_suppressed(event.dest_path):
                return
            self._scheduler.cancel(event.src_path)
            process_single_file(event.src_path, "deleted")
            self._schedule("created", event.dest_path)


_observer = None
_event_handler = None

def stop():
    global _observer, _event_handler
    logger.info("Stopping filesystem observer...")
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

    _load_ignore_patterns()

    logger.info("=" * 50)
    logger.info("  ShadowDrive++ Client Agent")
    logger.info("=" * 50)

    # Phase 2: Shift bootstrapping full scan to a background thread to prevent startup freezes
    logger.info("Spawning system structural file-tree scan in background...")
    scan_thread = threading.Thread(target=run_full_scan, daemon=True, name="BootstrapScanner")
    scan_thread.start()

    # Sync Core Daemon is now spawned by local_api.py to avoid duplicate runs
    _event_handler = WatcherHandler()
    _observer = Observer()
    _observer.schedule(_event_handler, str(watch_path), recursive=True)
    _observer.start()
    logger.info("Watcher active on resource path target: {}", watch_path)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Interrupted captured. Stopping worker handlers cleanly.")
        stop()

if __name__ == "__main__":
    main()
