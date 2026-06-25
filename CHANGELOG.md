# Changelog

All notable changes to ShadowDrive will be documented in this file.

## [0.5.0] - 2026-06-23

### Added
- `.shadowignore` support (gitignore-style patterns)
- Parallel chunk uploads (4 workers via ThreadPoolExecutor)
- On-the-wire zlib compression before encryption
- macOS installer script (`install.sh`)
- Launchd auto-start daemon
- System tray indicator (pystray)
- TransferQueue page in dashboard
- Storage quota display in file explorer
- Conflict file preview in ConflictResolution page
- SQLite WAL mode for better concurrency
- Structured logging with loguru
- pytest test suite (server + client)
- Playwright E2E tests
- GitHub Actions CI/CD pipeline
- DESIGN.md design system documentation

### Fixed
- CRITICAL: `client_modified_at` to `announced_at` in conflicts endpoint (AttributeError crash)
- VersionHistory download now includes JWT authentication token
- Removed redundant import inside `resolve_conflict` function body
- Added `suppress_path()` to `local_api.py` upload handler (prevents duplicate uploads)
- Replaced `alert()` placeholders in ConflictResolution and SystemHealth pages
- Replaced weak default SECRET_KEY with fail-fast check
- Replaced real-looking passwords in `.env.example`

### Changed
- `sync_engine.py` refactored from 772-line monolith to thin orchestrator plus modules
  - New: `uploader.py`, `downloader.py`, `heartbeat.py`, `state.py`, `database.py`
- All `print()` calls migrated to `loguru` structured logging
- Docker health checks added for PostgreSQL, MinIO, Redis

### Security
- Rate limiting verified on registration endpoint
- Timestamp clamping verified on metadata sync
- CORS restricted to localhost origins
