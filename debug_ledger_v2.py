from app import create_app
from models import db, LedgerEntry, Account
app = create_app()
with app.app_context():
    entries = LedgerEntry.query.all()
    print(f"Total entries: {len(entries)}")
    with_event = [e for e in entries if e.event_id is not None]
    print(f"Entries with event_id: {len(with_event)}")
    for e in with_event:
        print(f"  Entry ID {e.id}: Event {e.event_id}, Account {e.account.name if e.account else 'None'}, Dr {e.debit}, Cr {e.credit}")
    
    # Check specifically for event 1
    event_1_entries = LedgerEntry.query.filter_by(event_id=1).all()
    print(f"\nEvent 1 entries: {len(event_1_entries)}")
    for e in event_1_entries:
        print(f"  - Account: {e.account.name}, Balance effect: {e.debit - e.credit}")
