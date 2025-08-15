import os
from flask import Flask, render_template, request, redirect, url_for, session, make_response, flash
import pandas as pd
from datetime import datetime
import json
from werkzeug.utils import secure_filename

# --- Configuration ---
ADMIN_USERNAME = "RPCA70-Admin"
ADMIN_PASSWORD = "Admin70-1234"
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'csv'}
DATA_FILE = os.path.join(UPLOAD_FOLDER, 'data.csv')
SETTINGS_FILE = 'settings.json'

# --- App Initialization ---
app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- Helper Functions ---

def allowed_file(filename):
    """Checks if the uploaded file has a .csv extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def initialize_files():
    """Ensure necessary folders and files exist on startup."""
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    if not os.path.exists(SETTINGS_FILE):
        default_settings = {
            "directory_view_enabled": True,
            "user_editing_enabled": True
        }
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_settings, f, indent=4)

def load_settings():
    """Loads settings from the JSON file."""
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        initialize_files()
        return load_settings()

def save_settings(settings_data):
    """Saves settings to the JSON file."""
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings_data, f, indent=4)

def load_data():
    """Loads data from CSV, adds tracking columns if they don't exist."""
    if not os.path.exists(DATA_FILE):
        return None
    try:
        df = pd.read_csv(DATA_FILE, encoding='utf-8-sig')
        if 'สถานะอัปเดต' not in df.columns:
            df['สถานะอัปเดต'] = "ยังไม่ได้ยืนยัน"
        if 'วันที่อัปเดตล่าสุด' not in df.columns:
            df['วันที่อัปเดตล่าสุด'] = "ข้อมูล ณ วันที่ 15 เมษายน 2567"
        if 'ลำดับ' in df.columns:
            df['ลำดับ'] = pd.to_numeric(df['ลำดับ'], errors='coerce').fillna(0).astype(int)
        return df
    except Exception as e:
        print(f"Error loading data: {e}")
        return None

def save_data(df):
    """Saves the DataFrame back to the CSV file."""
    if df is not None:
        if 'ลำดับ' in df.columns:
            cols = df.columns.tolist()
            if 'ลำดับ' in cols:
                cols.insert(0, cols.pop(cols.index('ลำดับ')))
                df = df.loc[:, cols]
        df.to_csv(DATA_FILE, index=False, encoding='utf-8-sig')

# --- Initial Setup ---
initialize_files()

# --- Main Routes ---

@app.route('/')
def index():
    """Homepage: User search form or a message if editing is disabled."""
    settings = load_settings()
    return render_template('index.html', settings=settings)

@app.route('/search', methods=['POST'])
def search():
    """Handles the search request and redirects to the view page."""
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()

    if not first_name or not last_name:
        flash("กรุณากรอกทั้งชื่อและนามสกุล", "error")
        return redirect(url_for('index'))

    df = load_data()
    if df is None:
        flash("ยังไม่มีข้อมูลในระบบ กรุณาติดต่อผู้ดูแล", "error")
        return redirect(url_for('index'))

    result = df[(df['ชื่อ'].astype(str).str.strip().str.lower() == first_name.lower()) &
                (df['นามสกุล'].astype(str).str.strip().str.lower() == last_name.lower())]

    if result.empty:
        flash("ไม่พบข้อมูลของคุณ กรุณาตรวจสอบการสะกดและลองใหม่อีกครั้ง", "error")
        return redirect(url_for('index'))

    user_id = int(result.iloc[0].get('ลำดับ'))
    return redirect(url_for('view_profile', user_id=user_id))

@app.route('/view/<int:user_id>')
def view_profile(user_id):
    """Displays a read-only view of the user's profile."""
    settings = load_settings()
    df = load_data()
    if df is None or df[df['ลำดับ'] == user_id].empty:
        flash("ไม่พบข้อมูลผู้ใช้", "error")
        return redirect(url_for('index'))
    
    user_data = df[df['ลำดับ'] == user_id].to_dict('records')[0]
    return render_template('view.html', user=user_data, settings=settings)

@app.route('/confirm/<int:user_id>')
def confirm_profile(user_id):
    """Confirms the user's data without changes."""
    settings = load_settings()
    if not settings.get('user_editing_enabled', True):
        flash("ระบบปิดการแก้ไขข้อมูลชั่วคราว", "info")
        return redirect(url_for('index'))

    df = load_data()
    user_index = df[df['ลำดับ'] == user_id].index
    if not user_index.empty:
        df.loc[user_index, 'สถานะอัปเดต'] = "ยืนยัน/อัปเดตแล้ว"
        df.loc[user_index, 'วันที่อัปเดตล่าสุด'] = datetime.now().strftime('%d %B %Y, %H:%M')
        save_data(df)
        flash("ข้อมูลของคุณได้รับการยืนยันเรียบร้อยแล้ว ขอบคุณครับ/ค่ะ", "success")
    else:
        flash("ไม่พบข้อมูลผู้ใช้", "error")
    return redirect(url_for('index'))

@app.route('/edit/<int:user_id>')
def edit_form(user_id):
    """Displays the form for editing user data."""
    is_admin = session.get('logged_in', False)
    settings = load_settings()
    if not is_admin and not settings.get('user_editing_enabled', True):
        flash("ระบบปิดการแก้ไขข้อมูลชั่วคราว", "info")
        return redirect(url_for('index'))

    df = load_data()
    if df is None or df[df['ลำดับ'] == user_id].empty:
        flash("ไม่พบข้อมูลผู้ใช้", "error")
        return redirect(url_for('index'))
    
    user_data = df[df['ลำดับ'] == user_id].to_dict('records')[0]
    return render_template('edit.html', user=user_data, admin_mode=is_admin)

@app.route('/update/<int:user_id>', methods=['POST'])
def update(user_id):
    """Updates user information from user or admin form."""
    is_admin = session.get('logged_in', False)
    settings = load_settings()
    if not is_admin and not settings.get('user_editing_enabled', True):
        flash("ระบบปิดการแก้ไขข้อมูลชั่วคราว", "info")
        return redirect(url_for('index'))

    df = load_data()
    if df is None:
        flash("เกิดข้อผิดพลาด: ไม่พบไฟล์ข้อมูล", "error")
        return redirect(url_for('index'))

    user_index = df[df['ลำดับ'] == user_id].index
    if not user_index.empty:
        form_data = request.form.to_dict()
        for key, value in form_data.items():
            if key in df.columns and key != 'ลำดับ':
                df.loc[user_index, key] = value

        df.loc[user_index, 'สถานะอัปเดต'] = "ยืนยัน/อัปเดตแล้ว"
        df.loc[user_index, 'วันที่อัปเดตล่าสุด'] = datetime.now().strftime('%d %B %Y, %H:%M')
        save_data(df)
        
        if is_admin:
            flash(f"ข้อมูลของ {df.loc[user_index, 'ชื่อ'].iloc[0]} อัปเดตเรียบร้อย", "success")
            return redirect(url_for('admin_dashboard'))
        else:
            flash("อัปเดตข้อมูลของคุณเรียบร้อยแล้ว ขอบคุณครับ/ค่ะ", "success")
            return redirect(url_for('index'))

    flash("เกิดข้อผิดพลาด: ไม่พบข้อมูลผู้ใช้ที่จะอัปเดต", "error")
    return redirect(url_for('admin_dashboard') if is_admin else url_for('index'))

# --- Admin Routes ---

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

    df = load_data()
    records = []
    columns_to_show = ['ลำดับ', 'ยศ / คำนำหน้าชื่อ', 'ชื่อ', 'นามสกุล', 'ชื่อเล่น', 'สถานะอัปเดต', 'วันที่อัปเดตล่าสุด']
    stats = {'total': 0, 'confirmed': 0, 'unconfirmed': 0, 'percentage': 0}

    if df is not None:
        # Prepare data for the simplified admin view
        admin_view_df = df[columns_to_show].copy()
        records = admin_view_df.to_dict('records')
        
        stats['total'] = len(df)
        stats['confirmed'] = df[df['สถานะอัปเดต'] == 'ยืนยัน/อัปเดตแล้ว'].shape[0]
        stats['unconfirmed'] = stats['total'] - stats['confirmed']
        if stats['total'] > 0:
            stats['percentage'] = round((stats['confirmed'] / stats['total']) * 100, 2)

    settings = load_settings()
    return render_template('admin.html', records=records, columns=columns_to_show, stats=stats, settings=settings)

@app.route('/admin/reset_status/<int:user_id>')
def reset_status(user_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    df = load_data()
    if df is not None:
        user_index = df[df['ลำดับ'] == user_id].index
        if not user_index.empty:
            df.loc[user_index, 'สถานะอัปเดต'] = "ยังไม่ได้ยืนยัน"
            df.loc[user_index, 'วันที่อัปเดตล่าสุด'] = "ข้อมูล ณ วันที่ 15 เมษายน 2567"
            save_data(df)
            flash(f"รีเซ็ตสถานะของ {df.loc[user_index, 'ชื่อ'].iloc[0]} เรียบร้อย", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/upload', methods=['POST'])
def upload_file():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    if 'file' not in request.files or request.files['file'].filename == '':
        flash('ไม่ได้เลือกไฟล์ใดๆ', 'error')
        return redirect(url_for('admin_dashboard'))
    file = request.files['file']
    if file and allowed_file(file.filename):
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'data.csv')
        file.save(filepath)
        df = load_data()
        save_data(df)
        flash('อัปโหลดไฟล์ CSV ใหม่เรียบร้อยแล้ว', 'success')
    else:
        flash('อนุญาตเฉพาะไฟล์นามสกุล .csv เท่านั้น', 'error')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/settings', methods=['POST'])
def admin_settings():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
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
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    df = load_data()
    if df is None:
        flash("ไม่พบข้อมูลที่จะ Export", "error")
        return redirect(url_for('admin_dashboard'))
    output = make_response(df.to_csv(index=False, encoding='utf-8-sig'))
    timestamp = datetime.now().strftime("%Y-%m-%d")
    output.headers["Content-Disposition"] = f"attachment; filename=RPCA70_Directory_{timestamp}.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8-sig"
    return output

# --- Directory View ---
@app.route('/directory', methods=['GET', 'POST'])
def view_directory():
    settings = load_settings()
    if not settings.get('directory_view_enabled', False):
        flash("มุมมองทำเนียบรุ่นยังไม่เปิดใช้งาน", "info")
        return redirect(url_for('index'))
    
    df = load_data()
    records = []
    query = ""
    if request.method == 'POST':
        query = request.form.get('query', '').strip()
        if df is not None and query:
            # Search in name, lastname, and nickname
            search_query = query.lower()
            mask = (df['ชื่อ'].str.lower().str.contains(search_query, na=False) |
                    df['นามสกุล'].str.lower().str.contains(search_query, na=False) |
                    df['ชื่อเล่น'].str.lower().str.contains(search_query, na=False))
            records = df[mask].to_dict('records')
        elif df is not None:
             # If search is empty, show all
             records = df.to_dict('records')
    
    return render_template('directory.html', records=records, query=query)

# --- Main Execution ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)