from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Asset, AssetCategory, AssetTransaction
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
    return render_template('asset_ledger.html', asset=asset)

@assets_bp.route('/assets/<int:id>/add-transaction', methods=['POST'])
def add_asset_transaction(id):
    asset = Asset.query.get_or_404(id)
    description = request.form.get('description')
    amount = float(request.form.get('amount', 0))
    t_type = request.form.get('type', 'maintenance')
    date_str = request.form.get('date')
    
    date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else datetime.utcnow().date()
    
    transaction = AssetTransaction(asset_id=id, description=description, amount=amount, type=t_type, date=date)
    db.session.add(transaction)
    db.session.commit()
    flash('Transaction recorded in asset history', 'success')
    return redirect(url_for('assets.asset_ledger', id=id))
