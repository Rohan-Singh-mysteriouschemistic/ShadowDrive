import sys
sys.path.insert(0, r"c:\Users\ASUS\ShadowDrive\Server-Logic\server")
from sqlalchemy import create_engine, text
from app.database import SQLALCHEMY_DATABASE_URL
from app.models import Base

engine = create_engine(SQLALCHEMY_DATABASE_URL)
with engine.connect() as conn:
    trans = conn.begin()
    tables = [table.name for table in Base.metadata.sorted_tables]
    print(f"Clearing tables: {tables}")
    for table in tables:
        print(f"Truncating {table}...")
        conn.execute(text(f'TRUNCATE TABLE "{table}" CASCADE;'))
    trans.commit()
print("Backend PostgreSQL tables cleared successfully.")

import sqlite3
import os
local_db = r"c:\Users\ASUS\ShadowDrive\shadow.db"
if os.path.exists(local_db):
    print("Clearing local SQLite client database...")
    c_conn = sqlite3.connect(local_db)
    cursor = c_conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    for row in cursor.fetchall():
        table_name = row[0]
        if table_name != 'sqlite_sequence':
            cursor.execute(f"DELETE FROM {table_name};")
    c_conn.commit()
    c_conn.close()
    print("Local client database cleared successfully.")
