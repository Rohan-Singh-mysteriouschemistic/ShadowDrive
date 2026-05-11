# ShadowDrive++ — Product Brief

> **Team:** Rohan & Shabd
> A full, production-grade, MIT/Stanford-level distributed systems project roadmap.

---

## 1. Project Overview

**ShadowDrive++** is a minimal Dropbox-like distributed file sync system.

### Core System Features

- File watching
- Hashing + diff detection
- Metadata database
- Client-server sync protocol
- Storage backend via S3/MinIO
- Conflict resolution
- Background workers
- Version history dashboard

Rohan owns everything that happens on a user's machine. Shabd owns everything that happens on the server. Together, they build a professional distributed system.

---

## 2. Strict Division of Labor

### 🧭 Rohan — Client Agent + Sync Logic Owner (50%)

**Owns everything on the user's local machine.**

**Builds:**

- File watching system
- Hashing + diff detection
- Local metadata shadow DB
- Upload worker
- Download worker
- Client-side conflict detection
- Client state reconciliation

**Learning Focus:**

- OS file systems
- Hashing algorithms
- Concurrency (threads, async)
- State machines
- Networking basics

---

### 🟦 Shabd — Backend + DBMS + Storage Owner (50%)

**Owns everything on the server.**

**Builds:**

- PostgreSQL schema
- FastAPI/gRPC backend
- Metadata processing
- File chunk upload/download endpoints
- MinIO storage layer
- Server-side conflict resolution
- Redis background workers
- Dashboard UI

**Learning Focus:**

- DBMS internals
- Storage systems
- API design
- Distributed metadata management
- Background job processing

---

## 3. Technology Stack & Resources

### Rohan's Stack & Resources

| Domain | Technology / Resource |
|---|---|
| File Systems & Watchers | Python `watchdog` docs |
| File Systems & Watchers | DigitalOcean: inotify explained |
| File Systems & Watchers | Linux journey: filesystem basics |
| Hashing & Diff Algorithms | Python `hashlib` docs |
| Hashing & Diff Algorithms | Rsync algorithm: "Rsync Rolling Checksum" article |
| Hashing & Diff Algorithms | Karp–Rabin rolling hash (cp-algorithms) |

### Shabd's Stack & Resources

| Domain | Technology / Resource |
|---|---|
| PostgreSQL + Schema Design | postgresqltutorial.com |
| PostgreSQL + Schema Design | UseTheIndexLuke.com (indexing) |
| PostgreSQL + Schema Design | SQLAlchemy docs |
| FastAPI Backend | FastAPI documentation |
| FastAPI Backend | freeCodeCamp FastAPI video |
| MinIO Storage | MinIO official documentation |
| MinIO Storage | Python boto3 MinIO videos |

### Shared Resources (Both)

| Domain | Technology / Resource |
|---|---|
| gRPC (optional) | gRPC docs |
| gRPC (optional) | freeCodeCamp gRPC Python tutorial |
| Redis Queues (optional) | Redis Queue (RQ) docs |
| System Design Basics | ByteByteGo: free YT content |

---

## 4. Phased Deliverables — The 12-Week Plan

> Each week includes: 1) What to learn, 2) Who learns it, 3) What to implement immediately, 4) Deliverables.
> No ambiguity, no ifs or buts — do the steps in order.

---

### ⭐ PHASE 1 — Foundations + First Implementations (Weeks 1–4)

---

#### Week 1 — File Watching + Filesystem Foundations

| Owner | Activity |
|---|---|
| **Rohan** | *Learns:* OS-level file events · Watchdog library · File types, inodes, timestamps |
| **Rohan** | *Implements:* A folder watcher script · Logs every create/modify/delete · Stores events in a local JSON/SQLite file |
| **Shabd** | *Learns:* Basics of DBMS schema thinking · SQL relationships |
| **Shabd** | *Implements:* Initial ER diagram draft |

**Deliverable (Rohan):** `watcher.py` + log output proving events captured

---

#### Week 2 — Hashing + Diffing + Local State

| Owner | Activity |
|---|---|
| **Rohan** | *Learns:* SHA256, MD5 · Chunking strategy (4 MB) · Rolling hash (optional) |
| **Rohan** | *Implements:* Compute hash for each file · Compare new vs old hash · Detect: new/update/delete · Maintain local shadow state in SQLite |
| **Shabd** | *Learns:* PostgreSQL basics · Transactions, isolation |
| **Shabd** | *Implements:* DB schema: `files`, `versions`, `devices`, `file_device_map` |

**Deliverable (Rohan):** `diff_engine.py` that outputs detected changes

**Deliverable (Shabd):** SQL schema file + migrations

---

#### Week 3 — Networking + API Foundations

| Owner | Activity |
|---|---|
| **Rohan** | *Learns:* HTTP basics · REST semantics · Sending file chunks via HTTP |
| **Rohan** | *Implements:* Small client script to POST a file to server |
| **Shabd** | *Learns:* FastAPI routing · Pydantic models · Handling file uploads |
| **Shabd** | *Implements:* `/register_device` · `/upload_metadata` · `/get_metadata` |

**Deliverables:**

- Working server skeleton
- Client talks to server successfully

---

#### Week 4 — Sync Protocol (Done Together)

| Owner | Activity |
|---|---|
| **Both** | *Learn:* Sync cycles · Idempotency · Version numbering · Conflict rules |
| **Both** | *Implement:* A written protocol document containing: metadata JSON format · API contract · version rules · chunk rules · frequency of sync |

**Deliverable:** `ShadowDrive++ Sync Protocol v1.0.pdf`

---

### ⭐ PHASE 2 — Full Feature Development (Weeks 5–9)

---

#### Week 5 — Upload Pipeline

| Owner | Activity |
|---|---|
| **Rohan** | *Learns:* Threading basics · Background workers |
| **Rohan** | *Implements:* Upload worker thread · Upload file chunks sequentially · Update metadata accordingly |
| **Shabd** | *Learns:* MinIO bucket operations |
| **Shabd** | *Implements:* `/upload_chunk` · Chunk storage mapping |

**Integration Deliverable:** Rohan's agent uploads a file → metadata & chunks appear in server.

---

#### Week 6 — Download Pipeline

| Owner | Activity |
|---|---|
| **Rohan** | *Implements:* Compare local metadata with server's · Download missing chunks · Reconstruct files locally |
| **Shabd** | *Implements:* `/download_chunk` · Metadata diff endpoint |

**Deliverable:** Full local → server → local roundtrip works.

---

#### Week 7 — Conflict Resolution

| Owner | Activity |
|---|---|
| **Rohan** | *Learns:* State machines for sync · Local conflict markers |
| **Rohan** | *Implements:* Client detects simultaneous edits |
| **Shabd** | *Learns:* LWW · Vector clocks (optional) |
| **Shabd** | *Implements:* Server-side conflict resolution rules |

**Deliverable:** Conflicting edits produce conflict files.

---

#### Week 8 — Reliability (Queues + Retries)

| Owner | Activity |
|---|---|
| **Rohan** | *Learns:* Retry strategies · Exponential backoff |
| **Rohan** | *Implements:* Retry queue for failed uploads |
| **Shabd** | *Learns:* Redis Queue |
| **Shabd** | *Implements:* Background worker to reprocess failed requests |

**Deliverable:** System tolerates network failures.

---

#### Week 9 — Dashboard

| Owner | Activity |
|---|---|
| **Shabd** | *Implements:* Streamlit/React UI showing: file list · version list · conflict warnings · device activity |
| **Rohan** | *Supports:* Provides metadata formats for UI |

**Deliverable:** A visual interface of ShadowDrive++.

---

### ⭐ PHASE 3 — Finalization (Weeks 10–12)

---

#### Week 10 — Dockerization

| Owner | Activity |
|---|---|
| **Both** | *Learn:* Dockerfile basics · Docker Compose |
| **Both** | *Implement:* Containers for: Backend · PostgreSQL · MinIO · Redis |

**Deliverable:** `docker-compose up` launches full system.

---

#### Week 11 — End-to-End Testing + Load Testing

| Owner | Activity |
|---|---|
| **Both** | *Implement:* Multi-device sync tests · Conflict scenario tests · Network failure simulations |

**Deliverable:** Test report documenting all scenarios.

---

#### Week 12 — Documentation + Demo

| Owner | Activity |
|---|---|
| **Both** | *Implement:* README with diagrams · Final architecture diagram · Sequence diagrams · Demo video (2–3 min) |

---

## Final Integration Strategy

| Milestone | Purpose |
|---|---|
| **Week 4** → Protocol freeze | Ensures both codebases stay compatible. |
| **Weeks 5–9** → API-driven integration | Each new feature is tested end-to-end. |
| **Week 10** → Docker integration | Everything runs together. |
| **Week 11** → Final debugging | Fix inconsistencies, metadata mismatches, race conditions. |
| **Week 12** → Publish | Show polished project with confidence. |

---

## Final Outcome

After 12 weeks:

- **Rohan** becomes strong in OS, concurrency, hashing, sync logic.
- **Shabd** becomes strong in DBMS, backend, storage, system design.
- **Together:** a real distributed system is built.
- Perfect alignment with next semester's ADDA, DBMS, TOC.
- Resume gains a FAANG-level systems project.
