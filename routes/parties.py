from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, Party

parties_bp = Blueprint('parties', __name__)

@parties_bp.route('/parties')
def list_parties():
    parties = Party.query.all()
    from models import Account
    accounts = Account.query.all()
    return render_template('parties_list.html', parties=parties, accounts=accounts)

@parties_bp.route('/parties/add', methods=['POST'])
def add_party():
    name = request.form.get('name')
    type = request.form.get('type')
    default_account_code = request.form.get('default_account_code')
    phone = request.form.get('phone')
    address = request.form.get('address')
    
    if not name:
        flash('Name is required', 'error')
        return redirect(url_for('parties.list_parties'))
        
    party = Party(name=name, type=type, default_account_code=default_account_code, phone=phone, address=address)
    db.session.add(party)
    db.session.commit()
    flash(f'Party {name} added successfully', 'success')
    return redirect(url_for('parties.list_parties'))

@parties_bp.route('/parties/delete/<int:id>', methods=['POST'])
def delete_party(id):
    party = Party.query.get_or_404(id)
    name = party.name
    db.session.delete(party)
    db.session.commit()
    flash(f'Party {name} deleted', 'success')
    return redirect(url_for('parties.list_parties'))

@parties_bp.route('/parties/<int:id>')
def party_profile(id):
    party = Party.query.get_or_404(id)
    from_date = request.args.get('from_date')
    to_date = request.args.get('to_date')
    
    from models import LedgerEntry
    query = LedgerEntry.query.filter_by(party_id=id)
    
    if from_date:
        query = query.join(LedgerEntry.parent).filter(db.func.date(LedgerEntry.parent.date) >= from_date)
    if to_date:
        query = query.join(LedgerEntry.parent).filter(db.func.date(LedgerEntry.parent.date) <= to_date)
        
    history = query.all()
    
    # Balance = Total Debits - Total Credits
    debit_total = sum(e.debit for e in history)
    credit_total = sum(e.credit for e in history)
    balance = debit_total - credit_total
    
    return render_template('party_profile.html', 
                           party=party, 
                           history=history, 
                           balance=balance,
                           from_date=from_date,
                           to_date=to_date)
