import os
from app import create_app
from models import db, MonthlyBill
from datetime import date

def check_bills():
    app = create_app()
    with app.app_context():
        # Check first 5 bills for 2025/7
        sample = MonthlyBill.query.filter_by(year=2025, month=7).limit(5).all()
        print(f"Today's Date: {date.today()}")
        print("\nDetailed Sample Bills (2025/7):")
        print("ID | Amount | Mode | Pen Apply | Pen Amt | Due Date | Current Pen | Status")
        print("-" * 90)
        for b in sample:
            print(f"{b.id:2} | {b.amount:6.0f} | {b.penalty_mode:5} | {b.penalty_to_apply:9.0f} | {b.penalty_amount:7.2f} | {b.due_date} | {b.current_penalty:11.2f} | {b.status}")

if __name__ == "__main__":
    check_bills()
