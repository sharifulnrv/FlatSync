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
            
            # Check columns for monthly_bill
            cursor.execute("PRAGMA table_info(monthly_bill)")
            cols = [c[1] for c in cursor.fetchall()]
            
            if 'paid_amount' not in cols:
                print("Adding 'paid_amount' column to 'monthly_bill' table...")
                cursor.execute("ALTER TABLE monthly_bill ADD COLUMN paid_amount FLOAT DEFAULT 0.0")
                conn.commit()
                print("Column added successfully.")
            else:
                print("'paid_amount' already exists.")
                
            conn.close()
        else:
            print(f"Database file not found at: {db_path}")
else:
    print("config.json not found.")
