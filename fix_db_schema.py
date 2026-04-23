import sqlite3
import os
import json

# Load config to find db_path
config_file = 'config.json'
db_folder = 'instance'
if os.path.exists(config_file):
    with open(config_file, 'r') as f:
        config = json.load(f)
        db_folder = config.get('db_path') or 'instance'

db_path = os.path.join(db_folder, 'real_estate.db')

if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    print(f"Adding voucher_number column to journal_entry table in {db_path}...")
    cursor.execute("ALTER TABLE journal_entry ADD COLUMN voucher_number VARCHAR(50)")
    conn.commit()
    print("Column added successfully!")
except sqlite3.OperationalError as e:
    if "duplicate column name" in str(e):
        print("Column already exists.")
    else:
        print(f"Error: {e}")
finally:
    conn.close()
