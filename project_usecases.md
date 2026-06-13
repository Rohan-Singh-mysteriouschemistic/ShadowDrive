# ShadowDrive++ — Definitive Saturated Use Case & System Behavior Blueprint

> **Generated:** 2026-06-09 (v2 — Fully Saturated Red Team Edition)  
> **Scope:** `Client-Logic/` · `Server-Logic/` · `shadowdrive-ui/`  
> **Format:** Every item describes a discrete **User/System Action** and the exact **Expected System State** across all layers.  
> **Philosophy:** Zero abstraction. Every click, every byte, every failure mode.

---

## SECTION 1: Authentication, Onboarding & Access

### 1.1 — Account Creation via CLI

| # | User Action | System Response |
|---|-------------|-----------------|
| 1.1.1 | User runs `python main.py register` from the `Client-Logic/` directory. | `main.py:run_register()` prints the registration banner and prompts for **Username**, **Email**, and **Password** (password masked via `getpass`). |
| 1.1.2 | User enters valid username, email, and password. | `network_client.register_user()` sends `POST /users/register` with JSON `{username, email, password}` via `resilient_http.request()` (bypassing token injection). |
| 1.1.3 | Server receives the registration request. | `Server-Logic/server/app/routers/user.py` validates uniqueness of username and email against the `users` table. If unique, it hashes the password via `utils.hash()` (bcrypt) and inserts a new `User` row with a default `storage_quota` of **5 GB** (5368709120 bytes). Returns `201 Created`. |
| 1.1.4 | Registration succeeds on the client. | `main.py` immediately auto-logs in by calling `network_client.login_user(email, password)` → `POST /users/login`. The server returns a signed JWT (`access_token`). The token is persisted to `shadow.db` in the `settings` table under key `jwt_token`. |
| 1.1.5 | Auto-login succeeds. | `main.py` calls `_prompt_and_store_encryption_key(email)`. The user is prompted for an **Encryption Passphrase** (and confirmation). `crypto_utils.derive_key()` runs **PBKDF2-HMAC-SHA256** with 100,000 iterations using a SHA-256 hash of the normalized email as salt, producing a 32-byte AES-256 key. The hex-encoded key is stored in `shadow.db` under key `encryption_key`. The email is stored under key `user_email`. |
| 1.1.6 | User enters mismatched passphrases. | `main.py` prints `[ERROR] Passphrases do not match.` and returns without storing any key. Encryption remains **disabled** — files will be uploaded in plaintext. |
| 1.1.7 | User enters an already-registered email. | Server returns `400 Bad Request` with detail. `network_client.register_user()` returns `(False, "Registration failed: ...")`. The CLI prints the error and exits. |
| 1.1.8 | User enters an already-registered username but different email. | Server returns `400 Bad Request` with detail about username uniqueness violation (`unique_device_per_user` constraint). CLI prints the error. |
| 1.1.9 | User enters an empty username (just presses Enter). | Python `input()` returns `""`. `POST /users/register` sends `username: ""`. Server's validation rejects it (non-nullable, or length constraint). Returns `422 Unprocessable Entity`. |
| 1.1.10 | User enters a username with 51+ characters (exceeds `String(50)` column limit). | Server's SQLAlchemy `String(50)` column truncates or rejects depending on DB engine. PostgreSQL raises `DataError`. Client receives `500 Internal Server Error` or `422`. |
| 1.1.11 | User enters an email with 256+ characters (exceeds `String(255)` limit). | Same as above — column constraint violation. |
| 1.1.12 | User enters a password with special characters (`é`, `中文`, emoji 🔑). | `getpass` captures the raw Unicode string. `bcrypt` hashing handles arbitrary bytes. Server stores the bcrypt hash. Login with the same Unicode password succeeds. |
| 1.1.13 | Network drops exactly after registration succeeds but before auto-login. | `register_user()` returns `(True, ...)`. `login_user()` fails with `ConnectionError`. The user has an account but no JWT locally. Must manually run `python main.py login`. |
| 1.1.14 | User Ctrl+C during passphrase prompt. | `KeyboardInterrupt` is raised. `main.py` catches it or Python exits. No encryption key stored. The JWT from auto-login is already saved. Sync will work in plaintext mode. |
| 1.1.15 | User runs `python main.py register` when `shadow.db` does not exist. | `sqlite3.connect(config.DB_PATH)` auto-creates the file. `CREATE TABLE IF NOT EXISTS settings` ensures the table exists. Registration proceeds normally. |
| 1.1.16 | User runs `python main.py register` when `shadow.db` is locked by another process. | `sqlite3.connect(..., timeout=30.0)` waits up to 30 seconds. If still locked, raises `sqlite3.OperationalError: database is locked`. Registration fails with a local error. |
| 1.1.17 | Server is completely unreachable during registration. | `resilient_http.request()` retries 5 times with exponential backoff. Circuit breaker opens after 5 failures. `register_user()` catches `RequestException` and returns `(False, "Network error: ...")`. |
| 1.1.18 | User runs `register` twice rapidly in two terminals with the same email. | First request succeeds, second hits the `UNIQUE` constraint on `email`. Server returns `400`. Second terminal shows error. |

### 1.2 — Account Creation via Web UI

| # | User Action | System Response |
|---|-------------|-----------------|
| 1.2.1 | User navigates to the ShadowDrive web UI (`http://localhost:5173`) and sees the Landing Page. | `LandingPage.tsx` renders the hero section, feature grid, and "Get Started" CTA button. |
| 1.2.2 | User clicks "Get Started" or navigates to `/auth`. | `AuthScreen.tsx` renders the authentication form with **Login** and **Register** tabs. Default tab is Login. |
| 1.2.3 | User switches to the Register tab and fills in Username, Email, Password, and Encryption Passphrase. | Component state captures all four fields. The passphrase field is optional — if left blank, encryption is skipped. |
| 1.2.4 | User clicks "Create Account". | `AuthScreen.tsx` sends `POST http://127.0.0.1:8001/api/auth/register` to the **local client agent** (`local_api.py`), not directly to the backend. Payload: `{username, email, password, passphrase}`. |
| 1.2.5 | Local agent receives the registration request. | `local_api.py:register()` calls `network_client.register_user()` → server. On success, it auto-calls `network_client.login_user()` to get a JWT. If a passphrase was provided, it derives the AES key via `crypto_utils.derive_key()` and stores it in `shadow.db`. It then calls `_start_watcher_if_needed()` which spawns two daemon threads: the **Watchdog filesystem observer** (`watcher.main()`) and the **Sync Engine** (`sync_engine.start_sync_loop()`). Finally, `event_listener.start()` spawns the **SSE listener** daemon thread. |
| 1.2.6 | Local agent returns success. | `AuthScreen.tsx` stores the returned `access_token` in `localStorage` under key `shadowdrive_token` and navigates to `/vault` (the File Explorer). |
| 1.2.7 | User clicks "Create Account" with empty fields. | Frontend validation should catch empty fields. If not, the local agent forwards the empty payload to the server, which returns `422`. UI shows an error message. |
| 1.2.8 | User clicks "Create Account" but the local agent (port 8001) is not running. | `fetch()` throws `ERR_CONNECTION_REFUSED`. The `catch` block in `AuthScreen.tsx` shows "Connection to local agent failed" or similar error. |
| 1.2.9 | User clicks "Create Account" and local agent is running but backend server is down. | Local agent calls `network_client.register_user()` which fails with `ConnectionError`. Local agent returns `500` or error JSON. UI displays the server error. |
| 1.2.10 | User rapidly double-clicks "Create Account". | Two simultaneous `POST` requests hit the local agent. The first succeeds. The second hits the unique constraint on email. Local agent returns error for the second. UI may show a brief error flash before the first response navigates away. |
| 1.2.11 | User enters a passphrase on registration, then logs in on UI without entering passphrase. | Login proceeds without passphrase. `config.encryption_key` remains `None`. Files from the server are downloaded encrypted but decryption fails with `[CRYPTO ERROR] Failed to decrypt chunk ... InvalidTag`. Files are NOT written to disk. |

### 1.3 — Login & Session Initiation via CLI

| # | User Action | System Response |
|---|-------------|-----------------|
| 1.3.1 | User runs `python main.py login`. | `main.py:run_login()` prompts for Email and Password. |
| 1.3.2 | User enters valid credentials. | `network_client.login_user()` sends `POST /users/login` via `resilient_http.request()`. Server validates email existence and bcrypt password verification via `utils.verify()`. On success, `utils.create_access_token()` generates a JWT with `{"user_id": <id>}` payload. The JWT is returned. |
| 1.3.3 | Login succeeds. | The JWT is saved to `shadow.db` under key `jwt_token`. Any previous `device_id` is cleared via `_clear_device()` to prevent cross-user 403 errors. `config.sync_suspended` is set to `False`. The encryption key setup flow runs (same as 1.1.5). |
| 1.3.4 | User enters wrong password. | Server returns `401 Unauthorized` with `detail: "Invalid Credentials"`. `network_client.login_user()` returns `(False, "Login failed: Invalid Credentials")`. CLI prints the error. |
| 1.3.5 | User enters a non-existent email. | Server returns `401 Unauthorized` (same as wrong password — no user enumeration). CLI prints the error. |
| 1.3.6 | User enters correct password but wrong case for email. | Depends on server's email lookup. If `email` column uses case-sensitive collation, the lookup fails. If case-insensitive, login succeeds but the encryption key derivation uses the wrong salt (SHA-256 of the different-case email), producing a **different AES key**. All previously encrypted files become undecryptable. |
| 1.3.7 | User logs in on Device B after previously using Device A. | Device B gets a new JWT. `_clear_device()` removes any stale `device_id`. On first sync cycle, `_get_device_id()` generates a new random 6-digit ID via `random.randint(100000, 999999)`. |
| 1.3.8 | Two users log in on the same machine sequentially (User A then User B). | User B's `login_user()` overwrites `jwt_token` in `shadow.db`. `_clear_device()` removes User A's `device_id`. User A's files may still be in `watch_folder`. The sync engine now runs as User B and attempts to announce User A's files — the server rejects them if the paths conflict or creates new files under User B's account. |

### 1.4 — Login via Web UI

| # | User Action | System Response |
|---|-------------|-----------------|
| 1.4.1 | User navigates to `/auth` and enters Email + Password on the Login tab. | Component state captures both fields. |
| 1.4.2 | User clicks "Sign In". | `AuthScreen.tsx` sends `POST http://127.0.0.1:8001/api/auth/login` to the local agent with `{email, password, passphrase}`. |
| 1.4.3 | Local agent processes login. | `local_api.py:login()` calls `network_client.login_user()`. On success, if a passphrase was provided, derives the encryption key. Calls `_start_watcher_if_needed()` to spawn the watcher + sync engine threads (if not already running). Calls `event_listener.start()` to begin SSE listening. Returns `{status, access_token, message}`. |
| 1.4.4 | UI receives success. | `access_token` is stored in `localStorage`. React Router navigates to `/vault`. |
| 1.4.5 | User refreshes the browser on `/vault` without a token in localStorage. | `apiFetch()` reads `null` from `localStorage`. The `Authorization: Bearer null` header is sent. Server returns `401`. UI should redirect to `/auth`. |
| 1.4.6 | User manually edits `localStorage` to insert a garbage token. | Next API call sends the garbage token. Server's JWT decode fails. Returns `401`. `apiFetch` attempts refresh with the garbage token. Refresh also fails (can't decode). UI shows auth error. |
| 1.4.7 | User opens two browser tabs, logs out in Tab 1, then clicks a button in Tab 2. | Tab 1 clears `localStorage`. Tab 2's next `apiFetch` reads `null` token. Returns `401`. Tab 2 should redirect to `/auth`. |

### 1.5 — The Silent JWT Refresh Lifecycle

| # | User Action | System Response |
|---|-------------|-----------------|
| 1.5.1 | User leaves the browser tab open for 24+ hours. The JWT expires. User clicks any button that triggers an API call. | `api.ts:apiFetch()` makes the request with the expired token in the `Authorization` header. The backend returns `401 Unauthorized`. |
| 1.5.2 | `apiFetch` catches the 401. | The `catch` block detects `err.status === 401`. It reads the expired token from `localStorage` and sends `POST /auth/refresh` with the expired token in the `Authorization` header. |
| 1.5.3 | Server processes the refresh. | `auth.py:refresh_token()` decodes the JWT with `options={"verify_exp": False}` — explicitly ignoring expiration. It extracts `user_id`, verifies the user still exists in the database, and issues a fresh JWT via `utils.create_access_token()`. Returns `{access_token, token_type}`. |
| 1.5.4 | UI receives the new token. | `apiFetch` saves the new token to `localStorage` under `shadowdrive_token`, then **retries the original request** with the fresh token. The user sees no interruption. |
| 1.5.5 | Refresh fails (user was deleted, or token is corrupt). | `apiFetch` throws the original 401 error. The UI should redirect to `/auth`. |
| 1.5.6 | **Client Agent** encounters a 401 during sync. | `network_client._request()` catches the 401. It calls `POST /auth/refresh` with the old token. If refresh succeeds, the new token is saved to `shadow.db` and the original request is retried. If refresh fails, `config.sync_suspended = True` and the message `[AUTH ERROR] Unauthorized (401) and refresh failed. Sync has been suspended.` is printed. |
| 1.5.7 | JWT expires exactly during a chunked upload at chunk 500/1250. | `_request()` sends chunk 500 → gets 401 → refresh succeeds → new token stored → chunk 500 retried with new token → succeeds → chunks 501–1249 continue with the new token. |
| 1.5.8 | Two API calls fire simultaneously while JWT is expired. Both trigger refresh. | Both calls independently attempt `POST /auth/refresh`. Both succeed (server generates two JWTs). The second refresh's token overwrites the first in `localStorage`. Both original requests are retried. This is a benign race — both tokens are valid. |
| 1.5.9 | Admin deletes the user account while the client agent is syncing. | Next API call returns `401`. Refresh attempt finds no user in DB → fails. `config.sync_suspended = True`. Agent enters idle mode permanently. |

### 1.6 — Logout and Session Termination

| # | User Action | System Response |
|---|-------------|-----------------|
| 1.6.1 | User clicks "Sign Out" in the web UI sidebar. | `DashboardLayout.tsx` clears `localStorage.removeItem('shadowdrive_token')` and navigates to `/auth`. |
| 1.6.2 | The local agent continues running. | The agent still has its JWT in `shadow.db`. It continues syncing until the JWT expires. At expiration, the next API call triggers the refresh flow. If the user logged out server-side (token invalidation), refresh fails and sync suspends. |
| 1.6.3 | Server sends a `REVOKE` command to a device. | The `_heartbeat_worker()` in `sync_engine.py` polls `POST /devices/{device_id}/heartbeat`. If the response contains a `REVOKE` command, the agent: (1) deletes `access_token`, `device_id`, and `encryption_key` from `shadow.db`, (2) acknowledges the command via `POST /devices/{device_id}/command/{cmd_id}/ack`, (3) calls `sys.exit(0)` — hard shutdown. |
| 1.6.4 | User closes the browser without clicking "Sign Out". | `localStorage` still contains the token. If the user reopens the browser, they are still "logged in" to the UI. The token may or may not have expired. If expired, the refresh flow kicks in. |
| 1.6.5 | User clears browser data (cookies + localStorage). | Token is lost. Next visit to `/vault` fails with `401`. UI redirects to `/auth`. The local agent is unaffected (its JWT is in `shadow.db`). |

---

## SECTION 2: The Local "Magic Folder" Experience (Client Agent)

### 2.1 — Dropping a New File into the Watch Folder

| # | User Action | System Response |
|---|-------------|-----------------|
| 2.1.1 | User copies or saves a new file (e.g., `report.pdf`) into `ShadowDrive/watch_folder/`. | The **Watchdog** `Observer` (running in `watcher.py`) fires an `on_created` event with the file's absolute path. |
| 2.1.2 | Watchdog debounce timer starts. | `WatcherHandler._schedule()` creates a 2-second `threading.Timer`. If additional writes occur within 2 seconds (e.g., the OS writes the file in multiple passes), the timer resets. This prevents processing a half-written file. |
| 2.1.3 | Debounce timer fires. | `WatcherHandler._fire()` calls `diff_engine.process_single_file(path, "created")`. |
| 2.1.4 | `diff_engine` processes the new file. | It checks `is_local_mutation_active()` — if the sync engine is currently writing a downloaded file, the event is **silently dropped** to prevent infinite loops. Otherwise: (1) computes SHA-256 via `hash_utils.hash_file()`, (2) queries `shadow.db` `files` table — no existing row found → prints `[NEW] report.pdf`, (3) inserts an event into the `events` table with `event_type="new"`, `is_synced=0`, (4) inserts/updates the `files` table with `{file_path, hash, size, last_modified}`, (5) generates chunk signatures via `update_chunk_signatures()` — splits the file into 4 MB chunks and stores each chunk's SHA-256 in `chunk_signatures`. |
| 2.1.5 | Sync engine picks up the pending event. | The `start_sync_loop()` main loop (runs every `SYNC_INTERVAL_SECONDS` = 10s, or immediately if SSE nudges via `event_listener.sync_nudge`) queries `SELECT * FROM events WHERE is_synced = 0 ORDER BY id ASC`. It finds the new event. |
| 2.1.6 | Sync engine announces the file. | `network_client.announce_metadata()` sends `POST /sync/announce` with `{path: "report.pdf", hash: "<sha256>", event: "new", chunk_hashes: [...]}`. |
| 2.1.7 | Server processes the announcement. | `services/metadata.py:process_metadata_sync()` runs the full pipeline: (1) `_ensure_user()`, (2) `_get_or_create_file()` — creates a `File` row, (3) not a deletion, (4) `_check_hash_dedup()` — no existing version with this hash → returns `None`, (5) not empty file, (6) `_handle_conflict_if_any()` — no prior version → no conflict, (7) `_accept_new_version()` — creates a `Version` row with `version_num=1`, `size_bytes=0` (pending), `storage_path="{user_id}/report.pdf/v1"`, `upload_status=pending`. Also calls `reconcile_version_chunks()` which checks each announced chunk hash against the global `stored_chunks` table for cross-file deduplication. Returns `{status: "accepted", upload_required: true, version_id: X, missing_chunks: [...]}`. Fires SSE event `file_created`. |
| 2.1.8 | Client receives `upload_required: true`. | The sync engine creates an `UploadJob` and pushes it to the `upload_queue`. The event is marked "in flight" to prevent duplicate processing. |
| 2.1.9 | Upload worker processes the job. | `_upload_worker()` pulls the job from the queue. It verifies the file still exists and the hash hasn't changed since announcement. If `file_size < CHUNK_THRESHOLD` (4 MB): sends a single-shot `POST /sync/upload` with the file bytes. If encryption is active: encrypts the file with AES-256-GCM first. If `file_size >= CHUNK_THRESHOLD`: calls `_upload_chunks_resilient()` for chunked upload. |
| 2.1.10 | Server receives the upload. | For single-shot: `sync.py:upload_file()` enforces storage quota (locks user row with `WITH FOR UPDATE`), writes bytes to MinIO via `storage.put_object()`, sets `upload_status = processing`, enqueues `verify_file_hash` to the RQ worker. Returns `202 Accepted`. Fires SSE event `upload_processing`. |
| 2.1.11 | RQ background worker verifies the file. | `worker.py:verify_file_hash()` downloads the file from MinIO, computes SHA-256, compares against the announced hash. If match: sets `upload_status = complete`. If mismatch: sets `upload_status = failed`. |
| 2.1.12 | Client finalizes. | After upload success, `finalize_local_db_after_upload()` updates `shadow.db` with the `version_id` and `encrypted_hash`. Then `_ack_upload()` calls `POST /sync/ack_sync` to register that this device now has this version, preventing the diff endpoint from re-downloading it. The event is marked as `is_synced = 1`. |

### 2.2 — Modifying an Existing File

| # | User Action | System Response |
|---|-------------|-----------------|
| 2.2.1 | User edits and saves `report.pdf` in their editor. | Watchdog fires `on_modified`. Debounce timer starts (2s). |
| 2.2.2 | Timer fires → `diff_engine.process_single_file(path, "modified")`. | Computes new SHA-256. Queries `shadow.db` `files` table — existing row found with old hash. New hash differs → prints `[MODIFIED] report.pdf`. Logs event with `event_type="modified"` and the old `version_id` as `base_version_id`. Updates the `files` row and chunk signatures. |
| 2.2.3 | Sync engine announces with `base_version_id`. | `POST /sync/announce` includes `base_version_id` pointing to the previous version. Server uses this for conflict detection. If no other device modified the file, a new `Version` row (v2) is created. |
| 2.2.4 | Upload proceeds identically to 2.1.9–2.1.12. | Same pipeline. Delta chunk deduplication may skip uploading unchanged chunks if `missing_chunks` is a subset. |
| 2.2.5 | User saves the same file twice rapidly within the 2-second debounce window. | First `on_modified` starts a 2s timer. Second `on_modified` cancels the first timer and starts a new one. Only the final state is processed. Single event logged. |
| 2.2.6 | User modifies a file but the content hash is identical (e.g., save without changes). | `diff_engine` computes the hash. It matches the existing hash in `shadow.db`. **No event is logged.** The modification is silently ignored. |
| 2.2.7 | User modifies a file while a previous upload of that file is still in-flight. | The upload worker checks `current_hash != expected_plain_hash` before uploading. If the hash changed, the job is discarded as obsolete: `[UPLOAD WORKER] Job for report.pdf is obsolete (local hash changed). Discarding.` The new modification will be picked up by the next sync cycle. |

### 2.3 — Deleting a File Locally

| # | User Action | System Response |
|---|-------------|-----------------|
| 2.3.1 | User deletes `report.pdf` from the watch folder. | Watchdog fires `on_deleted`. **No debounce** — deletions are processed immediately. Checks `is_suppressed()` first — if the sync engine initiated the delete (server-side deletion), the event is dropped. |
| 2.3.2 | `diff_engine.process_single_file(path, "deleted")`. | Prints `[DELETED] report.pdf`. Logs event with `event_type="deleted"`. Removes the `files` and `chunk_signatures` rows for this path. |
| 2.3.3 | Sync engine announces the deletion. | `POST /sync/announce` with `event: "deleted"`. Server calls `_handle_deletion()` → sets `file.is_deleted = True`. Fires SSE event `file_deleted`. Returns `{status: "deleted_acknowledged", upload_required: false}`. |
| 2.3.4 | Other devices receive the SSE event. | On their next sync cycle, `process_downstream_downloads()` calls `GET /sync/metadata/diff`. The deleted file appears in `deleted_files[]`. The client deletes the local file (with `suppress_path()` to prevent re-triggering the watchdog) and removes it from `shadow.db`. |
| 2.3.5 | User deletes a file that is currently being uploaded (mid-chunk transfer). | Watchdog fires `on_deleted` immediately. `diff_engine` logs the delete event. Meanwhile, the upload worker is still processing the file. It checks `os.path.exists(job.local_path)` at the start — the file is gone → prints `[UPLOAD WORKER] File vanished before transit`. Job is discarded. The delete event is then announced to the server. |
| 2.3.6 | User deletes a file and immediately creates a new file with the same name. | Watchdog fires `on_deleted` (processed immediately). Then `on_created` fires (debounced 2s). The delete event is announced first. The server soft-deletes the file. Then the create event fires, the new file is announced as a fresh file, and a new `File` row is created. |

### 2.4 — Renaming / Moving a File

| # | User Action | System Response |
|---|-------------|-----------------|
| 2.4.1 | User renames `report.pdf` to `final_report.pdf` in the watch folder. | Watchdog fires `on_moved(src_path, dest_path)`. |
| 2.4.2 | `WatcherHandler.on_moved()` processes the event. | (1) Cancels any pending debounce timer for `src_path`. (2) Calls `process_single_file(src_path, "deleted")` — logs a delete event for the old path. (3) Calls `_schedule("created", dest_path)` — schedules a create event for the new path (debounced 2s). |
| 2.4.3 | Sync engine processes both events. | First announces the deletion of `report.pdf` → server soft-deletes. Then announces the creation of `final_report.pdf` with the same hash → server checks dedup → finds the hash already exists → returns `upload_required: false`. **Zero bytes re-uploaded.** The file effectively "moves" on the server as a delete + create with dedup. |
| 2.4.4 | User moves a file from `watch_folder/A/` to `watch_folder/B/`. | Same `on_moved` flow. Old path deleted, new path created. Server sees a new relative path `B/file.ext`. |
| 2.4.5 | User drags a file from outside the watch folder into it. | OS performs a copy (not move within the same filesystem). Watchdog fires `on_created`, not `on_moved`. Normal new-file flow applies. |
| 2.4.6 | User renames a directory containing 50 files. | Watchdog fires `on_moved` for **each file** inside the directory. 50 delete events + 50 create events are generated. Each is processed through the announce pipeline. Server-side dedup ensures zero re-upload for all 50. |

### 2.5 — Creating Deeply Nested Directories

| # | User Action | System Response |
|---|-------------|-----------------|
| 2.5.1 | User creates `ShadowDrive/watch_folder/Work/2026/Q1/` and drops `report.pdf` inside. | Watchdog is configured with `recursive=True` on the `Observer`. It fires `on_created` for the file. Directory creation events are filtered out (`if event.is_directory: return`). |
| 2.5.2 | `diff_engine` processes the file. | The `file_path` in `shadow.db` stores the **full absolute path**. The relative path `Work/2026/Q1/report.pdf` is computed in the sync engine via `os.path.relpath(full_path, config.WATCH_DIR)`. |
| 2.5.3 | Sync engine announces with the relative path. | `POST /sync/announce` with `path: "Work/2026/Q1/report.pdf"`. The server stores this path in the `files` table. Storage key becomes `{user_id}/Work/2026/Q1/report.pdf/v1`. |
| 2.5.4 | Another device downloads this file. | `process_downstream_downloads()` receives the relative path. `os.makedirs(os.path.dirname(full_local_path), exist_ok=True)` creates all intermediate directories before writing the file. |
| 2.5.5 | User creates a path with 200+ characters total. | Server `file_path` column is `String(1000)` — up to 1000 chars. `storage_path` is `String(500)`. As long as path < 500 chars, no issue. Beyond that, storage_path exceeds column limit → `DataError`. |

### 2.6 — Dropping Massive Files (Chunked Upload)

| # | User Action | System Response |
|---|-------------|-----------------|
| 2.6.1 | User drops a 500 MB video into the watch folder. | Watchdog fires `on_created`. Debounce timer waits 2 seconds for the write to complete. |
| 2.6.2 | Diff engine processes and computes SHA-256. | `hash_utils.hash_file()` reads the file in streaming blocks. `chunk_and_hash_file()` splits it into 4 MB chunks and computes per-chunk SHA-256 hashes. These are stored in `chunk_signatures`. |
| 2.6.3 | Sync engine announces with chunk hashes. | `POST /sync/announce` with `chunk_hashes: [<125 hashes>]`. Server's `reconcile_version_chunks()` checks each hash against `stored_chunks`. Any previously-uploaded identical chunk is **reused** (cross-file dedup). Only `missing_chunks` indices are returned. |
| 2.6.4 | Upload worker sends chunks. | `_upload_chunks_resilient()` iterates over `missing_chunks` (or all chunks if none specified). For each chunk: reads 4 MB from file at `offset = chunk_index * CHUNK_SIZE`, optionally encrypts, sends `POST /sync/upload_chunk` with form fields `{version_id, chunk_index, total_chunks, file_hash}`. Each chunk is stored in MinIO under `chunks/{sha256_of_chunk}` and recorded in `chunk_uploads` and `stored_chunks`. |
| 2.6.5 | A chunk upload fails mid-transfer. | `_upload_chunks_resilient()` catches the exception on that chunk. `_handle_failed_job()` computes exponential backoff: `base_backoff * 2^(retry_count-1) + jitter`. The job is re-enqueued via `threading.Timer`. `completed_chunks` is preserved so successfully uploaded chunks are not re-sent. |
| 2.6.6 | All chunks received. | The `/upload_chunk` endpoint detects `received_count >= total_chunks`. Sets `upload_status = processing`. Enqueues `assemble_and_verify_chunks` to the RQ worker. |
| 2.6.7 | RQ worker assembles and verifies. | `worker.py:assemble_and_verify_chunks()` reads all chunk objects from MinIO in order, concatenates them, writes the assembled file to the version's `storage_path`, computes SHA-256 of the whole file, and compares. On match: `upload_status = complete`. |
| 2.6.8 | User drops a 0-byte empty file. | Watchdog fires. `hash_utils.hash_file()` computes SHA-256 of empty bytes → `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. Sync engine announces with this hash and `chunk_hashes: []`. Server's `_handle_empty_file()` creates the version with `size_bytes=0` and `upload_status=complete` immediately. Returns `upload_required: false`. |
| 2.6.9 | User drops a file that is exactly 4 MB (the threshold boundary). | `file_size == CHUNK_THRESHOLD` → `file_size < CHUNK_THRESHOLD` is `False` → chunked upload path is taken. File is split into exactly 1 chunk. Single chunk uploaded. Assembly creates a single-chunk assembled file. |
| 2.6.10 | User drops a file that is exactly 4 MB minus 1 byte. | `file_size < CHUNK_THRESHOLD` → `True` → single-shot upload path. |

### 2.7 — Copying the Exact Same File Twice (Hash Deduplication)

| # | User Action | System Response |
|---|-------------|-----------------|
| 2.7.1 | User drops `photo.jpg` into the watch folder. Upload completes. | Normal flow (2.1.1–2.1.12). Version v1 created with hash `abc123`. |
| 2.7.2 | User copies the exact same file as `photo_copy.jpg`. | Watchdog fires. Diff engine creates event. Sync engine announces `{path: "photo_copy.jpg", hash: "abc123"}`. |
| 2.7.3 | Server checks hash dedup. | `_check_hash_dedup()` finds an existing `Version` for the same user with `hash = "abc123"` and `upload_status != failed`. Since `size_bytes > 0` (already uploaded), returns `{status: "already_synced", upload_required: false}`. |
| 2.7.4 | Client skips upload. | The event is marked as synced. **Zero bytes transferred.** The server creates a new `File` record pointing to the same storage, achieving instant deduplication. |

### 2.8 — Chunk-Level Cross-File Deduplication

| # | User Action | System Response |
|---|-------------|-----------------|
| 2.8.1 | User has `video_v1.mp4` (500 MB) already uploaded. User drops `video_v2.mp4` which differs only in the last 8 MB. | Sync engine computes 125 chunk hashes. 123 of them match chunks already in `stored_chunks`. |
| 2.8.2 | Server returns `missing_chunks: [123, 124]`. | Only 2 chunks (8 MB) need uploading instead of 500 MB. |
| 2.8.3 | Upload worker sends only the 2 missing chunks. | `chunks_to_upload = set(job.missing_chunks)`. Prints `[DELTA SYNC] Skipping 123/125 unchanged chunks`. Uploads only indices 123 and 124. Assembly proceeds normally. |

### 2.9 — File System Edge Cases

| # | User Action | System Response |
|---|-------------|-----------------|
| 2.9.1 | User drops a file with special characters in the name: `résumé (final) [v2].pdf`. | Watchdog fires with the full Unicode path. `os.path.relpath()` computes the relative path. `announce_metadata()` sends the path as-is. Server stores it in `file_path` column (`String(1000)` — handles Unicode). MinIO key contains the characters. Download works if the OS supports the characters. |
| 2.9.2 | User drops a file named `CON`, `PRN`, `NUL`, `COM1`, etc. (Windows reserved names). | On Windows, these are reserved device names. `os.path.exists()` may behave unpredictably. `open("CON", "rb")` opens the console device. `hash_utils.hash_file()` may read infinite bytes from the console or hang. **This is a bug** — no validation exists for reserved names. |
| 2.9.3 | User drops a file with a path containing `../` (path traversal attempt). | The file is physically inside `watch_folder`. `os.path.relpath()` computes the relative path from `WATCH_DIR`, which does not contain `../`. If the user somehow creates a symlink pointing outside, `hash_file()` follows the symlink and reads the target file's content. **The file content is uploaded** even though it lives outside the watch folder. |
| 2.9.4 | User creates a symbolic link inside `watch_folder` pointing to `/etc/passwd`. | Watchdog fires `on_created` for the symlink. `hash_utils.hash_file()` follows the symlink and hashes the target file. The content of `/etc/passwd` is uploaded to the server. **This is a security concern** — no symlink validation exists. |
| 2.9.5 | User drops a file with a name containing only spaces: `"   .txt"`. | Valid on most filesystems. Watchdog fires. Path is processed normally. The server stores `"   .txt"` in `file_path`. UI renders it with leading spaces (may look empty). |
| 2.9.6 | User drops a file with a very long name (255+ characters). | Most filesystems limit filenames to 255 bytes. The OS itself will reject the creation, so watchdog never fires. If the file somehow exists (e.g., on a filesystem without this limit), the server's `String(1000)` column for `file_path` handles it, but MinIO key limits may cause issues. |
| 2.9.7 | User drops a `.gitignore` or `.DS_Store` hidden file. | Watchdog has no ignore list. The file is processed and uploaded. All hidden/dot files are synced. |
| 2.9.8 | User drops a `shadow.db` file into the watch folder. | Watchdog fires. The file is hashed and uploaded. This creates a potential infinite loop if `DB_PATH` pointed inside `watch_folder` (it doesn't — it's one level up). |
| 2.9.9 | User locks a file with another application (e.g., Excel opens `data.xlsx` exclusively). | `hash_utils.hash_file()` tries to `open(path, "rb")`. On Windows, exclusive locks prevent reading. `open()` raises `PermissionError`. `diff_engine` catches this and skips the file. The event is not logged. On the next modification (when the lock is released), the file is processed. |
| 2.9.10 | User drops 10,000 small files simultaneously (e.g., extracting a zip). | Watchdog fires `on_created` 10,000 times. Each creates a 2-second debounce timer. After 2 seconds, `diff_engine.process_single_file()` runs 10,000 times (sequentially — the timers fire on separate threads but `process_single_file` likely acquires the SQLite lock). This creates heavy SQLite contention. Events are logged one by one. Sync engine processes them in FIFO order. |
| 2.9.11 | User drops a 100 GB file that exceeds the storage quota. | Watchdog fires. File is hashed (takes several minutes for 100 GB). Sync engine announces. Server's `reconcile_version_chunks()` processes the chunk hashes. Upload begins. Server's quota check on `upload_file()` or `upload_chunk()` runs `SUM(size_bytes)` against all versions. If `current_usage + file_size > storage_quota`, returns `413`. Upload worker receives the rejection. Job remains in queue but will fail on every retry until the user frees space. |
| 2.9.12 | Watch folder is on a network drive (NFS/SMB) that disconnects. | Watchdog may throw `OSError` when the Observer tries to poll the directory. If using `inotify` (Linux) or `ReadDirectoryChangesW` (Windows), the observer thread may crash. The watcher thread is a daemon thread — if it crashes, only the watcher dies; the sync engine continues running. Files will stop being detected until the agent is restarted. |
| 2.9.13 | User modifies file permissions to make a file read-only after it's been tracked. | Watchdog still fires `on_modified` (metadata change). `hash_file()` can still read (read permissions typically remain). The file is processed normally. If a download tries to overwrite a read-only file: `open(path, "wb")` raises `PermissionError`. The download fails. The file remains in `outdated_files` on the next diff. |

---

## SECTION 3: The Web Dashboard Experience (React UI)

### 3.1 — Viewing the Live File Explorer

| # | User Action | System Response |
|---|-------------|-----------------|
| 3.1.1 | User navigates to `/vault` after login. | `FileExplorer.tsx` mounts. `useEffect` calls `refreshFiles()` which calls `apiFetch('/sync/metadata')`. |
| 3.1.2 | Backend returns file list. | `GET /sync/metadata` queries all non-deleted `File` records for the user, joining with the latest `Version`. Returns `[{id, file_path, hash, version_num, size_bytes, storage_path}]`. |
| 3.1.3 | UI renders the file table. | Each file row shows: file icon (determined by extension — `.pdf` → `description`, `.json` → `code`, `.pem` → `key`, `.bin` → `lock`), file name, size (formatted via `formatBytes()`), last modified time, and status indicator. |
| 3.1.4 | User drops a file into the watch folder on their local machine. | The sync engine uploads it. Server fires SSE event `file_created`. |
| 3.1.5 | SSE event arrives at the UI. | `useEventStream` hook receives the event. The `switch` statement matches `file_created` and calls `refreshFiles()`. The file table **auto-updates in real-time** without the user pressing refresh. |
| 3.1.6 | SSE event types that trigger refresh. | `file_created`, `file_updated`, `file_deleted`, `upload_processing`, `upload_complete`, `upload_failed`, `conflict_detected`. |
| 3.1.7 | User has 0 files. | `FileExplorer.tsx` renders an empty state — either a blank table or a "No files yet" message. The upload button remains visible. |
| 3.1.8 | User has 5,000 files. | `GET /sync/metadata` returns all 5,000 records. No pagination implemented. The browser must render a 5,000-row table. May cause UI jank on low-end devices. `refreshFiles()` triggered by every SSE event fetches all 5,000 records each time. |
| 3.1.9 | The SSE connection drops (server restart). | `useEventStream.ts` → `es.onerror` fires → `EventSource` is closed → exponential backoff (1s, 2s, 4s, 8s, max 30s) → reconnect attempt → on success, backoff resets. During the outage, file changes are not reflected in real-time. The user must manually refresh or wait for reconnection. |

### 3.2 — Reading Visual Job Status Indicators

| # | User Action | System Response |
|---|-------------|-----------------|
| 3.2.1 | A file is being uploaded (status = `pending` or `uploading` or `processing`). | `getStatusDot()` renders a **yellow spinning icon** (`progress_activity` with `animate-spin` CSS class). Tooltip shows the status name. |
| 3.2.2 | Upload completes (status = `complete`). | `getStatusDot()` renders a **green checkmark** (`check_circle` in primary color). |
| 3.2.3 | Upload fails (status = `failed`). | `getStatusDot()` renders a **red error icon** (`error` in red). |
| 3.2.4 | File is a conflict copy. | `getStatusDot()` renders a **red warning icon** (`warning` in red), regardless of upload status. `is_conflict_copy` is derived from `file_path.includes('(Conflicted copy)')`. |
| 3.2.5 | Upload status is `null` or `undefined` (missing from server response). | `getStatusDot()` has no case for this → renders nothing (no icon). The status column appears empty. |

### 3.3 — Opening the In-Place Text Editor

| # | User Action | System Response |
|---|-------------|-----------------|
| 3.3.1 | User clicks on a text-compatible file row (`.txt`, `.md`, `.json`, `.js`, `.ts`, `.jsx`, `.tsx`, `.csv`, `.html`, `.css`). | `handleRowClick()` checks `isTextFile()` by file extension. |
| 3.3.2 | File is a text file. | Sends `GET http://127.0.0.1:8001/api/download?file_path=<name>` to the **local agent** to fetch the plaintext from the local watch folder. |
| 3.3.3 | Local agent serves the file. | `local_api.py:handle_ui_download()` reads the file from `watch_folder/<name>` and returns it as a `FileResponse`. |
| 3.3.4 | UI opens the editor modal. | A full-screen modal with a `<textarea>` pre-populated with the file's content. The file name is shown in the header. "Cancel" and "Save Changes" buttons are rendered. |
| 3.3.5 | User edits the text and clicks "Save Changes". | `isSaving` state is set to `true` (button shows "Saving...", textarea becomes disabled). A `Blob` is created from the edited text, wrapped in a `File` object, and sent via `uploadFile(fileObj, editingFile.name)` → `POST http://127.0.0.1:8001/api/upload`. |
| 3.3.6 | Local agent writes the file. | `local_api.py:handle_ui_upload()` writes the file bytes to `watch_folder/<name>`, overwriting the existing file. |
| 3.3.7 | Watchdog detects the modification. | `on_modified` fires → debounce → `diff_engine` detects hash changed → logs `[MODIFIED]` event → sync engine uploads the new version to the server. |
| 3.3.8 | Editor modal closes. | `refreshFiles()` is called. The file list updates with the new version. `setEditingFile(null)` closes the modal. `isSaving` resets to `false`. |
| 3.3.9 | Save fails (network error). | `catch` block triggers `alert("Failed to save changes.")`. Modal stays open so the user doesn't lose their edits. |
| 3.3.10 | User opens a 50 MB `.csv` file in the text editor. | `GET /api/download` returns 50 MB of text. The browser allocates 50 MB for the response string. Setting `textarea.value` to 50 MB of text may freeze or crash the browser tab. |
| 3.3.11 | User opens a binary file that has a text extension (e.g., `data.csv` that is actually binary). | `isTextFile()` returns `true` based on extension. The file is fetched and displayed in the textarea. Binary content appears as garbled characters. Saving overwrites the original with the garbled representation, potentially corrupting the file. |
| 3.3.12 | User opens the text editor for a file, then another device deletes that file. | The editor is still open with the old content. When the user clicks "Save", the upload writes the file back to `watch_folder`. Watchdog fires `on_created`. The sync engine announces it as a new file. The server creates a new `File` record (the old one is soft-deleted). The file is "resurrected". |
| 3.3.13 | User opens the text editor and makes no changes, then clicks "Save". | A `Blob` with the original content is created and uploaded. The local file is overwritten with identical content. Watchdog fires `on_modified`. `diff_engine` computes the hash — it matches the existing hash in `shadow.db`. **No event is logged.** No upload occurs. |

### 3.4 — Downloading a File

| # | User Action | System Response |
|---|-------------|-----------------|
| 3.4.1 | User hovers over a file row and clicks the download icon. | `handleDownload()` is called with the file's `storage_path`. |
| 3.4.2 | Download URL is constructed. | `api.ts:getDownloadUrl()` returns `http://127.0.0.1:8000/sync/download?storage_path=<path>&token=<jwt>`. The token is passed as a query parameter for the browser download flow. |
| 3.4.3 | Browser initiates download. | A hidden `<a>` element is created with `href=url` and `download=filename`, appended to the DOM, clicked programmatically, then removed. The browser opens a download dialog or saves the file directly. |
| 3.4.4 | Server serves the file. | `sync.py:download_file()` validates that the `storage_path` belongs to a real `Version` owned by the user. Fetches raw bytes from MinIO via `storage.get_object()`. Returns bytes with `Content-Disposition: attachment` and custom headers `X-Shadow-Hash` and `X-Shadow-Size`. |
| 3.4.5 | User clicks on a non-text file row. | `handleRowClick()` sees `isTextFile()` is false → calls `handleDownload()` directly. The file downloads instead of opening an editor. |
| 3.4.6 | User attempts to download a file whose MinIO object was manually deleted. | Server's `storage.get_object()` raises `NoSuchKey` or similar. Server returns `404` or `500`. Browser shows a download error. |
| 3.4.7 | User attempts to download with an expired JWT in the URL query param. | Server decodes the JWT → expired → returns `401`. Browser shows an error page instead of downloading. No refresh mechanism exists for direct URL downloads (only for `apiFetch` calls). |

### 3.5 — Deleting a File from the UI

| # | User Action | System Response |
|---|-------------|-----------------|
| 3.5.1 | User hovers over a file row and clicks the delete (trash) icon. | `handleDeleteClick()` sets `fileToDelete` state with `{id, name}`. |
| 3.5.2 | Confirmation modal appears. | "Are you sure you want to delete `<filename>`? This action cannot be undone." with Cancel and Delete buttons. |
| 3.5.3 | User clicks "Delete". | `confirmDelete()` calls `api.ts:deleteFile(id)` → `apiFetch('/sync/file/{id}', {method: 'DELETE'})`. |
| 3.5.4 | Server processes the deletion. | `sync.py:delete_file()` finds the `File` record for the user, sets `is_deleted = True` (soft delete). Fires SSE event `file_deleted`. Returns `{status: "deleted"}`. |
| 3.5.5 | UI updates. | `setFiles(prev => prev.filter(f => f.id !== id))` — immediately removes the file from the list. `setFileToDelete(null)` closes the modal. |
| 3.5.6 | Local agent receives the SSE event. | `event_listener.py` receives the `file_deleted` event and sets `sync_nudge` to wake the sync engine immediately. On next sync cycle, `process_downstream_downloads()` sees the file in `deleted_files[]` and deletes it from the local watch folder (with suppression to prevent watchdog re-triggering). |
| 3.5.7 | User clicks "Delete" on a file that another device is currently uploading. | Server soft-deletes the `File` record. The other device's upload continues to the `Version` row which still references the now-deleted file. The upload may succeed but the file won't appear in `GET /sync/metadata` (filtered by `is_deleted = False`). |
| 3.5.8 | User deletes the last file. | File list becomes empty. UI renders the empty state. |

### 3.6 — Uploading a File via the UI

| # | User Action | System Response |
|---|-------------|-----------------|
| 3.6.1 | User clicks "Upload File" button in the File Explorer header. | A hidden `<input type="file">` is programmatically clicked. The browser's native file picker opens. |
| 3.6.2 | User selects a file. | `handleFileChange()` fires. Calls `uploadFile(file, file.name)` → `POST http://127.0.0.1:8001/api/upload` with `FormData` containing the file. |
| 3.6.3 | Local agent writes the file. | `local_api.py:handle_ui_upload()` saves the file to `watch_folder/<filename>`. |
| 3.6.4 | Watchdog detects the new file. | Same flow as Section 2.1 — the file is picked up, announced, uploaded to the server, and verified. |
| 3.6.5 | UI optimistically adds the file to the list. | `setFiles(prev => [...prev, {id, file_path, size_bytes, updated_at, upload_status: 'complete'}])` adds a temporary entry. The real entry replaces it when the SSE event triggers `refreshFiles()`. |
| 3.6.6 | User cancels the file picker. | `handleFileChange()` fires with `e.target.files` being empty or null. No upload is triggered. |
| 3.6.7 | User selects a 5 GB file that exceeds quota. | File is written to watch folder. Watchdog fires. Sync engine announces. Server returns quota error on upload. The file persists locally but never fully syncs. Status remains `pending` or `failed`. |
| 3.6.8 | User uploads a file with the same name as an existing file. | `local_api.py` overwrites the existing file in `watch_folder`. Watchdog fires `on_modified`. Sync engine announces with `event_type="modified"`. Server creates a new version (v2). |
| 3.6.9 | User selects multiple files (if the input allows it). | Depends on whether `<input>` has `multiple` attribute. If not, only one file is selected. If yes, `handleFileChange()` would need to iterate over `e.target.files` and upload each — but the current implementation only handles a single file. |

### 3.7 — Version History Time Machine

| # | User Action | System Response |
|---|-------------|-----------------|
| 3.7.1 | User hovers over a file row and clicks the history icon. | `navigate('/vault/history?file={file.id}&name={file.file_path}')` — navigates to the Version History view with query params. |
| 3.7.2 | `VersionHistory.tsx` mounts. | Parses `file` and `name` from `window.location.search`. Calls `apiFetch('/sync/versions/recent?file_id={fileId}')`. |
| 3.7.3 | Server returns version history. | `sync.py:get_recent_versions()` queries up to 50 `Version` records for the file, ordered by `created_at` descending. For each version: `{id, version_number, hash, created_at, device_id, size_bytes, storage_path, file_name}`. |
| 3.7.4 | UI renders the timeline. | Left column: file info card with icon, filename, total version count, and "Download Latest" button. Right column: table with version number (latest highlighted in green), date/time, hash (truncated), device, size, and download button per version. |
| 3.7.5 | User clicks "Download Latest". | Calls `handleDownload(e, versions[0].storage_path)` — downloads the most recent version from MinIO. |
| 3.7.6 | User clicks the download button on an older version (e.g., v2). | `handleDownload(e, ver.storage_path)` — downloads that specific historical version. The storage path `{user_id}/{path}/v2` points to the exact MinIO object from that version. |
| 3.7.7 | User views global version history (no file selected). | Navigate to `/vault/history` without query params. `get_recent_versions()` returns the 50 most recent versions across **all files**, with `file_name` column showing which file each version belongs to. |
| 3.7.8 | File has 100+ versions. | Only the 50 most recent are returned. Older versions exist in the DB and MinIO but are not shown. No pagination control exists. |
| 3.7.9 | User clicks history on a file that was just deleted. | The file's `is_deleted = True`, but `Version` records still exist. The query may or may not filter by `is_deleted`. If versions are returned, the user can still download historical versions of a deleted file. |

### 3.8 — The Conflict Resolution UI

| # | User Action | System Response |
|---|-------------|-----------------|
| 3.8.1 | User navigates to the "Conflicts" section in the sidebar. | `ConflictResolution.tsx` mounts. Calls `apiFetch('/sync/conflicts')`. |
| 3.8.2 | Server returns conflict data. | `sync.py:get_conflicts()` queries all files where `file_path LIKE '%(Conflicted copy)%'` and `is_deleted = False`. For each, it finds the original file. Returns paired data. |
| 3.8.3 | UI renders the conflict dashboard. | If no conflicts: shows a green "No Active Conflicts" card with a `verified_user` icon. If conflicts exist: shows a red alert banner with filename and detection time, plus two side-by-side cards: **Option A** and **Option B**, each showing timestamp, size, and hash. |
| 3.8.4 | User clicks "Keep This Version" on Option A. | `resolveConflict('keep_original')` calls `POST /sync/resolve_conflict` with `{original_file_id, conflict_file_id, resolution_choice: 'keep_original'}`. |
| 3.8.5 | Server resolves: keep original. | Sets `c_file.is_deleted = True` (soft-deletes the conflict copy). Fires `file_deleted` SSE event. |
| 3.8.6 | User clicks "Keep This Version" on Option B. | `resolveConflict('keep_conflict')` sends `resolution_choice: 'keep_conflict'`. |
| 3.8.7 | Server resolves: keep conflict. | Sets `o_file.is_deleted = True`. Renames `c_file.file_path` to the original path (removes `(Conflicted copy)` suffix). Fires SSE events. |
| 3.8.8 | User clicks "Keep Both". | `resolveConflict('keep_both')` sends `resolution_choice: 'keep_both'`. |
| 3.8.9 | Server resolves: keep both. | Renames `c_file.file_path` from `(Conflicted copy)` to `(Resolved copy)`. Both files remain active. |
| 3.8.10 | User resolves a conflict while another device creates a new conflict on the same file. | The resolution completes. The new conflict creates a new `(Conflicted copy)` file. The conflict list refreshes and shows the new conflict. |
| 3.8.11 | The original file was deleted before the user resolves the conflict. | `resolve_conflict()` tries to find `o_file` by ID. If `is_deleted = True`, the resolution may behave unexpectedly — "keep_original" keeps a deleted file, "keep_conflict" renames the conflict copy to the original path (effective resurrection). |

---

## SECTION 4: Multi-Device & Split-Brain Scenarios

### 4.1 — Linking a Second Device

| # | User Action | System Response |
|---|-------------|-----------------|
| 4.1.1 | User installs the client agent on a second machine and runs `python main.py login`. | Same login flow as 1.3. The JWT is obtained and stored in the new machine's `shadow.db`. |
| 4.1.2 | Sync engine starts and calls `_get_device_id()`. | Checks `shadow.db` for a stored `device_id`. Not found on a fresh install. |
| 4.1.3 | Agent generates a unique device ID. | `random.randint(100000, 999999)` generates a 6-digit ID. Stored in `shadow.db` under key `device_id`. |
| 4.1.4 | Agent begins syncing. | `start_sync_loop()` calls `process_downstream_downloads(device_id)` which calls `GET /sync/metadata/diff?device_id=<new_id>`. Since this device has no entries in `file_device_map`, **every file** on the server appears in `missing_files[]`. |
| 4.1.5 | Two devices generate the same random `device_id` (collision). | `random.randint(100000, 999999)` has 900,000 possible values. Collision probability is low but non-zero. If both devices use the same ID, `file_device_map` entries from one device are shared with the other. This causes the second device to skip files it thinks are already synced. **Data loss risk.** |

### 4.2 — Initial Sync (New Device, Empty Watch Folder)

| # | User Action | System Response |
|---|-------------|-----------------|
| 4.2.1 | The new device's sync engine receives the full diff. | `missing_files` contains every non-deleted file with their latest version info. |
| 4.2.2 | Agent processes each missing file. | For each file: (1) creates directory structure via `os.makedirs()`, (2) calls `suppress_path()`, (3) if `chunk_hashes` present → delta download, (4) if no chunks → single-shot download, (5) if encryption active → decrypts, (6) writes file, (7) updates `shadow.db`, (8) calls `POST /sync/ack_sync`. |
| 4.2.3 | All files synced. | The watch folder now mirrors the server state. |
| 4.2.4 | Initial sync is interrupted (laptop lid closed at file 500/1000). | Files 1–499 are fully synced (ack_sync sent). File 500 may be partially written. On resume, `GET /sync/metadata/diff` returns files 500–1000 as missing. File 500's partial write is overwritten. |
| 4.2.5 | User has 10,000 files on the server. Initial sync starts. | `GET /sync/metadata/diff` returns 10,000 entries. The sync engine processes them sequentially in a single loop iteration. This could take hours depending on file sizes and network speed. The sync engine blocks on downloads during this entire time — no uploads are processed until all downloads complete. |

### 4.3 — The Split-Brain Collision

| # | User Action | System Response |
|---|-------------|-----------------|
| 4.3.1 | Device A goes offline. User edits `notes.txt` on Device A. | Watchdog on A fires, diff_engine logs the event in `shadow.db`. Sync engine tries to announce but `health_check()` returns `False`. The event remains `is_synced = 0`. |
| 4.3.2 | Simultaneously, user edits the same `notes.txt` on Device B / Web UI. | The file is uploaded to the server as version v2. |
| 4.3.3 | Device A comes back online. | Sync engine processes the queued event. `POST /sync/announce` with `base_version_id: <v1>`. |
| 4.3.4 | Server detects a conflict. | `_handle_conflict_if_any()` finds: `server_latest` = v2, `payload.base_version_id` = v1. v1 ≠ v2 → **conflict declared**. |
| 4.3.5 | Last-Write-Wins (LWW) resolution. | Compares `client_modified_at` (clamped to `min(client_ts, now())`) against `server_latest.announced_at`. The later timestamp **wins**. |
| 4.3.6 | **If client wins**: | Server demotes v2 to a `(Conflicted copy)` file. Creates v3 for Device A's version. Returns `{upload_required: true, version_id: v3}`. |
| 4.3.7 | **If server wins**: | Server keeps v2 as canonical. Creates a `(Conflicted copy)` for Device A's version. |
| 4.3.8 | SSE event fires. | `conflict_detected` event is broadcast to all connected clients. |
| 4.3.9 | Device A was offline for 30 days and made 50 edits to the same file. | All 50 events are queued in `shadow.db`. On reconnection, the sync engine processes them in FIFO order. The first announcement (based on v1) triggers a conflict with the server's latest version. Subsequent announcements (based on stale versions) may trigger additional conflicts. Only the final local state matters — earlier intermediate states are obsolete. |
| 4.3.10 | Three devices edit the same file simultaneously. | Device B uploads v2. Device C uploads v3 (conflict with v2 → creates conflicted copy). Device A comes online → announces based on v1 → conflict with v3 → creates another conflicted copy. Two conflict files exist. |

### 4.4 — Client-Side Conflict Detection (Simultaneous Edit During Download)

| # | User Action | System Response |
|---|-------------|-----------------|
| 4.4.1 | Sync engine discovers an outdated file during `process_downstream_downloads()`. | The server has v3, the local device has v2. |
| 4.4.2 | The user has also locally modified the file since v2. | `current_local_hash != db_plain_hash` (hash in `shadow.db` from v2 differs from current file on disk). |
| 4.4.3 | Local conflict handling activates. | `is_conflict = True`. The sync engine renames the local file to `<name>_conflict_<timestamp>.<ext>`. |
| 4.4.4 | Download proceeds. | The server's v3 is written to the original path. User's local edits preserved in the conflict file. |
| 4.4.5 | The conflict rename fails (permission denied, disk full). | `os.rename()` raises `OSError`. The download still proceeds → `open(full_local_path, "wb")` overwrites the user's local edits. **Data loss.** The conflict file was never created. |

### 4.5 — Delete Conflict (Server Deletes, Client Modifies)

| # | User Action | System Response |
|---|-------------|-----------------|
| 4.5.1 | Device B deletes `report.txt`. Server marks it as deleted. | `file.is_deleted = True`. |
| 4.5.2 | Device A (offline) modifies `report.txt`. | Local hash changes. |
| 4.5.3 | Device A comes online and syncs. | `process_downstream_downloads()` sees `report.txt` in `deleted_files[]`. Locally: `current_local_hash != db_hash` → modified after last sync. |
| 4.5.4 | Conflict preservation activates. | Local file renamed to `report_conflict_<timestamp>.txt`. Original tracking removed from `shadow.db`. The conflict file survives on disk but is treated as a new untracked file by the watchdog (which will announce it as a new file on the next scan). |

---

## SECTION 5: The Invisible UX (Network & Fault Tolerance)

### 5.1 — Wi-Fi Drops During Upload

| # | User Action | System Response |
|---|-------------|-----------------|
| 5.1.1 | User is uploading a 5 GB video (chunked). Wi-Fi disconnects at chunk 500/1250. | `resilient_http.request()` catches `ConnectionError`. |
| 5.1.2 | Retry policy activates. | `RetryPolicy` with `max_retries=5`, `base_delay=1.0s`, `backoff_factor=2.0`, `jitter=±50%`. |
| 5.1.3 | Circuit breaker engages. | After 5 consecutive failures, `CircuitBreaker` transitions to `OPEN` state. All requests immediately rejected for `recovery_timeout=30s`. |
| 5.1.4 | After 30 seconds, circuit enters `HALF_OPEN`. | One probe request allowed. If it succeeds → `CLOSED`. If it fails → re-opens. |
| 5.1.5 | Wi-Fi reconnects. | Probe succeeds. Circuit closes. Upload resumes from chunk 500 (completed_chunks preserved). |
| 5.1.6 | All remaining chunks upload successfully. | Assembly and verification proceed. **Zero data loss, zero duplicate chunks.** |
| 5.1.7 | Wi-Fi never reconnects (permanent outage). | Circuit breaker stays in OPEN → HALF_OPEN → OPEN cycle indefinitely. The upload job exhausts `UPLOAD_MAX_RETRIES` (5) retries. `_handle_failed_job()` prints `[FATAL FAILURE] Maximum fallback constraints hit`. The `in_flight` flag is cleared, allowing the event to be re-processed on the next sync cycle. The job is effectively abandoned until the network returns. |

### 5.2 — Laptop Lid Closed Mid-Download

| # | User Action | System Response |
|---|-------------|-----------------|
| 5.2.1 | Laptop lid closes. OS suspends. | All threads freeze. No crash. |
| 5.2.2 | Laptop reopens. | Threads resume. TCP connections have timed out. |
| 5.2.3 | Download resumes on next sync cycle. | `file_device_map` not updated (no `ack_sync`). `GET /sync/metadata/diff` still returns the file as missing. For chunked downloads, `_delta_download_file()` reuses any chunks already written. |

### 5.3 — Storage Quota Exceeded

| # | User Action | System Response |
|---|-------------|-----------------|
| 5.3.1 | User has used 4.9 GB of 5 GB quota. Uploads a 200 MB file. | Upload proceeds to server. |
| 5.3.2 | Server enforces quota. | User row locked with `FOR UPDATE`. SQL sums `size_bytes` of latest versions. `current_usage + file_size > storage_quota`. |
| 5.3.3 | Quota exceeded. | Returns `413 Request Entity Too Large`. |
| 5.3.4 | Client handles rejection. | Upload worker catches the error. Event remains in queue. |
| 5.3.5 | User is at exactly `5,368,709,120` bytes (5 GB). Uploads a 1-byte file. | `current_usage (5368709120) + 1 > storage_quota (5368709120)` → `True`. Rejected with `413`. Even a single byte over quota is blocked. |
| 5.3.6 | Two concurrent uploads race to fill the last 100 MB of quota. Upload A is 80 MB, Upload B is 80 MB. | Both lock the user row with `FOR UPDATE` — but only one can hold the lock at a time. First upload (e.g., A) acquires the lock, checks quota, succeeds, commits, releases lock. Second upload (B) acquires lock, checks quota → now `current_usage + 80MB > quota` → rejected with `413`. |
| 5.3.7 | User deletes files to free space, then retries. | Delete sets `is_deleted = True`. Quota calculation sums only non-deleted files' latest versions. Space is freed. Retry succeeds. |

### 5.4 — Server Goes Down for Maintenance

| # | User Action | System Response |
|---|-------------|-----------------|
| 5.4.1 | Backend server shuts down. | `health_check()` fails. |
| 5.4.2 | Sync engine enters idle mode. | Prints `[SYNC ENGINE] Remote node sleeping/unreachable. Idle hold pattern.` |
| 5.4.3 | Files continue to be tracked locally. | Watchdog and diff_engine operate normally. Events queued with `is_synced = 0`. |
| 5.4.4 | SSE listener loses connection. | Exponential backoff: 5s → 10s → 20s → 40s → 60s (max). |
| 5.4.5 | Server comes back online. | `health_check()` succeeds. Backlog processed in FIFO order. SSE reconnects. |
| 5.4.6 | The client agent **never crashes**. | All network calls go through `resilient_http.py`. Circuit breaker prevents tight retry loops. Agent runs indefinitely in degraded-but-alive state. |

### 5.5 — Heartbeat & Device Online Status

| # | User Action | System Response |
|---|-------------|-----------------|
| 5.5.1 | Client agent is running normally. | `_heartbeat_worker()` sends `POST /devices/{device_id}/heartbeat` every 60 seconds. |
| 5.5.2 | Server updates device status. | Sets `device.is_online = True`, `device.last_seen_at = now()`. Returns pending commands. |
| 5.5.3 | Server sends a `WAKE` command. | Client prints `🌟 WAKE SIGNAL RECEIVED FROM SERVER 🌟` and acknowledges. |
| 5.5.4 | Server sends a `REVOKE` command. | Client wipes local credentials, acknowledges, calls `sys.exit(0)`. |
| 5.5.5 | Heartbeat fails due to network outage. | `_heartbeat_worker()` catches the exception silently (`except Exception: pass`). Retries in 60 seconds. Device appears offline on the server after the `last_seen_at` goes stale. |
| 5.5.6 | Server sends both `WAKE` and `REVOKE` in the same heartbeat response. | Commands are processed in order. `WAKE` is acknowledged first. Then `REVOKE` wipes credentials and exits. |

### 5.6 — Zero-Knowledge Encryption Pipeline

| # | User Action | System Response |
|---|-------------|-----------------|
| 5.6.1 | Encryption is active. User drops a file. | `prepare_encrypted_payload()` splits into chunks, encrypts each with AES-256-GCM using random 12-byte nonces, packs as `[12B nonce][16B tag][ciphertext]`. |
| 5.6.2 | Encrypted bytes are uploaded. | Server **never sees plaintext**. Stores and verifies only encrypted hashes. |
| 5.6.3 | Another device downloads. | Encrypted bytes fetched. `unpack_encrypted()` extracts nonce/tag/ciphertext. `decrypt_chunk()` decrypts with AES-256-GCM. |
| 5.6.4 | Decryption fails (wrong passphrase). | `AESGCM.decrypt()` raises `InvalidTag`. File is **not written** to disk. |
| 5.6.5 | User changes their passphrase on Device B. | Device B derives a different AES key from the new passphrase. All files previously encrypted with the old key **cannot be decrypted** by Device B. Device A (still using the old passphrase) works fine. There is no key rotation mechanism — both keys would need to coexist, which they don't. |
| 5.6.6 | Encryption nonces are reused (deterministic retry). | `get_or_create_nonces()` persists nonces in `pending_chunk_uploads` keyed by `(file_path, chunk_index)`. On retry, the same nonce is reused for the same chunk. This ensures identical encrypted output → idempotent uploads. But if the file content changes between retries, the old nonces are cleared (`DELETE FROM pending_chunk_uploads WHERE plaintext_hash != ?`). |
| 5.6.7 | User uploads a file in plaintext (no passphrase), then enables encryption and uploads a new version. | v1 stored in plaintext on MinIO. v2 stored encrypted. Downloading v1 → server returns plaintext → client tries to decrypt (encryption_key is set) → `unpack_encrypted()` fails because the bytes aren't in `[nonce][tag][ciphertext]` format → `ValueError` or corruption. **v1 becomes undownloadable when encryption is enabled.** |
| 5.6.8 | Encryption key is 32 bytes of all zeros (weak passphrase). | `PBKDF2-HMAC-SHA256` with 100k iterations makes this still computationally expensive to brute-force. But the key is stored in plaintext in `shadow.db` — anyone with access to the file can read it. |

### 5.7 — SSE Event Bus Architecture

| # | User Action | System Response |
|---|-------------|-----------------|
| 5.7.1 | Client connects to SSE stream. | `event_listener.py` calls `GET /events/stream?token=<jwt>` with `stream=True`. Server subscribes user to `asyncio.Queue`. |
| 5.7.2 | Server publishes an event. | `publish_event()` iterates subscriber queues. `queue.put_nowait()`. If queue is full → event dropped for that subscriber. |
| 5.7.3 | Client receives an event. | Parses SSE `data:` line as JSON. If actionable type → sets `sync_nudge` to wake sync engine. |
| 5.7.4 | No events for 30 seconds. | Server sends `heartbeat` SSE event. Client ignores it. |
| 5.7.5 | SSE connection drops. | Client backs off: 5s → 10s → 20s → 40s → 60s max. Reconnects. |
| 5.7.6 | React UI SSE. | `useEventStream.ts` uses native `EventSource`. `es.onerror` handles reconnection with backoff 1s → 2s → 4s → 8s → 30s max. Cleanup on unmount closes EventSource and clears reconnect timeout. |
| 5.7.7 | 100 clients connect SSE simultaneously. | Server maintains 100 `asyncio.Queue` instances. Each event is put into all 100 queues. Memory grows linearly with subscriber count. No subscriber limit implemented. |
| 5.7.8 | SSE event published between client disconnect and reconnect. | Event is dropped for that subscriber (queue was removed on disconnect). The client misses the event. On reconnection, no replay mechanism exists — the client relies on the next `refreshFiles()` or sync cycle to catch up. |

---

## SECTION 6: System Health & Infrastructure Monitoring (UI Views)

### 6.1 — Node Management Dashboard

| # | User Action | System Response |
|---|-------------|-----------------|
| 6.1.1 | User navigates to "Network Nodes" in the sidebar. | `NodeManagement.tsx` renders a list of all registered devices showing name, online status, last seen time, and device commands. |
| 6.1.2 | User sees a device marked "offline" (last seen 2 hours ago). | The device's `is_online` may still be `True` if no mechanism resets it. The `last_seen_at` timestamp shows the stale time. |
| 6.1.3 | User sends a `WAKE` command to an offline device. | `POST /devices/{id}/command` with `{command: "WAKE"}`. A `DeviceCommand` row is created with `status: "pending"`. The command sits in the queue until the device's next heartbeat. |
| 6.1.4 | User sends a `REVOKE` command. | `DeviceCommand` with `command: "REVOKE"` created. On the device's next heartbeat, the REVOKE triggers credential wipe and shutdown. |
| 6.1.5 | User renames a device. | `PUT /devices/{id}` with `{device_name: "New Name"}`. The `device_name` column is updated. |

### 6.2 — System Health Dashboard

| # | User Action | System Response |
|---|-------------|-----------------|
| 6.2.1 | User navigates to "System Health". | `SystemHealth.tsx` renders system metrics including active connections, sync status, and infrastructure health. |

### 6.3 — Network Activity Monitor

| # | User Action | System Response |
|---|-------------|-----------------|
| 6.3.1 | User navigates to "Network Activity". | `NetworkActivity.tsx` displays real-time network transfer metrics and connection status. |

---

## SECTION 7: Chaotic & Destructive Behavior (Red Team Brainstorm)

### 7.1 — Filesystem Abuse

| # | User/System Action | Expected System State |
|---|--------------------|-----------------------|
| 7.1.1 | User fills the disk to 100% capacity, then tries to download a file from the server. | `open(full_local_path, "wb")` raises `OSError: [Errno 28] No space left on device`. Download fails. File remains in `missing_files` on next diff. |
| 7.1.2 | User fills the disk to 100%, watchdog fires for a file that was just created (the last bytes that fit). | `diff_engine` tries to write to `shadow.db` → `sqlite3.OperationalError: database or disk is full`. Event is not logged. File exists on disk but is untracked. |
| 7.1.3 | User creates a file inside `watch_folder`, then immediately makes it a FIFO/named pipe (Linux). | `hash_utils.hash_file()` opens and reads the FIFO. If nothing writes to the other end, `read()` **blocks forever**. The diff_engine thread hangs. Other file events are not processed. |
| 7.1.4 | User creates a file, then replaces it with a directory of the same name. | Watchdog fires `on_created` (file) then `on_deleted` (file) then possibly `on_created` (directory, filtered). `diff_engine` processes the delete. The directory is ignored. |
| 7.1.5 | User rapidly creates and deletes the same filename 1,000 times in a loop. | 1,000 `on_created` (debounced) + 1,000 `on_deleted` (immediate) events. The debounce timers for creates are constantly cancelled by the next delete. Most creates are never processed. Deletes are processed but may fail to find the file in `shadow.db` (it was never fully tracked). Lots of noise, no crash. |
| 7.1.6 | User creates a hard link to a file inside `watch_folder` from outside. | The hard link appears as a regular file. Watchdog may or may not fire (depends on filesystem). If it does, the file is tracked normally. Editing the original outside `watch_folder` changes the content (same inode), but watchdog only watches events inside `watch_folder`. The change is invisible until the next full scan. |
| 7.1.7 | User mounts a RAM disk as a subdirectory of `watch_folder`. | Watchdog with `recursive=True` may or may not detect events on the mounted filesystem (depends on OS). On Linux with inotify, cross-mount events are typically NOT detected. Files on the RAM disk are invisible to the watcher. |
| 7.1.8 | User creates a file with null bytes (`\x00`) in the name. | Most filesystems reject null bytes in filenames. If somehow created, `os.path.relpath()` may produce unexpected results. The server's `String(1000)` column may store it, but MinIO key encoding may fail. |
| 7.1.9 | User creates a file with newline characters (`\n`) in the name. | Valid on Linux. Watchdog fires. `os.path.relpath()` includes the newline. `POST /sync/announce` sends the path with the newline as JSON string. Server stores it. But MinIO and HTTP headers may break on newlines in keys. |
| 7.1.10 | `shadow.db` gets corrupted (power failure during write). | `sqlite3.connect()` may raise `sqlite3.DatabaseError: database disk image is malformed`. All operations that touch `shadow.db` fail. The diff engine, sync engine, and settings system all break. Agent is effectively dead. Requires manual deletion and re-creation of `shadow.db`. |
| 7.1.11 | User manually edits `shadow.db` to change a file's hash to a garbage value. | Sync engine reads the garbage hash. On the next `announce_metadata()`, the server sees a hash it doesn't recognize. It creates a new version and requests upload. The file is re-uploaded. Self-healing behavior (at the cost of bandwidth). |
| 7.1.12 | User deletes `shadow.db` while the agent is running. | Any SQLite operation raises `sqlite3.OperationalError: unable to open database file`. The agent crashes or enters a broken state. `_get_setting()` returns `None` for all keys. Token is lost. Encryption key is lost. The agent cannot authenticate or sync. |

### 7.2 — Network Abuse

| # | User/System Action | Expected System State |
|---|--------------------|-----------------------|
| 7.2.1 | Network has 90% packet loss. | `resilient_http.request()` retries are triggered constantly. Some requests eventually get through. Uploads take orders of magnitude longer. The circuit breaker may oscillate between OPEN and HALF_OPEN. Agent remains alive but extremely slow. |
| 7.2.2 | DNS resolution fails (server hostname can't be resolved). | `requests.get()` raises `ConnectionError`. Same retry/circuit-breaker behavior as a full network drop. |
| 7.2.3 | Server returns `502 Bad Gateway` (nginx proxy issue). | `resilient_http.request()` retries on `status_code >= 500`. After 5 retries, the request fails. Circuit breaker may engage. |
| 7.2.4 | Server returns `429 Too Many Requests`. | `resilient_http.request()` does not have special handling for `429`. The response is returned as-is. The sync engine treats it as a non-2xx response and may log an error. No rate-limiting backoff is implemented. |
| 7.2.5 | Response body is truncated mid-stream (server crash during response). | `requests` raises `ChunkedEncodingError` or `ConnectionError`. Retry policy handles it. |
| 7.2.6 | Server takes 120+ seconds to respond (timeout). | `resilient_http.request()` uses the caller's `timeout` parameter (typically 30–120s). `requests` raises `ReadTimeout`. Retry policy handles it. |
| 7.2.7 | TLS certificate is invalid (MITM attack). | `requests` raises `SSLError` by default. `resilient_http` does not disable SSL verification. The request fails. |
| 7.2.8 | WiFi drops exactly between the server receiving an upload and sending the response. | Server successfully writes to MinIO and enqueues verification. But the client never receives the `202` response. Client retries the upload → server receives a duplicate. If the `unique_chunk_per_version` constraint catches the duplicate chunk, a `409` or `IntegrityError` is raised. Server should handle this gracefully. |
| 7.2.9 | User is behind a corporate proxy that injects HTML into non-200 responses. | `resilient_http` receives an HTML page instead of JSON. `resp.json()` raises `JSONDecodeError`. The error propagates up. |

### 7.3 — Concurrent Operation Chaos

| # | User/System Action | Expected System State |
|---|--------------------|-----------------------|
| 7.3.1 | User uploads the same file from the UI and the CLI simultaneously. | Local agent writes the file once (UI upload). Watchdog fires once. CLI is not directly uploading — it watches the folder. So there's no true concurrent upload from two sources. But if the user runs two agent instances, two announce calls hit the server. The `unique_path_per_user` constraint prevents duplicate `File` rows. One succeeds, one gets an error. |
| 7.3.2 | Two sync engines run on the same machine (user launches `watcher.main()` twice). | Two `Observer` instances watch the same directory. Both fire events. Both diff_engines try to write to the same `shadow.db`. SQLite's file-level locking (`timeout=30.0`) serializes access. Both engines process the same events → two `POST /sync/announce` for each file → server deduplicates via hash check. Wasteful but not data-corrupting. |
| 7.3.3 | Upload worker is uploading chunk 50 of file A. User modifies file A on disk. | The upload worker opened the file before the modification. The read handle still points to the old data (depends on OS — Windows may block writes while the file is open for reading). If the OS allows concurrent writes, the upload worker reads stale data. After upload completes, the obsolescence check catches the hash mismatch, and a new event is processed for the modified version. |
| 7.3.4 | 50 files are dropped simultaneously. SQLite contention occurs. | 50 debounce timers fire after 2 seconds. 50 threads call `diff_engine.process_single_file()`. Each acquires the SQLite write lock (`timeout=30.0`). They are serialized — one completes, then the next. Total processing time = 50 × (hash_time + db_write_time). No data loss. |
| 7.3.5 | `event_listener.sync_nudge.set()` fires while sync engine is mid-loop. | `sync_nudge` is a `threading.Event`. `wait(timeout=10)` returns immediately if already set. The current sync cycle continues normally. On the next iteration, `sync_nudge.clear()` resets it and the loop runs again immediately. |

### 7.4 — MinIO / Object Storage Failures

| # | User/System Action | Expected System State |
|---|--------------------|-----------------------|
| 7.4.1 | MinIO bucket is full (disk space exhausted). | `storage.put_object()` raises an error. Server returns `500`. Upload fails. Client retries. |
| 7.4.2 | MinIO is completely down. | `storage.put_object()` and `storage.get_object()` raise connection errors. All uploads and downloads fail. Announcements still succeed (they only write to PostgreSQL). |
| 7.4.3 | A chunk object in MinIO is corrupted (bit rot). | `assemble_and_verify_chunks()` reads the corrupted chunk, concatenates all chunks, computes SHA-256 → mismatch → `upload_status = failed`. SSE event `upload_failed` fires. The user must re-upload. |
| 7.4.4 | Admin manually deletes objects from MinIO. | Downloads for the affected files fail with `NoSuchKey`. Version records in PostgreSQL still reference the deleted objects. |
| 7.4.5 | MinIO returns `SlowDown` (rate limiting). | `storage.put_object()` raises an error. Server returns `500`. Client retries with exponential backoff. |

### 7.5 — PostgreSQL / Database Failures

| # | User/System Action | Expected System State |
|---|--------------------|-----------------------|
| 7.5.1 | PostgreSQL connection pool is exhausted. | SQLAlchemy raises `TimeoutError` when trying to acquire a connection. Server returns `500`. Client retries. |
| 7.5.2 | PostgreSQL is restarted while the server is running. | Active connections drop. Next query raises `OperationalError: server closed the connection`. SQLAlchemy's pool recycles the connection. Subsequent requests succeed. |
| 7.5.3 | A database migration runs while the server is live. | Depending on the migration (e.g., adding a column), queries may fail with `ProgrammingError: column does not exist`. |
| 7.5.4 | `SELECT ... FOR UPDATE` deadlock between two concurrent uploads. | Two transactions lock user rows in different orders. PostgreSQL detects the deadlock and aborts one transaction with `DeadlockDetected`. The aborted request returns `500`. Client retries. |
| 7.5.5 | The `unique_path_per_user` constraint is violated by a race condition. | Two `announce` calls for the same path arrive simultaneously. Both call `_get_or_create_file()`. Both try to `INSERT INTO files`. One succeeds, the other hits `IntegrityError`. The server should catch this and retry with the existing file. |

### 7.6 — RQ Worker Failures

| # | User/System Action | Expected System State |
|---|--------------------|-----------------------|
| 7.6.1 | RQ worker process crashes during `assemble_and_verify_chunks()`. | The job remains in RQ's queue with a `failed` status. The version's `upload_status` remains `processing` forever. The file appears with a spinning yellow icon in the UI indefinitely. |
| 7.6.2 | RQ worker is not running at all. | Jobs are enqueued but never processed. All uploads get stuck at `processing` status. |
| 7.6.3 | RQ worker successfully verifies a hash but crashes before updating the DB. | `upload_status` remains `processing`. The file is correctly stored in MinIO but the status is wrong. On a re-run, the worker would re-verify and update the status. |
| 7.6.4 | Redis (RQ's broker) is down. | `rq.Queue.enqueue()` raises `ConnectionError`. The server catches this and returns `500`. The upload is not processed. |

---

## SECTION 8: Extreme State Permutations (Cross-Feature Interactions)

### 8.1 — Split-Brain + Network Drop

| # | Scenario | Expected Outcome |
|---|---------|------------------|
| 8.1.1 | Device A is offline and edits `file.txt`. Device B edits the same file and uploads v2. Device A comes online. Announces its edit. Server declares conflict. Upload of conflict version starts. Network drops at chunk 3 of the conflict upload. | Conflict is declared but the conflict version is partially uploaded. `upload_status = uploading`. The conflict copy file exists in `files` table but has incomplete data. Circuit breaker handles the network drop. On reconnection, the upload resumes from chunk 3. |
| 8.1.2 | Device A and B both go offline simultaneously. Both edit the same file. Both come online at the same time. | Both announce simultaneously. The first to be processed by the server creates v2. The second triggers a conflict with v2. LWW determines the winner. Two API calls are serialized by the database lock. |

### 8.2 — Encryption + Conflict Resolution

| # | Scenario | Expected Outcome |
|---|---------|------------------|
| 8.2.1 | Device A encrypts `secret.txt` with passphrase "alpha". Device B encrypts the same file with passphrase "beta" (different key). Conflict occurs. | Both devices encrypt with different keys. The server stores both encrypted versions. When Device A downloads the conflict copy (encrypted by B), decryption fails with `InvalidTag`. The conflict file is not written to disk. Device A cannot read Device B's version unless they use the same passphrase. |
| 8.2.2 | User resolves a conflict (keep original) on encrypted files. | Server soft-deletes the conflict copy. Both encrypted MinIO objects remain (soft delete doesn't purge storage). The winning version is downloadable by devices with the correct key. |

### 8.3 — Quota + Chunked Upload

| # | Scenario | Expected Outcome |
|---|---------|------------------|
| 8.3.1 | User has 100 MB of quota remaining. Starts uploading a 500 MB file (125 chunks). Chunk quota check passes for early chunks. Another upload from a different device consumes 80 MB. Chunk 100 arrives, quota check shows only 20 MB remaining but 100 MB of chunks already received. | Each `upload_chunk()` call runs the quota check. The quota calculation includes the partially-uploaded version's `size_bytes` (which is 0 until assembly). So individual chunk uploads don't fail on quota — only the final `upload_file()` or assembly step checks total size. **The 500 MB file may succeed even though it exceeds remaining quota** because chunk uploads don't individually enforce the quota against cumulative chunk sizes. |
| 8.3.2 | User is exactly at quota. Uploads a 0-byte file. | `announce_metadata()` succeeds. `_handle_empty_file()` creates the version with `size_bytes=0`. No upload needed. Quota unchanged. **0-byte files always succeed.** |

### 8.4 — SSE + Initial Sync

| # | Scenario | Expected Outcome |
|---|---------|------------------|
| 8.4.1 | New device starts initial sync (1,000 files to download). During the download, another device uploads 50 new files. SSE events fire. | The SSE `sync_nudge` wakes the sync engine. But the sync engine is busy in `process_downstream_downloads()` (blocking loop). The nudge is not consumed until the current sync cycle completes. After initial sync finishes, the next cycle runs immediately (nudge was set), picks up the 50 new files from `GET /sync/metadata/diff`, and downloads them. No files are missed, but there's a delay. |
| 8.4.2 | SSE event for `file_deleted` arrives while the sync engine is downloading that same file. | The download is in progress. The file is written to disk. Then `process_downstream_downloads()` finishes. On the next sync cycle, `GET /sync/metadata/diff` returns the file in `deleted_files[]`. The sync engine deletes it. Net effect: file is downloaded then immediately deleted. Wasted bandwidth but no corruption. |

### 8.5 — Assembly Failure + Download

| # | Scenario | Expected Outcome |
|---|---------|------------------|
| 8.5.1 | Device A uploads all chunks. RQ worker starts assembly. Assembly fails (hash mismatch). `upload_status = failed`. Device B requests `GET /sync/metadata/diff`. | The file's latest version has `upload_status = failed`. Depending on how `metadata/diff` filters, the file may appear as `missing` with a `storage_path` pointing to the failed version. Device B attempts to download → either gets a corrupt file or a `404` (if the assembled file was never written). |
| 8.5.2 | RQ worker crashes during assembly. Another device tries to download. | Version stuck at `processing`. Download may return the unassembled chunks directory or fail entirely depending on implementation. |

### 8.6 — Watcher Suppression Race Conditions

| # | Scenario | Expected Outcome |
|---|---------|------------------|
| 8.6.1 | Sync engine calls `suppress_path(path)` then writes a file. The write takes longer than `SUPPRESSION_WINDOW_SECONDS` (5 seconds). | The suppression expires before the write completes. Watchdog fires `on_modified` → `is_suppressed()` returns `False` (TTL expired). The file is processed by `diff_engine` and re-announced to the server, creating a redundant new version with the same hash. Server's hash dedup (`_check_hash_dedup()`) catches this and returns `upload_required: false`. No data corruption, but a wasted announce call. |
| 8.6.2 | Two downloads complete for the same path within the suppression window. | First download calls `suppress_path()` and writes. Second download calls `suppress_path()` again, resetting the TTL. Both writes are suppressed. No watchdog feedback loop. |

### 8.7 — JWT Expiry During Conflict Resolution

| # | Scenario | Expected Outcome |
|---|---------|------------------|
| 8.7.1 | User views the conflict resolution page. JWT expires. User clicks "Keep This Version". | `apiFetch` sends the request with expired token → `401` → refresh flow → new token → retry → conflict resolved. User sees no interruption (the refresh is transparent). |
| 8.7.2 | JWT expires during SSE connection. | `EventSource` receives an error (server closes the connection on auth failure). `es.onerror` triggers reconnect with the old token → still fails → reconnect with backoff. The UI doesn't automatically refresh the token for EventSource connections (it re-reads from localStorage, but the token there is also expired). The SSE stays disconnected until the user performs an action that triggers `apiFetch` → refresh → new token stored → next SSE reconnect uses the new token. |

### 8.8 — Full Scan Edge Cases

| # | Scenario | Expected Outcome |
|---|---------|------------------|
| 8.8.1 | Agent starts. `run_full_scan()` scans 10,000 files. During the scan, the user deletes 500 files. | `run_full_scan()` iterates `os.walk()`. For files it reaches before deletion: they are hashed and tracked normally. For files deleted before the scan reaches them: `hash_file()` fails (file not found) or `os.walk()` already yielded them. If `hash_file()` raises `FileNotFoundError`, `diff_engine` catches it and skips. The 500 deleted files may or may not be tracked depending on timing. |
| 8.8.2 | Agent starts with 5,000 files already in `watch_folder` but `shadow.db` is fresh (empty). | `run_full_scan()` discovers all 5,000 files. Each is logged as `[BOOTSTRAP FIND] New entry → <name>`. 5,000 events with `event_type="new"` are created. Sync engine processes all 5,000 on the next cycle. If the server already has these files (from another device), hash dedup kicks in → no re-upload. If the server doesn't have them, all 5,000 are uploaded. |
| 8.8.3 | Agent starts. `shadow.db` has entries for files that no longer exist on disk. | `run_full_scan()` does NOT clean up stale entries. It only processes files that exist. The stale entries remain in `shadow.db`. They won't cause immediate issues, but the sync engine may try to upload them → `os.path.exists()` fails → job discarded. |

---

## SECTION 9: Security Edge Cases

### 9.1 — Authentication Bypass Attempts

| # | Attack Vector | Expected System State |
|---|--------------|----------------------|
| 9.1.1 | Attacker sends `POST /sync/announce` without `Authorization` header. | FastAPI's `Depends(get_current_user)` raises `401 Unauthorized`. Request rejected. |
| 9.1.2 | Attacker sends a JWT signed with a different secret key. | `jwt.decode()` raises `InvalidSignatureError`. Returns `401`. |
| 9.1.3 | Attacker modifies the `user_id` claim in the JWT payload without re-signing. | Signature verification fails → `401`. |
| 9.1.4 | Attacker obtains a valid JWT and tries to access another user's files via `GET /sync/download?storage_path=<other_user_id>/file`. | `download_file()` validates that the `storage_path` belongs to a version owned by the authenticated user. If the check is robust (queries `Version` joined with `File` filtered by `user_id`), the request is rejected. If the check only validates path format, it may succeed. **Depends on implementation.** |
| 9.1.5 | Attacker sends `DELETE /sync/file/{id}` with another user's file ID. | `delete_file()` queries `File` filtered by `user_id = current_user.id AND id = file_id`. If the file doesn't belong to the authenticated user, no row is found → `404`. |
| 9.1.6 | Attacker floods `POST /users/register` with 10,000 accounts. | No rate limiting. 10,000 user rows created. Storage quota is allocated but no files uploaded. Database grows. |
| 9.1.7 | Attacker sends a malicious `storage_path` like `../../etc/passwd` to the download endpoint. | If the server constructs MinIO keys from the `storage_path`, path traversal may read arbitrary MinIO objects. MinIO keys are flat (no filesystem semantics), so `../` has no special meaning. But if the server uses `storage_path` to construct filesystem paths, traversal is possible. |

### 9.2 — Data Integrity Attacks

| # | Attack Vector | Expected System State |
|---|--------------|----------------------|
| 9.2.1 | Attacker intercepts a chunk upload and replaces bytes mid-transit (MITM without TLS). | The server stores the tampered bytes. `verify_file_hash()` or `assemble_and_verify_chunks()` computes SHA-256 of the received data → mismatch with announced hash → `upload_status = failed`. The tampered file is rejected. |
| 9.2.2 | Attacker announces a file with `hash: "fakehash"` but uploads different content. | Server stores the uploaded content. Verification computes the real hash → mismatch with `fakehash` → `upload_status = failed`. |
| 9.2.3 | Attacker announces with a valid hash, server dedup matches an existing version, attacker never uploads. | `_check_hash_dedup()` finds the hash → returns `upload_required: false`. A new `File` record is created pointing to the existing version's storage. The attacker now has a file record they didn't upload, pointing to another user's data. **If dedup is cross-user, this leaks data.** If dedup is per-user only, this is safe. |

---

## APPENDIX A: Event Type Reference

| SSE Event Type | Fired By | Consumed By | Trigger |
|---|---|---|---|
| `file_created` | `_accept_new_version()` | FileExplorer, sync_engine | New file announced |
| `file_updated` | `_handle_empty_file()` | FileExplorer, sync_engine | File version updated |
| `file_deleted` | `_handle_deletion()`, `delete_file()`, `resolve_conflict()` | FileExplorer, sync_engine | File soft-deleted |
| `upload_processing` | `upload_file()` | FileExplorer | Upload received, verifying |
| `upload_complete` | `worker.py` (via SSE) | FileExplorer | Background verification passed |
| `upload_failed` | `worker.py` (via SSE) | FileExplorer | Hash mismatch or error |
| `conflict_detected` | `_resolve_client_wins()`, `_resolve_server_wins()` | ConflictResolution, sync_engine | Split-brain collision found |
| `heartbeat` | `event_stream()` timeout | (ignored) | 30-second keep-alive |

## APPENDIX B: API Endpoint Inventory

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| `POST` | `/users/register` | None | Create new user account |
| `POST` | `/users/login` | None | Authenticate and receive JWT |
| `POST` | `/auth/login` | None | Alternative login endpoint |
| `POST` | `/auth/refresh` | Bearer (expired OK) | Renew expired JWT |
| `GET` | `/auth/me` | Bearer | Get current user info |
| `GET` | `/health` | None | Server health check |
| `POST` | `/sync/announce` | Bearer | Announce file metadata change |
| `POST` | `/sync/upload` | Bearer | Single-shot file upload |
| `POST` | `/sync/upload_chunk` | Bearer | Chunked file upload |
| `GET` | `/sync/metadata` | Bearer | List all user files |
| `GET` | `/sync/metadata/diff` | Bearer | Compute device sync diff |
| `GET` | `/sync/download` | Bearer | Download file from MinIO |
| `GET` | `/sync/download_chunk` | Bearer | Download single chunk |
| `POST` | `/sync/ack_sync` | Bearer | Acknowledge file sync |
| `GET` | `/sync/upload/status/{id}` | Bearer | Poll upload progress |
| `DELETE` | `/sync/file/{id}` | Bearer | Soft-delete a file |
| `GET` | `/sync/versions/recent` | Bearer | Get version history |
| `GET` | `/sync/conflicts` | Bearer | List unresolved conflicts |
| `POST` | `/sync/resolve_conflict` | Bearer | Resolve a file conflict |
| `POST` | `/devices/register` | None | Register a new device |
| `POST` | `/devices/{id}/heartbeat` | Bearer | Device keep-alive ping |
| `PUT` | `/devices/{id}` | Bearer | Update device name |
| `POST` | `/devices/{id}/command` | Bearer | Queue command for device |
| `POST` | `/devices/{id}/command/{cid}/ack` | Bearer | Acknowledge command |
| `GET` | `/events/stream` | Bearer | SSE event stream |

## APPENDIX C: Local Agent API (Port 8001)

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/auth/login` | Login via UI → triggers watcher start |
| `POST` | `/api/auth/register` | Register via UI → auto-login + watcher |
| `POST` | `/api/upload` | Write file to watch_folder from UI |
| `GET` | `/api/download` | Read local file for text editor |

## APPENDIX D: Database Schema Summary

| Table | Primary Key | Purpose |
|---|---|---|
| `users` | `id` (BigInt) | User accounts with storage quotas |
| `devices` | `id` (BigInt) | Registered client devices per user |
| `device_commands` | `id` (BigInt) | Queued commands (WAKE, REVOKE) |
| `files` | `id` (BigInt) | File metadata with soft-delete flag |
| `versions` | `id` (BigInt) | Immutable version history per file |
| `file_device_map` | `(device_id, file_id)` | Tracks sync state per device |
| `chunk_uploads` | `id` (BigInt) | In-progress chunk tracking |
| `stored_chunks` | `chunk_hash` (String) | Global content-addressable chunk store |
| `version_chunks` | `id` (BigInt) | Maps versions to their constituent chunks |

### Local SQLite Schema (`shadow.db`)

| Table | Purpose |
|---|---|
| `files` | Local file tracking (path, hash, size, version_id, encrypted_hash) |
| `events` | Outbound sync queue (event_type, file_path, hash, is_synced) |
| `chunk_signatures` | Per-file chunk hashes for delta sync |
| `settings` | Key-value store (jwt_token, device_id, encryption_key, user_email) |
| `pending_chunk_uploads` | Encryption nonce tracking for resumable uploads |
| `local_chunk_nonces` | Persistent nonce storage for deterministic re-encryption |

## APPENDIX E: Configuration Constants Reference

| Constant | Default Value | Source | Purpose |
|---|---|---|---|
| `SERVER_BASE_URL` | `http://localhost:8000` | `SHADOWDRIVE_SERVER` env | Backend API base URL |
| `WATCH_DIR` | `<project>/watch_folder` | `SHADOWDRIVE_WATCH_DIR` env | Monitored directory |
| `DB_PATH` | `<project>/shadow.db` | Derived from `BASE_DIR` | Local SQLite database |
| `CHUNK_SIZE` | `4,194,304` (4 MB) | `SHADOWDRIVE_CHUNK_SIZE` env | Chunk split size |
| `CHUNK_THRESHOLD` | `4,194,304` (4 MB) | Same as `CHUNK_SIZE` | Chunked vs single-shot boundary |
| `SYNC_INTERVAL_SECONDS` | `10` | `SHADOWDRIVE_SYNC_INTERVAL` env | Sync loop polling interval |
| `UPLOAD_MAX_RETRIES` | `5` | `SHADOWDRIVE_UPLOAD_RETRIES` env | Max retries per upload job |
| `RETRY_BACKOFF_SECONDS` | `2` | Hardcoded | Base backoff for retries |
| `RETRY_MAX_BACKOFF_SECONDS` | `60` | Hardcoded | Maximum backoff cap |
| `HASH_ALGORITHM` | `sha256` | Hardcoded | File integrity algorithm |
| `DEBOUNCE_DELAY` | `2.0` seconds | Hardcoded in `watcher.py` | Watchdog event debounce |
| `SUPPRESSION_WINDOW_SECONDS` | `5.0` seconds | Hardcoded in `watcher.py` | Path suppression TTL |
| `storage_quota` | `5,368,709,120` (5 GB) | DB default for `User.storage_quota` | Per-user storage limit |
| `PBKDF2 iterations` | `100,000` | Hardcoded in `crypto_utils.py` | Key derivation strength |
