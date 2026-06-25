"""
state.py — Shared application state for cross-module coordination.

Breaks the circular import between sync_engine.py and diff_engine.py
by providing a neutral location for shared state variables.
Owns the PathLock mechanism, stop events, and local mutation tracking.
"""

import os
import threading

# ─── Graceful Shutdown ────────────────────────────────────────────────────────
_stop_event = threading.Event()


# ─── Path-Level Locks ─────────────────────────────────────────────────────────
_path_locks = {}
_path_locks_lock = threading.Lock()


class PathLock:
    """Thread-safe context manager to serialize operations on a specific file path."""
    def __init__(self, path: str):
        self.path = os.path.normpath(path)
        with _path_locks_lock:
            if self.path not in _path_locks:
                _path_locks[self.path] = threading.Lock()
            self.lock = _path_locks[self.path]

    def __enter__(self):
        self.lock.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.lock.release()
        except RuntimeError:
            pass


# ─── Local Mutation Tracking ──────────────────────────────────────────────────
_local_mutator = threading.local()
_local_mutator.active = False


def is_local_mutation_active() -> bool:
    return getattr(_local_mutator, "active", False)


def set_local_mutation(active: bool):
    _local_mutator.active = active


# ─── Downstream Sync Lock ─────────────────────────────────────────────────────
_downstream_sync_lock = threading.Lock()
