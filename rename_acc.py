from app import create_app, db
from models import Account

app = create_app()
with app.app_context():
    acc = Account.query.filter_by(code='1101').first()
    if acc:
        acc.name = "Flat A 'Service Charge Receivable A/C"
        db.session.commit()
        print("Account renamed successfully.")
