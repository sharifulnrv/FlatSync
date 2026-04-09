import os
import json
import tkinter as tk
from tkinter import filedialog

def get_database_path():
    config_file = 'config.json'
    
    # Load config if exists
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
            if 'db_path' in config:
                return config['db_path']
    
    # Otherwise ask for path
    root = tk.Tk()
    root.withdraw() # Hide main window
    root.attributes("-topmost", True) # Ensure it's on top
    
    db_folder = filedialog.askdirectory(title="Select Folder to Save FlatSync Database")
    root.destroy()
    
    if not db_folder:
        # Fallback to current instance folder if cancelled
        db_folder = os.path.abspath('instance')
    
    # Create directory if doesn't exist
    if not os.path.exists(db_folder):
        os.makedirs(db_folder)
        
    # Save to config
    with open(config_file, 'w') as f:
        json.dump({'db_path': db_folder}, f)
        
    return db_folder

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-12345'
    
    DB_FOLDER = get_database_path()
    DB_NAME = 'real_estate.db'
    
    # Using absolute path for cross-platform reliability
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(DB_FOLDER, DB_NAME)}"
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SCHEDULER_API_ENABLED = True
