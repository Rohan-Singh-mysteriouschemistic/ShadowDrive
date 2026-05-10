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
                continue

            # SERVER NEEDS FILE
            if response.status_code == 201:

                if event_type == "deleted":
                    print(f"[SYNC] Deleted file acknowledged")
                    mark_synced(cursor, conn, event_id)
                    continue

                success = client.upload_file(
                    full_path,
                    relative_path
                )

                if success:
                    print(f"[UPLOAD SUCCESS] {relative_path}")
                    mark_synced(cursor, conn, event_id)

            # SERVER ALREADY HAS FILE
            elif response.status_code == 200:

                print(f"[SYNC] Already synced")

                mark_synced(cursor, conn, event_id)

            else:
                print(
                    f"[SERVER ERROR] "
                    f"Status={response.status_code}"
                )

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