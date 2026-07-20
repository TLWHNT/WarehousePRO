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


# ========== МАРШРУТЫ ==========

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


@app.route('/edit/<int:pid>', methods=['GET', 'POST'])
@require_role('admin', 'manager')
def edit(pid):
    product = db.get_by_id(pid)
    if not product:
        flash('Товар не найден!', 'danger')
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '').strip()
        try:
            quantity = int(request.form.get('quantity', 0))
            price = float(request.form.get('price', 0))
        except ValueError:
            flash('Количество и цена должны быть числами!', 'danger')
            return redirect(url_for('edit', pid=pid))

        if not name or not category or quantity < 0 or price < 0:
            flash('Проверьте введённые данные!', 'danger')
            return redirect(url_for('edit', pid=pid))

        # Загрузка нового фото
        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                filename = timestamp + filename
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_path = f'uploads/{filename}'

        db.update(pid, name, category, quantity, price, image_path, current_user.id)
        flash('Товар обновлён!', 'success')
        return redirect(url_for('index'))
    return render_template('edit.html', product=product)


@app.route('/stock/<int:pid>', methods=['POST'])
@require_role('admin', 'manager')
def stock(pid):
    try:
        delta = int(request.form.get('delta', 0))
    except ValueError:
        flash('Изменение должно быть числом!', 'danger')
        return redirect(url_for('index'))

    note = request.form.get('note', '').strip() or None
    new_qty, err = db.change_stock(pid, delta, note, current_user.id)
    if err:
        flash(err, 'danger')
    else:
        flash(f'Остаток обновлён: {new_qty} шт.', 'success')
    return redirect(url_for('index'))


@app.route('/delete/<int:pid>', methods=['POST'])
@require_role('admin')
def delete(pid):
    if db.delete(pid, current_user.id):
        flash('Товар удалён.', 'success')
    else:
        flash('Товар не найден.', 'danger')
    return redirect(url_for('index'))


@app.route('/search')
@login_required
def search():
    keyword = request.args.get('q', '').strip()
    results = db.search(keyword) if keyword else []
    return render_template('search.html', results=results, keyword=keyword)


@app.route('/transactions')
@login_required
def transactions():
    txs = db.get_transactions(limit=200)
    return render_template('transactions.html', transactions=txs)


@app.route('/transactions/clear', methods=['POST'])
@require_role('admin')
def clear_transactions():
    db.clear_transactions()
    flash('История операций очищена.', 'info')
    return redirect(url_for('transactions'))


@app.route('/dashboard')
@login_required
def dashboard():
    stats = db.get_statistics()
    return render_template('dashboard.html', stats=stats)


@app.route('/export')
@login_required
def export():
    export_dir = os.path.join(app.root_path, 'exports')
    os.makedirs(export_dir, exist_ok=True)
    filepath = os.path.join(export_dir, 'warehouse.csv')
    count = db.export_to_csv(filepath)
    flash(f'Экспортировано товаров: {count}', 'success')
    return send_file(filepath, as_attachment=True, download_name='warehouse.csv')


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)