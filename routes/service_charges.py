from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Unit, Customer, Account, JournalEntry, LedgerEntry, MonthlyBill
from utils.accounting import record_journal_entry
from datetime import datetime, date
from sqlalchemy import func

service_charges_bp = Blueprint('service_charges', __name__)

@service_charges_bp.route('/service-charges')
def dashboard():
    from sqlalchemy import case, and_
    
    # Summary of months/years
    summary = db.session.query(
        MonthlyBill.year, 
        MonthlyBill.month,
        func.count(MonthlyBill.id).label('total_bills'),
        func.coalesce(func.sum(MonthlyBill.amount), 0).label('total_amount'),
        # Accrued Penalty = (penalty_to_apply for overdue unpaid) + (penalty_amount for paid)
        (func.coalesce(func.sum(
            case(
                (and_(MonthlyBill.status == 'unpaid', date.today() > MonthlyBill.due_date), MonthlyBill.penalty_to_apply),
                else_=0
            )
        ), 0) + func.coalesce(func.sum(MonthlyBill.penalty_amount), 0)).label('total_penalty'),
        func.count(MonthlyBill.id).filter(MonthlyBill.status == 'paid').label('paid_count')
    ).group_by(MonthlyBill.year, MonthlyBill.month).order_by(MonthlyBill.year.desc(), MonthlyBill.month.desc()).all()
    
    occupied_count = Unit.query.filter_by(status='occupied').count()
    
    return render_template('service_charges/dashboard.html', 
                           summary=summary, 
                           date=date, 
                           now_month=datetime.now().month, 
                           now_year=datetime.now().year,
                           occupied_count=occupied_count)

@service_charges_bp.route('/service-charges/<int:year>/<int:month>')
def view_month(year, month):
    bills = MonthlyBill.query.filter_by(year=year, month=month).all()
    month_name = datetime(year, month, 1).strftime('%B')
    liquid_accounts = Account.query.filter(Account.type == 'asset', Account.code.like('31%'), Account.is_summary == False).all()
    return render_template('service_charges/month_details.html', bills=bills, year=year, month=month, month_name=month_name, date=date, liquid_accounts=liquid_accounts)

@service_charges_bp.route('/service-charges/generate', methods=['POST'])
def generate_bills():
    try:
        month = int(request.form.get('month'))
        year = int(request.form.get('year'))
        standard_amount = float(request.form.get('amount') or 0)
        due_date_str = request.form.get('due_date')
        penalty_to_apply = float(request.form.get('penalty_amount') or 0)
        daily_penalty_rate = float(request.form.get('daily_penalty_amount') or 0)
        next_month_daily_rate = float(request.form.get('next_month_penalty_amount') or 0)
        
        due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
    except (ValueError, TypeError) as e:
        flash(f"Invalid input values: {str(e)}", "danger")
        return redirect(url_for('service_charges.dashboard'))
    
    # Avoid duplicates
    existing = MonthlyBill.query.filter_by(month=month, year=year).first()
    if existing:
        flash(f"Bills for {month}/{year} already exist!", "warning")
        return redirect(url_for('service_charges.dashboard'))
    
    occupied_units = Unit.query.filter_by(status='occupied').all()
    if not occupied_units:
        flash("No occupied units found to generate bills. Please add residents first!", "danger")
        return redirect(url_for('service_charges.dashboard'))
    
    count = 0
    for unit in occupied_units:
        # Use standard amount if provided, otherwise fallback to unit specific charge
        final_amount = standard_amount if standard_amount > 0 else unit.monthly_charge
        
        bill = MonthlyBill(
            unit_id=unit.id,
            customer_id=unit.resident.id,
            month=month,
            year=year,
            amount=final_amount,
            penalty_to_apply=penalty_to_apply,
            daily_penalty_rate=daily_penalty_rate,
            next_month_daily_rate=next_month_daily_rate,
            due_date=due_date,
            status='unpaid'
        )
        db.session.add(bill)
        db.session.flush() # Get ID
        
        # Record Journal Entry (Accrual: AR vs Revenue)
        desc = f"Service Charge - {date(year, month, 1).strftime('%B %Y')}"
        items = [
            {'account_code': '3930', 'debit': final_amount, 'credit': 0, 'customer_id': unit.resident.id},
            {'account_code': '4100', 'debit': 0, 'credit': final_amount, 'customer_id': unit.resident.id}
        ]
        record_journal_entry(desc, items, reference=f"UNIT-{unit.unit_number}", date=datetime(year, month, 1), monthly_bill_id=bill.id)
        count += 1
        
    db.session.commit()
    flash(f"Successfully generated {count} bills for {date(year, month, 1).strftime('%B %Y')}", "success")
    return redirect(url_for('service_charges.dashboard'))

@service_charges_bp.route('/service-charges/pay/<int:bill_id>', methods=['POST'])
def record_payment(bill_id):
    bill = MonthlyBill.query.get_or_404(bill_id)
    payment_date_str = request.form.get('payment_date')
    payment_date = datetime.strptime(payment_date_str, '%Y-%m-%d').date() if payment_date_str else date.today()
    
    try:
        amount_paid = float(request.form.get('amount_paid') or 0)
    except ValueError:
        flash("Invalid payment amount.", "danger")
        return redirect(url_for('service_charges.view_month', year=bill.year, month=bill.month))

    if bill.status == 'paid':
        flash("This bill is already fully paid.", "warning")
        return redirect(url_for('service_charges.view_month', year=bill.year, month=bill.month))

    # Record Penalty if after the deadline AND not already applied
    penalty_now = 0
    if payment_date > bill.due_date:
        # Calculate penalty for THIS specific payment date
        full_penalty_on_payment_date = bill.calculate_penalty(payment_date)
        # We only record the difference if some penalty was already paid/recorded
        penalty_now = full_penalty_on_payment_date - bill.penalty_amount
        
        if penalty_now > 0:
            bill.penalty_amount += penalty_now
            
            # Record Penalty Entry in Ledger
            penalty_desc = f"Late Penalty - {bill.unit.unit_number} ({date(bill.year, bill.month, 1).strftime('%B %Y')})"
            penalty_items = [
                {'account_code': '3930', 'debit': penalty_now, 'credit': 0, 'customer_id': bill.customer_id},
                {'account_code': '4110', 'debit': 0, 'credit': penalty_now, 'customer_id': bill.customer_id}
            ]
            record_journal_entry(penalty_desc, penalty_items, reference="LATE-FEE", date=datetime.now(), monthly_bill_id=bill.id)

    # Record Payment Entry
    debit_acc_id = request.form.get('debit_account_id')
    debit_acc = Account.query.get(debit_acc_id) if debit_acc_id else None
    debit_code = debit_acc.code if debit_acc else '3100'

    payment_desc = f"Payment Received - {bill.unit.unit_number} ({date(bill.year, bill.month, 1).strftime('%B %Y')})"
    payment_items = [
        {'account_code': debit_code, 'debit': amount_paid, 'credit': 0, 'customer_id': bill.customer_id},
        {'account_code': '3930', 'debit': 0, 'credit': amount_paid, 'customer_id': bill.customer_id}
    ]
    record_journal_entry(payment_desc, payment_items, reference=f"PAY-{debit_code}", date=datetime.combine(payment_date, datetime.min.time()), monthly_bill_id=bill.id)
    
    bill.paid_amount += amount_paid
    bill.paid_date = payment_date
    
    if bill.balance_due <= 0:
        bill.status = 'paid'
    else:
        bill.status = 'partial'
        
    db.session.commit()
    
    flash(f"Payment of ৳{amount_paid:,.2f} recorded for Unit {bill.unit.unit_number}. Status: {bill.status.title()}", "success")
    return redirect(url_for('service_charges.view_month', year=bill.year, month=bill.month))

@service_charges_bp.route('/service-charges/bill/<int:bill_id>')
def bill_details(bill_id):
    bill = MonthlyBill.query.get_or_404(bill_id)
    return render_template('service_charges/bill_details.html', bill=bill, date=date)
