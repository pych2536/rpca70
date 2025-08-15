import os
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.utils import secure_filename

# --- App Initialization & Configuration ---
app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Configuration ---
ADMIN_USERNAME = "RPCA70-Admin"
ADMIN_PASSWORD = "Admin70-1234"
# Use Render's persistent disk path, available on paid plans.
UPLOAD_FOLDER = '/var/data/uploads' 

# --- CSV to Database Column Mapping ---
# This dictionary is the "translator" between CSV headers and DB columns.
CSV_TO_DB_MAP = {
    'ลำดับ': 'sequence_id',
    'ยศ / คำนำหน้าชื่อ': 'rank_prefix',
    'ชื่อ': 'first_name',
    'นามสกุล': 'last_name',
    'ชื่อเล่น': 'nickname',
    'ฉายา': 'alias',
    'ชมรม': 'club',
    'ชื่อ - นามสกุล (เดิม)': 'former_name',
    'ที่อยู่': 'address',
    'เบอร์โทรศัพท์': 'phone_primary',
    'เบอร์โทรศัพท์ (สำรอง)': 'phone_secondary',
    'Line ID': 'line_id',
    'Facebook': 'facebook',
    'Instagram': 'instagram',
    'สถานภาพ / อาชีพ ในปัจจุบัน': 'current_status_occupation',
    'อาชีพปัจจุบัน': 'current_occupation',
    'สถานที่ทำงานปัจจุบัน': 'current_workplace',
    'ตำแหน่งในที่ทำงาน': 'current_position',
    'ประเทศที่อาศัยอยู่': 'country_of_residence',
    'บช.': 'bureau',
    'ตำแหน่ง': 'position_detail', # Note: CSV has two 'ตำแหน่ง' columns
    'หมายเหตุ (หน้าที่พิเศษ)': 'special_notes'
}

# --- Database Model (using robust English names) ---
class User(db.Model):
    __tablename__ = 'alumni_data'
    id = db.Column(db.Integer, primary_key=True)
    
    # Define columns with robust English names
    sequence_id = db.Column(db.Integer, unique=True, nullable=False)
    rank_prefix = db.Column(db.String(100))
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    nickname = db.Column(db.String(100))
    alias = db.Column(db.String(100))
    club = db.Column(db.String(100))
    former_name = db.Column(db.String(255))
    address = db.Column(db.String(500))
    phone_primary = db.Column(db.String(50))
    phone_secondary = db.Column(db.String(50))
    line_id = db.Column(db.String(100))
    facebook = db.Column(db.String(255))
    instagram = db.Column(db.String(255))
    current_status_occupation = db.Column(db.String(255))
    current_occupation = db.Column(db.String(255))
    current_workplace = db.Column(db.String(255))
    current_position = db.Column(db.String(255))
    country_of_residence = db.Column(db.String(100))
    bureau = db.Column(db.String(100))
    position_detail = db.Column(db.String(255))
    special_notes = db.Column(db.String(500))

    # Tracking columns
    update_status = db.Column(db.String(50), default='ยังไม่ได้ยืนยัน')
    last_updated = db.Column(db.String(100), default='ข้อมูล ณ วันที่ 15 เมษายน 2567')

    def to_dict(self):
        # This function now translates DB names back to Thai for display
        display_dict = {}
        # Reverse the map for display purposes
        db_to_csv_map = {v: k for k, v in CSV_TO_DB_MAP.items()}
        for col in self.__table__.columns:
            if col.name in db_to_csv_map:
                display_dict[db_to_csv_map[col.name]] = getattr(self, col.name)
        
        display_dict['สถานะอัปเดต'] = self.update_status
        display_dict['วันที่อัปเดตล่าสุด'] = self.last_updated
        return display_dict

# --- Helper to create the table and folder ---
with app.app_context():
    # This will create the table based on the robust model above
    db.create_all()
    if not os.path.exists(UPLOAD_FOLDER):
        try:
            os.makedirs(UPLOAD_FOLDER)
        except OSError as e:
            print(f"Could not create upload folder: {e}")

# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()

    user = User.query.filter(db.func.lower(User.first_name) == first_name.lower(), 
                             db.func.lower(User.last_name) == last_name.lower()).first()

    if user:
        return redirect(url_for('view_profile', user_sequence_id=user.sequence_id))
    else:
        flash("ไม่พบข้อมูลของคุณ กรุณาตรวจสอบการสะกดและลองใหม่อีกครั้ง", "error")
        return redirect(url_for('index'))

@app.route('/view/<int:user_sequence_id>')
def view_profile(user_sequence_id):
    user = User.query.filter_by(sequence_id=user_sequence_id).first_or_404()
    return render_template('view.html', user=user.to_dict())

@app.route('/confirm/<int:user_sequence_id>')
def confirm_profile(user_sequence_id):
    user = User.query.filter_by(sequence_id=user_sequence_id).first_or_404()
    user.update_status = "ยืนยัน/อัปเดตแล้ว"
    user.last_updated = datetime.now().strftime('%d %B %Y, %H:%M')
    db.session.commit()
    flash("ข้อมูลของคุณได้รับการยืนยันเรียบร้อยแล้ว ขอบคุณครับ/ค่ะ", "success")
    return redirect(url_for('index'))

@app.route('/edit/<int:user_sequence_id>')
def edit_form(user_sequence_id):
    user = User.query.filter_by(sequence_id=user_sequence_id).first_or_404()
    return render_template('edit.html', user=user.to_dict(), admin_mode=session.get('logged_in', False))

@app.route('/update/<int:user_sequence_id>', methods=['POST'])
def update(user_sequence_id):
    user_to_update = User.query.filter_by(sequence_id=user_sequence_id).first_or_404()
    
    form_data = request.form.to_dict()
    for csv_key, value in form_data.items():
        db_key = CSV_TO_DB_MAP.get(csv_key)
        if db_key and hasattr(user_to_update, db_key) and db_key != 'sequence_id':
            setattr(user_to_update, db_key, value)
            
    user_to_update.update_status = "ยืนยัน/อัปเดตแล้ว"
    user_to_update.last_updated = datetime.now().strftime('%d %B %Y, %H:%M')
    
    db.session.commit()

    if session.get('logged_in', False):
        flash(f"ข้อมูลของ {user_to_update.first_name} อัปเดตเรียบร้อย", "success")
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
        
    all_users = User.query.order_by(User.update_status, User.sequence_id).all()
    
    total_users = len(all_users)
    confirmed_users = sum(1 for u in all_users if u.update_status == 'ยืนยัน/อัปเดตแล้ว')
    stats = {
        'total': total_users,
        'confirmed': confirmed_users,
        'unconfirmed': total_users - confirmed_users,
        'percentage': round((confirmed_users / total_users) * 100, 2) if total_users > 0 else 0
    }

    columns_to_show = ['ลำดับ', 'ยศ / คำนำหน้าชื่อ', 'ชื่อ', 'นามสกุล', 'ชื่อเล่น', 'สถานะอัปเดต', 'วันที่อัปเดตล่าสุด']
    db_cols_map = {'ลำดับ': 'sequence_id', 'ยศ / คำนำหน้าชื่อ': 'rank_prefix', 'ชื่อ': 'first_name', 'นามสกุล': 'last_name', 'ชื่อเล่น': 'nickname', 'สถานะอัปเดต': 'update_status', 'วันที่อัปเดตล่าสุด': 'last_updated'}
    
    records = []
    for user in all_users:
        record = {display_col: getattr(user, db_col) for display_col, db_col in db_cols_map.items()}
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
            # Drop the existing table and recreate it to ensure a clean slate
            with app.app_context():
                db.drop_all()
                db.create_all()
            
            df = pd.read_csv(file.stream, encoding='utf-8-sig')
            
            # Use the map to rename columns
            df.rename(columns=CSV_TO_DB_MAP, inplace=True)
            
            # Filter for only the columns that exist in our DB model
            model_columns = [c.name for c in User.__table__.columns if c.name != 'id']
            df_filtered = df[df.columns.intersection(model_columns)]

            data_to_insert = df_filtered.to_dict(orient='records')
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
