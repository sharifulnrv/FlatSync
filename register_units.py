import sqlite3
import os

db_path = r"C:\Litonsir\real_estate.db"

def register_units():
    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Blocks A to H, units 1 to 11
    blocks = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    units_to_add = []
    for block in blocks:
        for i in range(1, 12):
            units_to_add.append(f"{block}{i}")

    print(f"Total units to register: {len(units_to_add)}")

    added_count = 0
    skipped_count = 0

    for unit_num in units_to_add:
        # Check if exists
        cursor.execute("SELECT id FROM unit WHERE unit_number = ?", (unit_num,))
        if cursor.fetchone():
            skipped_count += 1
            continue
        
        # Insert
        try:
            cursor.execute("INSERT INTO unit (unit_number, monthly_charge, status) VALUES (?, ?, ?)", (unit_num, 0.0, 'vacant'))
            added_count += 1
        except Exception as e:
            print(f"Failed to insert {unit_num}: {e}")

    conn.commit()
    conn.close()

    print(f"Successfully added {added_count} units.")
    print(f"Skipped {skipped_count} units (already exist).")

if __name__ == "__main__":
    register_units()
