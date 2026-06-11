# ShadowDrive++ Master Blueprint — Part 2
## Triadic Fault-Tolerant Synchronization System
### From Fragmented Prototype to FAANG-Level Distributed Sync

> **Author Role:** Principal Staff Engineer & Distributed Systems Architect
> **Persona:** First-principles, bottom-up, build-it-from-scratch-then-use-the-library.
> **Date:** Week 9+ Specification
> **Scope:** Client-Logic ↔ Server-Logic ↔ shadowdrive-ui (the complete triad)

---

## Table of Contents

1. [Section 1: Triadic State Synchronization Protocol](#section-1-triadic-state-synchronization-protocol)
2. [Section 2: In-Place Editing & Infinite Loop Prevention](#section-2-in-place-editing--infinite-loop-prevention)
3. [Section 3: Zero-Failure Network Resilience Engine](#section-3-zero-failure-network-resilience-engine)
4. [Section 4: Feature Coverage Matrix — Every Operation, Every Node](#section-4-feature-coverage-matrix)
5. [Section 5: 100-Action Chaos Engineering Test Plan](#section-5-100-action-chaos-engineering-test-plan)

---

## Architectural Preamble — Understanding What We Have

Before we fix anything, let's be honest about what's under the hood right now. The current system has three actors that barely talk to each other:

```
┌──────────────────────┐        HTTP REST         ┌──────────────────────┐
│   Client-Logic       │ ─────────────────────── → │   Server-Logic       │
│   (Python Agent)     │ ← ───────────────────── ─ │   (FastAPI + PG)     │
│                      │                            │                      │
│   shadow.db (SQLite) │                            │   PostgreSQL + MinIO │
│   watch_folder/      │                            │                      │
└──────────┬───────────┘                            └──────────┬───────────┘
           │ localhost:8001                                      │ localhost:8000
           │                                                     │
           │              ┌──────────────────────┐              │
           └───────────── │   shadowdrive-ui      │ ─────────── ┘
                          │   (React SPA)         │
                          │   localhost:5173       │
                          └──────────────────────┘
```

**The core problem is not bugs — it's the absence of a real-time state bus.** The UI polls `/sync/metadata` once on mount. The client agent polls `/sync/metadata/diff` every 30 seconds. Neither is notified when the other acts. This is fundamentally broken for a sync system.

---

## Section 1: Triadic State Synchronization Protocol

### 1.1 — The Problem (First Principles)

Let's enumerate exactly what goes wrong today, line by line:

| # | Failure Mode | Root Cause | File(s) |
|---|-------------|-----------|---------|
| 1 | **UI stays stale after client uploads** | `FileExplorer.tsx:39-64` — `useEffect` runs ONCE on mount. No polling, no WebSocket, no SSE. After the client agent uploads a file, the UI has zero mechanism to discover it. | `FileExplorer.tsx` |
| 2 | **Client agent ignores UI uploads** | `local_api.py:105-116` — UI drops files into `watch_folder`. BUT: `watcher.py:33-43` uses watchdog's `FileSystemEventHandler`. On Windows, watchdog's `Observer` sometimes misses writes from other processes due to `ReadDirectoryChangesW` buffering. Even when it catches the event, `sync_engine.py:95-120` may be mid-cycle and the file gets picked up on the NEXT 30-second poll. | `local_api.py`, `watcher.py`, `sync_engine.py` |
| 3 | **UI edit → infinite upload loop** | `FileExplorer.tsx:344-369` — "Save Changes" calls `uploadFile()` which writes to `watch_folder` via `local_api.py:105-116`. Watchdog fires. `sync_engine.py` announces and uploads. Server creates a new version. On the NEXT diff poll, the client sees the new version and downloads it (same content). Download triggers watchdog again. Loop. | `FileExplorer.tsx`, `local_api.py`, `sync_engine.py` |
| 4 | **Delete from UI doesn't reach client** | `api.ts:52-56` calls `DELETE /sync/file/{id}` which sets `is_deleted=True` on the server (line `sync.py:442`). But the client agent only discovers deletes via `/sync/metadata/diff` which returns `deleted_files` (line `sync.py:568`). The client's `sync_engine.py` does process `deleted_files`, BUT it doesn't remove the local file from `watch_folder` — it only removes the record from `shadow.db`. The file persists on disk, watchdog sees it's still there, and the next sync cycle re-announces it. | `sync.py:424-444`, `sync_engine.py` |
| 5 | **No event sourcing** | State changes happen in the DB but nobody broadcasts them. The server has no concept of "this just changed, tell everyone." | `main.py` (no WS) |

### 1.2 — The Solution: Server-Sent Events (SSE) State Bus

WebSockets are bidirectional. We don't need that — the server is the authority, and it pushes. The clients (both the Python agent and the React UI) subscribe. SSE is the right primitive: unidirectional, auto-reconnecting, works through proxies, no upgrade handshake, built into every browser and trivial in Python.

**Why not WebSocket?** Because WebSockets require connection state management, heartbeats, reconnection logic, and binary framing. SSE gives us everything we need for push notifications with zero of that complexity. The client-to-server direction already has REST endpoints. Don't over-engineer the push channel.

#### 1.2.1 — Server: New SSE Endpoint

**New file: `Server-Logic/server/app/routers/events.py`**

```python
"""
events.py — Server-Sent Events (SSE) real-time state bus.

Every mutation endpoint (announce, upload complete, delete, conflict resolve)
publishes an event to an in-memory broadcast channel.  Connected clients
(UI, agent) receive the event within milliseconds.

Architecture:
    POST /sync/announce  ──→  DB mutation  ──→  publish_event()  ──→  SSE stream
    POST /sync/upload    ──→  DB mutation  ──→  publish_event()  ──→  SSE stream
    DELETE /sync/file    ──→  DB mutation  ──→  publish_event()  ──→  SSE stream

The broadcast uses asyncio.Queue per subscriber — no Redis needed for
single-server deployments.  For multi-server, swap in Redis Pub/Sub.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import APIRouter, Request, Depends
from fastapi.responses import StreamingResponse
from ..dependencies import get_current_user
from .. import models

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events", tags=["Events"])

# ── In-memory broadcast ──────────────────────────────────────────────────────
# Key: user_id → set of asyncio.Queue
# Each connected client gets its own queue.  publish_event fans out to all.
_subscribers: dict[int, set[asyncio.Queue]] = {}
_lock = asyncio.Lock()


async def subscribe(user_id: int) -> asyncio.Queue:
    """Register a new subscriber queue for a user."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=256)
    async with _lock:
        if user_id not in _subscribers:
            _subscribers[user_id] = set()
        _subscribers[user_id].add(queue)
    return queue


async def unsubscribe(user_id: int, queue: asyncio.Queue):
    """Remove a subscriber queue."""
    async with _lock:
        if user_id in _subscribers:
            _subscribers[user_id].discard(queue)
            if not _subscribers[user_id]:
                del _subscribers[user_id]


async def publish_event(user_id: int, event_type: str, payload: dict):
    """Fan-out an event to all subscribers of a user.

    Events are JSON-serialized and sent as SSE `data:` lines.
    If a subscriber's queue is full (slow consumer), the event is dropped
    for that subscriber — this is a deliberate backpressure decision.
    Dropped events are harmless because the client can always re-fetch
    the full state via GET /sync/metadata.

    Args:
        user_id:    The user whose subscribers should receive the event.
        event_type: One of: file_created, file_updated, file_deleted,
                    upload_complete, upload_failed, conflict_detected.
        payload:    Arbitrary dict — typically {file_id, file_path, version_id, ...}
    """
    message = {
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": payload,
    }
    async with _lock:
        queues = _subscribers.get(user_id, set()).copy()

    dropped = 0
    for q in queues:
        try:
            q.put_nowait(message)
        except asyncio.QueueFull:
            dropped += 1

    if dropped:
        logger.warning(
            "Dropped SSE event for %d slow subscriber(s) of user_id=%d",
            dropped, user_id,
        )


# ── SSE Streaming Endpoint ──────────────────────────────────────────────────

@router.get("/stream")
async def event_stream(
    request: Request,
    current_user: models.User = Depends(get_current_user),
):
    """GET /events/stream — SSE endpoint.

    The client opens a long-lived HTTP connection.  The server pushes
    JSON events as they occur.  On disconnect, the subscriber queue
    is cleaned up.

    Response format (SSE spec):
        event: file_updated
        data: {"type":"file_updated","timestamp":"...","data":{...}}

        event: heartbeat
        data: {"type":"heartbeat"}

    The heartbeat fires every 30 seconds to keep the connection alive
    through proxies and load balancers that kill idle connections.
    """
    user_id = current_user.id
    queue = await subscribe(user_id)

    async def generator() -> AsyncGenerator[str, None]:
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                try:
                    # Wait for event with 30-second timeout (heartbeat interval)
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    event_type = message.get("type", "message")
                    data = json.dumps(message)
                    yield f"event: {event_type}\ndata: {data}\n\n"
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield f"event: heartbeat\ndata: {json.dumps({'type': 'heartbeat'})}\n\n"
        finally:
            await unsubscribe(user_id, queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
```

#### 1.2.2 — Server: Wiring Events into Existing Mutations

Every existing endpoint that changes state must call `publish_event()`. Here are the exact injection points:

**File: `Server-Logic/server/app/services/metadata.py`**

```python
# ─── At module level, import the publisher ─────────────────────────────────
import asyncio
from ..routers.events import publish_event

def _fire_event(user_id: int, event_type: str, payload: dict):
    """Synchronous wrapper to publish async SSE events from sync code.

    The metadata service runs inside FastAPI's sync-to-async threadpool.
    We need to schedule the coroutine on the running event loop.
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(publish_event(user_id, event_type, payload))
    except RuntimeError:
        # No event loop running (e.g., during tests or RQ worker)
        pass
```

Injection points (line-by-line):

| Function | After Line | Event Call |
|----------|-----------|-----------|
| `_handle_deletion()` | After `db.commit()` (line 144) | `_fire_event(file_record.user_id, "file_deleted", {"file_id": file_record.id, "file_path": file_record.file_path})` |
| `_handle_empty_file()` | After `db.commit()` (line 224) | `_fire_event(user_id, "file_updated", {"file_id": file_record.id, "file_path": payload.path, "version_id": new_version.id})` |
| `_resolve_client_wins()` | After `db.commit()` (line 380) | `_fire_event(user_id, "conflict_detected", {"file_id": file_record.id, "file_path": payload.path, "conflict_path": conflict_path, "winner_version_id": winner_version.id})` |
| `_resolve_server_wins()` | After `db.commit()` (line 437) | `_fire_event(user_id, "conflict_detected", {"file_id": file_record.id, "file_path": payload.path, "conflict_path": conflict_path, "winner_version_id": server_latest.id})` |
| `_accept_new_version()` | After `db.commit()` (line 495) | `_fire_event(user_id, "file_created", {"file_id": file_record.id, "file_path": payload.path, "version_id": new_version.id})` |

**File: `Server-Logic/server/app/routers/sync.py`**

| Endpoint | After Line | Event Call |
|----------|-----------|-----------|
| `upload_file()` | After `db.commit()` (line 153) | `_fire_event(user_id, "upload_processing", {"file_path": remote_path, "version_id": version_record.id})` |
| `delete_file()` | After `db.commit()` (line 443) | `_fire_event(user_id, "file_deleted", {"file_id": file_id, "file_path": file_record.file_path})` |

**File: `Server-Logic/server/app/worker.py`** — The background worker runs in a separate process without the FastAPI event loop. It cannot directly use the in-memory SSE queues. Solution: After a job completes, write a status row to a `job_completions` table and have a lightweight FastAPI background task poll it every 2 seconds. Alternatively, use Redis Pub/Sub (already available since the worker uses Redis for RQ):

```python
# In worker.py — after setting version.upload_status = UploadStatus.complete:
def _notify_completion(version_id: int, status: str, file_path: str, user_id: int):
    """Push a completion notification to Redis Pub/Sub.
    The FastAPI SSE router subscribes to this channel."""
    import json
    notification = json.dumps({
        "type": "upload_complete" if status == "complete" else "upload_failed",
        "data": {
            "version_id": version_id,
            "file_path": file_path,
            "status": status,
        },
        "user_id": user_id,
    })
    redis_conn.publish("shadowdrive:events", notification)
```

**File: `Server-Logic/server/app/main.py`** — Register the events router:

```python
# Line 59, add:
from .routers import user, device, sync, auth, system, events

# Line 65, add:
app.include_router(events.router)
```

#### 1.2.3 — UI: EventSource Subscription

**New file: `shadowdrive-ui/src/lib/useEventStream.ts`**

```typescript
/**
 * useEventStream — React hook for SSE subscription.
 *
 * Opens a persistent EventSource to /events/stream.
 * On every event, calls the registered handler.
 * Auto-reconnects with exponential backoff on disconnect.
 *
 * Usage:
 *   useEventStream((event) => {
 *     if (event.type === 'file_updated') refreshFiles();
 *   });
 */
import { useEffect, useRef, useCallback } from 'react';
import { BASE_URL, getToken } from './api';

interface SSEEvent {
  type: string;
  timestamp: string;
  data: Record<string, any>;
}

export function useEventStream(onEvent: (event: SSEEvent) => void) {
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;

  const reconnectDelay = useRef(1000);

  useEffect(() => {
    let es: EventSource | null = null;
    let closed = false;

    function connect() {
      if (closed) return;

      const token = getToken();
      if (!token) return;

      // EventSource doesn't support headers, so we pass token as query param
      const url = `${BASE_URL}/events/stream?token=${encodeURIComponent(token)}`;
      es = new EventSource(url);

      es.onopen = () => {
        reconnectDelay.current = 1000; // Reset backoff on successful connect
      };

      // Listen for all named event types
      const eventTypes = [
        'file_created', 'file_updated', 'file_deleted',
        'upload_complete', 'upload_failed', 'upload_processing',
        'conflict_detected', 'heartbeat',
      ];

      for (const type of eventTypes) {
        es.addEventListener(type, (e: MessageEvent) => {
          try {
            const parsed: SSEEvent = JSON.parse(e.data);
            onEventRef.current(parsed);
          } catch (err) {
            console.warn('[SSE] Failed to parse event:', e.data);
          }
        });
      }

      es.onerror = () => {
        es?.close();
        // Exponential backoff: 1s, 2s, 4s, 8s, max 30s
        const delay = Math.min(reconnectDelay.current, 30000);
        reconnectDelay.current *= 2;
        setTimeout(connect, delay);
      };
    }

    connect();

    return () => {
      closed = true;
      es?.close();
    };
  }, []);
}
```

**File: `shadowdrive-ui/src/FileExplorer.tsx`** — Wire SSE into the file list:

```typescript
// At the top of FileExplorer(), after state declarations:
import { useEventStream } from './lib/useEventStream';

// Inside the component:
const refreshFiles = useCallback(async () => {
  try {
    const data = await apiFetch('/sync/metadata');
    const mappedFiles = data.map((f: any, idx: number) => ({
      id: f.id || f.hash || idx,
      file_path: f.file_path,
      size_bytes: f.size_bytes,
      updated_at: new Date().toLocaleString(),
      upload_status: 'complete',
      is_conflict_copy: f.file_path.includes('(Conflicted copy)'),
      storage_path: f.storage_path,
    }));
    setFiles(mappedFiles);
  } catch (err) {
    console.error('Failed to refresh files:', err);
  }
}, []);

useEventStream((event) => {
  switch (event.type) {
    case 'file_created':
    case 'file_updated':
    case 'file_deleted':
    case 'upload_complete':
    case 'conflict_detected':
      refreshFiles();
      break;
    case 'upload_failed':
      refreshFiles();
      // Optionally show a toast notification
      break;
  }
});
```

This replaces the one-shot `useEffect` fetch. The UI now updates within milliseconds of any server-side mutation.

#### 1.2.4 — Client Agent: SSE Subscription

**New file: `Client-Logic/event_listener.py`**

```python
"""
event_listener.py — SSE client for the Python sync agent.

Subscribes to /events/stream and triggers immediate sync actions
instead of waiting for the 30-second polling interval.

This is a performance optimization, not a correctness requirement.
The polling loop in sync_engine.py remains as a fallback.  If the
SSE connection drops, the agent degrades gracefully to polling.

Thread model:
    Main thread: sync_engine.main() polling loop
    Daemon thread: event_listener.listen() SSE stream
    Communication: threading.Event signals
"""

import threading
import logging
import json
import time
import requests

import config
import network_client

logger = logging.getLogger(__name__)

# ── Signals ──────────────────────────────────────────────────────────────────
# Set by the SSE listener when a relevant event arrives.
# The sync engine checks this flag at the top of its loop and, if set,
# runs an immediate sync cycle instead of sleeping for 30 seconds.
sync_nudge = threading.Event()


def listen():
    """Long-lived SSE listener.  Runs as a daemon thread.

    Reconnects with exponential backoff on failure.
    Never raises — all errors are caught and logged.
    """
    backoff = 1
    max_backoff = 60

    while True:
        token = network_client._get_token()
        if not token:
            time.sleep(5)
            continue

        url = f"{config.SERVER_URL}/events/stream?token={token}"
        try:
            logger.info("[SSE] Connecting to %s", url)
            with requests.get(url, stream=True, timeout=(10, None)) as resp:
                resp.raise_for_status()
                backoff = 1  # Reset on successful connection

                for line in resp.iter_lines(decode_unicode=True):
                    if line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            event = json.loads(data_str)
                            event_type = event.get("type", "")

                            if event_type in (
                                "file_created", "file_updated", "file_deleted",
                                "upload_complete", "conflict_detected",
                            ):
                                logger.info("[SSE] Received %s — nudging sync engine", event_type)
                                sync_nudge.set()

                        except json.JSONDecodeError:
                            pass

        except requests.exceptions.RequestException as e:
            logger.warning("[SSE] Connection failed: %s. Retrying in %ds", e, backoff)

        time.sleep(backoff)
        backoff = min(backoff * 2, max_backoff)


def start():
    """Start the SSE listener as a daemon thread."""
    t = threading.Thread(target=listen, daemon=True, name="sse-listener")
    t.start()
    logger.info("[SSE] Listener thread started.")
```

**File: `Client-Logic/sync_engine.py`** — Integrate the nudge signal:

```python
# At the top of the file, import:
import event_listener

# In the main loop (the sleep between sync cycles):
# BEFORE (current code):
#     time.sleep(30)
#
# AFTER:
#     # Wait up to 30 seconds, but wake immediately if SSE nudges us.
#     event_listener.sync_nudge.wait(timeout=30)
#     event_listener.sync_nudge.clear()
```

**File: `Client-Logic/local_api.py`** — Start the SSE listener on startup:

```python
# In startup_event(), after _start_watcher_if_needed():
import event_listener
event_listener.start()
```

### 1.3 — State Reconciliation Protocol

The SSE bus handles real-time push. But what happens when a client reconnects after being offline for hours? The existing `/sync/metadata/diff` endpoint handles this. The protocol is:

```
1. Client connects SSE stream.
2. Client calls GET /sync/metadata/diff?device_id=X.
3. Server returns {missing_files, outdated_files, deleted_files}.
4. Client processes each list:
   - missing_files  → download and write to watch_folder
   - outdated_files → download and overwrite in watch_folder
   - deleted_files  → delete from watch_folder + shadow.db
5. Client calls POST /sync/ack_sync for each processed file.
6. Going forward, SSE events trigger incremental syncs.
```

**Critical fix:** Step 4 for `deleted_files` is broken. The current `sync_engine.py` removes the record from `shadow.db` but does NOT delete the file from disk. Here's the fix:

```python
# In sync_engine.py, in the function that processes deleted_files:
# AFTER removing from shadow.db:
import os
local_path = os.path.join(config.WATCH_DIR, deleted_file_path)
if os.path.exists(local_path):
    # Suppress watchdog event for this delete (see Section 2)
    _suppressed_paths.add(os.path.normpath(local_path))
    os.remove(local_path)
    logger.info("Deleted local file: %s", local_path)
```

---

## Section 2: In-Place Editing & Infinite Loop Prevention

### 2.1 — The Loop (Anatomy)

Let's trace the exact infinite loop, step by step:

```
Step 1: User clicks "Save Changes" in UI editor
        → FileExplorer.tsx:344 calls uploadFile(fileObj, editingFile.name)
        → api.ts:43 POSTs to http://127.0.0.1:8001/api/upload
        → local_api.py:112 writes file to watch_folder/filename.txt

Step 2: Watchdog fires (watcher.py:40-60 — on_modified or on_created)
        → diff_engine.py logs the event
        → sync_engine.py picks it up on next cycle

Step 3: sync_engine.py computes SHA-256, calls POST /sync/announce
        → Server creates Version v(N+1) with upload_required=True
        → sync_engine.py uploads the file via POST /sync/upload

Step 4: Background worker verifies hash, sets upload_status=complete
        → SSE event fires (with our new system)

Step 5: On next diff poll, client sees v(N+1) as the latest version
        → But wait — the client JUST uploaded v(N+1)
        → The ack_sync was never called for the upload direction!
        → Client downloads v(N+1) and overwrites watch_folder/filename.txt

Step 6: Watchdog fires on the overwrite. GOTO Step 3. ♻️ INFINITE LOOP.
```

### 2.2 — The Fix: Origin Tagging + Suppression Window

The solution has three layers:

#### Layer 1: Upload-side `ack_sync`

After the client agent uploads a file and the background worker marks it complete, the client must call `POST /sync/ack_sync` with the new version_id. This prevents the diff endpoint from returning the file as "outdated" in the next poll.

**File: `Client-Logic/sync_engine.py`** — After a successful upload:

```python
# After upload completes and the server responds with version_id:
def _ack_upload(self, file_id: int, version_id: int):
    """Tell the server that THIS device now has this version.
    Without this, /metadata/diff will return the file as 'outdated'
    and the client will try to download its own upload."""
    try:
        network_client.ack_sync(
            device_id=config.DEVICE_ID,
            file_id=file_id,
            version_id=version_id,
        )
    except Exception as e:
        logger.warning("ack_sync failed for file_id=%d: %s", file_id, e)
```

#### Layer 2: Watchdog Event Suppression

When the client writes a file to `watch_folder` (either from UI upload or server download), the watchdog must NOT trigger a sync cycle for that write.

**File: `Client-Logic/watcher.py`** — Add a suppression set:

```python
import threading

# Thread-safe set of paths to suppress.
# When the sync engine or local_api writes a file, it adds the path here.
# The watchdog handler checks this set before processing an event.
_suppressed_paths: set[str] = set()
_suppression_lock = threading.Lock()
_suppression_ttl: dict[str, float] = {}  # path → expiry timestamp

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
            # TTL expired — remove and process normally
            _suppressed_paths.discard(normalized)
            _suppression_ttl.pop(normalized, None)
            return False
        return True


class ShadowEventHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory:
            return
        if is_suppressed(event.src_path):
            logger.debug("[SUPPRESSED] Ignoring watchdog event for %s", event.src_path)
            return
        # ... existing logic ...

    def on_created(self, event):
        if event.is_directory:
            return
        if is_suppressed(event.src_path):
            logger.debug("[SUPPRESSED] Ignoring watchdog event for %s", event.src_path)
            return
        # ... existing logic ...
```

**File: `Client-Logic/local_api.py`** — Suppress before writing:

```python
# In handle_ui_upload(), BEFORE writing the file:
from watcher import suppress_path

@app.post("/api/upload")
async def handle_ui_upload(file: UploadFile = File(...)):
    watch_dir = config.WATCH_DIR
    file_path = os.path.join(watch_dir, file.filename)

    suppress_path(file_path)  # ← Suppress BEFORE write

    os.makedirs(watch_dir, exist_ok=True)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    return {"status": "success", "message": "File added to local watcher."}
```

**File: `Client-Logic/sync_engine.py`** — Suppress before downloading:

```python
# In the download handler, BEFORE writing the downloaded bytes:
from watcher import suppress_path

def _download_and_write(self, file_path: str, storage_path: str):
    local_path = os.path.join(config.WATCH_DIR, file_path)

    suppress_path(local_path)  # ← Suppress BEFORE write

    file_bytes = network_client.download_file(storage_path)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, "wb") as f:
        f.write(file_bytes)
```

#### Layer 3: Hash-Based Dedup at the Sync Engine Level

Even with suppression, edge cases exist (TTL expiry, race conditions). The final safety net: before announcing a file change, compare the file's SHA-256 to the hash of the latest known version in `shadow.db`. If they match, skip the announce entirely.

```python
# In sync_engine.py, before calling announce_metadata:
def _should_announce(self, file_path: str, current_hash: str) -> bool:
    """Return False if the file content matches what we last synced."""
    last_known_hash = self._get_last_synced_hash(file_path)
    if last_known_hash and last_known_hash == current_hash:
        logger.debug("[DEDUP] Skipping announce for %s — hash unchanged", file_path)
        return False
    return True
```

### 2.3 — In-Place Edit Flow (After Fix)

```
Step 1: User edits file in UI → "Save Changes"
Step 2: UI calls POST /api/upload (local_api.py)
Step 3: local_api.py calls suppress_path(file_path)
Step 4: local_api.py writes file to watch_folder
Step 5: Watchdog fires → is_suppressed() returns True → event ignored ✓
Step 6: sync_engine.py picks up file on next cycle
Step 7: sync_engine.py computes hash → announces to server
Step 8: Server creates version → sync_engine.py uploads → ack_sync
Step 9: SSE event fires → UI calls refreshFiles() → UI updated ✓
Step 10: Next diff poll → server returns nothing (ack_sync was called) ✓
                          NO LOOP. ✓
```

---

## Section 3: Zero-Failure Network Resilience Engine

### 3.1 — Current Failure Modes

The current `network_client.py` has basic retry logic but it's not systematic. Let me enumerate every network operation and its current failure handling:

| Operation | Endpoint | Current Retry? | Current Failure Mode |
|-----------|----------|---------------|---------------------|
| `announce_metadata` | `POST /sync/announce` | Single attempt | Silent failure — file stuck in "pending" in shadow.db forever |
| `upload_file` | `POST /sync/upload` | Single attempt | Silent failure — version stuck as `pending` on server |
| `upload_chunk` | `POST /sync/upload_chunk` | Single attempt | Silent failure — partial upload, no recovery |
| `download_file` | `GET /sync/download` | Single attempt | Silent failure — file missing locally |
| `download_chunk` | `GET /sync/download_chunk` | Single attempt | Silent failure — corrupt partial file |
| `ack_sync` | `POST /sync/ack_sync` | Single attempt | Silent failure — next diff poll re-downloads |
| `metadata_diff` | `GET /sync/metadata/diff` | Single attempt | Entire sync cycle skipped |
| `health_check` | `GET /health` | Single attempt | Agent enters offline mode but never recovers gracefully |
| UI `apiFetch` | Various | Zero retries | `throw response` — user sees nothing or generic error |

### 3.2 — The Retry Engine

**New file: `Client-Logic/resilient_http.py`**

```python
"""
resilient_http.py — Fault-tolerant HTTP client with exponential backoff.

Every HTTP call in the ShadowDrive client goes through this module.
It provides:
    1. Automatic retries with exponential backoff + jitter
    2. Circuit breaker (stop hammering a dead server)
    3. Idempotency safety (safe to retry POSTs because our endpoints are idempotent)
    4. Structured error logging
    5. Network state tracking (online/offline transitions)

Architecture:
    network_client.py → resilient_http.request() → requests.Session
                                  ↓
                         RetryPolicy + CircuitBreaker
"""

import time
import random
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Server is down — reject all requests immediately
    HALF_OPEN = "half_open"  # Allowing one probe request through


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""
    max_retries: int = 5
    base_delay: float = 1.0        # seconds
    max_delay: float = 60.0        # seconds
    backoff_factor: float = 2.0
    jitter: float = 0.5            # ±50% randomization
    retryable_status_codes: tuple = (408, 429, 500, 502, 503, 504)
    retryable_exceptions: tuple = (
        requests.exceptions.ConnectionError,
        requests.exceptions.Timeout,
        requests.exceptions.ChunkedEncodingError,
    )


@dataclass
class CircuitBreaker:
    """Prevents hammering a dead server.

    After `failure_threshold` consecutive failures, the circuit opens
    for `recovery_timeout` seconds.  After that, one probe request is
    allowed through (half-open).  If it succeeds, the circuit closes.
    """
    failure_threshold: int = 5
    recovery_timeout: float = 30.0

    _failure_count: int = field(default=0, init=False)
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.time() - self._last_failure_time >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
            return self._state

    def record_success(self):
        with self._lock:
            self._failure_count = 0
            self._state = CircuitState.CLOSED

    def record_failure(self):
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    "[CIRCUIT] OPEN — %d consecutive failures. "
                    "Blocking requests for %ds.",
                    self._failure_count, self.recovery_timeout,
                )

    def allow_request(self) -> bool:
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            return True  # Allow one probe
        return False  # OPEN — reject


# ── Module-level singletons ──────────────────────────────────────────────────
_default_policy = RetryPolicy()
_circuit = CircuitBreaker()
_session: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    """Reusable session with connection pooling."""
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({"User-Agent": "ShadowDrive-Agent/1.0"})
    return _session


def request(
    method: str,
    url: str,
    policy: Optional[RetryPolicy] = None,
    on_retry: Optional[Callable] = None,
    **kwargs,
) -> requests.Response:
    """Make an HTTP request with retry + circuit breaker.

    Args:
        method:   HTTP method (GET, POST, PUT, DELETE).
        url:      Full URL.
        policy:   Override default retry policy.
        on_retry: Optional callback(attempt, delay, exception) for logging.
        **kwargs: Passed through to requests (json, data, files, headers, timeout).

    Returns:
        requests.Response on success.

    Raises:
        requests.exceptions.RequestException: After all retries exhausted.
        CircuitBreakerOpen: If the circuit breaker is open.
    """
    p = policy or _default_policy
    session = _get_session()

    # Default timeout: 30s connect, 120s read
    kwargs.setdefault("timeout", (30, 120))

    last_exception = None
    for attempt in range(1, p.max_retries + 1):
        # Circuit breaker check
        if not _circuit.allow_request():
            delay = _circuit.recovery_timeout - (time.time() - _circuit._last_failure_time)
            if delay > 0:
                logger.info("[CIRCUIT] Open. Waiting %.1fs before probe.", delay)
                time.sleep(delay)

        try:
            response = session.request(method, url, **kwargs)

            if response.status_code in p.retryable_status_codes:
                last_exception = requests.exceptions.HTTPError(
                    f"Server returned {response.status_code}", response=response,
                )
                _circuit.record_failure()
                # Fall through to retry logic
            else:
                _circuit.record_success()
                return response

        except p.retryable_exceptions as exc:
            last_exception = exc
            _circuit.record_failure()

        except Exception as exc:
            # Non-retryable exception (e.g., invalid URL, SSL error)
            _circuit.record_failure()
            raise

        # Compute backoff with jitter
        delay = min(
            p.base_delay * (p.backoff_factor ** (attempt - 1)),
            p.max_delay,
        )
        jitter = delay * p.jitter * (2 * random.random() - 1)
        delay = max(0.1, delay + jitter)

        if on_retry:
            on_retry(attempt, delay, last_exception)
        else:
            logger.warning(
                "[RETRY] Attempt %d/%d for %s %s failed: %s. "
                "Retrying in %.1fs.",
                attempt, p.max_retries, method, url, last_exception, delay,
            )

        time.sleep(delay)

    # All retries exhausted
    logger.error(
        "[FAILED] All %d attempts exhausted for %s %s. Last error: %s",
        p.max_retries, method, url, last_exception,
    )
    raise last_exception
```

### 3.3 — Wiring `resilient_http` into `network_client.py`

Every `requests.post()` / `requests.get()` call in `network_client.py` must be replaced with `resilient_http.request()`. The mapping:

| Current Call (network_client.py) | Replacement |
|----------------------------------|-------------|
| `requests.post(url, json=payload)` | `resilient_http.request("POST", url, json=payload)` |
| `requests.get(url, headers=headers)` | `resilient_http.request("GET", url, headers=headers)` |
| `requests.post(url, files=files)` | `resilient_http.request("POST", url, files=files)` |
| `requests.delete(url, headers=headers)` | `resilient_http.request("DELETE", url, headers=headers)` |

### 3.4 — UI-Side Resilience

**File: `shadowdrive-ui/src/lib/api.ts`** — Add retry wrapper:

```typescript
/**
 * Retry wrapper for API calls.
 * Retries on network errors and 5xx status codes.
 * Uses exponential backoff with jitter.
 */
async function withRetry<T>(
  fn: () => Promise<T>,
  maxRetries = 3,
  baseDelay = 1000,
): Promise<T> {
  let lastError: any;

  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await fn();
    } catch (err: any) {
      lastError = err;

      // Don't retry client errors (4xx) — they won't change
      if (err instanceof Response && err.status >= 400 && err.status < 500) {
        throw err;
      }

      if (attempt < maxRetries) {
        const delay = baseDelay * Math.pow(2, attempt - 1);
        const jitter = delay * 0.5 * (Math.random() * 2 - 1);
        await new Promise(r => setTimeout(r, Math.max(100, delay + jitter)));
      }
    }
  }

  throw lastError;
}

// Updated apiFetch:
export async function apiFetch(endpoint: string, options: RequestInit = {}) {
  return withRetry(async () => {
    const token = getToken();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string> || {}),
    };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const response = await fetch(`${BASE_URL}${endpoint}`, { ...options, headers });
    if (!response.ok) throw response;
    return response.json();
  });
}
```

### 3.5 — Upload Recovery (Chunked Uploads)

The current chunked upload has no recovery. If chunk 47 of 100 fails, the entire upload is lost. Fix:

**File: `Client-Logic/sync_engine.py`** — In the chunked upload loop:

```python
def _upload_chunks_resilient(self, file_path, version_id, chunk_hashes, file_hash):
    """Upload file chunks with per-chunk retry and resume capability.

    On failure:
        1. Individual chunk failures are retried via resilient_http.
        2. If the entire upload session fails (e.g., 30 minutes of retries),
           the version_id remains on the server as 'uploading'.
        3. On the next sync cycle, the client re-announces the file.
        4. The server's hash dedup (metadata.py:154-196) detects the existing
           version and returns the same version_id with upload_required=True.
        5. The client calls GET /sync/upload/status/{version_id} to check
           which chunks are already received.
        6. Only missing chunks are re-uploaded.

    This gives us resume-from-where-we-left-off for free.
    """
    chunk_size = 4 * 1024 * 1024  # 4 MB

    with open(file_path, 'rb') as f:
        total_size = os.path.getsize(file_path)
        total_chunks = (total_size + chunk_size - 1) // chunk_size

        for chunk_index in range(total_chunks):
            # Check if this chunk was already uploaded (resume case)
            if chunk_index not in missing_chunk_indices:
                logger.debug("Chunk %d already on server, skipping", chunk_index)
                continue

            f.seek(chunk_index * chunk_size)
            chunk_data = f.read(chunk_size)

            # resilient_http handles retries automatically
            resilient_http.request(
                "POST",
                f"{config.SERVER_URL}/sync/upload_chunk",
                files={"chunk": (f"chunk_{chunk_index}", chunk_data)},
                data={
                    "version_id": version_id,
                    "chunk_index": chunk_index,
                    "total_chunks": total_chunks,
                    "file_hash": file_hash,
                },
                headers={"Authorization": f"Bearer {network_client._get_token()}"},
            )
```

---

## Section 4: Feature Coverage Matrix

This matrix documents every user-facing operation and tracks whether it's correctly handled across all three nodes of the triad.

### 4.1 — File Operations

| # | Operation | Client-Logic | Server-Logic | UI (React) | Status | Notes |
|---|-----------|:---:|:---:|:---:|:---:|-------|
| 1 | **Create file (local)** | ✅ watchdog detects → announce → upload | ✅ announce creates File+Version | ❌ No push notification | 🔴 Broken | UI stale until manual refresh |
| 2 | **Create file (UI upload)** | ⚠️ watchdog fires but may loop | ✅ via local_api → watch_folder | ✅ uploadFile() works | 🟡 Risky | Loop risk without suppression |
| 3 | **Modify file (local)** | ✅ watchdog → hash compare → announce | ✅ new version created | ❌ No push notification | 🔴 Broken | UI stale |
| 4 | **Modify file (UI editor)** | ⚠️ Triggers infinite loop | ✅ via local_api | ✅ Editor modal works | 🔴 Broken | Infinite loop (Section 2) |
| 5 | **Delete file (local)** | ✅ watchdog → announce deleted | ✅ soft-delete | ❌ No push notification | 🔴 Broken | UI stale |
| 6 | **Delete file (UI)** | ❌ No local file removal | ✅ soft-delete API | ✅ deleteFile() UI works | 🔴 Broken | File reappears on next sync |
| 7 | **Download file** | ✅ diff → download → write | ✅ download endpoint | ✅ anchor tag download | 🟢 Works | But no auth on download URL |
| 8 | **Rename file** | ❌ Not implemented | ❌ Not implemented | ❌ Not implemented | ⬜ Missing | Appears as delete + create |
| 9 | **Move file** | ❌ Not implemented | ❌ Not implemented | ❌ Not implemented | ⬜ Missing | Same as rename |
| 10 | **Large file upload (>4MB)** | ✅ Chunked upload | ✅ upload_chunk endpoint | ❌ UI uses single upload | 🟡 Partial | UI can't upload large files |

### 4.2 — Sync Operations

| # | Operation | Client-Logic | Server-Logic | UI (React) | Status |
|---|-----------|:---:|:---:|:---:|:---:|
| 11 | **Initial sync (fresh device)** | ✅ metadata/diff → download all | ✅ Returns all files for device | ❌ No concept of initial sync | 🟡 Partial |
| 12 | **Incremental sync** | ✅ 30s poll loop | ✅ diff endpoint | ❌ One-shot fetch only | 🔴 Broken |
| 13 | **Real-time push sync** | ❌ No SSE/WebSocket | ❌ No event bus | ❌ No EventSource | 🔴 Missing |
| 14 | **Conflict detection** | ✅ base_version_id check | ✅ LWW resolution | ⚠️ UI shows conflict page but data is hardcoded | 🟡 Partial |
| 15 | **Conflict resolution (UI)** | N/A | ✅ Server resolves LWW | ❌ Buttons call `alert()` — nonfunctional | 🔴 Broken |
| 16 | **Upload ack (ack_sync)** | ⚠️ Only on download direction | ✅ Upsert into file_device_map | N/A | 🟡 Partial |
| 17 | **Multi-device sync** | ✅ device_id tracking | ✅ per-device diff | ❌ No device awareness | 🟡 Partial |

### 4.3 — Auth & Security

| # | Operation | Client-Logic | Server-Logic | UI (React) | Status |
|---|-----------|:---:|:---:|:---:|:---:|
| 18 | **User registration** | ✅ CLI + API | ✅ /users/register | ✅ AuthScreen | 🟢 Works |
| 19 | **User login** | ✅ CLI + API | ✅ /auth/login | ✅ AuthScreen | 🟢 Works |
| 20 | **JWT token refresh** | ❌ Token expires silently | ❌ No refresh endpoint | ❌ No refresh logic | 🔴 Broken |
| 21 | **Client-side encryption** | ✅ AES-256 via crypto_utils | N/A (server never sees plaintext) | ❌ UI downloads raw encrypted bytes | 🟡 Partial |
| 22 | **Storage quota enforcement** | N/A | ✅ Checked on upload | ❌ No quota display in UI | 🟡 Partial |

### 4.4 — Infrastructure

| # | Operation | Client-Logic | Server-Logic | UI (React) | Status |
|---|-----------|:---:|:---:|:---:|:---:|
| 23 | **Health check** | ✅ Polls /health before sync | ✅ /health endpoint | ❌ No health indicator | 🟡 Partial |
| 24 | **Device heartbeat** | ❌ Not called from agent | ✅ /{device_id}/heartbeat endpoint | ❌ No device status display | 🟡 Partial |
| 25 | **Version history (UI)** | N/A | ✅ /versions/recent | ✅ VersionHistory component | 🟢 Works |
| 26 | **Background job status** | ❌ No polling after upload | ✅ /upload/status/{version_id} | ❌ No progress indicator | 🔴 Broken |

### 4.5 — Priority Fix Order

Based on the matrix above, the implementation priority is:

```
P0 (MUST FIX — System fundamentally broken):
    [13] Real-time push sync (SSE)          → Section 1.2
    [ 4] In-place edit infinite loop        → Section 2
    [ 6] Delete from UI propagation         → Section 1.3
    [12] Incremental sync (UI side)         → Section 1.2.3

P1 (SHOULD FIX — Silent data loss or corruption):
    [16] Upload-side ack_sync               → Section 2.2 Layer 1
    [26] Background job status tracking     → New polling in sync_engine
    [20] JWT token refresh                  → New /auth/refresh endpoint

P2 (NICE TO HAVE — Completeness):
    [15] Conflict resolution UI (live)      → Wire ConflictResolution.tsx to API
    [14] Conflict detection in UI           → SSE event → navigate to /conflicts
    [10] Large file upload from UI          → Chunked upload in api.ts
    [24] Device heartbeat from agent        → Add to sync loop
    [22] Storage quota display in UI        → Call /auth/me on mount
```

---

## Section 5: 100-Action Chaos Engineering Test Plan

This test plan is designed to be run manually against a fully-deployed local stack (server, agent, UI). Each action has a verification step. The test progresses through increasingly adversarial scenarios.

### Test Environment Setup

```
Components:
    - PostgreSQL running on localhost:5432
    - Redis running on localhost:6379
    - MinIO running on localhost:9000
    - Server-Logic running on localhost:8000
    - RQ worker running with `rq worker shadowdrive-jobs`
    - Client-Logic local_api.py running on localhost:8001
    - shadowdrive-ui running on localhost:5173
    - watch_folder at ./watch_folder/

User: test_user / test@example.com
Device ID: 1
```

### Phase 1: Basic CRUD (Actions 1–20)

| # | Action | Expected Result | Verify |
|---|--------|----------------|--------|
| 1 | Drop `hello.txt` (5 bytes) into `watch_folder/` | Watchdog fires. `POST /sync/announce` creates File+Version. `POST /sync/upload` uploads bytes. Worker verifies hash → `complete`. | `GET /sync/metadata` returns `hello.txt` with correct hash |
| 2 | Open UI at `/vault` | File list loads via `GET /sync/metadata`. `hello.txt` appears with green status dot. | Visual: file row visible |
| 3 | Click `hello.txt` in UI → text editor opens | `GET /api/download?file_path=hello.txt` serves local plaintext. Editor modal shows content. | Visual: editor shows "hello" |
| 4 | Edit content to "hello world" → click "Save Changes" | `POST /api/upload` writes to `watch_folder`. Watchdog suppression prevents loop. Sync engine announces+uploads new version. | `GET /sync/metadata` shows updated hash. File content on disk is "hello world". |
| 5 | Wait 60 seconds | No additional sync activity. No duplicate versions created. No infinite loop. | Server logs show exactly ONE announce+upload for the edit. |
| 6 | Click delete icon on `hello.txt` in UI | `DELETE /sync/file/{id}` marks `is_deleted=True`. SSE event fires. UI removes row. | `GET /sync/metadata` returns empty list. |
| 7 | Wait for next sync cycle (≤30s) | Client receives `deleted_files: ["hello.txt"]` from diff. Client deletes local file. | `watch_folder/hello.txt` does not exist on disk. |
| 8 | Re-create `hello.txt` in `watch_folder/` | `is_deleted` flipped back to `False` by `_handle_un_deletion`. New version created. | `GET /sync/metadata` returns `hello.txt`. UI updates. |
| 9 | Create empty file `empty.txt` (0 bytes) | Announce with EMPTY_FILE_SHA256. Server creates version with `size_bytes=0`. No upload needed. | Version exists with `upload_status=complete`, `size_bytes=0`. |
| 10 | Upload `large.bin` (10 MB) to `watch_folder/` | Sync engine splits into 3 chunks (4MB + 4MB + 2MB). Each chunk uploaded. Assembly triggered. Worker verifies hash. | `GET /sync/upload/status/{version_id}` returns `complete`. `GET /sync/metadata` shows correct size. |
| 11 | Upload `large.bin` via UI | UI's `POST /api/upload` writes to `watch_folder`. Watchdog-suppressed. Sync picks it up. | Same as #10 but triggered from browser. |
| 12 | Create nested directory: `watch_folder/docs/sub/deep.txt` | Sync engine handles path correctly. File announced as `docs/sub/deep.txt`. | Server stores with `file_path=docs/sub/deep.txt`. |
| 13 | View version history for `hello.txt` | UI navigates to `/vault/history?file={id}`. Lists v1, v2, v3. | Visual: 3 version rows with correct timestamps and hashes. |
| 14 | Download version v1 of `hello.txt` | Browser downloads raw bytes from `/sync/download?storage_path=...`. | Downloaded file contains original "hello" content. |
| 15 | Create file with spaces: `my document.txt` | Path encoding handled correctly across all three nodes. | File syncs, appears in UI, downloads correctly. |
| 16 | Create file with unicode name: `日本語.txt` | UTF-8 encoding preserved in DB, MinIO key, and UI display. | File syncs without mojibake. |
| 17 | Upload binary file: `image.png` | Binary content preserved through encrypt → upload → download → decrypt cycle. | Downloaded file is byte-identical to original. |
| 18 | Rapidly create 10 files in sequence | All 10 are announced and uploaded within 2 sync cycles. | `GET /sync/metadata` returns 10+ files. |
| 19 | Delete all files from UI | 10 delete API calls. All succeed. | Metadata empty. `watch_folder/` empty after sync. |
| 20 | Verify shadow.db consistency | All tables in shadow.db reflect current state. No orphaned records. | Query shadow.db: `SELECT COUNT(*) FROM files WHERE synced=0` returns 0. |

### Phase 2: Conflict & Concurrent Edits (Actions 21–40)

| # | Action | Expected Result | Verify |
|---|--------|----------------|--------|
| 21 | Create `conflict.txt` → wait for sync | File synced normally. | Baseline established. |
| 22 | Simulate concurrent edit: modify `conflict.txt` locally AND call `POST /sync/announce` with a different hash and `base_version_id` pointing to v1 | Server detects conflict. LWW resolves based on `client_modified_at`. Conflict copy created. | `GET /sync/metadata` returns both `conflict.txt` and `conflict (Conflicted copy).txt`. |
| 23 | Check UI for conflict indicator | Conflict copy appears with red status dot (`is_conflict_copy: true`). | Visual: red pulsing dot in file list. |
| 24 | Navigate to `/conflicts` page | ConflictResolution component loads. (After fix: shows real data from API.) | Visual: conflict details shown. |
| 25 | Resolve conflict: "Keep A" | Winning version retained. Conflict copy soft-deleted or removed. | Single canonical file remains. |
| 26 | Create 5 files, disconnect network (kill server), modify 3 of them | Client queues 3 announce requests. They fail but are logged in shadow.db as pending. | shadow.db `pending_syncs` table has 3 entries. |
| 27 | Restart server | Client reconnects on next health check. Pending syncs are retried and succeed. | All 3 modifications reflected on server. |
| 28 | While offline: delete 2 files locally | Deletes queued. On reconnect, announce `event=deleted` for both. | Server marks both as `is_deleted=True`. |
| 29 | While offline: create new file → modify it → delete it | Net result: nothing to sync. Client should recognize the file was born and died offline. | No server-side record created (client deduplication). |
| 30 | Simulate server returns 500 on announce | `resilient_http` retries 5 times with backoff. After 5 failures, logs error. File stays in pending queue. | Client log shows 5 retry attempts. No crash. |
| 31 | Simulate server returns 429 (rate limit) | Client backs off per `Retry-After` header or exponential backoff. | Requests resume after backoff period. |
| 32 | Simulate MinIO down (server can accept announce but upload fails) | Announce succeeds. Upload fails. Version stays as `pending`. | `GET /sync/upload/status/{version_id}` shows `pending`. |
| 33 | Restart MinIO | Client retries upload on next cycle. Worker verifies hash. | Version transitions to `complete`. |
| 34 | Upload same file content twice (identical bytes, different filename) | Hash dedup: server creates two File records but stores only one copy in MinIO (via StoredChunk reuse). | Both files in metadata. MinIO has one object. |
| 35 | Rename file by deleting + recreating (workaround) | Old file soft-deleted. New file created with same content. | Both records exist. New file has `version_num=1`. |
| 36 | Concurrent UI edit + local edit of same file | Race condition. One wins via LWW. Other becomes conflict copy. | Two versions exist. Conflict resolved. |
| 37 | Rapid-fire: 50 file creates in 5 seconds | Watchdog batches events. Sync engine processes all within 2-3 cycles. | All 50 files appear on server within 90 seconds. |
| 38 | Upload file larger than storage quota | Server returns 413. Client logs error. File stays local. | No corrupt state. Error logged. |
| 39 | JWT token expires during upload session | Upload fails with 401. Client should re-authenticate or prompt user. | No crash. Graceful error. |
| 40 | Verify no data loss after all Phase 2 actions | Every file that should exist on server exists. Every delete propagated. No orphaned versions. | Comprehensive DB audit passes. |

### Phase 3: Network Adversarial (Actions 41–60)

| # | Action | Expected Result | Verify |
|---|--------|----------------|--------|
| 41 | Kill server mid-chunk-upload (chunk 2 of 5) | Client retries chunk 2. On server restart, idempotent upsert (line `sync.py:309-327`) updates existing record. | Upload resumes from chunk 2. |
| 42 | Kill client mid-download | Partial file on disk. On next sync cycle, client re-downloads (hash mismatch triggers re-fetch). | File eventually consistent. |
| 43 | Corrupt a chunk in MinIO (flip bits) | Worker hash verification fails → `upload_status=failed`. SSE event notifies. Client re-uploads. | Version transitions `failed` → re-announced → re-uploaded → `complete`. |
| 44 | Delete MinIO bucket while server running | All downloads fail. Server logs errors. Uploads fail with storage error. | Server does not crash. Errors are logged. Re-create bucket → recovery. |
| 45 | PostgreSQL connection pool exhausted | Server returns 500. Client retries. Circuit breaker opens after 5 failures. | Client stops hammering. Resumes after recovery_timeout. |
| 46 | Redis down (RQ queue unavailable) | `enqueue_verify()` raises. Upload endpoint catches exception, rolls back. Returns 500. | Version stays `pending`. Re-upload on retry succeeds after Redis restart. |
| 47 | DNS resolution failure (wrong server URL) | `resilient_http` catches ConnectionError. Retries. Eventually exhausts. | Clean error in logs. No crash. |
| 48 | Simulate 200ms latency on every request | All operations slower but complete correctly. No timeouts (default 30s connect). | Functional correctness preserved. |
| 49 | Simulate 50% packet loss | Some requests fail. Retries recover them. Throughput reduced but no data loss. | All files eventually sync. |
| 50 | Server restart while SSE stream active | EventSource `onerror` fires. Client reconnects with backoff. On reconnect, full diff sync. | No missed events (diff catches up). |
| 51 | Upload 100MB file over slow connection (1 Mbps) | Chunked upload: ~25 chunks. Total time ~13 minutes. Each chunk retried individually on failure. | Upload completes. Worker verifies hash. |
| 52 | Upload same 100MB file from a "second device" (different device_id) | Server deduplicates chunks via StoredChunk table. Only novel chunks uploaded. | Significantly faster second upload. |
| 53 | Kill RQ worker during assembly job | Assembly fails. Version stays `processing`. On worker restart, job is not re-queued (RQ default). | Need fix: periodic "stuck processing" scanner (new background task). |
| 54 | Concurrent uploads of same file from UI and CLI | One wins the version_num race. Other gets a conflict or is deduped. | No duplicate version_nums for same file_id. |
| 55 | SSE connection drop + 10 events fire | Client misses 10 events. On SSE reconnect, client calls `/sync/metadata/diff`. All 10 changes discovered. | Full state reconciliation. |
| 56 | Client clock 5 minutes ahead of server | LWW conflict resolution may favor the wrong side. `announced_at` from client is in the future. | Server should use `min(client_ts, server_now)` to clamp. **BUG: Not currently clamped.** |
| 57 | Client clock 5 minutes behind server | LWW may incorrectly favor server. `announced_at` from client is in the past. | Same clamping fix needed. |
| 58 | Zero-byte file followed by non-zero edit | Version v1 is empty (size_bytes=0). Version v2 has real content. Both stored. | History shows both versions correctly. |
| 59 | File with 0x00 bytes in content (binary) | SHA-256 computed correctly. MinIO stores correctly. Download returns exact bytes. | Byte-for-byte match. |
| 60 | Trigger circuit breaker → wait for recovery → verify auto-resume | After 5 consecutive failures, circuit opens. After 30s, half-open probe succeeds. Circuit closes. Normal operation resumes. | Logs show OPEN → HALF_OPEN → CLOSED transitions. |

### Phase 4: UI Integrity (Actions 61–80)

| # | Action | Expected Result | Verify |
|---|--------|----------------|--------|
| 61 | Login from UI → redirect to /vault | AuthScreen posts to local_api `/api/auth/login`. Token stored in localStorage. Redirect to `/vault`. | Token in localStorage. Files load. |
| 62 | Refresh browser on /vault | Token persists. Files reload from API. SSE reconnects. | No login prompt. Files appear. |
| 63 | Open /vault in two tabs | Both tabs connect SSE. Event in tab 1 updates tab 2. | Both tabs show same file list. |
| 64 | Upload file from tab 1 → check tab 2 | SSE event fires. Tab 2's `refreshFiles()` triggers. File appears. | File visible in both tabs within 1 second. |
| 65 | Delete file from tab 1 → check tab 2 | SSE event fires. Tab 2 removes file row. | File removed in both tabs. |
| 66 | Open text editor → edit → save → close → reopen | Content persists. New version created on server. Reopen shows saved content. | Content matches saved edit. |
| 67 | Open text editor → edit → close WITHOUT saving | No changes persisted. File on server/disk unchanged. | Hash unchanged. No new version. |
| 68 | Upload file with drag & drop (if supported) | File appears in list. Sync pipeline executes. | Same as click-upload flow. |
| 69 | Click "Download Latest" on version history | Browser downloads file. Content matches latest version. | File opens correctly. |
| 70 | Navigate /vault → /vault/history → /conflicts → /vault | No state corruption. Each page loads fresh data. | Visual: all pages render correctly. |
| 71 | Logout → attempt to access /vault | No token → API returns 401 → redirect to /auth. | User sees login screen. |
| 72 | Login with wrong credentials | API returns 401. UI shows error message. | Visual: "Invalid credentials" message. |
| 73 | Register new user → auto-login → upload file | Complete flow from registration to first upload. | File appears in vault for new user. |
| 74 | View system health page | SystemHealth component loads. (Currently mock data — verify no crash.) | Page renders without errors. |
| 75 | View network activity page | NetworkActivity component loads. (Currently mock data.) | Page renders without errors. |
| 76 | View node management page | NodeManagement component loads. | Page renders without errors. |
| 77 | Screen resize: desktop → mobile viewport | Responsive layout adjusts. File table becomes scrollable. | No overflow or clipping. |
| 78 | UI error boundary: make API unreachable | Error message displayed. No white screen of death. | Visual: "Failed to load files" message. |
| 79 | Rapidly click upload → cancel → upload → cancel | No orphaned uploads. No duplicate files. | Clean state after each cancel. |
| 80 | Check browser console for errors after full session | No uncaught exceptions. No React key warnings. No memory leaks. | Console clean. |

### Phase 5: Endurance & Edge Cases (Actions 81–100)

| # | Action | Expected Result | Verify |
|---|--------|----------------|--------|
| 81 | Run sync loop for 1 hour with no file changes | No spurious announces. No CPU spikes. No memory leaks. | Process memory stable. Zero announce calls in logs. |
| 82 | Run sync loop for 1 hour with a file changing every 10 seconds | 360 file changes processed. All versions on server. No missed events. | 360 versions in DB. Memory stable. |
| 83 | Create 1000 files in watch_folder simultaneously | Watchdog handles burst. Sync engine batches. All files synced within ~5 minutes. | `GET /sync/metadata` returns 1000 files. |
| 84 | Delete all 1000 files simultaneously | 1000 delete announces. All processed. | Metadata empty. |
| 85 | Create file with maximum path length (260 chars on Windows) | Path stored correctly in DB. MinIO key may need truncation/hashing. | File syncs. No truncation errors. |
| 86 | Create file named `.gitignore` (dotfile) | Watchdog picks it up. Sync handles it normally. | File in metadata. |
| 87 | Create file named `CON.txt` (Windows reserved name) | Sync engine handles gracefully. May need path sanitization. | No crash. Appropriate error or rename. |
| 88 | Create symlink in watch_folder | Watchdog may or may not follow. Sync engine should handle or skip gracefully. | No crash. Symlink either followed or ignored with log message. |
| 89 | Modify file permissions (read-only) then sync | Client can read for hash but watchdog might not fire. Announce uses cached hash. | No crash. File synced on next poll if hash changed. |
| 90 | `shadow.db` locked by another process | SQLite `OperationalError: database is locked`. Client retries with backoff. | Eventually succeeds. No data corruption. |
| 91 | `shadow.db` corrupted (manual bit flip) | Client detects integrity error. Re-creates shadow.db from server state. | Clean recovery. |
| 92 | MinIO disk full | Upload fails with storage error. Client logs error. Retries later. | No data loss. Upload succeeds after disk cleanup. |
| 93 | PostgreSQL disk full | DB write fails. Server returns 500. Client retries. | Server recovers after disk cleanup. |
| 94 | Multiple users uploading simultaneously | Each user's files isolated by user_id. No cross-contamination. | User A cannot see User B's files. |
| 95 | Upload file, immediately re-upload identical file | Second announce returns `already_synced`. No duplicate upload. | Single version in DB. |
| 96 | Upload file, modify 1 byte, re-upload | New version created. Only changed chunks re-uploaded (if chunked). | Two versions. Second upload minimal. |
| 97 | Run full test suite → check for PostgreSQL connection leaks | Connection count stable. No "too many connections" errors. | `pg_stat_activity` shows stable connection count. |
| 98 | Run full test suite → check for MinIO object leaks | Orphaned chunk objects cleaned up after assembly. | `mc ls shadowdrive/chunks/` shows only actively-referenced chunks. |
| 99 | Graceful shutdown: stop client agent → verify clean exit | All pending uploads completed or checkpointed. `shadow.db` closed cleanly. | No "database is locked" errors on restart. |
| 100 | Cold start: fresh database, fresh MinIO → register → login → upload → verify | Complete end-to-end flow from zero state. | File appears in UI. Download matches upload. All three nodes consistent. |

---

## Appendix A: File Change Manifest

### Files to Create (New)

| File | Purpose |
|------|---------|
| `Server-Logic/server/app/routers/events.py` | SSE real-time event bus |
| `shadowdrive-ui/src/lib/useEventStream.ts` | React hook for SSE subscription |
| `Client-Logic/event_listener.py` | Python SSE client for agent |
| `Client-Logic/resilient_http.py` | Retry engine with circuit breaker |

### Files to Modify

| File | Changes |
|------|---------|
| `Server-Logic/server/app/main.py` | Register events router |
| `Server-Logic/server/app/services/metadata.py` | Add `_fire_event()` calls after every DB mutation |
| `Server-Logic/server/app/routers/sync.py` | Add `_fire_event()` calls in upload and delete endpoints |
| `Server-Logic/server/app/worker.py` | Add Redis Pub/Sub notification on job completion |
| `Client-Logic/watcher.py` | Add event suppression (suppress_path / is_suppressed) |
| `Client-Logic/local_api.py` | Call suppress_path before writes; start SSE listener |
| `Client-Logic/sync_engine.py` | Integrate SSE nudge; add upload-side ack_sync; use resilient_http; add hash-based dedup guard |
| `Client-Logic/network_client.py` | Replace all `requests.*` calls with `resilient_http.request()` |
| `shadowdrive-ui/src/lib/api.ts` | Add `withRetry()` wrapper; update `apiFetch()` |
| `shadowdrive-ui/src/FileExplorer.tsx` | Wire `useEventStream()` hook; extract `refreshFiles()` callback |
| `shadowdrive-ui/src/ConflictResolution.tsx` | Wire to real API data instead of hardcoded state |

---

## Appendix B: Sequence Diagrams

### B.1 — Happy Path: File Created Locally

```
Client Agent          Server (FastAPI)         Background Worker       React UI
     │                       │                        │                    │
     │ ──1. watchdog fires── │                        │                    │
     │   (on_created)        │                        │                    │
     │                       │                        │                    │
     │ ──2. POST /announce─→ │                        │                    │
     │    {path, hash, event}│                        │                    │
     │                       │──3. INSERT File+Version│                    │
     │                       │    _fire_event()───────│────────────────────│
     │ ←─4. {accepted,       │                        │              5. SSE│
     │    version_id, upload_ │                        │         file_created
     │    required=True}     │                        │                    │
     │                       │                        │               6. UI│
     │ ──7. POST /upload───→ │                        │         refreshes │
     │    (file bytes)       │                        │                    │
     │                       │──8. PUT to MinIO       │                    │
     │                       │──9. enqueue_verify()─→ │                    │
     │ ←─10. 202 Accepted   │                        │                    │
     │                       │                    11. │verify hash        │
     │                       │                        │──12. complete──→  │
     │                       │                        │  Redis Pub/Sub    │
     │                       │                        │                13.│
     │ ──14. POST /ack_sync─→│                        │         SSE event │
     │   {device_id, file_id,│                        │    upload_complete│
     │    version_id}        │                        │                    │
     │                       │──15. upsert            │               16.UI│
     │                       │  file_device_map       │          refreshes│
     │                       │                        │                    │
```

### B.2 — UI Edit (No Loop)

```
React UI              Local API (8001)        Watchdog            Sync Engine
   │                       │                    │                      │
   │ ──1. POST /api/upload→│                    │                      │
   │   (edited file bytes) │                    │                      │
   │                       │──2. suppress_path()│                      │
   │                       │──3. write to       │                      │
   │                       │   watch_folder     │                      │
   │                       │                    │──4. on_modified      │
   │                       │                    │   is_suppressed()=T  │
   │                       │                    │   → SKIP ✓           │
   │ ←─5. {status: success}│                    │                      │
   │                       │                    │                  6. next│
   │                       │                    │                  cycle  │
   │                       │                    │                      │──7. hash file
   │                       │                    │                      │──8. _should_announce()
   │                       │                    │                      │   hash != last_synced
   │                       │                    │                      │──9. POST /announce
   │                       │                    │                      │──10. POST /upload
   │                       │                    │                      │──11. POST /ack_sync
   │                       │                    │                      │
   │←─────────────12. SSE: upload_complete──────│──────────────────────│
   │──13. refreshFiles()   │                    │                      │
   │                       │                    │                      │
   │  ✓ NO LOOP            │                    │                      │
```

---

## Appendix C: Known Bugs Discovered During Audit

| # | Bug | Severity | Location | Fix |
|---|-----|----------|----------|-----|
| 1 | **Duplicate version_record validation** in `upload_chunk()` — lines 218-226 and 240-244 check `version_record` existence twice | Low | `sync.py:240` | Remove second check |
| 2 | **No timestamp clamping** — client can send `client_modified_at` in the future, winning all LWW conflicts | Medium | `metadata.py:288` | `client_ts = min(client_ts, datetime.now(timezone.utc))` |
| 3 | **`is_deleted == False` comparison** uses `==` instead of `is` on a boolean column — works in SQLAlchemy but generates a lint warning | Low | `sync.py:398,534` | Use `models.File.is_deleted.is_(False)` |
| 4 | **Storage quota check races** — two concurrent uploads can both pass the quota check and exceed the limit | Medium | `sync.py:124-140, 258-274` | Use `SELECT ... FOR UPDATE` or DB-level constraint |
| 5 | **No `file` relationship** on `Version` model — `ver.file.file_path` (line `sync.py:475`) does a lazy load N+1 query per version | Medium | `models.py:59` | Add `file = relationship("File", backref="versions")` |
| 6 | **VersionHistory download** doesn't include auth token in URL | High | `VersionHistory.tsx:53` | Use `getDownloadUrl()` from api.ts instead of hardcoded URL |
| 7 | **Empty file hash check** in `_check_hash_dedup()` can return `already_synced` even when `upload_status` is `failed` | Medium | `metadata.py:167-196` | Add filter: `models.Version.upload_status != UploadStatus.failed` |
| 8 | **`import` inside function body** — `from fastapi.responses import Response` on lines 643 and 703 of sync.py | Low | `sync.py:643,703` | Move to top-level imports |
| 9 | **Device auto-create** in `get_metadata_diff` doesn't validate user ownership of the device_id | Medium | `sync.py:519-523` | The client can claim any device_id. Validate `device_id` belongs to `current_user`. |
| 10 | **`watch_folder` not gitignored** — but should be, to prevent accidental commits of synced files | Low | `.gitignore` | Add `watch_folder/` |

---

*This document is the single source of truth for the Week 9+ implementation. Every line number references the exact code as of the audit date. Build from scratch, understand every component, then ship it. That's how you build systems that don't break at 3 AM.*
