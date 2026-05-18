from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from models import User, db
import random
from utils.email_sender import send_otp_email

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

        # Generate and send OTP
        otp = str(random.randint(100000, 999999))
        session['otp'] = otp
        session['pre_auth_user_id'] = user.id
        session['remember_me'] = remember
        
        send_otp_email(otp)
        
        flash('Authorization code sent to the administrator.', 'info')
        return redirect(url_for('auth.verify_otp'))

    return render_template('auth/login.html')

@auth_bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    from flask import current_app
    
    if 'pre_auth_user_id' not in session:
        flash('Session expired or invalid.', 'danger')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        user_otp = request.form.get('otp')
        actual_otp = session.get('otp')
        
        # Check if Test OTP is enabled
        test_mode_enabled = current_app.config.get('TESTOTP', False)
        
        if user_otp == actual_otp or (test_mode_enabled and user_otp == '999999'):
            user = User.query.get(session.get('pre_auth_user_id'))
            if user:
                login_user(user, remember=session.get('remember_me', False))
                # Clear session variables
                session.pop('otp', None)
                session.pop('pre_auth_user_id', None)
                session.pop('remember_me', None)
                return redirect(url_for('main.index'))
        
        flash('Invalid verification code.', 'danger')
    
    return render_template('auth/verify_otp.html')

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
