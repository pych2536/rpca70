import os
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import pytz # For timezone handling
from werkzeug.utils import secure_filename

# --- App Initialization & Configuration ---
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Database Configuration from Environment Variable
# This is the key that connects to the PostgreSQL DB on Render
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bangkok_tz = pytz.timezone('Asia/Bangkok')

# --- Configuration ---
ADMIN_USERNAME = "RPCA70-Admin"
ADMIN_PASSWORD = "Admin70-1234"
UPLOAD_FOLDER = '/var/data/uploads' # Use Render's persistent disk for uploads
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- Database Model ---
# This class defines the structure of our database table.
# It should match the columns in your CSV file.
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ลำดับ = db.Column(db.Integer, unique=True, nullable=False)
    # Add all other columns from your CSV here as db.String or db.Integer
    # Example:
    ยศ_คำนำหน้าชื่อ = db.Column(db.String(100))
    ชื่อ = db.Column(db.String(100), nullable=False)
    นามสกุล = db.Column(db.String(100), nullable=False)
    ชื่อเล่น = db.Column(db.String(100))
    ตำแหน่ง = db.Column(db.String(255))
    เบอร์โทรศัพท์ = db.Column(db.String(50))
    # ... add all your other columns ...
    
    # Tracking columns
    สถานะอัปเดต = db.Column(db.String(50), default='ยังไม่ได้ยืนยัน')
    วันที่อัปเดตล่าสุด = db.Column(db.String(100), default='ข้อมูล ณ วันที่ 15 เมษายน 2567')

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

# --- Helper to create the table initially ---
with app.app_context():
    db.create_all()
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)


# --- Routes (Now using Database queries) ---

@app.route('/')
def index():
    # This route remains the same
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()

    # Query the database instead of reading a CSV
    user = User.query.filter(db.func.lower(User.ชื่อ) == first_name.lower(), 
                             db.func.lower(User.นามสกุล) == last_name.lower()).first()

    if user:
        return redirect(url_for('view_profile', user_id=user.ลำดับ))
    else:
        flash("ไม่พบข้อมูลของคุณ กรุณาตรวจสอบการสะกดและลองใหม่อีกครั้ง", "error")
        return redirect(url_for('index'))

@app.route('/view/<int:user_id>')
def view_profile(user_id):
    user = User.query.filter_by(ลำดับ=user_id).first_or_404()
    return render_template('view.html', user=user.to_dict())

@app.route('/confirm/<int:user_id>')
def confirm_profile(user_id):
    user = User.query.filter_by(ลำดับ=user_id).first_or_404()
    user.สถานะอัปเดต = "ยืนยัน/อัปเดตแล้ว"
    # Using Thailand Timezone
    user.วันที่อัปเดตล่าสุด = datetime.now(bangkok_tz).strftime('%d %B %Y, %H:%M')
    db.session.commit()
    flash("ข้อมูลของคุณได้รับการยืนยันเรียบร้อยแล้ว ขอบคุณครับ/ค่ะ", "success")
    return redirect(url_for('index'))

@app.route('/edit/<int:user_id>')
def edit_form(user_id):
    user = User.query.filter_by(ลำดับ=user_id).first_or_404()
    return render_template('edit.html', user=user.to_dict(), admin_mode=session.get('logged_in', False))

@app.route('/update/<int:user_id>', methods=['POST'])
def update(user_id):
    user_to_update = User.query.filter_by(ลำดับ=user_id).first_or_404()
    
    # Update user object from form data
    for key, value in request.form.items():
        if hasattr(user_to_update, key) and key != 'ลำดับ':
            setattr(user_to_update, key, value)
            
    user_to_update.สถานะอัปเดต = "ยืนยัน/อัปเดตแล้ว"
    user_to_update.วันที่อัปเดตล่าสุด = datetime.now(bangkok_tz).strftime('%d %B %Y, %H:%M')
    
    db.session.commit()

    if session.get('logged_in', False):
        flash(f"ข้อมูลของ {user_to_update.ชื่อ} อัปเดตเรียบร้อย", "success")
        return redirect(url_for('admin_dashboard'))
    else:
        flash("อัปเดตข้อมูลของคุณเรียบร้อยแล้ว ขอบคุณครับ/ค่ะ", "success")
        return redirect(url_for('index'))

# --- Admin Routes ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == ADMIN_USERNAME and request.form['password'] == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง", "error")
    return render_template('login.html')

@app.route('/admin')
def admin_dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    all_users = User.query.order_by(User.สถานะอัปเดต).all()
    
    stats = {
        'total': len(all_users),
        'confirmed': sum(1 for u in all_users if u.สถานะอัปเดต == 'ยืนยัน/อัปเดตแล้ว'),
    }
    stats['unconfirmed'] = stats['total'] - stats['confirmed']
    stats['percentage'] = round((stats['confirmed'] / stats['total']) * 100, 2) if stats['total'] > 0 else 0

    columns_to_show = ['ลำดับ', 'ยศ_คำนำหน้าชื่อ', 'ชื่อ', 'นามสกุล', 'ชื่อเล่น', 'สถานะอัปเดต', 'วันที่อัปเดตล่าสุด']
    records = [{col: getattr(user, col, '') for col in columns_to_show} for user in all_users]

    return render_template('admin.html', records=records, columns=columns_to_show, stats=stats)


@app.route('/admin/upload', methods=['POST'])
def upload_and_migrate():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    file = request.files.get('file')
    if not file or file.filename == '':
        flash('ไม่ได้เลือกไฟล์ใดๆ', 'error')
        return redirect(url_for('admin_dashboard'))

    if file and file.filename.endswith('.csv'):
        try:
            # Clear existing data
            db.session.query(User).delete()
            
            # Read CSV into pandas DataFrame
            df = pd.read_csv(file.stream, encoding='utf-8-sig')
            
            # Rename columns to match the model attributes (replace spaces with underscores)
            df.columns = [c.replace(' ', '_').replace('/', '_') for c in df.columns]

            # Iterate and add to database
            for index, row in df.iterrows():
                new_user = User(**row.to_dict())
                db.session.add(new_user)
            
            db.session.commit()
            flash('ย้ายข้อมูลจาก CSV ไปยังฐานข้อมูลเรียบร้อยแล้ว!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'เกิดข้อผิดพลาด: {e}', 'error')
            
    return redirect(url_for('admin_dashboard'))


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

# ... (other routes like directory search can be updated similarly) ...

if __name__ == '__main__':
    app.run(debug=True)
