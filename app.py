from flask import Flask
from config import Config
from models import db, User, Account
from flask_migrate import Migrate
from flask_login import LoginManager

migrate = Migrate()
login = LoginManager()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)

    with app.app_context():
        # Create tables if they don't exist
        db.create_all()
        # Seed COA
        seed_coa()
        # Seed Admin
        seed_admin()

    @app.context_processor
    def inject_now():
        from datetime import datetime
        return {'today_date': datetime.now().strftime('%d %b %Y')}

    # Register Blueprints
    from routes.main import main_bp
    from routes.units import units_bp
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

    return app

def seed_coa():
    if Account.query.first():
        return
    
    # Comprehensive 70-Account COA (Core Categories)
    coa_data = [
        ('3000', 'ASSETS', 'asset', True),
        ('3100', 'Cash & Bank', 'asset', True),
        ('3110', 'Cash in Hand', 'asset', False),
        ('3120', 'Operating Bank A/C', 'asset', False),
        ('3150', 'Event Fund', 'asset', False),
        ('3930', 'Service Charge Receivable', 'asset', False),
        ('3995', 'Event Participation Receivable', 'asset', False),
        
        ('2000', 'LIABILITIES', 'liability', True),
        ('2100', 'Accounts Payable', 'liability', False),
        
        ('1000', 'EQUITY', 'equity', True),
        ('1100', 'Accumulated Fund', 'equity', False),
        
        ('4000', 'REVENUE', 'revenue', True),
        ('4100', 'Service Charge Income', 'revenue', False),
        ('4110', 'Late Penalty Income', 'revenue', False),
        ('4700', 'Event Revenue', 'revenue', False),
        
        ('5000', 'EXPENSES', 'expense', True),
        ('5100', 'Management & Operating', 'expense', True),
        ('5800', 'Event Expense', 'expense', False),
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

import webview
import threading
import webbrowser

class JSAPI:
    def download_url(self, url):
        # Handle relative URLs from flask
        if not url.startswith('http'):
            url = f'http://127.0.0.1:5999{url}'
        webbrowser.open(url)

def run_server(app):
    app.run(port=5999, debug=False, use_reloader=False)

if __name__ == '__main__':
    app = create_app()
    api = JSAPI()
    
    # Start Flask in a background thread
    server_thread = threading.Thread(target=run_server, args=(app,))
    server_thread.daemon = True
    server_thread.start()
    
    # Launch Desktop Window
    webview.create_window('FlatSync', 'http://127.0.0.1:5999', 
                          js_api=api,
                          width=1400, height=900, 
                          resizable=True)
    webview.start()
