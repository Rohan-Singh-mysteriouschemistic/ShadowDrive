import time
import sqlite3
from datetime import datetime
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# DB Setup

DB_PATH = "file_events.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT,event_type TEXT NOT NULL,file_path TEXT NOT NULL,timestamp TEXT NOT NULL)""")
    conn.commit()
    conn.close()

def log_event(event_type, file_path):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO events (event_type, file_path, timestamp) VALUES (?, ?, ?)",(event_type, str(file_path), timestamp))
    conn.commit()
    conn.close()
    print(f"[{event_type.upper()}] {file_path} at {timestamp}")


# Event Handler
class WatcherHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            log_event("created", event.src_path)

    def on_modified(self, event):
        if not event.is_directory:
            log_event("modified", event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            log_event("deleted", event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            log_event("moved", f"{event.src_path} -> {event.dest_path}")

def main():
    init_db()

    watch_dir = Path("watch_folder")
    watch_dir.mkdir(exist_ok=True)

    print(f"Watching directory: {watch_dir.resolve()}")

    event_handler = WatcherHandler()
    observer = Observer()
    observer.schedule(event_handler, str(watch_dir), recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()


if __name__ == "__main__":
    main()
