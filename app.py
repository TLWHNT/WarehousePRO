import os
import secrets
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_login import LoginManager, login_required, current_user
from werkzeug.utils import secure_filename
from database import Database
from models import User
from auth import auth_bp

app = Flask(__name__)

# ✅ БЕЗОПАСНОСТЬ: Генерируем случайный secret_key
# В продакшене используйте переменную окружения!
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

# Настройки загрузки файлов
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB

# ✅ БЕЗОПАСНОСТЬ: Настройки сессий
app.config['SESSION_COOKIE_SECURE'] = True  # Только HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Запрет доступа из JS
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Защита от CSRF
app.config['PERMANENT_SESSION_LIFETIME'] = 3600  # 1 час

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Пожалуйста, войдите в систему'
login_manager.login_message_category = 'warning'

@login_manager.user_loader
def load_user(user_id):
    db = Database()
    user_data = db.get_user_by_id(int(user_id))
    if user_data:
        return User(**user_data)
    return None

db = Database()

# Регистрация blueprint авторизации
app.register_blueprint(auth_bp)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def require_role(*roles):
    """Декоратор для проверки ролей."""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if current_user.role not in roles:
                flash('У вас нет прав для этого действия', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ✅ БЕЗОПАСНОСТЬ: Ограничение попыток входа (простая реализация)
from collections import defaultdict
import time

login_attempts = defaultdict(list)

def check_login_rate_limit(ip_address, max_attempts=5, window=300):
    """Проверка: не более 5 попыток за 5 минут"""
    now = time.time()
    # Очищаем старые попытки
    login_attempts[ip_address] = [
        t for t in login_attempts[ip_address] 
        if now - t < window
    ]
    
    if len(login_attempts[ip_address]) >= max_attempts:
        return False  # Слишком много попыток
    
    login_attempts[ip_address].append(now)
    return True


# ---------- Маршруты ----------
@app.route('/')
@login_required
def index():
    category = request.args.get('category')
    sort_by = request.args.get('sort', 'id')
    order = request.args.get('order', 'asc')
    products = db.get_all(category=category, sort_by=sort_by, order=order)
    categories = db.get_categories()
    stats = db.get_statistics()
    return render_template('index.html',
                           products=products,
                           categories=categories,
                           current_category=category,
                           sort_by=sort_by,
                           order=order,
                           stats=stats)


@app.route('/add', methods=['GET', 'POST'])
@require_role('admin', 'manager')
def add():
    # ... (остальной код без изменений)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '').strip()
        try:
            quantity = int(request.form.get('quantity', 0))
            price = float(request.form.get('price', 0))
        except ValueError:
            flash('Количество и цена должны быть числами!', 'danger')
            return redirect(url_for('add'))

        if not name or not category:
            flash('Название и категория обязательны!', 'danger')
            return redirect(url_for('add'))
        if quantity < 0 or price < 0:
            flash('Количество и цена не могут быть отрицательными!', 'danger')
            return redirect(url_for('add'))

        # Загрузка фото
        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                filename = timestamp + filename
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_path = f'uploads/{filename}'

        db.add(name, category, quantity, price, image_path, current_user.id)
        flash(f'Товар «{name}» добавлен!', 'success')
        return redirect(url_for('index'))
    return render_template('add.html')


# ... (остальные маршруты без изменений: edit, stock, delete, search, transactions, dashboard, export)