from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Event, LedgerEntry
from datetime import datetime

events_bp = Blueprint('events', __name__)

@events_bp.route('/events')
def list_events():
    events = Event.query.all()
    return render_template('events.html', events=events)

@events_bp.route('/events/add', methods=['POST'])
def add_event():
    name = request.form.get('name')
    date_str = request.form.get('date')
    description = request.form.get('description')
    
    date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.utcnow().date()
    
    new_event = Event(name=name, date=date, description=description)
    db.session.add(new_event)
    db.session.commit()
    flash('Event created successfully', 'success')
    return redirect(url_for('events.list_events'))

@events_bp.route('/events/edit/<int:id>', methods=['GET', 'POST'])
def edit_event(id):
    event = Event.query.get_or_404(id)
    if request.method == 'POST':
        event.name = request.form.get('name')
        date_str = request.form.get('date')
        event.description = request.form.get('description')
        event.status = request.form.get('status', 'planned')
        
        if date_str:
            event.date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
        db.session.commit()
        flash('Event updated successfully', 'success')
        return redirect(url_for('events.event_detail', id=id))
    return render_template('event_form.html', event=event, action="Edit")

@events_bp.route('/events/delete/<int:id>', methods=['POST'])
def delete_event(id):
    event = Event.query.get_or_404(id)
    # Safety Check: Check for ledger entries
    if event.ledger_entries:
        flash(f"Cannot delete '{event.name}' because it has existing transactions. Delete transactions first.", "danger")
        return redirect(url_for('events.event_detail', id=id))
    
    db.session.delete(event)
    db.session.commit()
    flash('Event deleted successfully', 'success')
    return redirect(url_for('events.list_events'))

@events_bp.route('/events/<int:id>')
def event_detail(id):
    from models import Account, Unit, LedgerEntry, JournalEntry
    from sqlalchemy import func
    event = Event.query.get_or_404(id)
    # Fix: Use 3x series for new liquid accounts
    liquid_accounts = Account.query.filter(Account.type == 'asset', Account.code.like('3%'), Account.is_summary == False).all()
    units = Unit.query.filter_by(status='occupied').all()
    
    # Mapping for Event Independence
    AR_CODE = '3995' # Event Participation Receivable
    REV_CODE = '4700' # Event Revenue
    EXP_CODE = '5800' # Event Expense

    # Calculate income/expense (P&L)
    income = db.session.query(func.coalesce(func.sum(LedgerEntry.credit), 0))\
        .filter(LedgerEntry.event_id == id, LedgerEntry.account.has(Account.type == 'revenue')).scalar() or 0
    expense = db.session.query(func.coalesce(func.sum(LedgerEntry.debit), 0))\
        .filter(LedgerEntry.event_id == id, LedgerEntry.account.has(Account.type == 'expense')).scalar() or 0
        
    # Calculate Collection Stats (Receivables)
    # Collectable: Total invoiced to Event Receivable (3995) for this event
    collectable = db.session.query(func.coalesce(func.sum(LedgerEntry.debit), 0))\
        .filter(LedgerEntry.event_id == id, LedgerEntry.account.has(Account.code == AR_CODE)).scalar() or 0
    # Collected: Total payments received from residents for this event
    collected = db.session.query(func.coalesce(func.sum(LedgerEntry.credit), 0))\
        .filter(LedgerEntry.event_id == id, LedgerEntry.account.has(Account.code == AR_CODE)).scalar() or 0
        
    attendance_data = []
    for unit in units:
        if unit.resident:
            # Collectable for this resident
            res_collectable = db.session.query(func.coalesce(func.sum(LedgerEntry.debit), 0))\
                .filter(LedgerEntry.event_id == id, LedgerEntry.account.has(Account.code == AR_CODE), LedgerEntry.customer_id == unit.resident.id).scalar() or 0
            # Collected for this resident
            res_collected = db.session.query(func.coalesce(func.sum(LedgerEntry.credit), 0))\
                .filter(LedgerEntry.event_id == id, LedgerEntry.account.has(Account.code == AR_CODE), LedgerEntry.customer_id == unit.resident.id).scalar() or 0
            
            # Latest Payment Journal ID (for Receipt Download)
            payment_txn = db.session.query(JournalEntry.id)\
                .join(LedgerEntry)\
                .filter(LedgerEntry.event_id == id, LedgerEntry.account.has(Account.code == AR_CODE), LedgerEntry.customer_id == unit.resident.id, LedgerEntry.credit > 0)\
                .order_by(JournalEntry.date.desc()).first()
            payment_id = payment_txn[0] if payment_txn else None
            
            attendance_data.append({
                'unit': unit.unit_number,
                'unit_id': unit.id,
                'resident_name': unit.resident.name,
                'resident_id': unit.resident.id,
                'is_billed': res_collectable > 0,
                'collectable': res_collectable,
                'collected': res_collected,
                'balance': res_collectable - res_collected,
                'payment_id': payment_id
            })

    # For modal logic
    billed_resident_ids = [a['resident_id'] for a in attendance_data if a['is_billed']]

    return render_template('event_detail.html', 
                           event=event, 
                           liquid_accounts=liquid_accounts, 
                           units=units, 
                           income=income, 
                           expense=expense,
                           collectable=collectable,
                           collected=collected,
                           due=collectable - collected,
                           attendance_data=attendance_data,
                           billed_resident_ids=billed_resident_ids)

@events_bp.route('/events/<int:id>/bulk-bill', methods=['POST'])
def bulk_bill_residents(id):
    from models import Unit
    event = Event.query.get_or_404(id)
    unit_ids = request.form.getlist('unit_ids')
    amount = float(request.form.get('amount') or 0)
    
    if not unit_ids:
        flash('No residents selected', 'warning')
        return redirect(url_for('events.event_detail', id=id))
        
    if amount <= 0:
        flash('Amount must be greater than zero', 'danger')
        return redirect(url_for('events.event_detail', id=id))

    count = 0
    for u_id in unit_ids:
        unit = Unit.query.get(u_id)
        if unit and unit.resident:
            desc = f"Event Collection (Due) - {event.name} (Unit {unit.unit_number})"
            # Use new independent codes: Debit: Event Receivable (3995), Credit: Event Revenue (4700)
            items = [
                {'account_code': '3995', 'debit': amount, 'credit': 0, 'customer_id': unit.resident.id},
                {'account_code': '4700', 'debit': 0, 'credit': amount, 'customer_id': unit.resident.id}
            ]
            record_journal_entry(desc, items, reference=f"EVT-BILL-{id}", event_id=id)
            count += 1
            
    db.session.commit()
    flash(f"Successfully billed ৳{amount:,.2f} to {count} residents for {event.name}", 'success')
    return redirect(url_for('events.event_detail', id=id))

@events_bp.route('/events/<int:id>/pay', methods=['POST'])
def pay_resident_bill(id):
    from models import Customer
    event = Event.query.get_or_404(id)
    resident_id = int(request.form.get('resident_id'))
    amount = float(request.form.get('amount') or 0)
    # Use 3150 (Event Fund) as default liquid account
    liquid_code = request.form.get('account_code', '3150') 
    
    resident = Customer.query.get_or_404(resident_id)
    
    if amount <= 0:
        flash('Amount must be greater than zero', 'danger')
        return redirect(url_for('events.event_detail', id=id))
        
    # Record payment
    # Debit: Selected Liquid (Default 3150), Credit: Event Receivable (3995)
    desc = f"Event Payment Recv - {event.name} (Resident: {resident.name})"
    items = [
        {'account_code': liquid_code, 'debit': amount, 'credit': 0, 'customer_id': resident_id},
        {'account_code': '3995', 'debit': 0, 'credit': amount, 'customer_id': resident_id}
    ]
    record_journal_entry(desc, items, reference=f"EVT-PAY-{id}", event_id=id)
    flash(f"Payment of ৳{amount:,.2f} recorded for {resident.name}", 'success')
    return redirect(url_for('events.event_detail', id=id))

@events_bp.route('/events/<int:id>/complete', methods=['POST'])
def complete_event(id):
    event = Event.query.get_or_404(id)
    event.status = 'completed'
    db.session.commit()
    flash(f"Event '{event.name}' marked as completed", 'success')
    return redirect(url_for('events.list_events'))

from utils.accounting import record_journal_entry

@events_bp.route('/events/<int:id>/record', methods=['POST'])
def record_event_transaction(id):
    from models import Account, LedgerEntry
    from sqlalchemy import func
    event = Event.query.get_or_404(id)
    trans_type = request.form.get('type') # 'income' or 'expense'
    amount = float(request.form.get('amount') or 0)
    description = request.form.get('description')
    # Use 3150 (Event Fund) as default liquid account
    liquid_code = request.form.get('account_code', '3150') 
    
    if amount <= 0:
        flash('Amount must be greater than zero', 'danger')
        return redirect(url_for('events.event_detail', id=event.id))

    if trans_type == 'expense':
        # Check if enough collected for this event (Independent check)
        collected = db.session.query(func.coalesce(func.sum(LedgerEntry.credit), 0))\
            .filter(LedgerEntry.event_id == id, LedgerEntry.account.has(Account.code == '3995')).scalar() or 0
        total_expense = db.session.query(func.coalesce(func.sum(LedgerEntry.debit), 0))\
            .filter(LedgerEntry.event_id == id, LedgerEntry.account.has(Account.code == '5800')).scalar() or 0
        
        available = collected - total_expense
        if amount > available:
            flash(f"Warning: Expense (৳{amount:,.2f}) exceeds available collected funds (৳{available:,.2f}). Recording anyway.", 'warning')

        # Debit: Event Expense (5800), Credit: Selected Liquid (Default 3150)
        items = [
            {'account_code': '5800', 'debit': amount, 'credit': 0},
            {'account_code': liquid_code, 'debit': 0, 'credit': amount}
        ]
        desc = f"Event Expense - {event.name}: {description}"
    else:
        # Debit: Selected Liquid (Default 3150), Credit: Event Revenue (4700)
        items = [
            {'account_code': liquid_code, 'debit': amount, 'credit': 0},
            {'account_code': '4700', 'debit': 0, 'credit': amount}
        ]
        desc = f"Event Income - {event.name}: {description}"
        
    record_journal_entry(desc, items, reference=f"EVT-{event.id}", event_id=event.id)
    flash(f"{trans_type.capitalize()} of ৳{amount:,.2f} recorded for {event.name}", 'success')
    return redirect(url_for('events.event_detail', id=event.id))
