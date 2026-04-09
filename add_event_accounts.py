from app import create_app, db
from models import Account

def add_event_accounts():
    app = create_app()
    with app.app_context():
        # Dedicated Event Accounts
        event_accounts = [
            ('3150', 'Event Fund (Cash)', 'asset', False),
            ('3995', 'Event Participation Receivable', 'asset', False),
            ('4700', 'Event Revenue', 'revenue', False),
            ('5800', 'Event Expense', 'expense', False),
        ]

        print("Adding dedicated Event Accounts...")
        for code, name, acc_type, is_summary in event_accounts:
            existing = Account.query.filter_by(code=code).first()
            if not existing:
                new_acc = Account(code=code, name=name, type=acc_type, is_summary=is_summary)
                db.session.add(new_acc)
                print(f"  Added: {code} - {name}")
            else:
                print(f"  Existing: {code} - {name}")
        
        db.session.commit()
        print("Event Accounts setup COMPLETED.")

if __name__ == "__main__":
    add_event_accounts()
