from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
from sqlalchemy import or_

# Import models from models.py
from models import db, User, Event

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = 'secret123'

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Flask-Login user loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        is_admin = True if request.form.get('is_admin') == 'on' else False

        if not username or not email or not password:
            flash('All fields are required!', 'error')
            return redirect(url_for('register'))

        # ✅ Check if user already exists
        existing_user = User.query.filter(or_(User.username == username, User.email == email)).first()
        if existing_user:
            flash('Username or Email already exists!', 'error')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, password=hashed_password, is_admin=is_admin)
        db.session.add(new_user)
        db.session.commit()
        flash('Registered successfully. Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        role = request.form.get('role')

        user = User.query.filter_by(username=username).first()

        if not user or not check_password_hash(user.password, password):
            flash('Invalid username or password.', 'error')
            return redirect(url_for('login'))

        if role == "Admin" and not user.is_admin:
            flash("You are not authorized to log in as Admin!", "error")
            return redirect(url_for('login'))

        elif role == "Student" and user.is_admin:
            flash("Admins cannot log in as Students!", "error")
            return redirect(url_for('login'))

        login_user(user)
        flash('Login successful!', 'success')
        return redirect(url_for('admin_dashboard') if user.is_admin else url_for('student_dashboard'))

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin:
        return "Unauthorized", 403

    # ✅ Optional: Add pagination for events and users
    events = Event.query.order_by(Event.date.desc()).all()
    users = User.query.all()
    return render_template('admin_dashboard.html', events=events, users=users)

@app.route('/student_dashboard')
@login_required
def student_dashboard():
    events = Event.query.order_by(Event.date.desc()).all()
    return render_template('student_dashboard.html', events=events)

@app.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if not current_user.is_admin:
        return "Unauthorized", 403

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        date_str = request.form.get('date', '').strip()
        location = request.form.get('location', '').strip()

        if not name or not description or not date_str or not location:
            flash('All fields are required!', 'error')
            return redirect(url_for('create'))

        try:
            date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash("Invalid date format!", "error")
            return redirect(url_for('create'))

        new_event = Event(name=name, description=description, date=date, location=location)
        db.session.add(new_event)
        db.session.commit()
        flash('Event created successfully!', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('create_event.html')

@app.route('/event/<int:event_id>')
@login_required
def event(event_id):
    event = Event.query.get_or_404(event_id)
    return render_template('event.html', event=event)

@app.route('/edit/<int:event_id>', methods=['GET', 'POST'])
@login_required
def edit(event_id):
    if not current_user.is_admin:
        return "Unauthorized", 403

    event = Event.query.get_or_404(event_id)

    if request.method == 'POST':
        event.name = request.form.get('name', '').strip()
        date_str = request.form.get('date', '').strip()
        event.location = request.form.get('location', '').strip()
        event.description = request.form.get('description', '').strip()

        if not event.name or not date_str or not event.location or not event.description:
            flash('All fields are required!', 'error')
            return redirect(url_for('edit', event_id=event_id))

        try:
            event.date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        except ValueError:
            flash("Invalid date format!", "error")
            return redirect(url_for('edit', event_id=event_id))

        db.session.commit()
        flash('Event updated successfully!', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('edit.html', event=event)

@app.route('/delete/<int:event_id>', methods=['POST'])
@login_required
def delete(event_id):
    if not current_user.is_admin:
        return "Unauthorized", 403

    event = Event.query.get_or_404(event_id)
    db.session.delete(event)
    db.session.commit()
    flash('Event deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

# Run
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
