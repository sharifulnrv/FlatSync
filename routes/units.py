from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Unit, Customer, LedgerEntry, Account
from sqlalchemy import func
from datetime import datetime

units_bp = Blueprint('units', __name__)

@units_bp.route('/units')
def list_units():
    units = Unit.query.all()
    customers = Customer.query.all()
    return render_template('units.html', units=units, customers=customers)

@units_bp.route('/units/add', methods=['POST'])
def add_unit():
    unit_number = request.form.get('unit_number')
    new_unit = Unit(unit_number=unit_number, monthly_charge=0)
    db.session.add(new_unit)
    db.session.commit()
    flash('Unit added successfully', 'success')
    return redirect(url_for('units.list_units'))

@units_bp.route('/customers/add', methods=['POST'])
def add_customer():
    name = request.form.get('name')
    phone = request.form.get('phone')
    address = request.form.get('address')
    unit_id = request.form.get('unit_id')
    
    new_customer = Customer(name=name, phone=phone, address=address)
    db.session.add(new_customer)
    db.session.flush()
    
    if unit_id:
        unit = Unit.query.get(unit_id)
        if unit:
            unit.customer_id = new_customer.id
            unit.status = 'occupied'
            
    db.session.commit()
    flash('Customer added successfully', 'success')
    return redirect(url_for('units.list_units'))

@units_bp.route('/units/edit/<int:id>', methods=['POST'])
def edit_unit(id):
    unit = Unit.query.get_or_404(id)
    unit.unit_number = request.form.get('unit_number')
    db.session.commit()
    flash('Unit updated', 'success')
    return redirect(url_for('units.list_units'))

@units_bp.route('/units/delete/<int:id>', methods=['POST'])
def delete_unit(id):
    unit = Unit.query.get_or_404(id)
    db.session.delete(unit)
    db.session.commit()
    flash('Unit deleted', 'success')
    return redirect(url_for('units.list_units'))

@units_bp.route('/customers/edit/<int:id>', methods=['POST'])
def edit_customer(id):
    customer = Customer.query.get_or_404(id)
    customer.name = request.form.get('name')
    customer.phone = request.form.get('phone')
    customer.address = request.form.get('address')
    db.session.commit()
    flash('Customer updated', 'success')
    return redirect(url_for('units.list_units'))

@units_bp.route('/customers/profile/<int:id>')
def customer_profile(id):
    customer = Customer.query.get_or_404(id)
    # Get all ledger entries for this customer
    history = LedgerEntry.query.filter_by(customer_id=id).order_by(LedgerEntry.id.desc()).all()
    # Calculate current balance
    ar_acc = Account.query.filter(Account.code.like('39%')).first() # Use 3930 or similar
    balance = 0
    if ar_acc:
        debits = db.session.query(func.sum(LedgerEntry.debit)).filter_by(customer_id=id, account_id=ar_acc.id).scalar() or 0
        credits = db.session.query(func.sum(LedgerEntry.credit)).filter_by(customer_id=id, account_id=ar_acc.id).scalar() or 0
        balance = debits - credits
    return render_template('customer_profile.html', customer=customer, history=history, balance=balance)
