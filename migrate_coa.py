import sqlite3
import os

def migrate_coa():
    # 1. Direct SQLite column addition to avoid ORM errors (if not already done)
    db_path = 'C:/Litonsir/real_estate.db' 
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Add is_summary if missing
        try:
            cursor.execute("ALTER TABLE account ADD COLUMN is_summary BOOLEAN DEFAULT 0")
        except: pass
        conn.commit()
    except Exception as e:
        print(f"Direct update info: {e}")

    from app import create_app, db
    from models import Account

    app = create_app()
    with app.app_context():
        # New COA Structure from Image
        coa_data = [
            # 1000 Equity
            ('1000', 'Equity', 'equity', True),
            ('1100', 'Retain Earnings', 'equity', False),

            # 2000 Liabilities
            ('2000', 'Liabilities', 'liability', True),
            ('2100', 'Accounts Payable- Electricity', 'liability', False),
            ('2200', 'Accounts Payable- Wasa & Water', 'liability', False),
            ('2300', 'Accounts Payable- Security & Other Service', 'liability', False),
            ('2400', 'Accounts Payable- Lift Servicing', 'liability', False),
            ('2500', 'Accounts Payable- Camera Servicing', 'liability', False),
            ('2550', 'Salary Payable', 'liability', False),
            ('2560', 'Accounts Payable- Generator & Motor Servicing', 'liability', False),
            ('2600', 'Accounts Payable', 'liability', False),
            ('2900', 'Bank Loan (Short-Term)', 'liability', False),

            # 3000 Assets
            ('3000', 'Assets', 'asset', True),
            ('3100', 'Cash A/C', 'asset', False),
            ('3200', 'IFIC Bank', 'asset', False),
            ('3300', 'Dutch Bangla Bank', 'asset', False),
            ('3400', 'Pubali Bank Ltd', 'asset', False),
            ('3500', 'Furniture Purchase', 'asset', False),
            ('3600', 'Fan Purchase', 'asset', False),
            ('3700', 'Camera Purchase', 'asset', False),
            ('3800', 'Monitor/Smart TV Purchase', 'asset', False),
            ('3900', 'Lift Purchase', 'asset', False),
            ('3910', 'Water Pooling Motor Purchase', 'asset', False),
            ('3920', 'Generator Purchase', 'asset', False),
            ('3930', 'Service Charge Receivable', 'asset', False),
            ('3940', 'Service Charge Late Payment Receivable', 'asset', False),
            ('3950', 'Community Hall Rent Receivable', 'asset', False),
            ('3960', 'Gym Subscription Receivable', 'asset', False),
            ('3970', 'Gym Members Fee Receivable', 'asset', False),
            ('3980', 'General Members Fee Receivable', 'asset', False),
            ('3990', 'Others Income Receivable', 'asset', False),

            # 4000 Revenue
            ('4000', 'Revenue', 'revenue', True),
            ('4100', 'Service Charge', 'revenue', False),
            ('4200', 'Service Charge Late Payment', 'revenue', False),
            ('4300', 'Community Hall Rent Revenue', 'revenue', False),
            ('4400', 'Gym Subscription Revenue', 'revenue', False),
            ('4500', 'Gym Members Fee Revenue', 'revenue', False),
            ('4600', 'General Members Fee and Subscription Revenue', 'revenue', False),
            ('4700', 'Loss / Gain A/C-/RE (Rev)', 'revenue', False),

            # 5000 Building Maintenance Expense
            ('5000', 'Building Maintenance Expense', 'expense', True),
            ('5100', 'Electrical Expense', 'expense', False),
            ('5200', 'Plumbers Expense', 'expense', False),
            ('5300', 'Security and Others Expense', 'expense', False),
            ('5400', 'Mosque Expense- Salary', 'expense', False),
            ('5500', 'Gardeners Salary Expense', 'expense', False),
            ('5600', 'Electricity Expense', 'expense', False),
            ('5700', 'Wasa & Water Expense', 'expense', False),

            # 6000 Repair & Maintenance Expense
            ('6000', 'Repair & Maintenance Expense', 'expense', True),
            ('6100', 'Lift Repair & Maintenance Expense', 'expense', False),
            ('6200', 'Lift Servicing Expense', 'expense', False),
            ('6300', 'Water Motor Repair & Maintenance Expense', 'expense', False),
            ('6400', 'Generator Servicing Expense', 'expense', False),
            ('6500', 'Generator Fuel Expense', 'expense', False),
            ('6600', 'Deep Tubwell Repair & Maintenance Expense', 'expense', False),
            ('6700', 'Power station Repair & Maintenance Expense', 'expense', False),
            ('6800', 'Camera Repair & Maintenance Expense', 'expense', False),
            ('6900', 'Camera Servicing Expense', 'expense', False),
            ('6910', 'Intercom Repair & Maintenance Expense', 'expense', False),
            ('6920', 'Furniture Repair & Maintenance Expense', 'expense', False),
            ('6930', 'Fan Repair & Maintenance Expense', 'expense', False),
            ('6940', 'Gym Items Repair & Maintenance Expense', 'expense', False),
            ('6950', 'Tiles Repair & Maintenance Expense', 'expense', False),
            ('6960', 'Solar Systems Repair & Maintenance Expense', 'expense', False),
            ('6970', 'Computer & Printer Repair & Maintenance Expense', 'expense', False),

            # 7000 Office Expense
            ('7000', 'Office Expense', 'expense', True),
            ('7100', 'Stationary Purchase', 'expense', False),
            ('7200', 'Printer Cartidge Purchase', 'expense', False),
            ('7300', 'Papers Purchase', 'expense', False),
            ('7400', 'Conveyance Expense', 'expense', False),
            ('7500', 'Meeting Expense', 'expense', False),
            ('7600', 'Festival Expense', 'expense', False),
            ('7700', 'Bank Charge', 'expense', False),
            ('7800', 'Loss / Gain A/C-/RE', 'expense', False),
        ]

        # Process Migration
        all_accounts = Account.query.all()
        for acc in all_accounts:
            acc.name = acc.name + "_OLD"
        db.session.commit()
        print("Suffixed existing accounts with _OLD to avoid collisions.")

        existing_accounts_by_code = {a.code: a for a in Account.query.all()}
        
        for code, name, acc_type, summary in coa_data:
            if code in existing_accounts_by_code:
                acc = existing_accounts_by_code[code]
                acc.name = name
                acc.type = acc_type
                acc.is_summary = summary
                print(f"Updated: {code} - {name}")
            else:
                acc = Account(code=code, name=name, type=acc_type, is_summary=summary)
                db.session.add(acc)
                print(f"Added: {code} - {name}")
        
        db.session.commit()
        
        # Cleanup: Remove _OLD accounts that weren't updated if they have no transactions
        # (Optional, but let's keep it safe for now and just print them)
        remaining_old = Account.query.filter(Account.name.like("%_OLD")).all()
        for old_acc in remaining_old:
            print(f"DEBUG: Found orphaned account: {old_acc.code} - {old_acc.name}")
            # delete if no ledger entries
            from models import LedgerEntry
            if not LedgerEntry.query.filter_by(account_id=old_acc.id).first():
                db.session.delete(old_acc)
                print(f"Deleted orphaned account: {old_acc.code}")

        db.session.commit()
        print("Migration COMPLETED with user-provided COA.")

if __name__ == "__main__":
    migrate_coa()
