from app import create_app, db
from models import Account, LedgerEntry

def cleanup_legacy_coa():
    app = create_app()
    with app.app_context():
        # Mapping: Legacy Code -> New Code
        mapping = {
            '1001': '3100', # Cash -> Cash A/C
            '1101': '3930', # AR Residents -> Service Charge Receivable
            '4001': '4100', # Service Charge Rev -> Service Charge
            '4002': '4200', # Penalty -> Service Charge Late Payment
            '4005': '4300', # Event Income -> Community Hall Rent (Closest)
            '5001': '5500', # Payroll -> Gardeners Salary (Closest)
            '5003': '5300', # Event Expense -> Security and Others Expense
        }

        print("Starting COA History Merge...")
        
        for old_code, new_code in mapping.items():
            print(f"Processing Mapping: {old_code} -> {new_code}")
            old_acc = Account.query.filter(Account.code == old_code, Account.name.like("%_OLD%")).first()
            new_acc = Account.query.filter_by(code=new_code).first()

            if not old_acc:
                print(f"  [SKIP] Legacy account {old_code} not found.")
                continue
            if not new_acc:
                print(f"  [ERROR] Target account {new_code} NOT FOUND. Cannot merge {old_acc.name}.")
                continue

            print(f"  [MERGE] {old_acc.name} (ID: {old_acc.id}) -> {new_acc.name} (ID: {new_acc.id})")
            
            # Update entries
            entries = LedgerEntry.query.filter_by(account_id=old_acc.id).all()
            for entry in entries:
                entry.account_id = new_acc.id
            
            print(f"  [STATUS] Moved {len(entries)} transactions.")
            
            # Delete old (flush first to ensure entries are moved in DB view)
            db.session.flush()
            db.session.delete(old_acc)
            print(f"  [DELETE] Legacy account {old_acc.code} removed.")

        print("Finalizing orphans with no history...")
        others = Account.query.filter(Account.name.like("%_OLD%")).all()
        for other in others:
            has_history = LedgerEntry.query.filter_by(account_id=other.id).first()
            if not has_history:
                print(f"  [DELETE] Orphan: {other.code} ({other.name})")
                db.session.delete(other)
            else:
                print(f"  [KEEP] Legacy account {other.code} ({other.name}) has unmapped history.")

        db.session.commit()
        print("COA History Merge COMPLETED.")

if __name__ == "__main__":
    cleanup_legacy_coa()
