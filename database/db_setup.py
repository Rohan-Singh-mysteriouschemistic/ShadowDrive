"""
db_setup.py — One-time database initializer.

Run this once before anything else:
    python database/db_setup.py

After that, diff_engine.py calls ensure_db() automatically
at startup, so you don't need to run this again unless you
want to reset the DB manually.
"""

import sys
import os

# Make sure Client-Logic is on the path so we can import diff_engine
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Client-Logic"))

from diff_engine import ensure_db, DB_PATH

if __name__ == "__main__":
    ensure_db()
    print(f"Database initialized at: {DB_PATH}")
    print("Tables created: files, events")