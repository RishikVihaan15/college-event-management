from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from models import db, User, Event, Registration, Notification, ChatMessage
from flask_migrate import Migrate

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('admin_dashboard' if user.role == 'admin' else 'student_dashboard'))
        flash('Invalid username or password', 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
        else:
            new_user = User(
                username=username,
                password=generate_password_hash(password),
                role='student'
            )
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please login', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('student_dashboard'))
    events = Event.query.all()
    return render_template('admin_dashboard.html', events=events)

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.role != 'student':
        return redirect(url_for('admin_dashboard'))
    events = Event.query.all()
    return render_template('student_dashboard.html', events=events)

@app.route('/event/<int:event_id>')
@login_required
def view_event(event_id):
    event = Event.query.get_or_404(event_id)
    registered = Registration.query.filter_by(
        user_id=current_user.id,
        event_id=event.id
    ).first()
    return render_template('event.html', event=event, registered=registered)

@app.route('/create_event', methods=['GET', 'POST'])
@login_required
def create_event():
    if current_user.role != 'admin':
        return redirect(url_for('student_dashboard'))
    
    if request.method == 'POST':
        try:
            event = Event(
                name=request.form['name'],
                description=request.form['description'],
                date=datetime.strptime(request.form['date'], '%Y-%m-%dT%H:%M'),
                location=request.form['location'],
                max_seats=int(request.form.get('max_seats', 100)),
                registration_fee=float(request.form.get('registration_fee', 0.0))
            )
            db.session.add(event)
            db.session.commit()
            flash('Event created successfully!', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating event: {str(e)}', 'danger')
    return render_template('create_event.html')

@app.route('/edit_event/<int:event_id>', methods=['GET', 'POST'])
@login_required
def edit_event(event_id):
    if current_user.role != 'admin':
        return redirect(url_for('student_dashboard'))
    
    event = Event.query.get_or_404(event_id)
    if request.method == 'POST':
        try:
            event.name = request.form['name']
            event.description = request.form['description']
            event.date = datetime.strptime(request.form['date'], '%Y-%m-%dT%H:%M')
            event.location = request.form['location']
            event.max_seats = int(request.form.get('max_seats', 100))
            event.registration_fee = float(request.form.get('registration_fee', 0.0))
            db.session.commit()
            flash('Event updated successfully!', 'success')
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating event: {str(e)}', 'danger')
    return render_template('edit_event.html', event=event)

@app.route('/delete_event/<int:event_id>', methods=['POST'])
@login_required
def delete_event(event_id):
    if current_user.role != 'admin':
        return redirect(url_for('student_dashboard'))
    
    event = Event.query.get_or_404(event_id)
    try:
        # Delete all related registrations first
        Registration.query.filter_by(event_id=event.id).delete()
        # Then delete the event
        db.session.delete(event)
        db.session.commit()
        flash('Event deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting event: {str(e)}', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/register_event/<int:event_id>', methods=['GET', 'POST'])
@login_required
def register_event(event_id):
    if current_user.role != 'student':
        return redirect(url_for('admin_dashboard'))
    
    event = Event.query.get_or_404(event_id)
    if Registration.query.filter_by(user_id=current_user.id, event_id=event.id).first():
        flash('You are already registered for this event', 'info')
        return redirect(url_for('student_dashboard'))
    
    if request.method == 'POST':
        try:
            # Check seat availability
            registered_count = Registration.query.filter_by(event_id=event.id).count()
            if registered_count >= event.max_seats:
                flash('No seats available for this event', 'danger')
                return redirect(url_for('student_dashboard'))
            
            # Automatically confirm registration (no admin approval needed)
            registration = Registration(
                user_id=current_user.id,
                event_id=event.id,
                payment_amount=event.registration_fee,
                payment_status=True,
                is_confirmed=True  # Auto-confirm registration
            )
            db.session.add(registration)
            
            # Create notification for student
            notification = Notification(
                user_id=current_user.id,
                event_id=event.id,
                message=f"Your registration for {event.name} is confirmed!"
            )
            db.session.add(notification)
            
            db.session.commit()
            flash('Registration successful!', 'success')
            return redirect(url_for('student_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error registering for event: {str(e)}', 'danger')
    return render_template('register_event.html', event=event)

@app.route('/chat')
@login_required
def chat():
    messages = ChatMessage.query.filter(
        (ChatMessage.sender_id == current_user.id) | 
        (ChatMessage.receiver_id == current_user.id)
    ).order_by(ChatMessage.timestamp.asc()).all()
    return render_template('chat.html', messages=messages)

@app.route('/admin/chat')
@login_required
def admin_chat():
    if current_user.role != 'admin':
        return redirect(url_for('chat'))
    
    messages = ChatMessage.query.filter(
        (ChatMessage.sender_id == current_user.id) | 
        (ChatMessage.receiver_id == current_user.id)
    ).order_by(ChatMessage.timestamp.asc()).all()
    
    return render_template('admin_chat.html', messages=messages)

@app.route('/send_message', methods=['POST'])
@login_required
def send_message():
    content = request.form.get('content')
    if not content:
        return jsonify({'success': False, 'message': 'Message cannot be empty'})
    
    try:
        receiver_id = 1 if current_user.role == 'student' else request.form.get('student_id')
        message = ChatMessage(
            sender_id=current_user.id,
            receiver_id=receiver_id,
            content=content
        )
        db.session.add(message)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                password=generate_password_hash('admin123'),
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
    app.run(debug=True)