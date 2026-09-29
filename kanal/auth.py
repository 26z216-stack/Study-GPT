from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from . import db
from .models import User

auth = Blueprint('auth', __name__)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('planner.dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, request.form.get('password', '')):
            login_user(user, remember=True)
            return redirect(url_for('planner.dashboard'))
        flash('Wrong email or password.', 'error')
    return render_template('login.html')


@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('planner.dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        name = request.form.get('name', '').strip()
        password = request.form.get('password', '')
        if not email or '@' not in email:
            flash('Enter a valid email.', 'error')
        elif not name:
            flash('Enter your name.', 'error')
        elif len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
        elif User.query.filter_by(email=email).first():
            flash('An account with that email already exists.', 'error')
        else:
            user = User(email=email, name=name, password_hash=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            login_user(user, remember=True)
            return redirect(url_for('planner.subjects'))
    return render_template('signup.html')


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
