# ShadowDrive++ Metadata Formats Specification (Week 9 Support)

This document specifies the metadata formats and schema representations used by the ShadowDrive++ client agent (`Rohan`). It is provided to support the backend/DBMS owner (`Shabd`) in building the Streamlit/React Dashboard UI (Week 9).

Since Rohan's client has already implemented local shadow tracking, metadata announcement, and two-way sync in Weeks 5-8, **no active client-side code changes are required** to enable the dashboard. All required synchronization history, version histories, and conflict warnings are already populated in the server's PostgreSQL database by the client's API announcements.

---

## 1. Local Client Database Schema (`shadow.db`)

The client tracks the local workspace state in a SQLite database (`shadow.db`) using two primary tables. This structure can help Shabd understand how the client models files and events before syncing.

### `files` Table
Tracks the latest successfully synchronized state of the local files.
```sql
CREATE TABLE files (
    file_path     TEXT PRIMARY KEY,  -- Absolute path on the client's disk
    hash          TEXT NOT NULL,     -- SHA-256 hash of the file content
    size          INTEGER NOT NULL,  -- File size in bytes
    last_modified REAL NOT NULL,     -- OS last-modified timestamp (mtime)
    version_id    INTEGER DEFAULT 0  -- Server-assigned canonical version ID
);
```

### `events` Table
Acts as a staging queue logging change events captured by the file watcher until they are announced and synced.
```sql
CREATE TABLE events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,         -- 'new', 'modified', or 'deleted'
    file_path  TEXT NOT NULL,         -- Absolute path on the client's disk
    hash       TEXT,                  -- SHA-256 hash (NULL for deletions)
    is_synced  INTEGER DEFAULT 0,     -- 0 = Pending, 1 = Synchronized
    timestamp  TEXT NOT NULL,         -- ISO-8601 string of when the event occurred
    version_id INTEGER DEFAULT 0      -- Server-assigned base version ID
);
```

---

## 2. API Communication Payload Formats

These are the JSON and Form payload formats transited between Rohan's client and Shabd's server. The dashboard can use these formats to visualize device sync activity and track active transmissions.

### A. Metadata Announcement (`POST /sync/announce`)
Sent by the client when announcing a local file change.

**Request Payload:**
```json
{
  "path": "documents/report.pdf",
  "hash": "a58f3c834b9d0124e548f0293cb84a51e6040527af3fb55ffbc1e893e3b0c442",
  "event": "modified",
  "base_version_id": 4,
  "client_modified_at": "2026-05-21T08:52:25.123456"
}
```

**Response Payload (No Conflict):**
```json
{
  "status": "accepted",
  "file_id": 12,
  "version_id": 5,
  "upload_required": true
}
```

**Response Payload (Conflict Detected & LWW Resolved):**
If the server detects a split-brain condition (conflict), it resolves it via Last-Write-Wins (LWW) and returns the following structure, which is crucial for displaying **Conflict Warnings** on the dashboard.
```json
{
  "status": "conflict_resolved",
  "file_id": 12,
  "version_id": 6,
  "upload_required": true,
  "conflict_info": {
    "conflict_file_path": "documents/report (Conflicted copy).pdf",
    "conflict_version_id": 7,
    "winner_version_id": 6,
    "resolution": "lww"
  }
}
```

### B. Metadata Diff Discovery (`GET /sync/metadata/diff`)
The client calls this to reconcile downstream changes. The response contains all differences the dashboard represents.

**Response Payload:**
```json
{
  "device_id": 1,
  "missing_files": [
    {
      "file_path": "images/logo.png",
      "file_id": 3,
      "hash": "b2c3d4e5...",
      "version_num": 1,
      "version_id": 15,
      "size_bytes": 1048576,
      "storage_path": "1/images/logo.png/v1"
    }
  ],
  "outdated_files": [],
  "deleted_files": [
    "old_notes.txt"
  ]
}
```

### C. Chunk Upload Multipart Request (`POST /sync/upload_chunk`)
Used for large files (> 4MB). The dashboard can monitor chunk assembly status.

**Form Data Fields:**
* `version_id`: `15` (Integer as string)
* `chunk_index`: `2` (Integer as string, 0-indexed)
* `total_chunks`: `5` (Integer as string)
* `file_hash`: `"b2c3d4e5..."` (String)
* `chunk`: `[Raw Binary Data]`

---

## 3. Conflict File Naming Rules

To help the dashboard identify and highlight conflicted files visually:
* **Client local-only conflict rename**: `[filename]_conflict_[unix_timestamp][extension]` (e.g. `report_conflict_1779342410.pdf`).
* **Server-side conflict copy**: `[filename] (Conflicted copy)[extension]` (e.g. `report (Conflicted copy).pdf`).

The Dashboard UI can query the PostgreSQL database for versions marked as `is_conflict_copy = True` or filter files containing `" (Conflicted copy)"` in their name to render distinct **Warning Badges** or dedicated notification banners for the user.
