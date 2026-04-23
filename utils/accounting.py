from models import db, JournalEntry, LedgerEntry, Account, Unit, Customer
from datetime import datetime

def record_journal_entry(description, items, reference=None, date=None, monthly_bill_id=None, event_id=None, voucher_number=None):
    """
    items: list of dictionaries: 
    [{'account_code': '1001', 'debit': 100, 'credit': 0, 'customer_id': 1}]
    """
    if date is None:
        date = datetime.utcnow()
    
    # Check if debits equal credits
    total_debit = sum(i['debit'] for i in items)
    total_credit = sum(i['credit'] for i in items)
    
    if abs(total_debit - total_credit) > 0.001:
        raise ValueError("Debits must equal credits")
    
    journal = JournalEntry(date=date, description=description, reference=reference, 
                          monthly_bill_id=monthly_bill_id, event_id=event_id, 
                          voucher_number=voucher_number)
    db.session.add(journal)
    db.session.flush() # Get journal.id
    
    for item in items:
        account = Account.query.filter_by(code=item['account_code']).first()
        if not account:
            raise ValueError(f"Account code {item['account_code']} not found")
            
        ledger = LedgerEntry(
            journal_id=journal.id,
            account_id=account.id,
            debit=item['debit'],
            credit=item['credit'],
            customer_id=item.get('customer_id'),
            party_id=item.get('party_id'),
            event_id=item.get('event_id', event_id),
            asset_id=item.get('asset_id')
        )
        db.session.add(ledger)
    
    db.session.commit()
    return journal

def generate_monthly_service_charges():
    """
    Automated job to generate service charges for all occupied units.
    Debit: Service Charge Receivable (3930)
    Credit: Service Charge Revenue (4100)
    """
    units = Unit.query.filter_by(status='occupied').all()
    today = datetime.utcnow()
    description = f"Service Charge - {today.strftime('%B %Y')}"
    
    for unit in units:
        if unit.customer_id and unit.monthly_charge > 0:
            items = [
                {
                    'account_code': '3930', # Service Charge Receivable
                    'debit': unit.monthly_charge,
                    'credit': 0,
                    'customer_id': unit.customer_id
                },
                {
                    'account_code': '4100', # Service Charge Revenue
                    'debit': 0,
                    'credit': unit.monthly_charge,
                    'customer_id': unit.customer_id
                }
            ]
            record_journal_entry(description, items, reference=f"UNIT-{unit.unit_number}")

def apply_late_fees(penalty_amount=500):
    """
    Logic to apply penalties if payment is not made by the 10th.
    Debit: Service Charge Receivable (3930)
    Credit: Service Charge Late Payment (4200)
    """
    # This would typically run on the 11th
    customers = Customer.query.all()
    for customer in customers:
        # Check current unpaid balance for service charges
        # (This is a simplified check for the demonstration)
        # Real logic would check if specific monthly invoice is paid
        pass
