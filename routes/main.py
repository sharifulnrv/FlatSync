from flask import Blueprint, render_template, request, jsonify, url_for
from models import db, Unit, Customer, LedgerEntry, Account, MaintenanceTicket, Party, JournalEntry, MonthlyBill, Asset
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
    revenue_accs = Account.query.filter_by(type='revenue', is_summary=False).all()
    revenue_ids = [acc.id for acc in revenue_accs]
    cash_acc = Account.query.filter_by(code='3100').first()
    ar_acc = Account.query.filter_by(code='3930').first()
    
    total_income = 0
    total_collected = 0
    total_due = 0
    
    if revenue_ids:
        total_income = db.session.query(func.sum(LedgerEntry.credit - LedgerEntry.debit))\
            .filter(LedgerEntry.account_id.in_(revenue_ids), LedgerEntry.event_id == None).scalar() or 0
    if cash_acc:
        total_collected = db.session.query(func.sum(LedgerEntry.debit - LedgerEntry.credit))\
            .filter_by(account_id=cash_acc.id, event_id=None).scalar() or 0
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
    expense_accs = Account.query.filter_by(type='expense', is_summary=False).all()
    expense_ids = [acc.id for acc in expense_accs]
    total_cost = 0
    if expense_ids:
        total_cost = db.session.query(func.sum(LedgerEntry.debit - LedgerEntry.credit))\
            .filter(LedgerEntry.account_id.in_(expense_ids), LedgerEntry.event_id == None).scalar() or 0

    # NEW: Granular Balances (Cash, Bank, Funds)
    # Cash in Hand: 3110
    # Operating Bank: 3120
    # Event Fund: 3150
    
    def get_acc_bal(code_prefix):
        accs = Account.query.filter(Account.code.like(f'{code_prefix}%'), Account.is_summary == False).all()
        bal = 0
        for acc in accs:
            d = db.session.query(func.sum(LedgerEntry.debit)).filter_by(account_id=acc.id).scalar() or 0
            c = db.session.query(func.sum(LedgerEntry.credit)).filter_by(account_id=acc.id).scalar() or 0
            bal += (d - c)
        return float(bal)

    cash_bal = get_acc_bal('311')
    bank_bal = get_acc_bal('312')
    fund_bal = get_acc_bal('315')
    other_bal = get_acc_bal('31') - (cash_bal + bank_bal + fund_bal)
    
    current_balance = cash_bal + bank_bal + fund_bal + other_bal

    # NEW: Total Assets (All accounts of type 'asset' + Physical Assets)
    asset_accs = Account.query.filter_by(type='asset', is_summary=False).all()
    asset_ids = [acc.id for acc in asset_accs]
    total_assets = 0
    if asset_ids:
        a_debits = db.session.query(func.sum(LedgerEntry.debit)).filter(LedgerEntry.account_id.in_(asset_ids), LedgerEntry.event_id == None).scalar() or 0
        a_credits = db.session.query(func.sum(LedgerEntry.credit)).filter(LedgerEntry.account_id.in_(asset_ids), LedgerEntry.event_id == None).scalar() or 0
        total_assets = a_debits - a_credits

    # ADD: Physical Assets from Asset module
    from models import Asset as FixedAsset
    fixed_assets_val = sum(a.current_value for a in Asset.query.all())
    total_assets += fixed_assets_val

    # FIX: Event Fund (Total net economic value for events: Revenue - Expense)
    event_income = db.session.query(func.sum(LedgerEntry.credit - LedgerEntry.debit))\
        .join(Account).filter(Account.type == 'revenue', LedgerEntry.event_id != None).scalar() or 0
    event_expense = db.session.query(func.sum(LedgerEntry.debit - LedgerEntry.credit))\
        .join(Account).filter(Account.type == 'expense', LedgerEntry.event_id != None).scalar() or 0
    event_fund = float(event_income - event_expense)

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
            m_income = db.session.query(func.sum(LedgerEntry.credit - LedgerEntry.debit))\
                .join(JournalEntry).filter(LedgerEntry.account_id.in_(revenue_ids), LedgerEntry.event_id == None, JournalEntry.date >= m_start, JournalEntry.date < next_m).scalar() or 0
        income_data.append(float(m_income))
        
        m_collected = 0
        if cash_acc:
            m_collected = db.session.query(func.sum(LedgerEntry.debit - LedgerEntry.credit))\
                .join(JournalEntry).filter(LedgerEntry.account_id == cash_acc.id, JournalEntry.date >= m_start, JournalEntry.date < next_m).scalar() or 0
        collection_data.append(float(m_collected))

        m_expense = 0
        if expense_ids:
            m_expense = db.session.query(func.sum(LedgerEntry.debit - LedgerEntry.credit))\
                .join(JournalEntry).filter(LedgerEntry.account_id.in_(expense_ids), LedgerEntry.event_id == None, JournalEntry.date >= m_start, JournalEntry.date < next_m).scalar() or 0
        expense_data.append(float(m_expense))

    stats = {
        'total_income': f"{total_income:,.2f}",
        'total_cost': f"{total_cost:,.2f}",
        'total_assets': f"{total_assets:,.2f}",
        'current_balance': f"{current_balance:,.2f}",
        'total_due': f"{total_due:,.2f}",
        'total_units': total_units,
        'occupied': occupied,
        'cash_balance': f"{cash_bal:,.2f}",
        'bank_balance': f"{bank_bal:,.2f}",
        'fund_balance': f"{event_fund:,.2f}",
        'raw_collected': total_collected,
        'raw_due': total_due,
        'monthly_labels': monthly_labels,
        'income_data': income_data,
        'collection_data': collection_data,
        'expense_data': expense_data
    }

    return render_template('index.html', stats=stats, overdue=overdue_list, tickets=tickets_data, today_date=datetime.now().strftime('%d %b %Y'))

@main_bp.route('/reports/category-summary')
def category_summary_report():
    cat_type = request.args.get('type', 'revenue') # 'revenue' or 'expense'
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if cat_type == 'event':
        from models import Event
        events = Event.query.all()
        summary_data = []
        total_all = 0
        for ev in events:
            rev = db.session.query(func.sum(LedgerEntry.credit - LedgerEntry.debit)).join(Account).filter(Account.type == 'revenue', LedgerEntry.event_id == ev.id).scalar() or 0
            exp = db.session.query(func.sum(LedgerEntry.debit - LedgerEntry.credit)).join(Account).filter(Account.type == 'expense', LedgerEntry.event_id == ev.id).scalar() or 0
            net = float(rev - exp)
            summary_data.append({
                'id': ev.id,
                'code': ev.date.strftime('%Y-%m'),
                'name': ev.name,
                'total': net
            })
            total_all += net
    else:
        accounts = Account.query.filter_by(type=cat_type, is_summary=False).all()
        account_ids = [acc.id for acc in accounts]
        
        # Calculate totals per account
        if cat_type == 'revenue':
            agg_func = func.sum(LedgerEntry.credit - LedgerEntry.debit)
        elif cat_type == 'asset':
            agg_func = func.sum(LedgerEntry.debit - LedgerEntry.credit)
        elif cat_type == 'expense' or cat_type == 'cost':
            agg_func = func.sum(LedgerEntry.debit - LedgerEntry.credit)
        else:
            agg_func = func.sum(LedgerEntry.credit - LedgerEntry.debit)
            
        query = db.session.query(
            Account, 
            agg_func.label('total')
        ).join(LedgerEntry, LedgerEntry.account_id == Account.id).filter(Account.id.in_(account_ids), LedgerEntry.event_id == None)

        if start_date:
            query = query.join(JournalEntry).filter(JournalEntry.date >= datetime.strptime(start_date, '%Y-%m-%d'))
        if end_date:
            if JournalEntry not in [m.class_ for m in query._setup_joins]:
                query = query.join(JournalEntry)
            query = query.filter(JournalEntry.date <= datetime.strptime(end_date, '%Y-%m-%d'))
            
        results = query.group_by(Account.id).all()
        
        summary_data = []
        total_all = 0
        for acc, total in results:
            val = float(total or 0)
            summary_data.append({
                'id': acc.id,
                'code': acc.code,
                'name': acc.name,
                'total': val
            })
            total_all += val
            
        # NEW: Inject Physical Assets if type is 'asset'
        if cat_type == 'asset':
            fixed_assets_val = sum(a.current_value for a in Asset.query.all())
            if fixed_assets_val > 0:
                summary_data.append({
                    'id': 'fixed-assets',
                    'code': 'PHYS',
                    'name': 'Physical Assets & Inventory',
                    'total': float(fixed_assets_val)
                })
                total_all += float(fixed_assets_val)
        
    # Sort by total descending
    summary_data = sorted(summary_data, key=lambda x: x['total'], reverse=True)
    
    return render_template('reports/category_summary.html', 
                            summary_data=summary_data, 
                            total_all=total_all,
                            cat_type=cat_type,
                            start_date=start_date,
                            end_date=end_date)

@main_bp.route('/reports/income-breakdown')
def income_breakdown():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    account_id = request.args.get('account_id')
    
    revenue_accounts = Account.query.filter_by(type='revenue').all()
    revenue_ids = [acc.id for acc in revenue_accounts]
    
    query = LedgerEntry.query.filter(LedgerEntry.account_id.in_(revenue_ids), LedgerEntry.event_id == None).join(JournalEntry)
    
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
    # Filter by specific type if provided: 'bank' or 'cash'
    filter_type = request.args.get('type')
    
    query = Account.query.filter(Account.type == 'asset', Account.code.like('31%'), Account.is_summary == False)
    
    if filter_type == 'bank':
        query = query.filter(Account.code.like('312%'))
        header_title = "Bank Account Detail"
    elif filter_type == 'cash':
        query = query.filter(Account.code.like('311%'))
        header_title = "Cash Inventory"
    else:
        header_title = "Total Liquid Liquidity"
        
    liquid_accs = query.all()
    balance_details = []
    total_balance = 0
    
    for acc in liquid_accs:
        debits = db.session.query(func.sum(LedgerEntry.debit)).filter_by(account_id=acc.id).scalar() or 0
        credits = db.session.query(func.sum(LedgerEntry.credit)).filter_by(account_id=acc.id).scalar() or 0
        bal = debits - credits
        total_balance += bal
        balance_details.append({'name': acc.name, 'balance': bal, 'id': acc.id, 'code': acc.code})
        
    return render_template('reports/balance_breakdown.html', details=balance_details, total=total_balance, title=header_title)
