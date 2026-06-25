# ShadowDrive — Project Context

> Auto-generated from exhaustive source scan on 2026-06-23.
> Use this document as a single-source-of-truth reference for AI agents working on the codebase.

---

## 1. Project Overview

ShadowDrive is a decentralized file synchronization platform with three architectural layers:

| Layer | Location | Tech Stack |
|---|---|---|
| **Server-Logic** | `Server-Logic/` | Python 3.12, FastAPI, PostgreSQL (SQLAlchemy/asyncpg), MinIO (S3), Redis, Alembic |
| **Client-Logic** | `Client-Logic/` | Python 3.12+, aiohttp, watchdog (filesystem watcher), cryptography (Fernet) |
| **shadowdrive-ui** | `shadowdrive-ui/` | React 19, TypeScript, Vite, Tailwind CSS v4, shadcn/ui, better-auth, TanStack Query, Recharts, Sonner |

**Architecture pattern**: Three-tier. Clients sync to a central server. The server stores files in MinIO (S3-compatible object store) and metadata in PostgreSQL. Redis is used for pub/sub event broadcasting and caching. The UI communicates with the server via REST API + SSE.

---

## 2. Repository Structure

```
ShadowDrive/
├── AGENTS.md                    # AI agent collaboration rules
├── DESIGN.md                    # UI/UX design system
├── README.md                    # Project README
├── project-context.md           # THIS FILE
├── run.sh                       # Dev startup script
├── shadowdrive.yaml             # Docker Compose (server+infra)
│
├── Server-Logic/                # FastAPI backend
│   ├── docker-compose.yml
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .env.example
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 001_initial.py
│   ├── clear_db.py
│   ├── main.py
│   ├── database.py
│   ├── dependencies.py
│   ├── models.py
│   ├── schemas.py
│   ├── utils.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── sync.py
│   │   ├── events.py
│   │   ├── device.py
│   │   └── system.py
│   └── services/
│       ├── __init__.py
│       ├── metadata.py
│       ├── storage.py
│       └── worker.py
│
├── Client-Logic/               # Python sync client
│   ├── requirements.txt
│   ├── main.py
│   ├── __main__.py
│   ├── config.py
│   ├── logging_setup.py
│   ├── sync_engine.py
│   ├── diff_engine.py
│   ├── watcher.py
│   ├── local_api.py
│   ├── network_client.py
│   ├── resilient_http.py
│   ├── crypto_utils.py
│   ├── hash_utils.py
│   └── event_listener.py
│
├── shadowdrive-ui/             # React frontend
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── tsconfig.app.json
│   ├── tsconfig.node.json
│   ├── tailwind.config.ts
│   ├── postcss.config.js
│   ├── index.html
│   ├── public/
│   │   ├── logo.svg
│   │   ├── og-image.png
│   │   └── favicon/
│   │       └── ...
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── index.css
│       ├── vite-env.d.ts
│       ├── lib/
│       │   ├── client.ts
│       │   ├── auth-client.ts
│       │   └── utils.ts
│       ├── hooks/
│       │   ├── use-events.ts
│       │   ├── use-files.ts
│       │   ├── use-conflicts.ts
│       │   ├── use-nodes.ts
│       │   └── use-telemetry.ts
│       ├── components/
│       │   ├── ui/
│       │   │   ├── button.tsx
│       │   │   ├── card.tsx
│       │   │   ├── input.tsx
│       │   │   ├── label.tsx
│       │   │   ├── badge.tsx
│       │   │   ├── dialog.tsx
│       │   │   ├── table.tsx
│       │   │   ├── tabs.tsx
│       │   │   ├── scroll-area.tsx
│       │   │   ├── separator.tsx
│       │   │   ├── skeleton.tsx
│       │   │   ├── progress.tsx
│       │   │   └── tooltip.tsx
│       │   ├── dashboard-layout.tsx
│       │   └── theme-provider.tsx
│       ├── pages/
│       │   ├── AuthScreen.tsx
│       │   ├── FileExplorer.tsx
│       │   ├── ConflictResolution.tsx
│       │   ├── VersionHistory.tsx
│       │   ├── SystemHealth.tsx
│       │   ├── NetworkActivity.tsx
│       │   ├── NodeManagement.tsx
│       │   ├── NodeDeployment.tsx
│       │   └── LandingPage.tsx
│       └── contexts/
│           └── AuthContext.tsx
│
├── docs/                       # Project documentation
│   ├── architecture.md
│   ├── database.md
│   ├── api.md
│   ├── client.md
│   ├── deployment.md
│   ├── local-development.md
│   ├── getting-started.md
│   └── implementation-guide/
│       ├── 01-sprint-1-bug-fixes.md
│       ├── 02-sprint-2-file-explorer.md
│       ├── 03-sprint-3-conflict-resolution.md
│       ├── 04-sprint-4-version-history.md
│       ├── 05-sprint-5-real-time-collaboration.md
│       ├── 06-sprint-6-search.md
│       ├── 07-sprint-7-admin-dashboard-ux.md
│       ├── 08-sprint-8-soft-delete-restore.md
│       └── 09-sprint-9-sequential-scan-sync.md
│
├── database/                   # Database scripts
│   └── init.sql
│
└── tests/                      # Test directory (currently empty except __init__.py)
    └── __init__.py
```

---

## 3. Server-Logic (FastAPI Backend)

### 3.1 Main Application (`main.py`)

- FastAPI app with title "ShadowDrive API"
- CORS middleware configured to allow all origins (for dev)
- On startup: creates MinIO bucket (`shadowdrive-files`), connects Redis pub/sub, starts background file processing worker
- Route prefixes: `/api/v1/auth`, `/api/v1/users`, `/api/v1/sync`, `/api/v1/events`, `/api/v1/devices`, `/api/v1/system`
- Root endpoint (`GET /`) returns `{"message": "ShadowDrive API"}`
- SSE endpoint at `/api/v1/events/sse` for real-time event streaming
- Background worker processes file chunks concurrently via `asyncio.create_task`
- Global exception handlers for HTTPException, RequestValidationError, and generic Exception

Key patterns:
- Uses `database.get_db()` as dependency
- Redis pub/sub channels: `user:{user_id}:events` per user
- Background task for processing uploaded file chunks

### 3.2 Database Layer (`database.py`)

- **Engine**: `create_async_engine` with `asyncpg` driver
- **Session**: `async_sessionmaker` with `AsyncSession`
- **Base**: `DeclarativeBase` from SQLAlchemy 2.0
- `get_db()` — async generator that yields session, ensures rollback/close on exception
- `init_db()` — creates all tables via `Base.metadata.create_all`
- Database URL from env `DATABASE_URL` (default: `postgresql+asyncpg://postgres:postgres@localhost:5432/shadowdrive`)

### 3.3 Dependencies (`dependencies.py`)

- `get_current_user_id()` — extracts user UUID from JWT in `Authorization: Bearer <token>` header
  - Uses `python-jose` JWT with HS256
  - Looks for `sub` claim
  - Returns `uuid.UUID`
  - Used as a FastAPI dependency injected into protected routes
- `require_auth` — alias for `Depends(get_current_user_id)`

### 3.4 Utilities (`utils.py`)

- `hash_password(plain: str)` — SHA-256 hashing (NOT bcrypt — intentional choice documented in code)
- `verify_password(plain: str, hashed: str)` — constant-time comparison via `hmac.compare_digest`
- `create_access_token(data: dict)` — creates JWT with 30-day expiration
- `verify_access_token(token: str)` — verifies JWT, returns payload or raises 401

### 3.5 Models (`models.py`)

SQLAlchemy 2.0 mapped classes:

**`User`** (`users`):
- `id` — UUID, PK, default `uuid4`
- `email` — String(255), unique, non-null, indexed
- `username` — String(100), unique, non-null
- `password_hash` — String(255), non-null
- `storage_quota` — BigInteger, default 5_000_000_000 (5GB)
- `storage_used` — BigInteger, default 0
- `is_active` — Boolean, default True
- `created_at`, `updated_at` — DateTime, server_default now()

**`Device`** (`devices`):
- `id` — UUID, PK
- `user_id` — FK to users.id
- `device_name` — String(255)
- `device_type` — String(50) (e.g. "desktop", "laptop", "mobile")
- `os_type` — String(100)
- `last_ip` — String(45)
- `last_seen` — DateTime
- `is_active` — Boolean, default True
- `created_at`, `updated_at` — DateTime
- Relation: `user`

**`File`** (`files`):
- `id` — UUID, PK
- `user_id` — FK to users.id
- `name` — String(1024), non-null
- `path` — Text, non-null (full relative path including filename)
- `mime_type` — String(255)
- `size` — BigInteger, default 0
- `checksum` — String(64) (SHA-256 hex)
- `is_directory` — Boolean, default False
- `is_deleted` — Boolean, default False (soft delete)
- `parent_id` — UUID, self-referencing FK (nullable)
- `created_at`, `updated_at` — DateTime
- `version` — Integer, default 1
- Relations: `user`, `versions`, `parent`

**`FileVersion`** (`file_versions`):
- `id` — UUID, PK
- `file_id` — FK to files.id
- `version_number` — Integer
- `size` — BigInteger
- `checksum` — String(64)
- `storage_path` — Text (path in MinIO)
- `created_at` — DateTime
- Relation: `file`

**`Conflict`** (`conflicts`):
- `id` — UUID, PK
- `file_id` — FK to files.id
- `user_id` — FK to users.id
- `device_id` — FK to devices.id
- `conflict_type` — String(50)
- `base_version` — Integer
- `our_version` — Integer
- `their_version` — Integer
- `resolution` — String(20), nullable (pending/resolved/manual)
- `resolved_at` — DateTime, nullable
- `created_at` — DateTime
- Relations: `file`, `user`, `device`

**`SyncEvent`** (`sync_events`):
- `id` — UUID, PK
- `user_id` — FK to users.id (nullable — system events)
- `device_id` — FK to devices.id (nullable)
- `file_id` — FK to files.id (nullable)
- `event_type` — String(50) (file_created, file_modified, file_deleted, file_restored, conflict_detected, conflict_resolved, device_connected, device_disconnected, sync_started, sync_completed, sync_error, share_created, share_updated, share_deleted, heartbeat)
- `payload` — JSON, nullable
- `severity` — String(20), default "info"
- `created_at` — DateTime, indexed
- Relations: `user`, `device`, `file`

**`ShareLink`** (`share_links`):
- `id` — UUID, PK
- `file_id` — FK to files.id
- `owner_id` — FK to users.id
- `token` — String(64), unique, indexed
- `permission` — String(20), default "view" (view/edit)
- `expires_at` — DateTime, nullable
- `max_downloads` — Integer, nullable
- `download_count` — Integer, default 0
- `is_revoked` — Boolean, default False
- `created_at` — DateTime
- Relations: `file`, `owner`

**`ScannedFolder`** (`scanned_folders`):
- `id` — UUID, PK
- `user_id` — FK to users.id
- `device_id` — FK to devices.id
- `local_path` — Text (path on client device)
- `remote_path` — Text (path in cloud), unique
- `last_scanned_at` — DateTime, nullable
- `is_active` — Boolean, default True
- `sync_interval` — Integer, default 300 (seconds)
- `created_at`, `updated_at` — DateTime
- Relations: `user`, `device`

### 3.6 Schemas (`schemas.py`)

Pydantic models for request/response serialization:

- **Auth**: `LoginRequest` (email, password), `LoginResponse` (access_token, token_type, user), `RegisterRequest` (email, username, password), `RegisterResponse` (message), `UserResponse` (id, email, username, storage_quota, storage_used, is_active, created_at)
- **Device**: `DeviceResponse`, `CreateDeviceRequest`, `UpdateDeviceRequest`
- **File**: `FileResponse`, `FileCreate`, `FileUpdate`
- **Sync**: `SyncStatusResponse`, `ScanRequest`, `SyncFileRequest`, `SyncChunkRequest`, `SyncCompleteRequest`, `SyncBatchRequest`, `SyncBatchResponse`, `SyncBatchItem`
- **Conflict**: `ConflictResponse`, `ResolveConflictRequest`
- **Version**: `FileVersionResponse`
- **Event**: `SyncEventResponse`, `EventListResponse`
- **System**: `SystemHealthResponse`, `NodeInfoResponse`, `RegisterNodeRequest`, `UpdateNodeRequest`, `NodeMetricsResponse`, `PaginationMetadata`

Key schema details:
- `SyncBatchRequest` accepts list of `SyncBatchItem` with file metadata
- `SyncChunkRequest` contains file_id, chunk_index, total_chunks, data (bytes)
- `SystemHealthResponse` includes db_status, redis_status, minio_status, uptime_seconds, active_users, active_devices, pending_conflicts, version
- `NodeInfoResponse` includes id, name, node_type, status, ip, metrics, tags, region, etc.
- Pagination metadata with page, page_size, total_items, total_pages

### 3.7 Routers

#### `routers/auth.py` — Prefix `/api/v1/auth`
- `POST /register` — creates user, hashes password, returns message
- `POST /login` — validates credentials, returns JWT + user response
- `GET /me` — returns current user (requires auth)
- `POST /logout` — placeholder (returns success message)

#### `routers/user.py` — Prefix `/api/v1/users`
- `GET /` — returns current user profile
- `PATCH /` — updates profile fields (username kept as placeholder)
- `GET /usage` — returns storage usage (used/quota)

#### `routers/sync.py` — Prefix `/api/v1/sync`
- `POST /scan` — creates/updates ScannedFolder entry
- `POST /batch` — processes batch sync items (checks new/modified/deleted files, returns actions)
- `GET /status` — returns sync status summary
- `POST /upload` — creates file entry, uploads to MinIO, creates FileVersion, publishes event
- `POST /download/{file_id}` — returns signed S3 URL
- `POST /delete` — soft-deletes file(s)
- `POST /restore` — restores soft-deleted file(s)
- `POST /chunk/upload` — initiates chunked upload
- `POST /chunk/complete` — finalizes chunked upload (reassembles chunks)
- `GET /list` — lists files at a given path with pagination (path query param, page, page_size)
- `GET /search` — searches files by name with pagination

#### `routers/events.py` — Prefix `/api/v1/events`
- `GET /` — returns recent events with pagination (type filter, severity filter, page, page_size)
- `GET /sse` — SSE endpoint (streams events from Redis pub/sub per user)
- `POST /` — creates a manual event entry

#### `routers/device.py` — Prefix `/api/v1/devices`
- `GET /` — lists user's devices
- `POST /` — registers new device
- `GET /{device_id}` — get device detail
- `PATCH /{device_id}` — update device
- `DELETE /{device_id}` — deactivate device

#### `routers/system.py` — Prefix `/api/v1/system`
- `GET /health` — comprehensive health check (DB ping, MinIO ping, Redis ping, uptime, active_users, active_devices, pending_conflicts, version)
- `GET /nodes` — lists nodes (paginated)
- `POST /nodes` — register node
- `GET /nodes/{node_id}` — get node detail
- `PATCH /nodes/{node_id}` — update node
- `DELETE /nodes/{node_id}` — delete node
- `GET /metrics` — system metrics (cpu, memory, disk, db_connections, active_syncs, event_rate)

### 3.8 Services

#### `services/storage.py` — MinIO interaction
- `StorageService` class initialized with `Minio` client
- `_init_bucket()` — creates bucket if not exists
- `upload_file(user_id, file_id, data)` — uploads bytes to `{user_id}/{file_id}`
- `download_file(user_id, file_id)` — returns `BytesIO` of object
- `delete_file(user_id, file_id)` — removes object
- `get_signed_url(user_id, file_id)` — returns presigned GET URL (7-day expiry)
- `file_exists(user_id, file_id)` — checks object existence
- `list_user_files(user_id)` — lists all objects with prefix `{user_id}/`
- `upload_chunk(user_id, file_id, chunk_index, data)` — uploads chunk to `{user_id}/{file_id}/chunks/{chunk_index}`
- `complete_chunked_upload(user_id, file_id, total_chunks)` — downloads and reassembles chunks, uploads final, cleans up chunks
- `delete_user_directory(user_id)` — removes all objects with prefix `{user_id}/` (for user deletion)

#### `services/metadata.py` — Database queries
- `MetadataService` class — static methods, session first arg
- CRUD for: User, File, FileVersion, Conflict, Device, SyncEvent, ShareLink, ScannedFolder
- Key methods:
  - `get_user_by_email`, `get_user_by_id`, `create_user`
  - `create_file`, `get_user_files`, `get_file_by_path`, `get_file_by_id`, `update_file`, `delete_file`, `search_files`
  - `create_version`, `get_file_versions`
  - `create_conflict`, `resolve_conflict`, `get_file_conflicts`
  - `create_event`, `get_events_paginated`
  - `get_or_create_device`, `update_device`
  - `create_share_link`, `get_share_link_by_token`, `increment_download_count`
  - `health_check_db` — returns `{"status": "healthy"}` or raises
  - `get_active_users_count`, `get_active_devices_count`, `get_pending_conflicts_count`
  - `get_or_create_scanned_folder`, `get_scanned_folders`

#### `services/worker.py` — Background processing
- `process_chunked_upload(session, file_id, total_chunks)` — orchestrates chunk assembly
- `process_file_upload(session, user_id, file_data, filename, path, mime_type, file_size, checksum, device_id)` — full upload pipeline (create/update file, create version, upload to MinIO, create event)
- `process_file_delete(session, user_id, file_id, device_id)` — soft delete pipeline
- `process_file_restore(session, user_id, file_id)` — restore pipeline
- `handle_conflict(session, file_id, user_id, device_id, conflict_type, base_version, our_version, their_version)` — creates conflict entry and event
- `publish_event(redis, user_id, event_data)` — publishes to Redis channel `user:{user_id}:events`

### 3.9 Infrastructure (`docker-compose.yml`)

Services defined:
- **postgres**: PostgreSQL 16 on port 5432, with `init.sql` mounted, persistent volume
- **minio**: MinIO on ports 9000 (API) and 9001 (console), persistent volume, default bucket creation
- **redis**: Redis 7 on port 6379, persistent volume
- **api**: FastAPI app built from Dockerfile, port 8000, depends on postgres+minio+redis, env vars for all connections

Environment variables (.env.example):
- `DATABASE_URL`, `SECRET_KEY`, `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`, `REDIS_URL`

### 3.10 Database Migrations (`alembic/`)

- `alembic.ini` configured for async with `target_metadata = models.Base.metadata`
- `env.py` imports `models.Base`, uses async engine
- Initial migration (`001_initial.py`) creates all 8 tables with proper types (UUID, Text, Boolean, etc.)

### 3.11 Other Server Files

- `clear_db.py` — standalone script that drops all tables (for dev reset)
- `Dockerfile` — multi-stage Python 3.12-slim build
- `requirements.txt` — fastapi, uvicorn, sqlalchemy, asyncpg, alembic, minio, redis, python-jose, pydantic, pydantic-settings, aiofiles, python-multipart

---

## 4. Client-Logic (Python Sync Client)

### 4.1 Entry Points

- **`main.py`** — `main()` function: loads config, creates `SyncEngine`, runs `engine.run()`
- **`__main__.py`** — allows `python -m client_logic`, imports and calls `main()`

### 4.2 Configuration (`config.py`)

- `SyncConfig` dataclass loaded from `shadowdrive.yaml` (or env vars):
  - `server_url` (default: `http://localhost:8000`)
  - `api_key` (for auth)
  - `device_name`, `device_type`, `os_type`
  - `sync_dir` (local directory to sync)
  - `sync_interval` (seconds, default 300)
  - `max_file_size` (bytes, default 100MB)
  - `exclude_patterns` (list of glob patterns)
  - `enable_encryption` (bool, default False)
  - `encryption_key` (Fernet key)
  - `log_level` (default "INFO")
  - `watch_enabled` (bool, default True)
  - `chunk_size` (bytes, default 5MB, for chunked upload)
- `load_config(path="shadowdrive.yaml")` — reads YAML file, returns `SyncConfig`

### 4.3 Logging (`logging_setup.py`)

- Configures file + console logging
- Log file: `shadowdrive.log` in working directory
- Rotating file handler (10MB, 3 backups)
- Format: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`

### 4.4 Sync Engine (`sync_engine.py`)

`SyncEngine` class — the orchestrator:

- **`__init__`**: receives config, creates all sub-components (DiffEngine, Watcher, NetworkClient, EventListener, LocalAPI, CryptoUtils)
- **`run()`**: main loop
  1. Registers device with server (POST /devices)
  2. Starts sync if registration succeeds
  3. Full sync: scan local files → compute diff → upload/download as needed
  4. Starts `Watcher` for real-time file monitoring (if enabled)
  5. Starts `EventListener` for SSE events
  6. Falls into periodic sync loop with configurable interval
  7. On KeyboardInterrupt: graceful shutdown
  8. On login failure: waits 60s, retries
- **`perform_full_sync()`**: collects local file states, computes diff, uploads new/modified, downloads remote changes
- **`handle_remote_event(event)`**: dispatches on event_type (file_modified → download, file_deleted → delete local, conflict_detected → resolve strategy)
- **`resolve_conflict(conflict)`**: currently uses "ours" strategy (local version wins)
- **`stop()`**: signals shutdown for all components

### 4.5 Diff Engine (`diff_engine.py`)

`DiffEngine` — computes differences between local and remote file trees:

- Uses a dict-based structure to represent file trees
- `compute_diff(local_files, remote_files)` → returns `DiffResult` with:
  - `to_upload`: files that exist locally but not remotely, or have different checksums
  - `to_download`: files that exist remotely but not locally, or have different checksums
  - `to_delete_remote`: files deleted locally but exist remotely
  - `to_delete_local`: files deleted remotely but exist locally
- `build_file_tree(file_list)` — converts list of file dicts to `{relative_path: checksum}` dict
- Comparisons based on file path (relative to sync root) and SHA-256 checksum

### 4.6 Watcher (`watcher.py`)

`Watcher` — real-time filesystem monitoring via `watchdog`:

- `start()`: sets up `watchdog.observers.Observer` with custom `FileSystemEventHandler`
- Handler processes: `on_modified`, `on_created`, `on_deleted`, `on_moved`
- Events are debounced (500ms) to avoid duplicate triggers
- Debounced events → put into `asyncio.Queue` for processing
- `stop()`: stops observer
- `get_pending_changes()`: returns and clears pending changes queue

### 4.7 Network Client (`network_client.py`)

`NetworkClient` — HTTP API wrapper using aiohttp:

- `__init__`: stores server URL, auth token, creates session with connector limits
- `set_auth_token(token)`: updates bearer token
- `register_device(device_info)` → POST /devices
- `fetch_remote_files(path="/")` → GET /sync/list
- `upload_file(file_path, file_data, ...)` → POST /sync/upload
- `download_file(file_id)` → POST /sync/download (gets signed URL, then fetches)
- `delete_file(file_id)` → POST /sync/delete
- `restore_file(file_id)` → POST /sync/restore
- `upload_chunk(file_id, chunk_index, total_chunks, data)` → POST /sync/chunk/upload
- `complete_chunked_upload(file_id, total_chunks)` → POST /sync/chunk/complete
- `search_files(query)` → GET /sync/search
- `send_sync_batch(items)` → POST /sync/batch
- `report_sync_status(status)` → GET /sync/status
- `health_check()` → GET /system/health
- Implements retry with exponential backoff for transient failures

### 4.8 Resilient HTTP Client (`resilient_http.py`)

`ResilientHTTPClient` — HTTP layer with retry and circuit breaker:

- Constructor: base_url, timeout (default 30s), max_retries (default 3), initial_backoff (1s), max_backoff (30s), circuit_breaker_threshold (5 failures), circuit_breaker_reset_timeout (60s)
- `_get_session()` — creates aiohttp.ClientSession with timeout
- `request(method, endpoint, ...)` — core:
  - Implements retry with exponential backoff + jitter
  - Circuit breaker: after `circuit_breaker_threshold` consecutive failures, opens circuit for `circuit_breaker_reset_timeout` seconds
  - Logs retry attempts and circuit state changes
  - Handles aiohttp errors, timeouts, connection errors
- Convenience methods: `get()`, `post()`, `put()`, `patch()`, `delete()`
- `close()` — closes session

### 4.9 Crypto Utilities (`crypto_utils.py`)

`CryptoUtils` — file encryption/decryption using `cryptography.fernet.Fernet`:

- `__init__`: accepts encryption key (bytes), creates Fernet cipher
- `encrypt_file(file_path)` — reads file bytes, encrypts, writes back
- `decrypt_file(file_path)` — reads encrypted bytes, decrypts, writes back
- `encrypt_data(data: bytes)` → encrypted bytes
- `decrypt_data(data: bytes)` → decrypted bytes
- `generate_key()` → static method, returns new Fernet key
- `key_to_str(key)`, `str_to_key(s)` — conversion helpers

### 4.10 Hash Utilities (`hash_utils.py`)

- `compute_checksum(file_path, chunk_size=8192)` — computes SHA-256 hex digest of file, streaming (memory efficient for large files)
- `checksum_match(file_path, expected_checksum)` — returns bool

### 4.11 Event Listener (`event_listener.py`)

`EventListener` — SSE client for real-time events:

- `start()`: connects to `/events/sse` via aiohttp, iterates SSE events
- Events parsed as JSON, put into `asyncio.Queue`
- Auto-reconnect on connection loss (5s delay)
- `stop()`: signals shutdown
- `get_pending_events()`: returns and clears pending events
- `received_events`: counter of total events received

### 4.12 Local API (`local_api.py`)

`LocalAPI` — local filesystem abstraction:

- `__init__`: sync_root path
- `scan_directory(subdir="")` — walks directory, returns list of `{path, checksum, size, mtime}` dicts, respects exclude patterns
- `read_file(relative_path)` — reads file bytes
- `write_file(relative_path, data)` — writes file bytes, creates parent dirs
- `delete_file(relative_path)` — deletes file
- `move_file(src, dst)` — renames/moves file
- `get_file_info(relative_path)` — returns `{path, checksum, size, mtime, exists}`
- `file_exists(relative_path)` — bool
- `ensure_directory(relative_path)` — creates directories

### 4.13 Client `requirements.txt`

```
aiohttp>=3.9.0
pyyaml>=6.0
watchdog>=4.0.0
cryptography>=41.0.0
```

---

## 5. shadowdrive-ui (React/TypeScript Frontend)

### 5.1 Project Setup (`package.json`)

```json
{
  "name": "shadowdrive-ui",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "lint": "eslint .",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "react-router-dom": "^7.1.1",
    "better-auth": "^1.1.16",
    "@better-auth/react": "^1.1.16",
    "@tanstack/react-query": "^5.62.7",
    "recharts": "^2.15.0",
    "sonner": "^1.7.1",
    "lucide-react": "^0.468.0",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.6.0",
    "class-variance-authority": "^0.7.1",
    "@radix-ui/react-dialog": "^1.1.4",
    "@radix-ui/react-scroll-area": "^1.2.2",
    "@radix-ui/react-separator": "^1.1.1",
    "@radix-ui/react-slot": "^1.1.1",
    "@radix-ui/react-tabs": "^1.1.2",
    "@radix-ui/react-tooltip": "^1.1.7"
  },
  "devDependencies": {
    "@types/react": "^19.0.2",
    "@types/react-dom": "^19.0.2",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "~5.7.2",
    "vite": "^6.0.5",
    "tailwindcss": "^4.0.0",
    "@tailwindcss/vite": "^4.0.0",
    "postcss": "^8.4.49",
    "autoprefixer": "^10.4.20",
    "eslint": "^9.17.0",
    "@eslint/js": "^9.17.0",
    "globals": "^15.14.0",
    "typescript-eslint": "^8.18.2",
    "eslint-plugin-react-hooks": "^5.1.0",
    "eslint-plugin-react-refresh": "^0.4.16"
  }
}
```

### 5.2 Build Configuration

- **Vite** v6 with React plugin + Tailwind CSS v4 vite plugin
- **TypeScript** 5.7, strict mode, path alias `@/` → `src/`
- **Tailwind CSS** v4 with `@tailwindcss/vite` plugin (no Tailwind config needed for v4)
- **PostCSS** with autoprefixer
- **ESLint** 9 flat config, react-hooks + react-refresh plugins

### 5.3 App Entry (`main.tsx`, `App.tsx`, `index.css`)

**`main.tsx`**:
```tsx
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <ThemeProvider defaultTheme="dark">
        <AuthProvider>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>
  </StrictMode>
)
```

**`App.tsx`** — Routes:
- `/` → LandingPage
- `/auth` → AuthScreen
- `/dashboard` → DashboardLayout (protected, redirects to /auth if unauthenticated)
  - Index → FileExplorer
  - `conflicts` → ConflictResolution
  - `versions` → VersionHistory
  - `health` → SystemHealth
  - `activity` → NetworkActivity
  - `nodes` → NodeManagement
  - `nodes/deploy` → NodeDeployment

**`index.css`** — Tailwind CSS v4 import: `@import "tailwindcss"`

### 5.4 Library Modules

#### `lib/client.ts` — API Client

- Creates Axios instance with `baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1"`
- Request interceptor: attaches `Authorization: Bearer <token>` from localStorage
- Response interceptor: on 401, clears token and redirects to `/auth`
- Exported helper functions matching each backend endpoint:
  - Auth: `login()`, `register()`, `getMe()`, `logout()`
  - Files: `listFiles()`, `searchFiles()`, `uploadFile()`, `deleteFile()`, `restoreFile()`, `getFileVersions()`, `getFileConflicts()`
  - Conflicts: `listConflicts()`, `resolveConflict()`
  - Events: `listEvents()`
  - Devices: `listDevices()`, `registerDevice()`, `updateDevice()`, `deleteDevice()`
  - System: `getSystemHealth()`, `listNodes()`, `registerNode()`, `getNodeMetrics()`, `getSystemMetrics()`
  - Users: `getUserProfile()`, `getStorageUsage()`

#### `lib/auth-client.ts` — better-auth Configuration

- Configured `better-auth` client with `react` plugin
- Uses `http://localhost:8000/api/v1/auth` as base URL
- Exports `authClient`, `useSession`, `useListSessions`, etc.
- Note: currently unused as the app uses custom auth flow via `AuthContext`

#### `lib/utils.ts` — Utilities

- `cn()` — merges Tailwind classes using `clsx` + `tailwind-merge`

### 5.5 Auth Context (`contexts/AuthContext.tsx`)

- `AuthContext` created via `createContext`
- `AuthProvider` component:
  - Manages `user`, `token`, `loading` state
  - On mount: reads token from localStorage, calls `/auth/me` to validate
  - `login(email, password)` → POST `/auth/login`, stores token in localStorage, sets user
  - `register(email, username, password)` → POST `/auth/register`
  - `logout()` → clears token and user, removes from localStorage
  - `isAuthenticated` derived boolean
- `useAuth()` hook — consumes context, throws if used outside provider

### 5.6 Theme Provider (`components/theme-provider.tsx`)

- Simple React context for dark/light theme toggle
- `ThemeProvider` with `defaultTheme="dark"`, stores preference in localStorage
- Applies `dark` class to `document.documentElement`
- `useTheme()` hook returns `{ theme, setTheme }`

### 5.7 Dashboard Layout (`components/dashboard-layout.tsx`)

- `DashboardLayout` component:
  - Sidebar navigation with links to FileExplorer, Conflicts, Versions, Health, Activity, Nodes, Deploy
  - Uses `lucide-react` icons
  - Top bar with user info (avatar, email) and logout button
  - `<Outlet />` for nested routes
  - Collapsible sidebar (state stored in localStorage)
  - `useAuth()` for user data + logout

### 5.8 UI Components (`components/ui/`)

All built with Radix UI primitives + `cn()` utility, following shadcn/ui conventions:

- **button.tsx** — `Button` with variants (default, destructive, outline, secondary, ghost, link) and sizes (default, sm, lg, icon), uses `Slot` from Radix
- **card.tsx** — `Card`, `CardHeader`, `CardTitle`, `CardDescription`, `CardContent`, `CardFooter`
- **input.tsx** — `Input` with consistent styling
- **label.tsx** — `Label` with Radix primitive
- **badge.tsx** — `Badge` with variants (default, secondary, destructive, outline)
- **dialog.tsx** — `Dialog`, `DialogTrigger`, `DialogContent`, `DialogHeader`, `DialogFooter`, `DialogTitle`, `DialogDescription`, uses Radix Dialog
- **table.tsx** — `Table`, `TableHeader`, `TableBody`, `TableRow`, `TableHead`, `TableCell`
- **tabs.tsx** — `Tabs`, `TabsList`, `TabsTrigger`, `TabsContent`, uses Radix Tabs
- **scroll-area.tsx** — `ScrollArea` with Radix
- **separator.tsx** — `Separator` with Radix
- **skeleton.tsx** — `Skeleton` for loading states
- **progress.tsx** — `Progress` with Radix
- **tooltip.tsx** — `TooltipProvider`, `Tooltip`, `TooltipTrigger`, `TooltipContent` with Radix

### 5.9 Pages

#### `LandingPage.tsx`
- Landing page with hero section, features grid, and CTA to login
- Marketing copy about decentralized file sync
- Styled with Tailwind, uses `lucide-react` icons

#### `AuthScreen.tsx`
- Login/Register toggle
- Form fields: email, password (login); email, username, password, confirm password (register)
- Uses `useAuth()` hook
- Shows error messages from API
- Redirects to `/dashboard` on success

#### `FileExplorer.tsx`
- File browser with breadcrumb navigation
- Lists files/folders at current path
- Shows file metadata (name, size, type, modified date)
- Uses `useFiles()` hook
- Placeholder comment: "TODO: Implement proper file upload with progress tracking"

#### `ConflictResolution.tsx`
- Lists unresolved conflicts
- Each conflict shows: file path, conflict type, versions (base/ours/theirs)
- "Resolve" button with strategy picker
- Uses `useConflicts()` hook
- Loading, empty, and error states handled

#### `VersionHistory.tsx`
- Select a file, view its version history
- Version list with version number, size, checksum, timestamp
- No download/restore buttons yet (TODO)
- Uses `useFiles().getFileVersions` from the hook

#### `SystemHealth.tsx`
- Displays system health metrics from `/system/health`
- Metric cards: DB status, Redis status, MinIO status, Uptime, Active Users, Active Devices, Pending Conflicts
- Auto-refresh every 30s via TanStack Query `refetchInterval`
- Loading, error states

#### `NetworkActivity.tsx`
- Real-time event log
- Recharts line chart showing event rate over time (last 60 data points)
- Event list with type, severity, timestamp, description
- Uses `useEvents()` hook
- Loading, empty, error states

#### `NodeManagement.tsx`
- Lists registered nodes
- Table with: name, type, status, IP, region, tags, last seen, actions
- Node status badges (online=green, offline=red, maintenance=yellow)
- Uses `useNodes()` hook
- Loading, empty, error states handled

#### `NodeDeployment.tsx`
- Form to deploy a new node
- Fields: name, node type (storage/compute/mirror), IP address, region, tags
- Uses `useNodes().registerNode()` mutation
- Success toast + redirect to NodeManagement on success

### 5.10 Custom Hooks

#### `use-files.ts`
- `useFiles()` returns:
  - `files`, `isLoading`, `error` — from `listFiles(currentPath)`
  - `currentPath`, `setCurrentPath` — for breadcrumb navigation
  - `searchQuery`, `setSearchQuery`, `searchResults` — from `searchFiles`
  - `uploadFile(file, path)` — mutation
  - `deleteFile(fileId)` — mutation
  - `restoreFile(fileId)` — mutation
  - `getFileVersions(fileId)` — query (enabled only when fileId provided)
  - `getFileConflicts(fileId)` — query (enabled only when fileId provided)
- Uses TanStack Query with `queryKey: ['files', currentPath]`

#### `use-events.ts`
- `useEvents()` returns:
  - `events`, `isLoading`, `error` — from `listEvents`
  - Pagination: `page`, `setPage`, `totalPages`
  - Auto-refresh every 10s
- Query key: `['events', page]`

#### `use-conflicts.ts`
- `useConflicts()` returns:
  - `conflicts`, `isLoading`, `error` — from `listConflicts`
  - `resolveConflict(conflictId, resolution)` — mutation that invalidates conflicts query

#### `use-nodes.ts`
- `useNodes()` returns:
  - `nodes`, `isLoading`, `error` — from `listNodes`
  - `registerNode(data)` — mutation, invalidates nodes query
  - `nodeMetrics`, `metricsLoading` — from `getNodeMetrics`
  - `getNodeById(id)` — query

#### `use-telemetry.ts`
- `useTelemetry()` returns:
  - `health`, `healthLoading`, `healthError` — from `getSystemHealth`, auto-refresh 30s
  - `metrics`, `metricsLoading` — from `getSystemMetrics`, auto-refresh 15s

---

## 6. Tests

- `tests/__init__.py` — empty package marker
- No test files currently exist beyond the package marker

---

## 7. Infrastructure & Configuration

### 7.1 Docker Compose (`shadowdrive.yaml`)

The root `shadowdrive.yaml` mirrors the `Server-Logic/docker-compose.yml`:
- Services: postgres, minio, redis, api
- Ports: PostgreSQL 5432, MinIO 9000/9001, Redis 6379, API 8000

### 7.2 Database Init (`database/init.sql`)

- Creates `shadowdrive` database and user
- Grants all privileges
- Note: This is a fallback — Alembic migrations handle schema management

### 7.3 Environment Configuration

Server requires: `DATABASE_URL`, `SECRET_KEY`, `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET`, `REDIS_URL`

### 7.4 `run.sh`

Development startup script:
```bash
docker compose -f shadowdrive.yaml up -d    # Start infra
# Wait for PostgreSQL
cd Server-Logic && alembic upgrade head      # Run migrations
uvicorn main:app --reload --port 8000        # Start API
```

### 7.5 `AGENTS.md`

AI agent rules including:
- Keep responses concise
- Use planning mode for new features (ask clarifying questions, use deep-dive sub-agents)
- Never implement features yourself when possible — use sub-agents
- After completing features, run lint, type check, and build
- On DB schema changes: always run drizzle generate + migrate (never push)
- Test your changes, don't assume they work
---

## 8. Documentation Index

| File | Purpose |
|---|---|
| `docs/architecture.md` | Three-tier architecture, data flow, component interaction |
| `docs/database.md` | Schema details, relationships, indexes, migration strategy |
| `docs/api.md` | Full REST API reference, auth, endpoints, SSE, pagination |
| `docs/client.md` | Client-Logic architecture, sync lifecycle, configuration |
| `docs/deployment.md` | Docker deployment, configuration, scaling, monitoring |
| `docs/local-development.md` | Setup guide for local dev without Docker |
| `docs/getting-started.md` | Quick-start guide for new developers |
| `docs/implementation-guide/01-sprint-1-bug-fixes.md` | **Current active sprint** — 6 bugs to fix (auth error handling, watcher crash, SSE reconnect, chunked upload, conflict edge cases, health check timeout) |
| `docs/implementation-guide/02-sprint-2-file-explorer.md` | File browser UI improvements, search, filtering |
| `docs/implementation-guide/03-sprint-3-conflict-resolution.md` | Visual conflict resolver, three-way merge UI |
| `docs/implementation-guide/04-sprint-4-version-history.md` | Version timeline, diff viewer, restore workflow |
| `docs/implementation-guide/05-sprint-5-real-time-collaboration.md` | Live cursors, presence, real-time updates |
| `docs/implementation-guide/06-sprint-6-search.md` | Full-text search, indexing, search UI |
| `docs/implementation-guide/07-sprint-7-admin-dashboard-ux.md` | Admin panel, user management, analytics |
| `docs/implementation-guide/08-sprint-8-soft-delete-restore.md` | Trash UI, retention policies, purge |
| `docs/implementation-guide/09-sprint-9-sequential-scan-sync.md` | Full sync protocol, progress tracking, resume |

---

## 9. Key Architectural Decisions

1. **SHA-256 for passwords** (not bcrypt): documented as intentional — likely for simplicity in a local/self-hosted tool
2. **JWT with 30-day expiry**: long-lived tokens, no refresh token mechanism
3. **Soft delete for files**: `is_deleted` flag, no trash/purge UI yet (planned in sprint 8)
4. **Background worker pattern**: async background tasks for file processing, not separate worker process
5. **SSE via Redis pub/sub**: events published to Redis, SSE endpoint reads from Redis per-user channels
6. **Chunked upload**: files split into configurable chunks (default 5MB), reassembled server-side
7. **"Ours" conflict strategy**: current default — local version wins
8. **Tailwind CSS v4**: no `tailwind.config.js` needed (uses CSS-based configuration)
9. **Radix UI primitives**: accessible, unstyled component primitives wrapped with shadcn/ui patterns
10. **better-auth configured but unused**: auth-client.ts exists but AuthContext provides custom auth flow; better-auth is installed but not wired into the app

---

## 10. Known Issues & Technical Debt

1. **Tests**: No test files implemented (only `tests/__init__.py` exists)
2. **Sprint 1 bugs**: 6 known bugs documented in implementation guide — highest priority
3. **No refresh tokens**: JWT tokens valid for 30 days with no rotation
4. **Conflict resolution**: Only "ours" strategy implemented; no UI for user to choose
5. **Version history**: No download/restore buttons on VersionHistory page
6. **File upload**: No progress tracking on FileExplorer (placeholder comment)
7. **Logout**: Server-side logout endpoint is a no-op (no token blacklist)
8. **better-auth**: Library installed but not integrated; custom auth used instead
9. **No pagination component**: API supports pagination but UI pages don't implement pagination controls (except NetworkActivity)
10. **CORS**: Allow all origins in production (should be restricted)
11. **No rate limiting**: API endpoints have no rate limiting
12. **Search functionality**: Client has `search_files` method but no search UI on FileExplorer
