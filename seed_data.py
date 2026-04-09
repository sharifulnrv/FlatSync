from app import create_app
from models import db, Unit, Customer, Account, JournalEntry, LedgerEntry, Asset, AssetCategory, MaintenanceTicket
from utils.accounting import record_journal_entry
from datetime import datetime, timedelta
import random

def seed_dummy_data():
    app = create_app()
    with app.app_context():
        # Clean the database for a fresh start (Optional)
        # db.drop_all()
        # db.create_all()

        # 1. Accounts are already seeded by create_app()
        cash = Account.query.filter_by(code='1001').first()
        ar = Account.query.filter_by(code='1101').first()
        rev = Account.query.filter_by(code='4001').first()
        penalty = Account.query.filter_by(code='4002').first()

        # 2. Add Units
        if not Unit.query.first():
            units = []
            for building in ['A', 'B', 'C']:
                for floor in range(1, 11):
                    for flat in [1, 2, 3]:
                        u_num = f"{building}-{floor}{flat:02d}"
                        u = Unit(unit_number=u_num, monthly_charge=random.choice([5000, 5500, 6000]))
                        units.append(u)
            db.session.add_all(units)
            db.session.commit()
            print(f"Added {len(units)} units.")

        # 3. Add Customers
        if not Customer.query.first():
            names = ["Rahim Ahmed", "Karim Islam", "Sultana Begum", "Arif Hossain", "Mehedi Hasan", "Nusrat Jahan"]
            available_units = Unit.query.all()
            for i, name in enumerate(names):
                customer = Customer(name=name, phone=f"01700{100000+i}", address="Dhaka, Bangladesh")
                db.session.add(customer)
                db.session.flush()
                
                # Assign to a unit
                unit = available_units[i]
                unit.resident = customer
                unit.status = 'occupied'
            db.session.commit()
            print("Added 6 customers and assigned them to units.")

        # 4. Generate Some Transactions
        if not JournalEntry.query.first():
            occupied_units = Unit.query.filter_by(status='occupied').all()
            
            # Record Service Charge for last month (March 2024)
            march_date = datetime(2024, 3, 1)
            for unit in occupied_units:
                items = [
                    {'account_code': '1101', 'debit': unit.monthly_charge, 'credit': 0, 'customer_id': unit.resident.id},
                    {'account_code': '4001', 'debit': 0, 'credit': unit.monthly_charge, 'customer_id': unit.resident.id}
                ]
                record_journal_entry(f"Service Charge - Mar 2024", items, reference=f"UNIT-{unit.unit_number}", date=march_date)

            # Record some payments
            for unit in occupied_units[:3]: # Only half paid
                items = [
                    {'account_code': '1001', 'debit': unit.monthly_charge, 'credit': 0, 'customer_id': unit.resident.id},
                    {'account_code': '1101', 'debit': 0, 'credit': unit.monthly_charge, 'customer_id': unit.resident.id}
                ]
                record_journal_entry("Payment Received - Cash", items, reference="PAY-MAR", date=datetime(2024, 3, 5))
            
            print("Generated initial service charges and some payments.")

        # 5. Add Assets
        if not AssetCategory.query.first():
            cat1 = AssetCategory(name="Furniture")
            cat2 = AssetCategory(name="Electrical")
            db.session.add_all([cat1, cat2])
            db.session.commit()
            
            a1 = Asset(name="Security Desk", category_id=cat1.id, purchase_cost=15000, purchase_date=datetime(2023, 1, 10).date())
            a2 = Asset(name="Lobby Generator", category_id=cat2.id, purchase_cost=450000, purchase_date=datetime(2023, 5, 20).date())
            db.session.add_all([a1, a2])
            db.session.commit()
            print("Added asset categories and items.")

        # 6. Add Maintenance Ticket
        if not MaintenanceTicket.query.first():
            unit = Unit.query.filter_by(status='occupied').first()
            ticket = MaintenanceTicket(unit_id=unit.id, description="AC not working in common area near this unit.")
            db.session.add(ticket)
            db.session.commit()
            print("Added a maintenance ticket.")

if __name__ == "__main__":
    seed_dummy_data()
    print("Database seeding complete!")
