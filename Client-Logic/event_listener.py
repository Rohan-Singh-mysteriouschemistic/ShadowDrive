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

        url = f"{config.SERVER_BASE_URL}/events/stream?token={token}"
        try:
            logger.info("[SSE] Connecting to %s", url)
            with requests.get(url, stream=True, timeout=(10, 45)) as resp:
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
