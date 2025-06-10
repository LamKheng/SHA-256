from flask import Flask, request, jsonify, send_file, redirect, url_for
from werkzeug.utils import secure_filename
import os
import hashlib
import json
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Cấu hình
UPLOAD_FOLDER = 'uploads'
USERS_FILE = 'users.json'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx'}

# Tạo thư mục nếu chưa tồn tại
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Hàm kiểm tra định dạng file
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Hàm đọc user data
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {
        "admin": {
            "password": hashlib.sha256("admin123".encode()).hexdigest(),
            "created_at": datetime.now().isoformat(),
            "last_login": None,
            "is_admin": True
        }
    }

# Hàm lưu user data
def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

# Khởi tạo dữ liệu
USERS = load_users()
FILES = []

# API endpoints
@app.route('/')
def home():
    return redirect(url_for('static', filename='client.html'))

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    if not username or not password:
        return jsonify({'status': 'error', 'message': 'Tên đăng nhập và mật khẩu không được để trống!'}), 400
    
    if username in USERS:
        return jsonify({'status': 'error', 'message': 'Tên đăng nhập đã tồn tại!'}), 400
    
    # Mã hóa mật khẩu bằng SHA-256
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    USERS[username] = {
        "password": hashed_password,
        "created_at": datetime.now().isoformat(),
        "last_login": None,
        "is_admin": False
    }
    
    save_users(USERS)
    return jsonify({'status': 'success', 'message': 'Đăng ký thành công!'})

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    if username not in USERS:
        return jsonify({'status': 'error', 'message': 'Tên đăng nhập không tồn tại!'}), 401
    
    # Kiểm tra mật khẩu đã mã hóa
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    if USERS[username]['password'] != hashed_password:
        return jsonify({'status': 'error', 'message': 'Mật khẩu không đúng!'}), 401
    
    # Cập nhật thời gian đăng nhập
    USERS[username]['last_login'] = datetime.now().isoformat()
    save_users(USERS)
    
    return jsonify({
        'status': 'success', 
        'message': 'Đăng nhập thành công!',
        'is_admin': USERS[username].get('is_admin', False)
    })

@app.route('/list_users', methods=['GET'])
def list_users():
    return jsonify([user for user in USERS.keys() if not USERS[user].get('is_admin', False)])

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'message': 'Không tìm thấy file!'}), 400
    
    file = request.files['file']
    sender = request.form.get('sender')
    receiver = request.form.get('receiver')
    
    if not file or file.filename == '':
        return jsonify({'status': 'error', 'message': 'Không có file được chọn!'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'status': 'error', 'message': 'Định dạng file không được hỗ trợ!'}), 400
    
    if not sender or not receiver:
        return jsonify({'status': 'error', 'message': 'Thiếu thông tin người gửi hoặc người nhận!'}), 400
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    # Đảm bảo không ghi đè file
    counter = 1
    base, ext = os.path.splitext(filename)
    while os.path.exists(filepath):
        filename = f"{base}_{counter}{ext}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        counter += 1
    
    file.save(filepath)
    
    # Tính toán hash SHA-256
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    sha256 = sha256_hash.hexdigest()
    
    # Lưu thông tin file
    file_info = {
        'id': len(FILES) + 1,
        'name': filename,
        'original_name': file.filename,
        'sender': sender,
        'receiver': receiver,
        'sha256': sha256,
        'upload_time': datetime.now().isoformat(),
        'size': os.path.getsize(filepath)
    }
    FILES.append(file_info)
    
    return jsonify({
        'status': 'success',
        'message': 'Upload thành công!',
        'file': file_info
    })

@app.route('/list_files', methods=['GET'])
def list_files():
    return jsonify(FILES)

@app.route('/download/<int:file_id>', methods=['GET'])
def download_file(file_id):
    file_info = next((f for f in FILES if f['id'] == file_id), None)
    if not file_info:
        return jsonify({'status': 'error', 'message': 'File không tồn tại!'}), 404
    
    filepath = os.path.join(UPLOAD_FOLDER, file_info['name'])
    if not os.path.exists(filepath):
        return jsonify({'status': 'error', 'message': 'File không tồn tại trên server!'}), 404
    
    return send_file(filepath, as_attachment=True, download_name=file_info['original_name'])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)