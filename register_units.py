from app import create_app
from models import db, Unit

def register_units():
    app = create_app()
    with app.app_context():
        # Blocks A to H, units 1 to 11
        blocks = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
        units_to_add = []
        for block in blocks:
            for i in range(1, 12):
                units_to_add.append(f"{block}{i}")

        print(f"Total units to register: {len(units_to_add)}")

        added_count = 0
        skipped_count = 0

        for unit_num in units_to_add:
            # Check if exists
            existing = Unit.query.filter_by(unit_number=unit_num).first()
            if existing:
                skipped_count += 1
                continue
            
            # Create new unit
            try:
                new_unit = Unit(
                    unit_number=unit_num,
                    monthly_charge=0.0,
                    status='vacant'
                )
                db.session.add(new_unit)
                added_count += 1
            except Exception as e:
                print(f"Failed to create {unit_num}: {e}")
                db.session.rollback()

        db.session.commit()

        print(f"Successfully added {added_count} units.")
        print(f"Skipped {skipped_count} units (already exist).")

if __name__ == "__main__":
    register_units()
