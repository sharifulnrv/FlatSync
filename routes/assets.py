from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from models import db, Asset, AssetCategory, AssetTransaction, Party, Account, LedgerEntry, JournalEntry
from utils.accounting import record_journal_entry
from utils.pdf_generator import render_to_pdf
from datetime import datetime

assets_bp = Blueprint('assets', __name__)

@assets_bp.route('/assets')
def list_assets():
    assets = Asset.query.all()
    categories = AssetCategory.query.all()
    return render_template('assets.html', assets=assets, categories=categories)

@assets_bp.route('/assets/add', methods=['POST'])
def add_asset():
    name = request.form.get('name')
    category_id = request.form.get('category_id')
    cost = float(request.form.get('cost', 0))
    purchase_date_str = request.form.get('purchase_date')
    
    purchase_date = datetime.strptime(purchase_date_str, '%Y-%m-%d').date() if purchase_date_str else None
    
    new_asset = Asset(name=name, category_id=category_id, purchase_cost=cost, purchase_date=purchase_date)
    db.session.add(new_asset)
    db.session.commit()
    flash('Asset recorded successfully', 'success')
    return redirect(url_for('assets.list_assets'))

@assets_bp.route('/assets/categories/add', methods=['POST'])
def add_category():
    name = request.form.get('name')
    if name:
        new_cat = AssetCategory(name=name)
        db.session.add(new_cat)
        db.session.commit()
        flash('Category added', 'success')
    return redirect(url_for('assets.list_assets'))

@assets_bp.route('/assets/categories/edit/<int:id>', methods=['POST'])
def edit_category(id):
    category = AssetCategory.query.get_or_404(id)
    name = request.form.get('name')
    if name:
        category.name = name
        db.session.commit()
        flash('Category updated', 'success')
    return redirect(url_for('assets.list_assets'))

@assets_bp.route('/assets/categories/delete/<int:id>', methods=['POST'])
def delete_category(id):
    category = AssetCategory.query.get_or_404(id)
    # Check if any assets are linked to this category
    if category.assets:
        flash('Cannot delete category with linked assets', 'error')
    else:
        db.session.delete(category)
        db.session.commit()
        flash('Category deleted', 'success')
    return redirect(url_for('assets.list_assets'))

@assets_bp.route('/assets/edit/<int:id>', methods=['POST'])
def edit_asset(id):
    asset = Asset.query.get_or_404(id)
    asset.name = request.form.get('name')
    asset.category_id = request.form.get('category_id')
    asset.purchase_cost = float(request.form.get('cost', 0))
    p_date = request.form.get('purchase_date')
    if p_date:
        asset.purchase_date = datetime.strptime(p_date, '%Y-%m-%d').date()
    db.session.commit()
    flash('Asset updated', 'success')
    return redirect(url_for('assets.list_assets'))

@assets_bp.route('/assets/delete/<int:id>', methods=['POST'])
def delete_asset(id):
    asset = Asset.query.get_or_404(id)
    db.session.delete(asset)
    db.session.commit()
    flash('Asset deleted', 'success')
    return redirect(url_for('assets.list_assets'))

@assets_bp.route('/assets/<int:id>/ledger')
def asset_ledger(id):
    asset = Asset.query.get_or_404(id)
    parties = Party.query.all()
    # Support both liquid (31xx) and payables (47xx) for transactions
    payment_accounts = Account.query.filter(
        (Account.code.like('31%')) | (Account.code.like('47%')),
        Account.is_summary == False
    ).all()
    
    # Fetch all ledger entries tagged with this asset
    entries = LedgerEntry.query.filter_by(asset_id=id).join(JournalEntry).order_by(JournalEntry.date.desc()).all()
    
    return render_template('asset_ledger.html', 
                            asset=asset, 
                            parties=parties, 
                            payment_accounts=payment_accounts,
                            ledger_entries=entries)

@assets_bp.route('/assets/<int:id>/add-transaction', methods=['POST'])
def add_asset_transaction(id):
    asset = Asset.query.get_or_404(id)
    description = request.form.get('description')
    amount = float(request.form.get('amount', 0))
    t_type = request.form.get('type', 'maintenance')
    party_id = request.form.get('party_id', type=int) or None
    account_code = request.form.get('account_code') # Selected payment or liability account
    date_str = request.form.get('date')
    
    date = datetime.strptime(date_str, '%Y-%m-%d') if date_str else datetime.utcnow()
    
    # Integrated Accounting Logic
    dr_code = ""
    cr_code = ""
    
    if t_type == 'maintenance':
        dr_code = '5100' # Management & Operating
        cr_code = account_code or '3110' # Generic liquid or payable
    elif t_type == 'depreciation':
        dr_code = '5900' # Depreciation Expense
        cr_code = '3010' # Fixed Assets
    elif t_type == 'sale':
        dr_code = account_code or '3110'
        cr_code = '3010'
    elif t_type == 'appreciation':
        dr_code = '3010'
        cr_code = '4900' # Other Income
    
    # Record in Ledger if we have accounts
    journal_id = None
    if dr_code and cr_code:
        # Tag the expense line with asset_id for maintenance
        asset_tag_id = id if t_type == 'maintenance' else None
        
        items = [
            {'account_code': dr_code, 'debit': amount, 'credit': 0, 'party_id': party_id, 'asset_id': asset_tag_id},
            {'account_code': cr_code, 'debit': 0, 'credit': amount, 'party_id': party_id}
        ]
        journal = record_journal_entry(f"Asset {t_type.capitalize()}: {asset.name} - {description}", items, reference=f"AST-{asset.id}", date=date)
        journal_id = journal.id
    
    transaction = AssetTransaction(
        asset_id=id, 
        description=description, 
        amount=amount, 
        type=t_type, 
        date=date.date(),
        party_id=party_id,
        journal_id=journal_id
    )
    db.session.add(transaction)
    db.session.commit()
    
    flash(f'Transaction recorded and posted to ledger (Journal #{journal_id})', 'success')
    return redirect(url_for('assets.asset_ledger', id=id))

@assets_bp.route('/assets/transaction/<int:tid>/pdf')
def download_asset_voucher(tid):
    transaction = AssetTransaction.query.get_or_404(tid)
    pdf_content = render_to_pdf('reports/asset_voucher.html', {'transaction': transaction})
    if pdf_content:
        return send_file(
            BytesIO(pdf_content),
            download_name=f"Voucher_AST_{tid}.pdf",
            as_attachment=True
        )
    return "Error generating PDF", 500

from io import BytesIO # Added for send_file in download route
