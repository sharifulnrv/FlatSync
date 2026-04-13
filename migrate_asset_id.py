import sqlite3
import os
import json
import sys

def get_db_path():
    if getattr(sys, 'frozen', False):
        app_data_root = os.environ.get('APPDATA', os.path.expanduser('~'))
        application_path = os.path.join(app_data_root, 'FlatSync')
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))
    
    config_file = os.path.join(application_path, 'config.json')
    db_folder = os.path.abspath('instance')
    db_name = 'real_estate.db'
    
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            try:
                config = json.load(f)
                db_folder = config.get('db_path', db_folder)
            except:
                pass
                
    return os.path.join(db_folder, db_name)

db_path = get_db_path()
print(f"Connecting to database at: {db_path}")

if not os.path.exists(db_path):
    print("Database file not found at expected location.")
    sys.exit(1)

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Checking if 'asset_id' already exists in 'ledger_entry'...")
    cursor.execute("PRAGMA table_info(ledger_entry)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'asset_id' in columns:
        print("Column 'asset_id' already exists.")
    else:
        print("Adding 'asset_id' column to 'ledger_entry' table...")
        cursor.execute("ALTER TABLE ledger_entry ADD COLUMN asset_id INTEGER REFERENCES asset(id)")
        conn.commit()
        print("Column added successfully.")
        
    conn.close()
except Exception as e:
    print(f"Error during migration: {e}")
    sys.exit(1)
