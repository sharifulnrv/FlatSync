from app import create_app
from models import db, Account, LedgerEntry
from sqlalchemy import func

app = create_app()
with app.app_context():
    print("--- ACCOUNTS ---")
    accs = Account.query.all()
    for a in accs:
        d = db.session.query(func.sum(LedgerEntry.debit)).filter_by(account_id=a.id).scalar() or 0
        c = db.session.query(func.sum(LedgerEntry.credit)).filter_by(account_id=a.id).scalar() or 0
        if d != 0 or c != 0:
            print(f"ID: {a.id}, Code: {a.code}, Name: {a.name}, Type: {a.type}, Summary: {a.is_summary}, Net: {d-c}")

    print("\n--- DASHBOARD EXPENSE CALC ---")
    expense_accs = Account.query.filter_by(type='expense').all()
    expense_ids = [acc.id for acc in expense_accs]
    total_cost = db.session.query(func.sum(LedgerEntry.debit - LedgerEntry.credit))\
                .filter(LedgerEntry.account_id.in_(expense_ids), LedgerEntry.event_id == None).scalar() or 0
    print(f"Dashboard Total Cost (All expense accounts): {total_cost}")

    print("\n--- REPORT EXPENSE CALC ---")
    report_accs = Account.query.filter_by(type='expense', is_summary=False).all()
    report_ids = [acc.id for acc in report_accs]
    report_total = db.session.query(func.sum(LedgerEntry.debit - LedgerEntry.credit))\
                .filter(LedgerEntry.account_id.in_(report_ids), LedgerEntry.event_id == None).scalar() or 0
    print(f"Report Total Cost (Non-summary expense accounts): {report_total}")
