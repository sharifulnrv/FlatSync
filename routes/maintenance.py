from flask import Blueprint, render_template, request, redirect, url_for, flash
from models import db, MaintenanceTicket, Unit
from datetime import datetime

maintenance_bp = Blueprint('maintenance', __name__)

@maintenance_bp.route('/maintenance')
def list_tickets():
    tickets = MaintenanceTicket.query.order_by(MaintenanceTicket.created_at.desc()).all()
    units = Unit.query.filter_by(status='occupied').all()
    return render_template('maintenance.html', tickets=tickets, units=units)

@maintenance_bp.route('/maintenance/add', methods=['POST'])
def add_ticket():
    unit_id = request.form.get('unit_id')
    description = request.form.get('description')
    
    if unit_id and description:
        ticket = MaintenanceTicket(unit_id=unit_id, description=description)
        db.session.add(ticket)
        db.session.commit()
        flash('Maintenance ticket created', 'success')
    return redirect(url_for('maintenance.list_tickets'))

@maintenance_bp.route('/maintenance/resolve/<int:ticket_id>', methods=['POST'])
def resolve_ticket(ticket_id):
    ticket = MaintenanceTicket.query.get_or_404(ticket_id)
    ticket.status = 'resolved'
    db.session.commit()
    flash('Ticket marked as resolved', 'success')
    return redirect(url_for('maintenance.list_tickets'))
