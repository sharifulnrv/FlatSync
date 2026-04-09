from flask import Blueprint, render_template, request, send_file
from models import db, Account, LedgerEntry, Customer, Unit, JournalEntry
from sqlalchemy import func
import openpyxl
from io import BytesIO
from datetime import datetime

reports_bp = Blueprint('reports', __name__)

def get_dates():
    from_date_str = request.args.get('from_date')
    to_date_str = request.args.get('to_date')
    
    today = datetime.now()
    default_from = today.replace(day=1).strftime('%Y-%m-%d')
    default_to = today.strftime('%Y-%m-%d')
    
    # Use default if not provided or empty string
    f_str = from_date_str if from_date_str else default_from
    t_str = to_date_str if to_date_str else default_to
    
    f_date = datetime.strptime(f_str, '%Y-%m-%d')
    t_date = datetime.strptime(t_str, '%Y-%m-%d')
    
    return f_date, t_date, f_str, t_str

@reports_bp.route('/reports/aging')
def ar_aging_report():
    from_date, to_date, from_date_str, to_date_str = get_dates()
    
    # NEW COA: 3930 is Service Charge Receivable
    ar_acc = Account.query.filter_by(code='3930').first()
    if not ar_acc:
        # Fallback or check for main AR range
        ar_acc = Account.query.filter(Account.code.like('39%'), Account.type == 'asset').first()
        
    if not ar_acc:
        return "A/R Account not found", 404
        
    # Base query for ledger entries in A/R
    q = db.session.query(LedgerEntry).filter(LedgerEntry.account_id == ar_acc.id)
    
    q = q.join(JournalEntry).filter(JournalEntry.date >= from_date)
    q = q.filter(JournalEntry.date <= to_date)
        
    all_entries = q.all()
    
    # Calculate balances per customer
    customer_balances = {}
    for entry in all_entries:
        cid = entry.customer_id
        if not cid: continue
        if cid not in customer_balances:
            customer_balances[cid] = {'customer': entry.customer or Customer.query.get(cid), 'balance': 0, 'oldest_date': None, 'transactions': []}
        
        customer_balances[cid]['balance'] += (entry.debit - entry.credit)
        customer_balances[cid]['transactions'].append(entry)
        
        entry_date = entry.parent.date
        if not customer_balances[cid]['oldest_date'] or entry_date < customer_balances[cid]['oldest_date']:
            customer_balances[cid]['oldest_date'] = entry_date

    aging_data = []
    now = datetime.now()
    
    for cid, data in customer_balances.items():
        if data['balance'] <= 0: continue
        
        days_old = (now - data['oldest_date']).days if data['oldest_date'] else 0
        category = "0-30 days"
        if days_old > 90: category = "90+ days"
        elif days_old > 60: category = "61-90 days"
        elif days_old > 30: category = "31-60 days"
        
        aging_data.append({
            'customer': data['customer'].name,
            'unit': data['customer'].units[0].unit_number if data['customer'].units else 'N/A',
            'balance': data['balance'],
            'days': days_old,
            'category': category,
            'transactions': data['transactions']
        })
        
    return render_template('aging_report.html', aging_data=aging_data, from_date=from_date_str, to_date=to_date_str)

@reports_bp.route('/reports/daily-cash')
def daily_cash_report():
    from_date, to_date, from_date_str, to_date_str = get_dates()
    
    # NEW COA: 3x are Assets, 31xx are Cash/Bank
    # Group by date for the summary
    q_stats = db.session.query(
        func.date(JournalEntry.date).label('day'),
        func.sum(LedgerEntry.debit).label('total_in'),
        func.sum(LedgerEntry.credit).label('total_out')
    ).join(LedgerEntry, JournalEntry.id == LedgerEntry.journal_id)\
    .join(Account, LedgerEntry.account_id == Account.id)\
    .filter(Account.code.like('31%')) # 31xx are liquid cash/bank
    
    # Detailed query for individual transactions
    q_details = db.session.query(LedgerEntry).join(JournalEntry).join(Account, LedgerEntry.account_id == Account.id).filter(Account.code.like('31%'))

    q_stats = q_stats.filter(JournalEntry.date >= from_date)
    q_details = q_details.filter(JournalEntry.date >= from_date)
    q_stats = q_stats.filter(JournalEntry.date <= to_date)
    q_details = q_details.filter(JournalEntry.date <= to_date)
        
    daily_stats = q_stats.group_by(func.date(JournalEntry.date)).order_by(func.date(JournalEntry.date).desc()).all()
    transactions = q_details.order_by(JournalEntry.date.desc()).all()
    
    return render_template('daily_cash_report.html', stats=daily_stats, transactions=transactions, from_date=from_date_str, to_date=to_date_str)

@reports_bp.route('/reports/ledger')
def ledger_report():
    account_id = request.args.get('account_id', type=int)
    from_date, to_date, from_date_str, to_date_str = get_dates()
    
    accounts = Account.query.order_by(Account.code).all()
    target_account = Account.query.get(account_id) if account_id else None
    
    entries = []
    if target_account:
        q = LedgerEntry.query.join(JournalEntry).filter(LedgerEntry.account_id == target_account.id)
        q = q.filter(JournalEntry.date >= from_date)
        q = q.filter(JournalEntry.date <= to_date)
        entries = q.order_by(JournalEntry.date.asc()).all()
        
    return render_template('ledger_report.html', 
                           accounts=accounts, 
                           target_account=target_account, 
                           entries=entries,
                           from_date=from_date_str, 
                           to_date=to_date_str)

@reports_bp.route('/reports')
def report_index():
    return render_template('reports_index.html')

@reports_bp.route('/reports/pnl')
def pnl_statement():
    from_date, to_date, from_date_str, to_date_str = get_dates()
    
    revenue_accounts = Account.query.filter_by(type='revenue').order_by(Account.code).all()
    expense_accounts = Account.query.filter_by(type='expense').order_by(Account.code).all()
    
    pnl_data = {'revenue': [], 'expense': [], 'total_revenue': 0, 'total_expense': 0, 
                'from_date': from_date_str, 'to_date': to_date_str}
    
    for acc in revenue_accounts:
        if acc.is_summary: continue
        q = db.session.query(LedgerEntry).filter(LedgerEntry.account_id == acc.id)
        q = q.join(JournalEntry).filter(JournalEntry.date >= from_date)
        q = q.filter(JournalEntry.date <= to_date)
            
        entries = q.all()
        balance = sum(e.credit - e.debit for e in entries)
        if balance != 0:
            pnl_data['revenue'].append({'name': acc.name, 'code': acc.code, 'balance': balance})
            pnl_data['total_revenue'] += balance
            
    for acc in expense_accounts:
        if acc.is_summary: continue
        q = db.session.query(LedgerEntry).filter(LedgerEntry.account_id == acc.id)
        q = q.join(JournalEntry).filter(JournalEntry.date >= from_date)
        q = q.filter(JournalEntry.date <= to_date)
            
        entries = q.all()
        balance = sum(e.debit - e.credit for e in entries)
        if balance != 0:
            pnl_data['expense'].append({'name': acc.name, 'code': acc.code, 'balance': balance})
            pnl_data['total_expense'] += balance
            
    pnl_data['net_profit'] = pnl_data['total_revenue'] - pnl_data['total_expense']
    
    return render_template('pnl_report.html', data=pnl_data)

@reports_bp.route('/reports/due-report')
def due_report():
    from_date, to_date, from_date_str, to_date_str = get_dates()
    # Service Charge Receivable (3930) or any 39x
    target_accs = Account.query.filter(Account.code.like('39%')).all()
    acc_ids = [a.id for a in target_accs]
    
    results = db.session.query(
        Customer.name,
        func.sum(LedgerEntry.debit) - func.sum(LedgerEntry.credit)
    ).join(LedgerEntry, Customer.id == LedgerEntry.customer_id)\
     .join(JournalEntry)\
     .filter(LedgerEntry.account_id.in_(acc_ids))\
     .filter(JournalEntry.date >= from_date)\
     .filter(JournalEntry.date <= to_date)\
     .group_by(Customer.id, Customer.name).all()
    return render_template('due_report.html', results=[r for r in results if r[1] != 0], from_date=from_date_str, to_date=to_date_str)

@reports_bp.route('/reports/trial-balance')
def trial_balance():
    from_date, to_date, from_date_str, to_date_str = get_dates()

    all_accounts = Account.query.order_by(Account.code).all()
    results = []
    total_debit = 0
    total_credit = 0
    
    for acc in all_accounts:
        if acc.is_summary: continue
            
        # Get debit/credit for this account with date filters
        q = db.session.query(func.sum(LedgerEntry.debit), func.sum(LedgerEntry.credit)).filter_by(account_id=acc.id)
        q = q.join(JournalEntry).filter(JournalEntry.date >= from_date)
        q = q.filter(JournalEntry.date <= to_date)
        
        debit, credit = q.first()
        debit = debit or 0
        credit = credit or 0
        
        if debit != 0 or credit != 0:
            results.append({'code': acc.code, 'name': acc.name, 'debit': debit, 'credit': credit, 'type': acc.type})
            total_debit += debit
            total_credit += credit
            
    return render_template('reports/trial_balance.html', 
                           results=results, 
                           total_debit=total_debit, 
                           total_credit=total_credit,
                           from_date=from_date_str,
                           to_date=to_date_str)

@reports_bp.route('/reports/balance-sheet')
def balance_sheet():
    from_date, to_date, from_date_str, to_date_str = get_dates()
    target_date = to_date

    assets = []
    liabilities = []
    equity = []
    
    total_assets = 0
    total_liabilities = 0
    total_equity = 0
    
    accounts = Account.query.filter(Account.type.in_(['asset', 'liability', 'equity'])).order_by(Account.code).all()
    
    for acc in accounts:
        if acc.is_summary: continue
        
        q = db.session.query(func.sum(LedgerEntry.debit), func.sum(LedgerEntry.credit)).join(JournalEntry).filter(LedgerEntry.account_id == acc.id, JournalEntry.date <= target_date)
        debit, credit = q.first()
        debit = debit or 0
        credit = credit or 0
        
        balance = (debit - credit) if acc.type in ['asset', 'expense'] else (credit - debit)
        if balance != 0:
            item = {'code': acc.code, 'name': acc.name, 'balance': balance}
            if acc.type == 'asset':
                assets.append(item)
                total_assets += balance
            elif acc.type == 'liability':
                liabilities.append(item)
                total_liabilities += balance
            elif acc.type == 'equity':
                equity.append(item)
                total_equity += balance
                
    # Calculate Retained Earnings (Net Profit from beginning to target_date)
    rev_q = db.session.query(func.sum(LedgerEntry.credit - LedgerEntry.debit)).join(JournalEntry).join(Account).filter(Account.type == 'revenue', JournalEntry.date <= target_date).scalar() or 0
    exp_q = db.session.query(func.sum(LedgerEntry.debit - LedgerEntry.credit)).join(JournalEntry).join(Account).filter(Account.type == 'expense', JournalEntry.date <= target_date).scalar() or 0
    retained_earnings = rev_q - exp_q
    
    if retained_earnings != 0:
        equity.append({'code': 'RE', 'name': 'Retained Earnings (Net Profit)', 'balance': retained_earnings})
        total_equity += retained_earnings

    return render_template('reports/balance_sheet.html', 
                            assets=assets, liabilities=liabilities, equity=equity,
                            total_assets=total_assets, total_liabilities=total_liabilities, total_equity=total_equity,
                            target_date=to_date_str, from_date=from_date_str, to_date=to_date_str)

@reports_bp.route('/reports/service-revenue')
def service_revenue_report():
    from models import MonthlyBill
    month = request.args.get('month', type=int, default=datetime.now().month)
    year = request.args.get('year', type=int, default=datetime.now().year)
    
    query = MonthlyBill.query
    if month: query = query.filter_by(month=month)
    if year: query = query.filter_by(year=year)
    bills = query.order_by(MonthlyBill.year.desc(), MonthlyBill.month.desc()).all()
    
    stats = {
        'billed_service': sum(b.amount for b in bills),
        'billed_penalty': sum(b.penalty_amount for b in bills),
        'total_paid': sum(b.paid_amount for b in bills),
        'total_due': sum(b.balance_due for b in bills)
    }
    
    # Other Revenues from Journal (hall, gym, scrap, events)
    # COA Range 4000-4999 are Revenue
    rev_accounts = Account.query.filter(Account.type == 'revenue', Account.code != '4100').all() # 4100 is likely main service charge
    other_revs = []
    for acc in rev_accounts:
        amount = db.session.query(func.sum(LedgerEntry.credit - LedgerEntry.debit))\
            .filter(LedgerEntry.account_id == acc.id).scalar() or 0
        if amount != 0:
            other_revs.append({'name': acc.name, 'amount': amount})

    months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
    return render_template('reports/service_revenue_report.html', 
                           bills=bills, stats=stats, other_revs=other_revs,
                           selected_month=month, selected_year=year, months=months)
@reports_bp.route('/reports/export/customers')
def export_customers():
    # Fetch units with residents
    units = Unit.query.all()
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Property Inventory"
    
    from openpyxl.styles import Font, Alignment, PatternFill, Side, Border
    
    # Association styling
    title_font = Font(size=16, bold=True, color="1E293B")
    addr_font = Font(size=10, color="64748B")
    report_title_font = Font(size=12, bold=True, color="4F46E5")
    
    # Association Branding
    ws.append(["Assurance Sultan Legacy Flat Owners Association"])
    ws.append(["23/4, Katasur, Ser-E Bangla Road, Mohammadpur, Dhaka"])
    ws.append(["PROPERTY INVENTORY REPORT"])
    ws.append([])
    
    # Merge and center Branding
    last_col = "E"
    ws.merge_cells(f'A1:{last_col}1')
    ws.merge_cells(f'A2:{last_col}2')
    ws.merge_cells(f'A3:{last_col}3')
    
    for row_idx in [1, 2, 3]:
        cell = ws.cell(row=row_idx, column=1)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        if row_idx == 1: cell.font = title_font
        elif row_idx == 2: cell.font = addr_font
        else: cell.font = report_title_font

    # Modern Header Row (Row 5)
    headers = ["Unit Number", "Status", "Resident Name", "Phone", "Mailing Address"]
    ws.append(headers)
    
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    
    for cell in ws[5]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin_border

    # Data
    for unit in units:
        res_name = unit.resident.name if unit.resident else "N/A"
        res_phone = unit.resident.phone if unit.resident else "N/A"
        res_addr = unit.resident.address if unit.resident else "N/A"
        ws.append([unit.unit_number, unit.status.title(), res_name, res_phone, res_addr])

    # Autosize columns
    for column_cells in ws.columns:
        length = max(len(str(cell.value)) for cell in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = length + 5

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    filename = f"Property_Inventory_{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    return send_file(output, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@reports_bp.route('/reports/export/pnl')
def export_pnl():
    from_date, to_date, from_date_str, to_date_str = get_dates()
    
    revenue_accounts = Account.query.filter_by(type='revenue').order_by(Account.code).all()
    expense_accounts = Account.query.filter_by(type='expense').order_by(Account.code).all()
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Profit & Loss"
    
    from openpyxl.styles import Font, Alignment, PatternFill, Side, Border
    
    ws.append(["Assurance Sultan Legacy Flat Owners Association"])
    ws.append(["23/4, Katasur, Ser-E Bangla Road, Mohammadpur, Dhaka"])
    ws.append(["PROFIT & LOSS STATEMENT"])
    ws.append([f"Reporting Period: {from_date_str} to {to_date_str}"])
    ws.append([]) # Spacer
    
    # Styling
    last_col = "B"
    title_font = Font(size=16, bold=True, color="1E293B")
    addr_font = Font(size=10, color="64748B")
    report_title_font = Font(size=12, bold=True, color="4F46E5")
    
    for row_idx in [1, 2, 3, 4]:
        ws.merge_cells(f'A{row_idx}:{last_col}{row_idx}')
        cell = ws.cell(row=row_idx, column=1)
        cell.alignment = Alignment(horizontal="center")
        if row_idx == 1: cell.font = title_font
        elif row_idx == 2: cell.font = addr_font
        else: cell.font = report_title_font
    
    ws.append(["REVENUE"])
    total_rev = 0
    for acc in revenue_accounts:
        if acc.is_summary: continue
        q = db.session.query(LedgerEntry).filter(LedgerEntry.account_id == acc.id)
        q = q.join(JournalEntry).filter(JournalEntry.date >= from_date)
        q = q.filter(JournalEntry.date <= to_date)
        balance = sum(e.credit - e.debit for e in q.all())
        if balance != 0:
            ws.append([f"{acc.code} - {acc.name}", balance])
            total_rev += balance
    ws.append(["Total Revenue", total_rev])
    ws.append([])

    ws.append(["EXPENSES"])
    total_exp = 0
    for acc in expense_accounts:
        if acc.is_summary: continue
        q = db.session.query(LedgerEntry).filter(LedgerEntry.account_id == acc.id)
        q = q.join(JournalEntry).filter(JournalEntry.date >= from_date)
        q = q.filter(JournalEntry.date <= to_date)
        balance = sum(e.debit - e.credit for e in q.all())
        if balance != 0:
            ws.append([f"{acc.code} - {acc.name}", balance])
            total_exp += balance
    ws.append(["Total Expenses", total_exp])
    ws.append([])
    ws.append(["NET PROFIT", total_rev - total_exp])

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f"PNL_Statement_{datetime.now().strftime('%Y-%m-%d')}.xlsx")

@reports_bp.route('/reports/export/trial-balance')
def export_trial_balance():
    from_date, to_date, from_date_str, to_date_str = get_dates()
    all_accounts = Account.query.order_by(Account.code).all()
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Trial Balance"
    from openpyxl.styles import Font, Alignment, PatternFill, Side, Border
    ws.append(["Assurance Sultan Legacy Flat Owners Association"])
    ws.append(["23/4, Katasur, Ser-E Bangla Road, Mohammadpur, Dhaka"])
    ws.append(["TRIAL BALANCE REPORT"])
    ws.append([f"As Of Period: {from_date_str} to {to_date_str}"])
    ws.append([])
    
    # Styling
    last_col = "D"
    title_font = Font(size=16, bold=True, color="1E293B")
    addr_font = Font(size=10, color="64748B")
    report_title_font = Font(size=12, bold=True, color="4F46E5")
    
    for row_idx in [1, 2, 3, 4]:
        ws.merge_cells(f'A{row_idx}:{last_col}{row_idx}')
        cell = ws.cell(row=row_idx, column=1)
        cell.alignment = Alignment(horizontal="center")
        if row_idx == 1: cell.font = title_font
        elif row_idx == 2: cell.font = addr_font
        else: cell.font = report_title_font
    
    ws.append(["Code", "Account Name", "Debit", "Credit"])
    
    t_debit = 0
    t_credit = 0
    for acc in all_accounts:
        if acc.is_summary: continue
        q = db.session.query(func.sum(LedgerEntry.debit), func.sum(LedgerEntry.credit)).filter_by(account_id=acc.id)
        q = q.join(JournalEntry).filter(JournalEntry.date >= from_date)
        q = q.filter(JournalEntry.date <= to_date)
        d, c = q.first()
        d, c = (d or 0), (c or 0)
        if d != 0 or c != 0:
            ws.append([acc.code, acc.name, d, c])
            t_debit += d
            t_credit += c
    ws.append(["Total", "TOTAL", t_debit, t_credit])

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f"Trial_Balance_{datetime.now().strftime('%Y-%m-%d')}.xlsx")

@reports_bp.route('/reports/export/balance-sheet')
def export_balance_sheet():
    from_date, to_date, from_date_str, to_date_str = get_dates()
    target_date = to_date # BS is usually as of date, we'll use 'to_date'
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Balance Sheet"
    from openpyxl.styles import Font, Alignment, PatternFill, Side, Border
    ws.append(["Assurance Sultan Legacy Flat Owners Association"])
    ws.append(["23/4, Katasur, Ser-E Bangla Road, Mohammadpur, Dhaka"])
    ws.append(["BALANCE SHEET STATEMENT"])
    ws.append([f"As Of Date: {to_date_str}"])
    ws.append([])
    
    # Styling
    last_col = "B"
    title_font = Font(size=16, bold=True, color="1E293B")
    addr_font = Font(size=10, color="64748B")
    report_title_font = Font(size=12, bold=True, color="4F46E5")
    
    for row_idx in [1, 2, 3, 4]:
        ws.merge_cells(f'A{row_idx}:{last_col}{row_idx}')
        cell = ws.cell(row=row_idx, column=1)
        cell.alignment = Alignment(horizontal="center")
        if row_idx == 1: cell.font = title_font
        elif row_idx == 2: cell.font = addr_font
        else: cell.font = report_title_font
    
    def add_section(title, acc_type, is_credit_balance):
        ws.append([title])
        total = 0
        accounts = Account.query.filter_by(type=acc_type).order_by(Account.code).all()
        for acc in accounts:
            if acc.is_summary: continue
            q = db.session.query(func.sum(LedgerEntry.debit), func.sum(LedgerEntry.credit)).join(JournalEntry).filter(LedgerEntry.account_id == acc.id, JournalEntry.date <= target_date)
            d, c = q.first()
            d, c = (d or 0), (c or 0)
            bal = (c - d) if is_credit_balance else (d - c)
            if bal != 0:
                ws.append([acc.name, bal])
                total += bal
        return total

    t_assets = add_section("ASSETS", "asset", False)
    ws.append(["Total Assets", t_assets])
    ws.append([])
    
    t_liabs = add_section("LIABILITIES", "liability", True)
    ws.append(["Total Liabilities", t_liabs])
    ws.append([])
    
    # Equity + Retained Earnings
    ws.append(["EQUITY"])
    t_equity = 0
    equity_accs = Account.query.filter_by(type='equity').all()
    for acc in equity_accs:
        if acc.is_summary: continue
        q = db.session.query(func.sum(LedgerEntry.debit), func.sum(LedgerEntry.credit)).join(JournalEntry).filter(LedgerEntry.account_id == acc.id, JournalEntry.date <= target_date)
        d, c = q.first()
        bal = (c or 0) - (d or 0)
        if bal != 0:
            ws.append([acc.name, bal])
            t_equity += bal
            
    # Retained Earnings
    rev_q = db.session.query(func.sum(LedgerEntry.credit - LedgerEntry.debit)).join(JournalEntry).join(Account).filter(Account.type == 'revenue', JournalEntry.date <= target_date).scalar() or 0
    exp_q = db.session.query(func.sum(LedgerEntry.debit - LedgerEntry.credit)).join(JournalEntry).join(Account).filter(Account.type == 'expense', JournalEntry.date <= target_date).scalar() or 0
    re = rev_q - exp_q
    ws.append(["Retained Earnings", re])
    ws.append(["Total Equity", t_equity + re])

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f"Balance_Sheet_{datetime.now().strftime('%Y-%m-%d')}.xlsx")

@reports_bp.route('/reports/export/ledger')
def export_ledger():
    account_id = request.args.get('account_id', type=int)
    from_date, to_date, from_date_str, to_date_str = get_dates()
    
    target_account = Account.query.get_or_404(account_id)
    
    q = LedgerEntry.query.join(JournalEntry).filter(LedgerEntry.account_id == target_account.id)
    q = q.filter(JournalEntry.date >= from_date)
    q = q.filter(JournalEntry.date <= to_date)
    entries = q.order_by(JournalEntry.date.asc()).all()
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Ledger_{target_account.code}"
    
    from openpyxl.styles import Font, Alignment, PatternFill, Side, Border
    ws.append(["Assurance Sultan Legacy Flat Owners Association"])
    ws.append(["23/4, Katasur, Ser-E Bangla Road, Mohammadpur, Dhaka"])
    ws.append([f"DETAILED LEDGER REPORT: {target_account.code}"])
    ws.append([f"{target_account.name} | Period: {from_date_str} to {to_date_str}"])
    ws.append([])
    
    last_col = "F"
    title_font = Font(size=16, bold=True, color="1E293B")
    addr_font = Font(size=10, color="64748B")
    report_title_font = Font(size=12, bold=True, color="4F46E5")
    
    for row_idx in [1, 2, 3, 4]:
        ws.merge_cells(f'A{row_idx}:{last_col}{row_idx}')
        cell = ws.cell(row=row_idx, column=1)
        cell.alignment = Alignment(horizontal="center")
        if row_idx == 1: cell.font = title_font
        elif row_idx == 2: cell.font = addr_font
        else: cell.font = report_title_font
    
    ws.append(["Date", "Reference", "Description", "Debit", "Credit", "Balance"])
    
    balance = 0
    for entry in entries:
        if target_account.type in ['asset', 'expense']:
            balance += (entry.debit - entry.credit)
        else:
            balance += (entry.credit - entry.debit)
            
        ws.append([
            entry.parent.date.strftime('%Y-%m-%d'),
            entry.parent.reference or 'JR',
            entry.parent.description,
            entry.debit,
            entry.credit,
            balance
        ])

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f"Ledger_{target_account.code}_{datetime.now().strftime('%Y-%m-%d')}.xlsx")

@reports_bp.route('/reports/export/aging')
def export_aging():
    from_date, to_date, from_date_str, to_date_str = get_dates()
    
    residents = Resident.query.all()
    aging_data = []
    
    for res in residents:
        q = LedgerEntry.query.join(JournalEntry).filter(LedgerEntry.account_id == 3930, JournalEntry.description.contains(res.name))
        q = q.filter(JournalEntry.date >= from_date)
        q = q.filter(JournalEntry.date <= to_date)
        
        balance = sum(e.debit - e.credit for e in q.all())
        if balance > 0:
            first_unpaid = q.filter(LedgerEntry.debit > LedgerEntry.credit).order_by(JournalEntry.date.asc()).first()
            days = (datetime.utcnow() - first_unpaid.parent.date).days if first_unpaid else 0
            cat = "0-30 days" if days <= 30 else "31-60 days" if days <= 60 else "61-90 days" if days <= 90 else "90+ days"
            aging_data.append({'customer': res.name, 'balance': balance, 'days': days, 'category': cat})

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "AR Aging"
    from openpyxl.styles import Font, Alignment, PatternFill, Side, Border
    ws.append(["Assurance Sultan Legacy Flat Owners Association"])
    ws.append(["23/4, Katasur, Ser-E Bangla Road, Mohammadpur, Dhaka"])
    ws.append(["ACCOUNTS RECEIVABLE AGING REPORT"])
    ws.append([f"Aging Basis: {from_date_str} to {to_date_str}"])
    ws.append([])
    
    last_col = "D"
    title_font = Font(size=16, bold=True, color="1E293B")
    addr_font = Font(size=10, color="64748B")
    report_title_font = Font(size=12, bold=True, color="4F46E5")
    
    for row_idx in [1, 2, 3, 4]:
        ws.merge_cells(f'A{row_idx}:{last_col}{row_idx}')
        cell = ws.cell(row=row_idx, column=1)
        cell.alignment = Alignment(horizontal="center")
        if row_idx == 1: cell.font = title_font
        elif row_idx == 2: cell.font = addr_font
        else: cell.font = report_title_font
    
    ws.append(["Customer", "Days Overdue", "Category", "Balance"])
    
    for item in aging_data:
        ws.append([item['customer'], item['days'], item['category'], item['balance']])
        
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f"AR_Aging_{datetime.now().strftime('%Y-%m-%d')}.xlsx")

@reports_bp.route('/reports/export/daily-cash')
def export_daily_cash():
    from_date, to_date, from_date_str, to_date_str = get_dates()
    
    q = LedgerEntry.query.join(Account).filter(Account.code.like('31%'))
    q = q.join(JournalEntry).filter(JournalEntry.date >= from_date)
    q = q.filter(JournalEntry.date <= to_date)
    entries = q.order_by(JournalEntry.date.desc()).all()
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Daily Cash"
    from openpyxl.styles import Font, Alignment, PatternFill, Side, Border
    ws.append(["Assurance Sultan Legacy Flat Owners Association"])
    ws.append(["23/4, Katasur, Ser-E Bangla Road, Mohammadpur, Dhaka"])
    ws.append(["DAILY CASH FLOW REPORT"])
    ws.append([f"Audit Period: {from_date_str} to {to_date_str}"])
    ws.append([])
    
    last_col = "F"
    title_font = Font(size=16, bold=True, color="1E293B")
    addr_font = Font(size=10, color="64748B")
    report_title_font = Font(size=12, bold=True, color="4F46E5")
    
    for row_idx in [1, 2, 3, 4]:
        ws.merge_cells(f'A{row_idx}:{last_col}{row_idx}')
        cell = ws.cell(row=row_idx, column=1)
        cell.alignment = Alignment(horizontal="center")
        if row_idx == 1: cell.font = title_font
        elif row_idx == 2: cell.font = addr_font
        else: cell.font = report_title_font
    
    ws.append(["Date", "Account", "Description", "Inflow (+)", "Outflow (-)", "Net"])
    
    for e in entries:
        inflow = e.debit if e.debit > 0 else 0
        outflow = e.credit if e.credit > 0 else 0
        ws.append([e.parent.date.strftime('%Y-%m-%d'), e.account.name, e.parent.description, inflow, outflow, inflow - outflow])
        
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f"Daily_Cash_{datetime.now().strftime('%Y-%m-%d')}.xlsx")

@reports_bp.route('/reports/export/due-report')
def export_due_report():
    from_date, to_date, from_date_str, to_date_str = get_dates()
    target_accs = Account.query.filter(Account.code.like('39%')).all()
    acc_ids = [a.id for a in target_accs]
    
    results = db.session.query(
        Customer.name,
        func.sum(LedgerEntry.debit) - func.sum(LedgerEntry.credit)
    ).join(LedgerEntry, Customer.id == LedgerEntry.customer_id)\
     .join(JournalEntry)\
     .filter(LedgerEntry.account_id.in_(acc_ids))\
     .filter(JournalEntry.date >= from_date)\
     .filter(JournalEntry.date <= to_date)\
     .group_by(Customer.id, Customer.name).all()

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Due Report"
    from openpyxl.styles import Font, Alignment, PatternFill, Side, Border
    ws.append(["Assurance Sultan Legacy Flat Owners Association"])
    ws.append(["23/4, Katasur, Ser-E Bangla Road, Mohammadpur, Dhaka"])
    ws.append(["CUSTOMER OUTSTANDING BALANCES"])
    ws.append([f"Reference Period: {from_date_str} to {to_date_str}"])
    ws.append([])
    
    last_col = "B"
    title_font = Font(size=16, bold=True, color="1E293B")
    addr_font = Font(size=10, color="64748B")
    report_title_font = Font(size=12, bold=True, color="4F46E5")
    
    for row_idx in [1, 2, 3, 4]:
        ws.merge_cells(f'A{row_idx}:{last_col}{row_idx}')
        cell = ws.cell(row=row_idx, column=1)
        cell.alignment = Alignment(horizontal="center")
        if row_idx == 1: cell.font = title_font
        elif row_idx == 2: cell.font = addr_font
        else: cell.font = report_title_font
    
    ws.append(["Customer Name", "Outstanding Amount"])
    
    for name, balance in results:
        if balance != 0:
            ws.append([name, balance])
            
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f"Due_Report_{datetime.now().strftime('%Y-%m-%d')}.xlsx")
