from app import create_app
from models import db, EventCategory, EventFinance

app = create_app()
with app.app_context():
    # This will create any missing tables (EventCategory)
    db.create_all()
    
    # Check if we need to migrate EventFinance (if category column exists but category_id doesn't)
    # SQLAlchemy might not add columns to existing tables with create_all()
    # Let's check if the column exists
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    columns = [c['name'] for c in inspector.get_columns('event_finance')]
    
    if 'category_id' not in columns:
        print("Adding category_id column to event_finance...")
        with db.engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text('ALTER TABLE event_finance ADD COLUMN category_id INTEGER REFERENCES event_category(id)'))
            conn.commit()
    
    # Seed some default categories if empty
    if not EventCategory.query.first():
        defaults = [
            ('Ticket Sales', 'income'),
            ('Sponsorship', 'income'),
            ('Catering', 'expense'),
            ('Venue Rent', 'expense'),
            ('Marketing', 'expense'),
            ('Decorations', 'expense')
        ]
        for name, ctype in defaults:
            db.session.add(EventCategory(name=name, type=ctype))
        db.session.commit()
        print("Default categories seeded.")

print("Migration complete.")
