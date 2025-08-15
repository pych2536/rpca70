import os
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.utils import secure_filename

# --- App Initialization & Configuration ---
app = Flask(__name__)
app.secret_key = os.urandom(24)

# Database Configuration from Environment Variable
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Configuration ---
ADMIN_USERNAME = "RPCA70-Admin"
ADMIN_PASSWORD = "Admin70-1234"
# FIX: Use Render's persistent disk path, available on paid plans.
# This ensures uploaded files are not lost on server restart.
UPLOAD_FOLDER = '/var/data/uploads' 
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- Database Model ---
class User(db.Model):
    __tablename__ = 'alumni_data'
    id = db.Column(db.Integer, primary_key=True)
    ลำดับ = db.Column(db.Integer, unique=True, nullable=False)
    
    # This is a placeholder list of expected columns.
    # The application will dynamically handle columns found in the CSV.
    _column_names = [
        'ยศ_คำนำหน้าชื่อ', 'ชื่อ', 'นามสกุล', 'ชื่อเล่น', 'ฉายา', 'ชมรม', 
        'ชื่อ_นามสกุล_เดิม', 'ที่อยู่', 'เบอร์โทรศัพท์', 'เบอร์โทรศัพท์_สำรอง', 
        'Line_ID', 'Facebook', 'Instagram', 'สถานภาพ_อาชีพ_ในปัจจุบัน', 
        'อาชีพปัจจุบัน', 'สถานที่ทำงานปัจจุบัน', 'ตำแหน่งในที่ทำงาน', 
        'ประเทศที่อาศัยอยู่', 'บช', 'ตำแหน่ง', 'หมายเหตุ_หน้าที่พิเศษ'
    ]

    สถานะอัปเดต = db.Column(db.String(50), default='ยังไม่ได้ยืนยัน')
    วันที่อัปเดตล่าสุด = db.Column(db.String(100), default='ข้อมูล ณ วันที่ 15 เมษายน 2567')

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

# Dynamically add columns to the User model
for col_name in User._column_names:
    if not hasattr(User, col_name):
        setattr(User, col_name, db.Column(db.String(255), nullable=True))


# --- Helper to create the table and folder initially ---
with app.app_context():
    db.create_all()
    # This will now correctly create the folder on the persistent disk
    if not os.path.exists(UPLOAD_FOLDER):
        try:
            os.makedirs(UPLOAD_FOLDER)
        except OSError as e:
            # This might fail locally if you don't have permissions, but will work on Render
            print(f"Could not create upload folder (this is expected locally): {e}")


# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()

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
    # datetime.now() will use the server's timezone (set to Asia/Bangkok via TZ env var)
    user.วันที่อัปเดตล่าสุด = datetime.now().strftime('%d %B %Y, %H:%M')
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
    
    form_data = request.form.to_dict()
    for key, value in form_data.items():
        sane_key = key.replace(' ', '_').replace('/', '_')
        if hasattr(user_to_update, sane_key) and sane_key != 'ลำดับ':
            setattr(user_to_update, sane_key, value)
            
    user_to_update.สถานะอัปเดต = "ยืนยัน/อัปเดตแล้ว"
    user_to_update.วันที่อัปเดตล่าสุด = datetime.now().strftime('%d %B %Y, %H:%M')
    
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
        
    all_users = User.query.order_by(User.สถานะอัปเดต, User.ลำดับ).all()
    
    stats = { 'total': len(all_users) }
    stats['confirmed'] = sum(1 for u in all_users if u.สถานะอัปเดต == 'ยืนยัน/อัปเดตแล้ว')
    stats['unconfirmed'] = stats['total'] - stats['confirmed']
    stats['percentage'] = round((stats['confirmed'] / stats['total']) * 100, 2) if stats['total'] > 0 else 0

    columns_to_show = ['ลำดับ', 'ยศ_คำนำหน้าชื่อ', 'ชื่อ', 'นามสกุล', 'ชื่อเล่น', 'สถานะอัปเดต', 'วันที่อัปเดตล่าสุด']
    records = []
    for user in all_users:
        record = {}
        for col in columns_to_show:
            # Check if the attribute exists before trying to get it
            if hasattr(user, col):
                record[col] = getattr(user, col)
            else:
                record[col] = '' # Provide a default value if column not in DB
        records.append(record)

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
            # Clear existing data before importing
            db.session.query(User).delete()
            
            df = pd.read_csv(file.stream, encoding='utf-8-sig')
            
            # Sanitize column names from CSV to match Python attribute rules
            df.columns = [c.strip().replace(' ', '_').replace('/', '_') for c in df.columns]
            
            # Convert DataFrame to a list of dictionaries
            data_to_insert = df.to_dict(orient='records')

            # Use bulk_insert_mappings for efficiency
            db.session.bulk_insert_mappings(User, data_to_insert)
            
            db.session.commit()
            flash('ย้ายข้อมูลจาก CSV ไปยังฐานข้อมูลเรียบร้อยแล้ว!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'เกิดข้อผิดพลาดในการย้ายข้อมูล: {e}', 'error')
            
    return redirect(url_for('admin_dashboard'))

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=False)
