import os
import sys
import json
import tkinter as tk
from tkinter import filedialog, ttk

def get_app_config():
    if getattr(sys, 'frozen', False):
        # Use AppData for persistent configuration in frozen state
        app_data_root = os.environ.get('APPDATA', os.path.expanduser('~'))
        application_path = os.path.join(app_data_root, 'FlatSync')
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))
    
    if not os.path.exists(application_path):
        os.makedirs(application_path, exist_ok=True)
    
    config_file = os.path.join(application_path, 'config.json')
    config = {}
    
    # Load config if exists
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            try:
                config = json.load(f)
            except json.JSONDecodeError:
                config = {}
                
    # If any required field is missing or the configured database folder is missing, re-run setup
    db_path = config.get('db_path')
    # Trigger setup if company info is missing OR if db_path is specified but invalid
    # Empty db_path is now treated as "use default instance folder"
    if not config.get('company_name') or not config.get('company_address') or (db_path and not os.path.exists(db_path)):
        root = tk.Tk()
        root.title("FlatSync Initial Setup")
        root.geometry("500x400")
        root.attributes("-topmost", True)
        
        # Center the window
        root.update_idletasks()
        width = root.winfo_width()
        height = root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (width // 2)
        y = (root.winfo_screenheight() // 2) - (height // 2)
        root.geometry(f'{width}x{height}+{x}+{y}')
        
        style = ttk.Style()
        style.configure('TLabel', font=('Segoe UI', 10))
        style.configure('TButton', font=('Segoe UI', 10, 'bold'))
        
        main_frame = ttk.Frame(root, padding="30")
        main_frame.pack(fill='both', expand=True)
        
        ttk.Label(main_frame, text="Welcome to FlatSync", font=('Segoe UI', 16, 'bold')).pack(pady=(0, 20))
        
        # Database Folder
        ttk.Label(main_frame, text="Database Save Location:").pack(fill='x', pady=(10, 0))
        folder_var = tk.StringVar(value=config.get('db_path') or os.path.abspath('instance'))
        folder_frame = ttk.Frame(main_frame)
        folder_frame.pack(fill='x', pady=5)
        ttk.Entry(folder_frame, textvariable=folder_var).pack(side='left', fill='x', expand=True, padx=(0, 5))
        def browse():
            d = filedialog.askdirectory()
            if d: folder_var.set(d)
        ttk.Button(folder_frame, text="Browse", command=browse, width=10).pack(side='right')
        
        # Company Name
        ttk.Label(main_frame, text="Company/Association Name:").pack(fill='x', pady=(10, 0))
        name_var = tk.StringVar(value=config.get('company_name', ''))
        ttk.Entry(main_frame, textvariable=name_var).pack(fill='x', pady=5)
        
        # Company Address
        ttk.Label(main_frame, text="Address:").pack(fill='x', pady=(10, 0))
        addr_var = tk.StringVar(value=config.get('company_address', ''))
        ttk.Entry(main_frame, textvariable=addr_var).pack(fill='x', pady=5)
        
        def save():
            config['db_path'] = folder_var.get()
            config['company_name'] = name_var.get()
            config['company_address'] = addr_var.get()
            # Preserve existing TG and Email tokens if present
            if 'tg_bot_token' not in config:
                config['tg_bot_token'] = _config_data.get('tg_bot_token', '')
            if 'tg_chat_id' not in config:
                config['tg_chat_id'] = _config_data.get('tg_chat_id', '')
            if 'smtp_email' not in config:
                config['smtp_email'] = _config_data.get('smtp_email', '')
            if 'smtp_password' not in config:
                config['smtp_password'] = _config_data.get('smtp_password', '')
            if 'admin_email' not in config:
                config['admin_email'] = _config_data.get('admin_email', '')
            if 'admin_username' not in config:
                config['admin_username'] = _config_data.get('admin_username', 'admin')
            if 'admin_password' not in config:
                config['admin_password'] = _config_data.get('admin_password', 'admin')
            if 'testotp' not in config:
                config['testotp'] = _config_data.get('testotp', False)
            if not os.path.exists(config['db_path']):
                os.makedirs(config['db_path'])
            
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=4)
            root.destroy()
            
        ttk.Button(main_frame, text="Save and Continue", command=save).pack(pady=30)
        
        root.mainloop()
    
    return config

# Get configuration at startup
_config_data = get_app_config()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-12345'
    
    DB_FOLDER = _config_data.get('db_path') or os.path.abspath('instance')
    DB_NAME = 'real_estate.db'
    
    COMPANY_NAME = _config_data.get('company_name', 'Assurance Sultan Legacy Flat Owners Association')
    COMPANY_ADDRESS = _config_data.get('company_address', '23/4, Katasur, Ser-E Bangla Road, Mohammadpur, Dhaka')
    
    TG_BOT_TOKEN = _config_data.get('tg_bot_token', '')
    TG_CHAT_ID = _config_data.get('tg_chat_id', '')
    
    SMTP_EMAIL = _config_data.get('smtp_email', '')
    SMTP_PASSWORD = _config_data.get('smtp_password', '')
    ADMIN_EMAIL = _config_data.get('admin_email', '')
    
    ADMIN_USERNAME = _config_data.get('admin_username', 'admin')
    ADMIN_PASSWORD = _config_data.get('admin_password', 'admin')
    
    TESTOTP = _config_data.get('testotp', False)
    
    # Ensure the directory exists
    if not os.path.exists(DB_FOLDER):
        os.makedirs(DB_FOLDER, exist_ok=True)
    
    # Using absolute path for cross-platform reliability
    # SQLite on Windows: sqlite:///C:/path/to/db (3 slashes + drive letter)
    _db_path = os.path.join(DB_FOLDER, DB_NAME).replace('\\', '/')
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{_db_path}"
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SCHEDULER_API_ENABLED = True
    WEBVIEW_ENABLED = False
    DEBUG = False
    ENV = 'production'
