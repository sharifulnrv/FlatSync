import threading
import time
import requests
import os
from sqlalchemy import event

# Global debounce timer
_debounce_timer = None

def _send_backup(app):
    global _debounce_timer
    _debounce_timer = None
    
    with app.app_context():
        token = app.config.get('TG_BOT_TOKEN')
        chat_id = app.config.get('TG_CHAT_ID')
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        
        if not token or not chat_id or not db_uri:
            return
            
        db_path = db_uri.replace('sqlite:///', '')
        if not os.path.exists(db_path):
            return
            
        try:
            url = f"https://api.telegram.org/bot{token}/sendDocument"
            with open(db_path, 'rb') as f:
                files = {'document': (os.path.basename(db_path), f)}
                data = {
                    'chat_id': chat_id, 
                    'caption': f"FlatSync DB Backup\n{time.strftime('%Y-%m-%d %H:%M:%S')}"
                }
                requests.post(url, data=data, files=files, timeout=60)
        except Exception as e:
            print(f"TG Backup Error: {e}")

def setup_tg_backup(app, db):
    def on_db_commit(session):
        global _debounce_timer
        if _debounce_timer is not None:
            _debounce_timer.cancel()
        # Debounce for 5 seconds after a commit
        _debounce_timer = threading.Timer(5.0, _send_backup, args=[app])
        _debounce_timer.daemon = True
        _debounce_timer.start()

    # Listen to SQLAlchemy commit events
    event.listen(db.session, 'after_commit', on_db_commit)
