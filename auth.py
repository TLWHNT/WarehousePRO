from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from database import Database
from models import User

auth_bp = Blueprint('auth', __name__)
db = Database()


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        user_data = db.get_user_by_username(username)
        
        # Проверяем пароль используя check_password_hash
        if user_data and check_password_hash(user_data['password_hash'], password):
            # Создаём объект User после успешной проверки
            user = User(
                id=user_data['id'],
                username=user_data['username'],
                password_hash=user_data['password_hash'],
                role=user_data['role']
            )
            login_user(user, remember=True)
            flash(f'Добро пожаловать, {username}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль', 'danger')
    
    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    if not current_user.is_admin:
        flash('Только администратор может создавать пользователей', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'viewer')
        
        if not username or not password:
            flash('Заполните все поля', 'danger')
            return redirect(url_for('auth.register'))
        
        if db.get_user_by_username(username):
            flash('Пользователь с таким именем уже существует', 'danger')
            return redirect(url_for('auth.register'))
        
        db.create_user(username, password, role)
        flash(f'Пользователь {username} создан с ролью {role}', 'success')
        return redirect(url_for('auth.users_list'))
    
    return render_template('register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/users')
@login_required
def users_list():
    if not current_user.is_admin:
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))
    
    users = db.get_all_users()
    return render_template('users.html', users=users)


@auth_bp.route('/user/delete/<int:uid>', methods=['POST'])
@login_required
def delete_user(uid):
    if not current_user.is_admin:
        flash('Доступ запрещён', 'danger')
        return redirect(url_for('index'))
    
    if uid == current_user.id:
        flash('Нельзя удалить самого себя', 'danger')
        return redirect(url_for('auth.users_list'))
    
    db.delete_user(uid)
    flash('Пользователь удалён', 'success')
    return redirect(url_for('auth.users_list'))