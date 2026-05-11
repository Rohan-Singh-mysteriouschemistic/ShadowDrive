# Codebase Audit & Next Steps

## Task 1: The Codebase Audit (Where are we?)
I have compared the local repository (`ShadowDrive++`) against Phase 1 (Weeks 1, 2, and 3) of the `product-brief.md`.

**Complete:**
- `models.py` + `alembic/versions/30da9aebda0c_creating_the_5_tables.py` (DB schema: `files`, `versions`, `devices`, `file_device_map` — Phase 1, Week 2)
- `main.py` + `database.py` (FastAPI backend skeleton and DB connection — Phase 1, Week 3 Foundations)

**Partially Complete:**
- `routers/user.py` + `main.py` (FastAPI routing and Pydantic models are set up, but only for `/users`. The required sync endpoints are missing — Phase 1, Week 3)
- ER Diagram Draft (Shabd learned DBMS schema and implemented `models.py`, but there is no standalone ER diagram file — Phase 1, Week 1)

**Missing Entirely:**
- `watcher.py` (File watcher script — Phase 1, Week 1)
- `diff_engine.py` (Compute hash, compare hash, SQLite shadow state — Phase 1, Week 2)
- Small client script to POST a file to server (Phase 1, Week 3)
- `/register_device` endpoint (Phase 1, Week 3)
- `/upload_metadata` endpoint (Phase 1, Week 3)
- `/get_metadata` endpoint (Phase 1, Week 3)

> [!IMPORTANT]
> **Definitive State:** We definitively stopped working at **Phase 1, Week 3** for the backend (Shabd) and **Phase 1, Week 1** for the client (Rohan). Shabd has the database schema and a basic FastAPI app running, but the core Week 3 endpoints are unwritten. Rohan has not committed any client code.

---

## Task 2: The Re-Onboarding (What did I write?)

### Shabd's Backend Logic (Existing)
- **Architecture**: A standard FastAPI application with SQLAlchemy ORM and Alembic for migrations.
- **Database Structures (`models.py`)**: You built 5 tables.
  - `users`: Stores `username`, `email`, and `password_hash`.
  - `devices`: Links to `users` (`user_id`). Stores `device_name`, `is_online`, and `last_seen_at`. Unique constraint on `(user_id, device_name)`.
  - `files`: Links to `users`. Stores `file_path` and `is_deleted` flag. Unique constraint on `(user_id, file_path)`.
  - `versions`: Links to `files` (`file_id`). Stores `version_num`, `hash`, `size_bytes`, and `storage_path` (MinIO path).
  - `file_device_map`: A many-to-many mapping table linking `devices`, `files`, and `versions`, including a `synced_at` timestamp.
- **API Logic (`routers/user.py`)**: You have a `POST /users` endpoint (with password hashing) and a `GET /users/{id}` endpoint.

### Rohan's Client Logic (Existing)
- **Client Systems**: Currently, Rohan's codebase is completely empty. There is no `watcher.py` or `diff_engine.py` in the repository. The client-server communication systems have not been initiated yet.

---

## Task 3: The Immediate Next Step (What next?)

To complete **Phase 1, Week 3**, Shabd needs to build the three missing endpoints. Since endpoints build on each other logically, the **very next feature** to build is the `/register_device` endpoint. A client must register its device before it can sync any file metadata.

### Technical Logic & Architectural Steps for `/register_device`

1. **Schemas (`schemas.py`)**:
   - Create a `DeviceCreate` Pydantic model expecting `user_id` (int) and `device_name` (str).
   - Create a `DeviceOut` Pydantic model to return `id`, `device_name`, `is_online`, and `last_seen_at`.

2. **Routing (`routers/device.py`)**:
   - Create a new router module for device-related endpoints to keep the code organized (mirroring what you did with `routers/user.py`).
   - Register this router in `main.py`.

3. **Core Logic (`POST /devices/register`)**:
   - **Lookup**: Query the `devices` table to see if a device with the provided `user_id` and `device_name` already exists.
   - **Update (If Exists)**: If it exists, update its `is_online` status to `True` and refresh `last_seen_at` to `func.now()`.
   - **Insert (If Not Exists)**: If it does not exist, create a new `Device` record.
   - **Commit & Return**: Commit the transaction and return the device record (specifically the `device_id`, which Rohan's client will need to cache locally and use for all subsequent `/upload_metadata` calls).

## User Review Required
Please review the audit and the proposed logic for `/register_device`. Let me know if you approve of this next step, or if you'd like to adjust the logic before we write the code!
