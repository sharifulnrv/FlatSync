from app import create_app
from models import db, Account

app = create_app()

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

with app.app_context():
    print("Updating Chart of Accounts...")
    added_count = 0
    updated_count = 0
    
    for code, name, acc_type, summary in coa_data:
        existing = Account.query.filter_by(code=code).first()
        if existing:
            if existing.name != name:
                print(f"Updating name for {code}: {existing.name} -> {name}")
                existing.name = name
                updated_count += 1
        else:
            print(f"Adding new account: {code} - {name}")
            new_acc = Account(code=code, name=name, type=acc_type, is_summary=summary)
            db.session.add(new_acc)
            added_count += 1
            
    db.session.commit()
    print(f"Finished! Added {added_count} accounts, Updated {updated_count} accounts.")
