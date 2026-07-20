from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


class User(UserMixin):
    """Модель пользователя."""
    
    def __init__(self, id, username, password_hash, role='viewer'):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.role = role  # admin, manager, viewer
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @property
    def is_admin(self):
        return self.role == 'admin'
    
    @property
    def is_manager(self):
        return self.role == 'manager'
    
    @property
    def role_name(self):
        roles = {
            'admin': 'Администратор',
            'manager': 'Кладовщик',
            'viewer': 'Наблюдатель'
        }
        return roles.get(self.role, 'Неизвестно')