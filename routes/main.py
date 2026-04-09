from flask import Blueprint, render_template, request, jsonify, url_for
from models import db, Unit, Customer, LedgerEntry, Account, MaintenanceTicket, Party, JournalEntry, MonthlyBill
from datetime import datetime, timedelta
from sqlalchemy import func, or_

main_bp = Blueprint('main', __name__)

@main_bp.route('/api/search')
def global_search():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])
    
    results = []
    
    # Search Customers
    customers = Customer.query.filter(Customer.name.ilike(f'%{query}%')).limit(5).all()
    for c in customers:
        results.append({
            'type': 'Resident',
            'label': c.name,
            'url': url_for('units.customer_profile', id=c.id)
        })
        
    # Search Units
    units = Unit.query.filter(Unit.unit_number.ilike(f'%{query}%')).limit(5).all()
    for u in units:
        results.append({
            'type': 'Unit',
            'label': f"Unit {u.unit_number}",
            'url': url_for('units.list_units')
        })
        
    # Search Parties
    parties = Party.query.filter(Party.name.ilike(f'%{query}%')).limit(5).all()
    for p in parties:
        results.append({
            'type': 'Vendor',
            'label': p.name,
            'url': url_for('parties.party_profile', id=p.id)
        })
        
    return jsonify(results)

@main_bp.route('/api/notifications')
def get_notifications():
    notifications = []
    
    # 1. Open Maintenance Tickets
    open_tickets = MaintenanceTicket.query.filter_by(status='open').count()
    if open_tickets > 0:
        notifications.append({
            'title': 'Maintenance Required',
            'body': f'{open_tickets} tickets are currently open.',
            'category': 'maintenance',
            'time': 'Action Required',
            'url': url_for('maintenance.list_tickets')
        })
        
    # 2. Overdue A/R (Residents with balance > 0)
    ar_acc = Account.query.filter_by(code='3930').first()
    if ar_acc:
        debtors_count = db.session.query(Customer).join(LedgerEntry)\
            .filter(LedgerEntry.account_id == ar_acc.id)\
            .group_by(Customer.id)\
            .having(func.sum(LedgerEntry.debit - LedgerEntry.credit) > 0).count()
        
        if debtors_count > 0:
            notifications.append({
                'title': 'Outstanding Dues',
                'body': f'{debtors_count} residents have unpaid balances.',
                'category': 'finance',
                'time': 'Financial Alert',
                'url': url_for('reports.ar_aging_report')
            })

    return jsonify(notifications)

@main_bp.route('/')
def index():
    # Get stats for dashboard
    total_units = Unit.query.count()
    occupied = Unit.query.filter_by(status='occupied').count()
    
    # Universal Revenue Consolidation
    revenue_accs = Account.query.filter_by(type='revenue').all()
    revenue_ids = [acc.id for acc in revenue_accs]
    cash_acc = Account.query.filter_by(code='3100').first()
    ar_acc = Account.query.filter_by(code='3930').first()
    
    total_income = 0
    total_collected = 0
    total_due = 0
    
    if revenue_ids:
        total_income = db.session.query(func.sum(LedgerEntry.credit)).filter(LedgerEntry.account_id.in_(revenue_ids)).scalar() or 0
    if cash_acc:
        total_collected = db.session.query(func.sum(LedgerEntry.debit)).filter_by(account_id=cash_acc.id).scalar() or 0
    if ar_acc:
        # A/R balance = Total Debits - Total Credits (from Ledger)
        ar_debits = db.session.query(func.sum(LedgerEntry.debit)).filter_by(account_id=ar_acc.id).scalar() or 0
        ar_credits = db.session.query(func.sum(LedgerEntry.credit)).filter_by(account_id=ar_acc.id).scalar() or 0
        total_due = ar_debits - ar_credits
        
        # Add Accrued (Pending) Penalties from Service Charges
        accrued_penalties = db.session.query(func.sum(MonthlyBill.penalty_to_apply))\
            .filter(MonthlyBill.status == 'unpaid', datetime.now().date() > MonthlyBill.due_date).scalar() or 0
        total_due += accrued_penalties

    # NEW: Total Cost (Expense sum)
    expense_accs = Account.query.filter_by(type='expense').all()
    expense_ids = [acc.id for acc in expense_accs]
    total_cost = 0
    if expense_ids:
        total_cost = db.session.query(func.sum(LedgerEntry.debit)).filter(LedgerEntry.account_id.in_(expense_ids)).scalar() or 0

    # NEW: Current Balance (Cash + Bank accounts)
    liquid_accs = Account.query.filter(Account.type == 'asset', Account.code.like('10%')).all()
    current_balance = 0
    for acc in liquid_accs:
        debits = db.session.query(func.sum(LedgerEntry.debit)).filter_by(account_id=acc.id).scalar() or 0
        credits = db.session.query(func.sum(LedgerEntry.credit)).filter_by(account_id=acc.id).scalar() or 0
        current_balance += (debits - credits)

    # Real overdue data from A/R account
    overdue_list = []
    if ar_acc:
        debtors = db.session.query(
            Customer,
            func.sum(LedgerEntry.debit - LedgerEntry.credit).label('balance')
        ).join(LedgerEntry).filter(LedgerEntry.account_id == ar_acc.id)\
        .group_by(Customer.id).having(func.sum(LedgerEntry.debit - LedgerEntry.credit) > 0).all()
        
        today = datetime.now().date()
        for customer, balance in debtors:
            cust_accrued = db.session.query(func.sum(MonthlyBill.penalty_to_apply))\
                .filter(MonthlyBill.customer_id == customer.id, MonthlyBill.status != 'paid', today > MonthlyBill.due_date).scalar() or 0
            
            total_balance = balance + cust_accrued
            
            # Lifetime stats for % calculation
            total_billed = db.session.query(func.sum(MonthlyBill.amount + MonthlyBill.penalty_amount))\
                .filter(MonthlyBill.customer_id == customer.id).scalar() or 0
            # Add current accrued to total billed for accurate %
            final_billed = total_billed + cust_accrued
            due_percent = (total_balance / final_billed * 100) if final_billed > 0 else 0

            oldest_debit = LedgerEntry.query.filter_by(customer_id=customer.id, account_id=ar_acc.id)\
                .filter(LedgerEntry.debit > 0)\
                .join(JournalEntry).order_by(JournalEntry.date.asc()).first()
            
            unit = customer.units[0] if customer.units else None
            overdue_list.append({
                'unit': unit.unit_number if unit else 'N/A',
                'customer': customer.name,
                'due_date': oldest_debit.parent.date.strftime('%d %b %Y') if oldest_debit else 'Unknown',
                'amount': f"{total_balance:,.2f}",
                'due_percent': f"{due_percent:.1f}"
            })

    # Real maintenance tickets
    recent_tickets = MaintenanceTicket.query.filter_by(status='open').order_by(MaintenanceTicket.created_at.desc()).limit(5).all()
    tickets_data = []
    for t in recent_tickets:
        tickets_data.append({
            'unit': t.unit.unit_number if t.unit else 'N/A',
            'issue': t.description[:30] + '...' if len(t.description) > 30 else t.description,
            'customer': t.unit.resident.name if t.unit and t.unit.resident else 'Unknown',
            'date': t.created_at.strftime('%d %b')
        })

    # Monthly data for charts
    monthly_labels = []
    income_data = []
    collection_data = []
    expense_data = []
    
    for i in range(5, -1, -1):
        month_date = datetime.now() - timedelta(days=i*30)
        m_start = month_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_m = (m_start + timedelta(days=32)).replace(day=1)
        monthly_labels.append(m_start.strftime('%b'))
        
        m_income = 0
        if revenue_ids:
            m_income = db.session.query(func.sum(LedgerEntry.credit))\
                .join(JournalEntry).filter(LedgerEntry.account_id.in_(revenue_ids), JournalEntry.date >= m_start, JournalEntry.date < next_m).scalar() or 0
        income_data.append(float(m_income))
        
        m_collected = 0
        if cash_acc:
            m_collected = db.session.query(func.sum(LedgerEntry.debit))\
                .join(JournalEntry).filter(LedgerEntry.account_id == cash_acc.id, JournalEntry.date >= m_start, JournalEntry.date < next_m).scalar() or 0
        collection_data.append(float(m_collected))

        m_expense = 0
        if expense_ids:
            m_expense = db.session.query(func.sum(LedgerEntry.debit))\
                .join(JournalEntry).filter(LedgerEntry.account_id.in_(expense_ids), JournalEntry.date >= m_start, JournalEntry.date < next_m).scalar() or 0
        expense_data.append(float(m_expense))

    stats = {
        'total_income': f"{total_income:,.2f}",
        'total_cost': f"{total_cost:,.2f}",
        'current_balance': f"{current_balance:,.2f}",
        'total_collected': f"{total_collected:,.2f}",
        'total_due': f"{total_due:,.2f}",
        'total_units': total_units,
        'occupied': occupied,
        'raw_income': total_income,
        'raw_collected': total_collected,
        'raw_due': total_due,
        'monthly_labels': monthly_labels,
        'income_data': income_data,
        'collection_data': collection_data,
        'expense_data': expense_data
    }

    return render_template('index.html', stats=stats, overdue=overdue_list, tickets=tickets_data, today_date=datetime.now().strftime('%d %b %Y'))

@main_bp.route('/reports/income-breakdown')
def income_breakdown():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    account_id = request.args.get('account_id')
    
    revenue_accounts = Account.query.filter_by(type='revenue').all()
    revenue_ids = [acc.id for acc in revenue_accounts]
    
    query = LedgerEntry.query.filter(LedgerEntry.account_id.in_(revenue_ids)).join(JournalEntry)
    
    if start_date:
        query = query.filter(JournalEntry.date >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        query = query.filter(JournalEntry.date <= datetime.strptime(end_date, '%Y-%m-%d'))
    if account_id:
        query = query.filter(LedgerEntry.account_id == account_id)
        
    entries = query.order_by(JournalEntry.date.desc()).all()
    
    category_summary = db.session.query(
        Account.name, 
        func.sum(LedgerEntry.credit).label('total')
    ).join(LedgerEntry).filter(Account.id.in_(revenue_ids)).join(JournalEntry)

    if start_date:
        category_summary = category_summary.filter(JournalEntry.date >= datetime.strptime(start_date, '%Y-%m-%d'))
    if end_date:
        category_summary = category_summary.filter(JournalEntry.date <= datetime.strptime(end_date, '%Y-%m-%d'))
        
    category_summary = category_summary.group_by(Account.id).all()
    
    return render_template('reports/income_breakdown.html', entries=entries, category_summary=category_summary,
                           revenue_accounts=revenue_accounts, selected_account=int(account_id) if account_id else None,
                           start_date=start_date, end_date=end_date)

@main_bp.route('/reports/balance-breakdown')
def balance_breakdown():
    liquid_accs = Account.query.filter(Account.type == 'asset', Account.code.like('10%')).all()
    balance_details = []
    total_balance = 0
    
    for acc in liquid_accs:
        debits = db.session.query(func.sum(LedgerEntry.debit)).filter_by(account_id=acc.id).scalar() or 0
        credits = db.session.query(func.sum(LedgerEntry.credit)).filter_by(account_id=acc.id).scalar() or 0
        bal = debits - credits
        total_balance += bal
        balance_details.append({'name': acc.name, 'balance': bal, 'id': acc.id, 'code': acc.code})
        
    return render_template('reports/balance_breakdown.html', details=balance_details, total=total_balance)
