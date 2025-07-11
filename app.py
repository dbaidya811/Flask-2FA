import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import pyotp
import qrcode
import io
from PIL import Image
import secrets
from flask_migrate import Migrate

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'  # Change this in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)  # Flask-Migrate initialization

# User model for SQLite
# Stores email, password hash, TOTP secret, and failed login attempts
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    totp_secret = db.Column(db.String(16))
    failed_attempts = db.Column(db.Integer, default=0)
    api_key = db.Column(db.String(64), unique=True, nullable=True)  # New field

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_totp_uri(self):
        # Returns the otpauth URI for Google Authenticator
        return f"otpauth://totp/Flask2FA:{self.email}?secret={self.totp_secret}&issuer=Flask2FA"

# Remove the @app.before_first_request create_tables function

MAX_FAILED_ATTEMPTS = 5  # Lock account after 5 failed attempts

@app.route('/')
def home():
    return redirect(url_for('register'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration route."""
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return redirect(url_for('register'))
        user = User(email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login route. Checks password and handles brute-force protection."""
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        # Check for lockout
        if user and user.failed_attempts >= MAX_FAILED_ATTEMPTS:
            flash('Account locked due to too many failed attempts. Please contact support or logout to reset.', 'danger')
            return redirect(url_for('login'))
        # Check credentials
        if not user or not user.check_password(password):
            if user:
                user.failed_attempts += 1
                db.session.commit()
            flash('Invalid email or password.', 'danger')
            return redirect(url_for('login'))
        # Reset failed attempts on successful login
        user.failed_attempts = 0
        db.session.commit()
        session['user_id'] = user.id
        # If first login, generate TOTP secret and redirect to QR setup
        if not user.totp_secret:
            secret = pyotp.random_base32()
            user.totp_secret = secret
            db.session.commit()
            return redirect(url_for('qr'))
        else:
            # If TOTP already set, go to OTP verification
            return redirect(url_for('verify_otp'))
    return render_template('login.html')

@app.route('/generate-api-key', methods=['POST'])
def generate_api_key():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    user = User.query.get(user_id)
    if user and not user.api_key:
        import secrets
        user.api_key = secrets.token_hex(32)
        db.session.commit()
        flash('API Key generated successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/qr')
def qr():
    """Display QR code for Google Authenticator setup."""
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    user = User.query.get(user_id)
    if not user or not user.totp_secret:
        return redirect(url_for('login'))
    # Generate QR code for Google Authenticator
    totp_uri = user.get_totp_uri()
    qr_img = qrcode.make(totp_uri)
    buf = io.BytesIO()
    qr_img.save(buf, format='PNG')
    buf.seek(0)
    qr_data = buf.getvalue()
    import base64
    qr_b64 = base64.b64encode(qr_data).decode('utf-8')
    return render_template('qr.html', qr_b64=qr_b64, secret=user.totp_secret)

@app.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    """OTP verification route. Checks TOTP code and brute-force protection."""
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    user = User.query.get(user_id)
    if not user or not user.totp_secret:
        return redirect(url_for('login'))
    # Check for lockout
    if user.failed_attempts >= MAX_FAILED_ATTEMPTS:
        flash('Account locked due to too many failed attempts. Please contact support or logout to reset.', 'danger')
        return redirect(url_for('login'))
    if request.method == 'POST':
        otp = request.form['otp']
        totp = pyotp.TOTP(user.totp_secret)
        if totp.verify(otp, valid_window=1):
            user.failed_attempts = 0
            db.session.commit()
            session['authenticated'] = True
            flash('2FA verification successful! You are logged in.', 'success')
            return redirect(url_for('dashboard'))
        else:
            user.failed_attempts += 1
            db.session.commit()
            flash('Invalid OTP. Please try again.', 'danger')
    return render_template('verify_otp.html')

@app.route('/dashboard')
def dashboard():
    """Protected dashboard page. Only accessible after 2FA."""
    if not session.get('authenticated'):
        return redirect(url_for('login'))
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    # API info for dashboard
    api_link = request.url_root.rstrip('/') + '/api/2fa/verify'
    return render_template('dashboard.html', email=user.email, api_key=user.api_key, api_link=api_link)

@app.route('/logout')
def logout():
    """Logout route. Clears session and resets failed attempts (for demo)."""
    user_id = session.get('user_id')
    if user_id:
        user = User.query.get(user_id)
        if user:
            user.failed_attempts = 0  # Reset lockout on logout for demo
            db.session.commit()
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/delete-account', methods=['POST'])
def delete_account():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    user = User.query.get(user_id)
    if user:
        db.session.delete(user)
        db.session.commit()
    session.clear()
    flash('Your account has been deleted.', 'info')
    return redirect(url_for('login'))

# --- API Endpoints for 2FA Integration ---

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({'success': False, 'message': 'Email and password required.'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'message': 'Email already registered.'}), 409
    user = User(email=email)
    user.set_password(password)
    # Generate API key
    user.api_key = secrets.token_hex(32)
    db.session.add(user)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Registration successful!', 'user_id': user.id}), 201

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({'success': False, 'message': 'Invalid email or password.'}), 401
    # If first login, generate TOTP secret
    if not user.totp_secret:
        secret = pyotp.random_base32()
        user.totp_secret = secret
        db.session.commit()
    # Generate API key if not exists
    if not user.api_key:
        user.api_key = secrets.token_hex(32)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Login successful. Proceed to 2FA.', 'user_id': user.id}), 200

@app.route('/api/2fa/init', methods=['POST'])
def api_2fa_init():
    data = request.get_json()
    user_id = data.get('user_id')
    user = User.query.get(user_id)
    if not user or not user.totp_secret:
        return jsonify({'success': False, 'message': 'User not found or TOTP not set.'}), 404
    totp_uri = user.get_totp_uri()
    import base64
    qr_img = qrcode.make(totp_uri)
    buf = io.BytesIO()
    qr_img.save(buf, format='PNG')
    buf.seek(0)
    qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    return jsonify({'success': True, 'secret': user.totp_secret, 'qr_b64': qr_b64, 'otpauth_url': totp_uri}), 200

@app.route('/api/2fa/verify', methods=['POST'])
def api_2fa_verify():
    # API Key authentication
    api_key = request.headers.get('X-API-KEY')
    if not api_key:
        return jsonify({'success': False, 'message': 'API Key required in X-API-KEY header.'}), 401
    user = User.query.filter_by(api_key=api_key).first()
    if not user or not user.totp_secret:
        return jsonify({'success': False, 'message': 'Invalid API Key or TOTP not set.'}), 403
    data = request.get_json()
    otp = data.get('otp')
    totp = pyotp.TOTP(user.totp_secret)
    if totp.verify(otp, valid_window=1):
        return jsonify({'success': True, 'message': '2FA verification successful!'}), 200
    else:
        return jsonify({'success': False, 'message': 'Invalid OTP.'}), 401

@app.route('/api-docs')
def api_docs():
    return render_template('api_docs.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 