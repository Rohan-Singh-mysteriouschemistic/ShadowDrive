# ShadowDrive

> Self-hosted, zero-knowledge encrypted file synchronization.

[![CI](https://github.com/YOUR_USERNAME/ShadowDrive/actions/workflows/ci.yml/badge.svg)]()
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)]()
[![React](https://img.shields.io/badge/react-19-61dafb)]()

ShadowDrive is a self-hosted file synchronization system where the server never sees your data. All encryption happens client-side using AES-256-GCM before files leave your machine.

## Features

- **Zero-Knowledge Encryption** -- AES-256-GCM client-side encryption, server stores only ciphertext
- **Real-Time Sync** -- Watchdog filesystem monitoring with SSE push notifications
- **Delta Sync** -- Only changed chunks are transferred, not entire files
- **Parallel Uploads** -- 4-worker chunked upload pipeline via ThreadPoolExecutor
- **Version History** -- Every file change is tracked and versioned for recovery
- **Conflict Resolution** -- Automatic conflict detection with manual resolution UI
- **Web Dashboard** -- React/TypeScript UI for monitoring and management
- **Multi-Device** -- Register unlimited devices under a single account
- **Self-Hosted** -- Deploy on your own infrastructure with Docker Compose

## Architecture

The system consists of three components:

- **Server** -- FastAPI/Python application providing REST endpoints, authentication, metadata management, and job queuing. Backed by PostgreSQL for metadata, MinIO for object storage, and Redis for job queues and SSE events.
- **Client** -- Python sync engine that watches files, encrypts chunks, and synchronizes with the server. Runs as a daemon with a system tray indicator.
- **UI** -- React/TypeScript single-page application served by Vite, providing the web dashboard for file management, version history, and conflict resolution.

## Quick Start

1. **Start the server:**
   ```bash
   cd Server-Logic/server
   cp .env.example .env
   docker-compose up -d
   ```

2. **Install the client:**
   ```bash
   bash install.sh
   ```

3. **Login:**
   ```bash
   shadowdrive login
   ```

4. **Open the dashboard:**
   Navigate to `http://127.0.0.1:5173`

## Configuration

The client is configured via `shadowdrive.yaml` in the project root. Key settings include the server URL, watch directory paths, chunk size for delta sync, encryption parameters, and device registration tokens. See the example file for all available options.

## Development

Run tests for each component:

```bash
# Server tests
cd Server-Logic/server && python -m pytest tests/ -v

# Client tests
cd Client-Logic && python -m pytest tests/ -v

# UI tests
cd shadowdrive-ui && npm test
```

## Security Model

ShadowDrive uses client-side AES-256-GCM encryption with a key derived from your passphrase and email using PBKDF2 with 480,000 iterations. Files are encrypted before leaving the device, and the server stores only ciphertext. Even if the server infrastructure is compromised, your files remain confidential. The server never possesses the decryption keys.

## License

See the [LICENSE](LICENSE) file for details.
