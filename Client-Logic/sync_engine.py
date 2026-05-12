import time
import sqlite3
import os

from network_client import ShadowDriveClient


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "shadow.db")

SERVER_URL = "http://127.0.0.1:8000"

SYNC_INTERVAL = 10

client = ShadowDriveClient(SERVER_URL)


def start_sync_loop():

    print("[SYNC ENGINE] Started")

    while True:

        try:

            if client.check_health():
                sync_pending_events()

            else:
                print("[NETWORK] Server unreachable")

        except Exception as e:
            print(f"[SYNC ENGINE ERROR] {e}")

        time.sleep(SYNC_INTERVAL)


def sync_pending_events():
    """Process all un-synced events from the SQLite shadow database.

    Week 4 Hardening (Scenario B — Network Drop Recovery):
        The key insight is that `is_synced` stays `0` until BOTH the
        announce AND the upload succeed. If the client drops network
        between announce and upload:
            1. The event remains `is_synced=0` in SQLite.
            2. On the next sync cycle (10 seconds later), this function
               picks it up again.
            3. The client re-announces to the server.
            4. The server's Week 4 hardened /announce detects the stale
               pending version (size_bytes=0, non-empty-file hash) and
               deletes it, creating a fresh one.
            5. The client gets upload_required=True and re-uploads.
            6. If upload succeeds, mark_synced() fires.
        This is fully automatic. No human intervention needed.
    """

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM events
        WHERE is_synced = 0
        ORDER BY id ASC
    """)

    events = cursor.fetchall()

    if not events:
        conn.close()
        return

    print(f"[SYNC] Found {len(events)} pending events")

    for event in events:

        try:

            event_id = event["id"]
            event_type = event["event_type"]
            full_path = event["file_path"]
            file_hash = event["hash"]

            relative_path = os.path.basename(full_path)

            metadata = {
                "path": relative_path,
                "hash": file_hash,
                "event": event_type
            }

            print(f"[SYNC] Processing: {relative_path}")

            response = client.announce_metadata(metadata)

            if response is None:
                # Network error during announce — skip, retry next cycle.
                print(f"[SYNC] Announce failed for {relative_path}, will retry")
                continue

            # ── Week 4 Fix: Read the JSON body instead of relying solely
            #    on status codes. The server returns a MetadataResponse
            #    with explicit fields like upload_required. ────────────────
            if response.status_code in (200, 201):
                data = response.json()

                if data.get("upload_required") and event_type != "deleted":
                    # ── Check if file still exists before trying to upload.
                    #    The user may have deleted it after the event was logged.
                    if not os.path.exists(full_path):
                        print(f"[SYNC] File vanished before upload: {relative_path}")
                        mark_synced(cursor, conn, event_id)
                        continue

                    success = client.upload_file(
                        full_path,
                        relative_path
                    )

                    if success:
                        print(f"[UPLOAD SUCCESS] {relative_path}")
                        mark_synced(cursor, conn, event_id)
                    else:
                        # Upload failed (network drop, timeout, etc.).
                        # Do NOT mark as synced. It will retry next cycle.
                        print(f"[UPLOAD FAILED] {relative_path}, will retry next cycle")
                else:
                    print(f"[SYNC] Server acknowledged (no upload needed): {data.get('status')}")
                    mark_synced(cursor, conn, event_id)
            else:
                print(f"[SYNC] Unexpected status {response.status_code} for {relative_path}")

        except Exception as e:
            print(f"[EVENT ERROR] {e}")

    conn.close()


def mark_synced(cursor, conn, event_id):

    cursor.execute("""
        UPDATE events
        SET is_synced = 1
        WHERE id = ?
    """, (event_id,))

    conn.commit()