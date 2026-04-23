from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from models import User, db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(username=username).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash('Please check your login details and try again.', 'danger')
            return redirect(url_for('auth.login'))

        login_user(user, remember=remember)
        return redirect(url_for('main.index'))

    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile', methods=['GET'])
@login_required
def profile():
    return render_template('auth/profile.html')

@auth_bp.route('/profile/update-info', methods=['POST'])
@login_required
def update_profile_info():
    new_username = request.form.get('username')
    
    if not new_username:
        flash('Username cannot be empty.', 'warning')
        return redirect(url_for('auth.profile'))
        
    # Check if username exists and it's not the current user
    existing = User.query.filter_by(username=new_username).first()
    if existing and existing.id != current_user.id:
        flash('That username is already taken. Please choose another.', 'danger')
        return redirect(url_for('auth.profile'))
        
    current_user.username = new_username
    db.session.commit()
    
    flash('Identity updated successfully!', 'success')
    return redirect(url_for('auth.profile'))

@auth_bp.route('/profile/change-password', methods=['POST'])
@login_required
def change_password():
    current_pw = request.form.get('current_password')
    new_pw = request.form.get('new_password')
    confirm_pw = request.form.get('confirm_password')

    if not check_password_hash(current_user.password_hash, current_pw):
        flash('Verification failed: Current password incorrect.', 'danger')
        return redirect(url_for('auth.profile'))

    if new_pw != confirm_pw:
        flash('Confirmation failed: New passwords do not match.', 'danger')
        return redirect(url_for('auth.profile'))

    if len(new_pw) < 4:
        flash('Password too short. Minimum 4 characters required.', 'warning')
        return redirect(url_for('auth.profile'))

    current_user.password_hash = generate_password_hash(new_pw)
    db.session.commit()

    flash('Security credentials updated successfully!', 'success')
    return redirect(url_for('auth.profile'))
