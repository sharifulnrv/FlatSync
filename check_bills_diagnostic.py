from app import create_app
from models import db, Unit, MonthlyBill, Customer
from sqlalchemy import func

app = create_app()
with app.app_context():
    print(f"Total Units: {Unit.query.count()}")
    print(f"Occupied Units: {Unit.query.filter_by(status='occupied').count()}")
    
    latest_bills = MonthlyBill.query.order_by(MonthlyBill.id.desc()).limit(20).all()
    print("\nLatest 20 Bills:")
    for b in latest_bills:
        print(f"Bill ID: {b.id}, Unit: {b.unit.unit_number}, Month: {b.month}/{b.year}, Amount: {b.amount}, Penalty: {b.penalty_to_apply}, Status: {b.status}")

    # Check for duplicates
    # Use tuple instead of named attributes for older SQLA if needed, but let's try direct
    duplicates = db.session.query(
        MonthlyBill.unit_id, MonthlyBill.month, MonthlyBill.year, func.count(MonthlyBill.id)
    ).group_by(MonthlyBill.unit_id, MonthlyBill.month, MonthlyBill.year).having(func.count(MonthlyBill.id) > 1).all()
    
    if duplicates:
        print("\nDUPLICATE BILLS FOUND:")
        for d in duplicates:
            print(f"Unit ID: {d[0]}, Month: {d[1]}/{d[2]}, Count: {d[3]}")
    else:
        print("\nNo duplicate bills found.")
