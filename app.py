from flask import Flask
from config import Config
from models import db, User, Account
from flask_migrate import Migrate
from flask_login import LoginManager
import traceback
import logging
from datetime import datetime

migrate = Migrate()
login = LoginManager()

import sys
import os

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def create_app(config_class=Config):
    app = Flask(__name__, 
                template_folder=resource_path('templates'),
                static_folder=resource_path('static'))
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    app.config['PROPAGATE_EXCEPTIONS'] = True

    with app.app_context():
        # Create tables if they don't exist
        db.create_all()
        # Seed COA
        seed_coa()
        # Seed Admin
        seed_admin()

    @app.errorhandler(500)
    def handle_500(e):
        with open("error.log", "a") as f:
            f.write(f"\n--- ERROR AT {datetime.now()} ---\n")
            traceback.print_exc(file=f)
        return "Internal Server Error (Logged)", 500

    @app.context_processor
    def inject_global_data():
        from datetime import datetime
        return {
            'today_date': datetime.now().strftime('%d %b %Y'),
            'company_name': app.config.get('COMPANY_NAME'),
            'company_address': app.config.get('COMPANY_ADDRESS')
        }

    # Register Blueprints
    from routes.main import main_bp
    from routes.units import units_bp
    
    # Custom Jinja Filters
    @app.template_filter('words')
    def to_words_filter(n):
        try:
            from num2words import num2words
            return num2words(float(n), lang='en').capitalize() + " Taka Only"
        except:
            return str(n)
    from routes.accounting import accounting_bp
    from routes.assets import assets_bp
    from routes.maintenance import maintenance_bp
    from routes.reports import reports_bp
    from routes.events import events_bp
    from routes.parties import parties_bp
    from routes.service_charges import service_charges_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(units_bp)
    app.register_blueprint(accounting_bp)
    app.register_blueprint(assets_bp)
    app.register_blueprint(maintenance_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(events_bp)
    app.register_blueprint(parties_bp)
    app.register_blueprint(service_charges_bp)

    @app.context_processor
    def utility_processor():
        def sum_debits(journal):
            return sum(e.debit for e in journal.entries if e.debit > 0)
        def sum_credits(journal):
            return sum(e.credit for e in journal.entries if e.credit > 0)
        return dict(sum_debits=sum_debits, sum_credits=sum_credits)

    return app

def seed_coa():
    if Account.query.first():
        return
    
    # Comprehensive 70-Account COA (Core Categories)
    coa_data = [
        # ASSETS (3XXX)
        ('3000', 'ASSETS', 'asset', True),
        ('3010', 'Fixed Assets (Buildings & Equipment)', 'asset', False),
        ('3100', 'Cash & Bank', 'asset', True),
        ('3110', 'Cash in Hand', 'asset', False),
        ('3120', 'Operating Bank A/C', 'asset', False),
        ('3130', 'Petty Cash', 'asset', False),
        ('3150', 'Event Fund', 'asset', False),
        ('3930', 'Service Charge Receivable', 'asset', False),
        ('3995', 'Event Participation Receivable', 'asset', False),
        
        # LIABILITIES (2XXX)
        ('2000', 'LIABILITIES', 'liability', True),
        ('2100', 'Accounts Payable', 'liability', False),
        ('2200', 'Accrued Expenses', 'liability', False),
        ('2300', 'Resident Security Deposits', 'liability', False),
        
        # EQUITY (1XXX)
        ('1000', 'EQUITY', 'equity', True),
        ('1100', 'Accumulated Fund (Retained Earnings)', 'equity', False),
        
        # REVENUE (4XXX)
        ('4000', 'REVENUE', 'revenue', True),
        ('4100', 'Service Charge Income', 'revenue', False),
        ('4110', 'Late Penalty Income', 'revenue', False),
        ('4120', 'Service Charge Arrears (Previous Years)', 'revenue', False),
        ('4300', 'Facility Rental Income', 'revenue', False),
        ('4400', 'Utility Recovery Income', 'revenue', False),
        ('4700', 'Event Revenue', 'revenue', False),
        ('4900', 'Other Income', 'revenue', False),
        
        # EXPENSES (5XXX)
        ('5000', 'EXPENSES', 'expense', True),
        ('5100', 'Management & Salaries', 'expense', False),
        ('5200', 'Electricity Expense (Common Areas)', 'expense', False),
        ('5210', 'Water & Sewerage Expense', 'expense', False),
        ('5220', 'Gas & Fuel Expense', 'expense', False),
        ('5300', 'Security & Guard Services', 'expense', False),
        ('5400', 'Cleaning & Janitorial Services', 'expense', False),
        ('5500', 'Generator Operating & Fuel', 'expense', False),
        ('5600', 'Lift/Elevator Maintenance', 'expense', False),
        ('5700', 'Printing & Stationery', 'expense', False),
        ('5710', 'Legal & Audit Fees', 'expense', False),
        ('5800', 'Event Expense', 'expense', False),
        ('5900', 'Depreciation Expense', 'expense', False),
    ]
    for code, name, acc_type, summary in coa_data:
        acc = Account(code=code, name=name, type=acc_type, is_summary=summary)
        db.session.add(acc)
    db.session.commit()

def seed_admin():
    from werkzeug.security import generate_password_hash
    if User.query.first():
        return
    admin = User(
        username='admin',
        password_hash=generate_password_hash('admin'),
        role='admin'
    )
    db.session.add(admin)
    db.session.commit()

@login.user_loader
def load_user(id):
    return User.query.get(int(id))

import threading
import sys
import os
from pathlib import Path

class JSAPI:
    def download_url(self, url):
        # Handle relative URLs from flask
        if not url.startswith('http'):
            url = f'http://127.0.0.1:5999{url}'
        webbrowser.open(url)

def run_server(app):
    app.run(port=5999, debug=app.config.get('DEBUG', False), use_reloader=False)

def wait_for_server(window):
    """ Poll the server until it's ready, then switch from loading screen to app """
    import time
    import http.client
    
    while True:
        try:
            conn = http.client.HTTPConnection("127.0.0.1", 5999)
            conn.request("GET", "/")
            response = conn.getresponse()
            if response.status == 200:
                print("Server is ready, transitioning UI...")
                window.load_url('http://127.0.0.1:5999')
                break
        except Exception:
            time.sleep(0.5)
        finally:
            try: conn.close()
            except: pass

if __name__ == '__main__':
    app = create_app()
    api = JSAPI()
    
    if app.config.get('WEBVIEW_ENABLED', False):
        import webview
        import webbrowser
        
        # Start Flask in a background thread
        server_thread = threading.Thread(target=run_server, args=(app,))
        server_thread.daemon = True
        server_thread.start()
        
        # Launch Desktop Window with Loading Screen first
        loading_path = resource_path('templates/loading.html')
        # Use URI for local file loading in EXE
        loading_screen = Path(loading_path).as_uri()
        
        window = webview.create_window('FlatSync', 
                                      url=loading_screen,
                                      js_api=api,
                                      width=1400, height=900, 
                                      resizable=True)
        
        # Start transition thread
        threading.Thread(target=wait_for_server, args=(window,), daemon=True).start()
        
        webview.start()
    else:
        # Standard Browser Mode: Run Flask directly
        is_debug = app.config.get('DEBUG', False)
        print(f"WEBVIEW_ENABLED is false. Running in Browser Mode at http://127.0.0.1:5999 (Debug: {is_debug})")
        app.run(port=5999, debug=is_debug)
