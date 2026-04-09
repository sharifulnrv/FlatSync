import sqlite3
import os
import json

# Use absolute path for safety
config_path = r"g:\TEst\LitonSir\config.json"

if os.path.exists(config_path):
    with open(config_path, "r") as f:
        data = json.load(f)
        db_folder = data.get("db_path")
        db_path = os.path.join(db_folder, "real_estate.db")
        
        if os.path.exists(db_path):
            print(f"Connecting to database at: {db_path}")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Check columns for journal_entry
            cursor.execute("PRAGMA table_info(journal_entry)")
            cols = [c[1] for c in cursor.fetchall()]
            
            if 'event_id' not in cols:
                print("Adding 'event_id' column to 'journal_entry' table...")
                cursor.execute("ALTER TABLE journal_entry ADD COLUMN event_id INTEGER REFERENCES event(id)")
                conn.commit()
                print("Column added successfully.")
            else:
                print("'event_id' already exists in 'journal_entry'.")
                
            conn.close()
        else:
            print(f"Database file not found at: {db_path}")
else:
    print("config.json not found.")
