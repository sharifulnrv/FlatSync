import os
import sys
import json
from app import create_app
from models import db
from app import seed_coa, seed_admin

app = create_app()

def reset():
    with app.app_context():
        print("!!! WARNING: Purging all data in the database !!!")
        
        # Drop all tables safely
        db.drop_all()
        print("Tables dropped.")
        
        # Recreate tables with new schema
        db.create_all()
        print("Schema recreated.")
        
        # Re-seed the expanded COA and Admin
        seed_coa()
        print("Chart of Accounts seeded.")
        
        seed_admin()
        print("Admin user created (username: admin, password: admin).")
        
        print("\nDatabase Reset COMPLETE. You can now start the app fresh.")

if __name__ == "__main__":
    force = "-f" in sys.argv or "--force" in sys.argv
    if force:
        reset()
    else:
        confirm = input("Are you absolutely sure you want to delete ALL data? (y/n): ")
        if confirm.lower() == 'y':
            reset()
        else:
            print("Reset cancelled.")
