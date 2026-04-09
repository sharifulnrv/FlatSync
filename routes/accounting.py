from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from models import db, Account, JournalEntry, LedgerEntry, Customer, Unit, MonthlyBill
from utils.accounting import record_journal_entry
from datetime import datetime
from sqlalchemy import func

accounting_bp = Blueprint('accounting', __name__)

@accounting_bp.route('/accounting')
def dashboard():
    from models import Party
    all_accounts = Account.query.order_by(Account.code).all()
    suppliers = Party.query.all()
    
    major_categories = {
        '1': 'Assets',
        '2': 'Liabilities',
        '3': 'Equity',
        '4': 'Revenue',
        '5': 'Expenses'
    }

    grouped = {}
    for acc in all_accounts:
        cat_key = major_categories.get(acc.code[0], 'Other')
        if cat_key not in grouped:
            grouped[cat_key] = {}
        
        # Use first 2 digits as subcategory key
        sub_key = acc.code[:2]
        if sub_key not in grouped[cat_key]:
            grouped[cat_key][sub_key] = {'header': None, 'accounts': []}
        
        if acc.is_summary and acc.code.endswith('00'):
            grouped[cat_key][sub_key]['header'] = acc
        else:
            grouped[cat_key][sub_key]['accounts'].append(acc)

    recent_journals = JournalEntry.query.order_by(JournalEntry.id.desc()).limit(10).all()
    return render_template('accounting_dashboard.html', 
                           grouped_accounts=grouped, 
                           suppliers=suppliers,
                           journals=recent_journals)

@accounting_bp.route('/accounting/billing')
def manual_billing():
    units = Unit.query.filter_by(status='occupied').all()
    # Find last service charge date for each unit to show status
    billing_data = []
    ar_acc = Account.query.filter_by(code='3930').first() # Service Charge Receivable
    for u in units:
        last_charge = None
        if u.resident and ar_acc:
            last_charge = db.session.query(func.max(JournalEntry.date))\
                .join(LedgerEntry, JournalEntry.id == LedgerEntry.journal_id)\
                .filter(LedgerEntry.customer_id == u.resident.id, LedgerEntry.account_id == ar_acc.id, JournalEntry.description.like('%Service Charge%'))\
                .scalar()
        billing_data.append({'unit': u, 'last_charge': last_charge})
        
    return render_template('billing.html', 
                           billing_data=billing_data, 
                           current_year=datetime.now().year,
                           now_month=datetime.now().strftime('%B'))

@accounting_bp.route('/accounting/generate-charges', methods=['POST'])
def generate_charges():
    unit_ids = request.form.getlist('unit_ids')
    billing_month = request.form.get('month')
    billing_year = request.form.get('year')
    due_date_str = request.form.get('due_date')
    
    if not unit_ids:
        flash('No units selected', 'warning')
        return redirect(url_for('accounting.manual_billing'))
        
    due_date = datetime.strptime(due_date_str, '%Y-%m-%d') if due_date_str else datetime.now()
    
    count = 0
    for u_id in unit_ids:
        unit = Unit.query.get(u_id)
        if unit and unit.resident:
            # Create Journal Entry
            description = f"Service Charge - {billing_month} {billing_year}"
            items = [
                {'account_code': '3930', 'debit': unit.monthly_charge, 'credit': 0, 'customer_id': unit.resident.id}, # Service Charge Receivable
                {'account_code': '4100', 'debit': 0, 'credit': unit.monthly_charge, 'customer_id': unit.resident.id} # Service Charge Revenue
            ]
            record_journal_entry(description, items, reference=f"UNIT-{unit.unit_number}", date=datetime.now())
            count += 1
            
    db.session.commit()
    flash(f'Successfully generated charges for {count} units.', 'success')
    return redirect(url_for('accounting.manual_billing'))

@accounting_bp.route('/accounting/ledger/<int:account_id>')
def view_ledger(account_id):
    account = Account.query.get_or_404(account_id)
    entries = LedgerEntry.query.filter_by(account_id=account.id).order_by(LedgerEntry.id.desc()).all()
    
    # Calculate running balance
    # (Simple approach for display)
    total_debit = db.session.query(func.sum(LedgerEntry.debit)).filter_by(account_id=account.id).scalar() or 0
    total_credit = db.session.query(func.sum(LedgerEntry.credit)).filter_by(account_id=account.id).scalar() or 0
    balance = total_debit - total_credit
    
    return render_template('ledger.html', account=account, entries=entries, balance=balance)

@accounting_bp.route('/accounting/record-transaction', methods=['GET', 'POST'])
def record_transaction():
    if request.method == 'POST':
        amount = float(request.form.get('amount') or 0)
        description = request.form.get('description')
        dr_code = request.form.get('dr_account')
        cr_code = request.form.get('cr_account')
        customer_id = request.form.get('customer_id') or None
        party_id = request.form.get('party_id') or None
        event_id = request.form.get('event_id', type=int) or None
        month = request.form.get('month')
        year = request.form.get('year')
        date_str = request.form.get('date')
        
        txn_date = None
        if date_str:
            try:
                txn_date = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                pass
        
        if month and year:
            description = f"{description} ({month} {year})"
        
        if amount <= 0 or not dr_code or not cr_code:
            flash('Invalid transaction details. Description, Accounts, and Amount are required.', 'error')
            return redirect(url_for('accounting.record_transaction'))
            
        items = [
            {'account_code': dr_code, 'debit': amount, 'credit': 0, 'customer_id': customer_id, 'party_id': party_id, 'event_id': event_id},
            {'account_code': cr_code, 'debit': 0, 'credit': amount, 'customer_id': customer_id, 'party_id': party_id, 'event_id': event_id}
        ]
        record_journal_entry(description, items, reference="GENERAL", date=txn_date)
        flash('Transaction recorded successfully', 'success')
        return redirect(url_for('accounting.dashboard'))
        
    accounts = Account.query.all()
    customers = Customer.query.all()
    from models import Event, Party
    events = Event.query.order_by(Event.date.desc()).all()
    parties = Party.query.all()
    # Pass pre-selection from query params
    selected_event_id = request.args.get('event_id', type=int)
    selected_party_id = request.args.get('party_id', type=int)
    selected_customer_id = request.args.get('customer_id', type=int)
    
    months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
    current_year = datetime.now().year
    today_date_iso = datetime.now().strftime('%Y-%m-%d')
    
    return render_template('record_transaction.html', 
                           accounts=accounts, 
                           customers=customers, 
                           parties=parties,
                           events=events,
                           months=months,
                           current_year=current_year,
                           selected_event_id=selected_event_id,
                           selected_party_id=selected_party_id,
                           selected_customer_id=selected_customer_id,
                           today_date_iso=today_date_iso)

@accounting_bp.route('/accounting/ledger/<int:account_id>/export')
def export_ledger(account_id):
    import openpyxl
    from io import BytesIO
    account = Account.query.get_or_404(account_id)
    entries = LedgerEntry.query.filter_by(account_id=account.id).order_by(LedgerEntry.id.desc()).all()
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Ledger"
    ws.append(['Date', 'Description', 'Reference', 'Debit', 'Credit'])
    
    for e in entries:
        ws.append([
            e.parent.date.strftime('%d-%m-%Y'),
            e.parent.description,
            e.parent.reference or '',
            e.debit if e.debit > 0 else '',
            e.credit if e.credit > 0 else ''
        ])
    
    output = BytesIO()
    wb.save(output)
    output.seek(0)
@accounting_bp.route('/accounting/transactions/export')
def export_all_transactions():
    import openpyxl
    from io import BytesIO
    journals = JournalEntry.query.order_by(JournalEntry.id.desc()).all()
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "All Transactions"
    ws.append(['Date', 'Description', 'Reference', 'Account', 'Debit', 'Credit'])
    
    for j in journals:
        for e in j.entries:
            ws.append([
                j.date.strftime('%d-%m-%Y %H:%M'),
                j.description,
                j.reference or '',
                e.account.name,
                e.debit if e.debit > 0 else '',
                e.credit if e.credit > 0 else ''
            ])
    
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f"all_transactions_{datetime.now().strftime('%Y%m%d')}.xlsx")

@accounting_bp.route('/accounting/transaction/<int:journal_id>')
def transaction_details(journal_id):
    journal = JournalEntry.query.get_or_404(journal_id)
    return render_template('transaction_details.html', journal=journal)

@accounting_bp.route('/accounting/voucher/<int:journal_id>')
def voucher_print(journal_id):
    journal = JournalEntry.query.get_or_404(journal_id)
    # Determine if it's a Debit or Credit voucher
    total_debit = sum(e.debit for e in journal.entries)
    total_credit = sum(e.credit for e in journal.entries)
    
    return render_template('accounting/voucher_print.html', journal=journal, total_debit=total_debit, total_credit=total_credit)

@accounting_bp.route('/accounting/receipt/<int:journal_id>')
def receipt_print(journal_id):
    from models import Event
    journal = JournalEntry.query.get_or_404(journal_id)
    bill = None
    event = None
    
    if journal.monthly_bill_id:
        bill = MonthlyBill.query.get(journal.monthly_bill_id)
    if journal.event_id:
        event = Event.query.get(journal.event_id)
    
    # Discover Resident and Unit
    resident = None
    unit = None
    resident_entry = next((e for e in journal.entries if e.customer_id), None)
    if resident_entry:
        resident = resident_entry.customer
        if resident and resident.units:
            unit = resident.units[0]
    
    # Extract the payment amount (usually the debit to cash/bank)
    payment_amount = sum(e.debit for e in journal.entries if e.account.code.startswith('31'))
    if payment_amount == 0:
        payment_amount = sum(e.debit for e in journal.entries)
        
    return render_template('accounting/receipt_print.html', 
                           journal=journal, 
                           bill=bill, 
                           event=event, 
                           unit=unit,
                           amount=payment_amount)
@accounting_bp.route('/accounting/account/add', methods=['GET', 'POST'])
def add_account():
    from flask import request, redirect, url_for, flash
    if request.method == 'POST':
        name = request.form.get('name')
        code = request.form.get('code')
        acc_type = request.form.get('type')
        is_summary = 'is_summary' in request.form
        
        if not name or not code or not acc_type:
            flash("All fields are required!", "error")
        else:
            new_acc = Account(name=name, code=code, type=acc_type, is_summary=is_summary)
            try:
                db.session.add(new_acc)
                db.session.commit()
                flash("Account added successfully!", "success")
                return redirect(url_for('accounting.dashboard'))
            except Exception as e:
                db.session.rollback()
                flash(f"Error: {str(e)}", "error")
                
    return render_template('account_form.html', action="Add")

@accounting_bp.route('/accounting/account/edit/<int:id>', methods=['GET', 'POST'])
def edit_account(id):
    from flask import request, redirect, url_for, flash
    acc = Account.query.get_or_404(id)
    if request.method == 'POST':
        acc.name = request.form.get('name')
        acc.code = request.form.get('code')
        acc.type = request.form.get('type')
        acc.is_summary = 'is_summary' in request.form
        
        try:
            db.session.commit()
            flash("Account updated successfully!", "success")
            return redirect(url_for('accounting.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "error")
            
    return render_template('account_form.html', action="Edit", account=acc)

@accounting_bp.route('/accounting/account/delete/<int:id>', methods=['POST'])
def delete_account(id):
    from flask import redirect, url_for, flash
    acc = Account.query.get_or_404(id)
    
    # Check for linked ledger entries
    if acc.ledger_entries:
        flash(f"Cannot delete '{acc.name}' because it has existing transactions.", "error")
    else:
        try:
            db.session.delete(acc)
            db.session.commit()
            flash("Account deleted successfully!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "error")
            
    return redirect(url_for('accounting.dashboard'))
