import os
from flask import Flask, render_template, request, redirect, url_for, session, make_response, flash
import pandas as pd
from datetime import datetime
import json
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
import locale

# --- Configuration ---
ADMIN_USERNAME = "RPCA70-Admin"
ADMIN_PASSWORD = "Admin70-1234"
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv'}
SETTINGS_FILE = 'settings.json'

# --- App & Database Initialization ---
app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

try:
    locale.setlocale(locale.LC_TIME, 'th_TH.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'Thai')
    except locale.Error:
        print("Locale 'th_TH.UTF-8' or 'Thai' not found. Date formatting might be in English.")


# --- COLUMN MAPPING (หัวใจสำคัญของการแปลงชื่อ) ---
COLUMN_MAP = {
    'ลำดับ': 'id', 'ยศ / คำนำหน้าชื่อ': 'rank_title', 'ชื่อ': 'first_name', 'นามสกุล': 'last_name',
    'ชื่อเล่น': 'nickname', 'ฉายา': 'alias', 'ชมรม': 'club', 'ชื่อ - นามสกุล (เดิม)': 'former_name',
    'ที่อยู่': 'address', 'เบอร์โทรศัพท์': 'phone_primary', 'เบอร์โทรศัพท์ (สำรอง)': 'phone_secondary',
    'Line ID': 'line_id', 'Facebook': 'facebook', 'Instagram': 'instagram',
    'สถานภาพ / อาชีพ ในปัจจุบัน': 'current_status_occupation', 'อาชีพปัจจุบัน': 'occupation',
    'สถานที่ทำงานปัจจุบัน': 'workplace', 'ตำแหน่งในที่ทำงาน': 'job_title', 'ประเทศที่อาศัยอยู่': 'country_residence',
    'บช.': 'division', 'ตำแหน่ง': 'position', 'หมายเหตุ (หน้าที่พิเศษ)': 'special_duties',
    'สถานะอัปเดต': 'update_status', 'วันที่อัปเดตล่าสุด': 'last_updated'
}
REVERSE_COLUMN_MAP = {v: k for k, v in COLUMN_MAP.items()}


# --- Database Model (อัปเดตให้มีทุกคอลัมน์) ---
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    rank_title = db.Column(db.Text, nullable=True)
    first_name = db.Column(db.Text, nullable=True)
    last_name = db.Column(db.Text, nullable=True)
    nickname = db.Column(db.Text, nullable=True)
    alias = db.Column(db.Text, nullable=True)
    club = db.Column(db.Text, nullable=True)
    former_name = db.Column(db.Text, nullable=True)
    address = db.Column(db.Text, nullable=True)
    phone_primary = db.Column(db.Text, nullable=True)
    phone_secondary = db.Column(db.Text, nullable=True)
    line_id = db.Column(db.Text, nullable=True)
    facebook = db.Column(db.Text, nullable=True)
    instagram = db.Column(db.Text, nullable=True)
    current_status_occupation = db.Column(db.Text, nullable=True)
    occupation = db.Column(db.Text, nullable=True)
    workplace = db.Column(db.Text, nullable=True)
    job_title = db.Column(db.Text, nullable=True)
    country_residence = db.Column(db.Text, nullable=True)
    division = db.Column(db.Text, nullable=True)
    position = db.Column(db.Text, nullable=True)
    special_duties = db.Column(db.Text, nullable=True)
    update_status = db.Column(db.Text, default="ยังไม่ได้ยืนยัน")
    last_updated = db.Column(db.Text, default="ข้อมูล ณ วันที่ 15 เมษายน 2567")

    def to_dict(self):
        return {REVERSE_COLUMN_MAP.get(key, key): value for key, value in self.__dict__.items() if not key.startswith('_')}

# --- Helper Functions ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def initialize_files():
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    if not os.path.exists(SETTINGS_FILE):
        default_settings = {
            "directory_view_enabled": True,
            "user_editing_enabled": True,
            "csv_columns": []
        }
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_settings, f, indent=4)

def load_settings():
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        initialize_files()
        return load_settings()

def save_settings(settings_data):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f: json.dump(settings_data, f, indent=4)

# --- Routes ---
@app.route('/')
def index():
    settings = load_settings()
    return render_template('index.html', settings=settings)

@app.route('/search', methods=['POST'])
def search():
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    if not first_name or not last_name:
        flash("กรุณากรอกทั้งชื่อและนามสกุล", "error")
        return redirect(url_for('index'))
    result = User.query.filter(db.func.lower(User.first_name) == first_name.lower(), db.func.lower(User.last_name) == last_name.lower()).first()
    if not result:
        flash("ไม่พบข้อมูลของคุณ กรุณาตรวจสอบการสะกดและลองใหม่อีกครั้ง", "error")
        return redirect(url_for('index'))
    return redirect(url_for('view_profile', user_id=result.id))

@app.route('/view/<int:user_id>')
def view_profile(user_id):
    settings = load_settings()
    columns = settings.get('csv_columns', [])
    user = User.query.get(user_id)
    if not user:
        flash("ไม่พบข้อมูลผู้ใช้", "error")
        return redirect(url_for('index'))
    return render_template('view.html', user=user.to_dict(), settings=settings, columns=columns)

@app.route('/confirm/<int:user_id>')
def confirm_profile(user_id):
    settings = load_settings()
    if not settings.get('user_editing_enabled', True):
        flash("ระบบปิดการแก้ไขข้อมูลชั่วคราว", "info")
        return redirect(url_for('index'))
    user = User.query.get(user_id)
    if user:
        user.update_status = "ยืนยัน/อัปเดตแล้ว"
        user.last_updated = datetime.now().strftime('%d %B %Y, %H:%M')
        db.session.commit()
        flash("ข้อมูลของคุณได้รับการยืนยันเรียบร้อยแล้ว ขอบคุณครับ/ค่ะ", "success")
    else:
        flash("ไม่พบข้อมูลผู้ใช้", "error")
    return redirect(url_for('index'))

@app.route('/edit/<int:user_id>')
def edit_form(user_id):
    is_admin = session.get('logged_in', False)
    settings = load_settings()
    if not is_admin and not settings.get('user_editing_enabled', True):
        flash("ระบบปิดการแก้ไขข้อมูลชั่วคราว", "info")
        return redirect(url_for('index'))
    columns = settings.get('csv_columns', [])
    user = User.query.get(user_id)
    if not user:
        flash("ไม่พบข้อมูลผู้ใช้", "error")
        return redirect(url_for('index'))
    return render_template('edit.html', user=user.to_dict(), admin_mode=is_admin, columns=columns)

@app.route('/update/<int:user_id>', methods=['POST'])
def update(user_id):
    is_admin = session.get('logged_in', False)
    settings = load_settings()
    if not is_admin and not settings.get('user_editing_enabled', True):
        flash("ระบบปิดการแก้ไขข้อมูลชั่วคราว", "info")
        return redirect(url_for('index'))
    user = User.query.get(user_id)
    if user:
        form_data = request.form.to_dict()
        for thai_key, value in form_data.items():
            model_attr = COLUMN_MAP.get(thai_key)
            if model_attr and hasattr(user, model_attr):
                setattr(user, model_attr, value)
        user.update_status = "ยืนยัน/อัปเดตแล้ว"
        user.last_updated = datetime.now().strftime('%d %B %Y, %H:%M')
        db.session.commit()
        flash_message = f"ข้อมูลของ {user.first_name} อัปเดตเรียบร้อย" if is_admin else "อัปเดตข้อมูลของคุณเรียบร้อยแล้ว ขอบคุณครับ/ค่ะ"
        flash(flash_message, "success")
        return redirect(url_for('admin_dashboard') if is_admin else url_for('view_profile', user_id=user.id))
    flash("เกิดข้อผิดพลาด: ไม่พบข้อมูลผู้ใช้ที่จะอัปเดต", "error")
    return redirect(url_for('admin_dashboard') if is_admin else url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('logged_in'):
        return redirect(url_for('admin_dashboard'))
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
    settings = load_settings()
    columns = settings.get('csv_columns', [])
    if not columns:
        flash("ยังไม่มีข้อมูลในระบบ กรุณาอัปโหลดไฟล์ CSV เพื่อเริ่มต้น", "warning")
    users = User.query.order_by(User.id).all()
    records = [user.to_dict() for user in users]
    stats = {'total': 0, 'confirmed': 0, 'unconfirmed': 0, 'percentage': 0}
    if users:
        stats['total'] = len(users)
        stats['confirmed'] = User.query.filter_by(update_status="ยืนยัน/อัปเดตแล้ว").count()
        stats['unconfirmed'] = stats['total'] - stats['confirmed']
        if stats['total'] > 0:
            stats['percentage'] = round((stats['confirmed'] / stats['total']) * 100, 2)
    return render_template('admin.html', records=records, columns=columns, stats=stats, settings=settings)

@app.route('/admin/reset_status/<int:user_id>')
def reset_status(user_id):
    if not session.get('logged_in'): return redirect(url_for('login'))
    user = User.query.get(user_id)
    if user:
        user.update_status = "ยังไม่ได้ยืนยัน"
        user.last_updated = "ข้อมูล ณ วันที่ 15 เมษายน 2567"
        db.session.commit()
        flash(f"รีเซ็ตสถานะของ {user.first_name} เรียบร้อย", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/upload', methods=['POST'])
def upload_file():
    if not session.get('logged_in'): return redirect(url_for('login'))
    if 'file' not in request.files or request.files['file'].filename == '':
        flash('ไม่ได้เลือกไฟล์ใดๆ', 'error'); return redirect(url_for('admin_dashboard'))
    file = request.files['file']
    if file and allowed_file(file.filename):
        try:
            df = pd.read_csv(file, encoding='utf-8-sig')
            csv_columns = df.columns.tolist()
            df.rename(columns=COLUMN_MAP, inplace=True)

            # กรองแถวที่ไม่มีค่าในคอลัมน์ 'id' (ลำดับ) หรือเป็นค่าที่ไม่ใช่ตัวเลข
            df.dropna(subset=['id'], inplace=True)
            df = df[pd.to_numeric(df['id'], errors='coerce').notna()]
            df['id'] = df['id'].astype(int)

            db.session.query(User).delete()
            for _, row in df.iterrows():
                user_data = {col: row.get(col) for col in COLUMN_MAP.values() if col in row and pd.notna(row.get(col))}
                new_user = User(**user_data)
                db.session.add(new_user)
            db.session.commit()
            settings = load_settings()
            settings['csv_columns'] = csv_columns
            save_settings(settings)
            flash('อัปโหลดและนำเข้าข้อมูลสู่ฐานข้อมูลเรียบร้อยแล้ว', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'เกิดข้อผิดพลาดในการประมวลผลไฟล์: {e}', 'error')
    else:
        flash('อนุญาตเฉพาะไฟล์นามสกุล .csv เท่านั้น', 'error')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/settings', methods=['POST'])
def admin_settings():
    if not session.get('logged_in'): return redirect(url_for('login'))
    settings = load_settings()
    settings['directory_view_enabled'] = 'directory_view_enabled' in request.form
    settings['user_editing_enabled'] = 'user_editing_enabled' in request.form
    save_settings(settings)
    flash('บันทึกการตั้งค่าเรียบร้อยแล้ว', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash("ออกจากระบบเรียบร้อย", "info")
    return redirect(url_for('index'))

@app.route('/export/csv')
def export_csv():
    if not session.get('logged_in'): return redirect(url_for('login'))
    settings = load_settings()
    columns = settings.get('csv_columns', [])
    if not columns:
        flash("ไม่พบข้อมูลที่จะ Export", "error"); return redirect(url_for('admin_dashboard'))
    users = User.query.all()
    records = [user.to_dict() for user in users]
    df = pd.DataFrame(records)
    df = df[columns] # Reorder dataframe to match original CSV
    output = make_response(df.to_csv(index=False, encoding='utf-8-sig'))
    timestamp = datetime.now().strftime("%Y-%m-%d")
    output.headers["Content-Disposition"] = f"attachment; filename=RPCA70_Directory_{timestamp}.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8-sig"
    return output

@app.route('/directory', methods=['GET', 'POST'])
def view_directory():
    settings = load_settings()
    if not settings.get('directory_view_enabled', False):
        flash("มุมมองทำเนียบรุ่นยังไม่เปิดใช้งาน", "info"); return redirect(url_for('index'))
    query = request.form.get('query', '').strip()
    users = []
    if query:
        search_query = f"%{query.lower()}%"
        users = User.query.filter(db.or_(
            db.func.lower(User.first_name).like(search_query),
            db.func.lower(User.last_name).like(search_query),
            db.func.lower(User.nickname).like(search_query)
        )).all()
    records = [user.to_dict() for user in users] if request.method == 'POST' else []
    return render_template('directory.html', records=records, query=query)

if __name__ == '__main__':
    with app.app_context():
        initialize_files()
    app.run(host='0.0.0.0', port=5000, debug=True)
