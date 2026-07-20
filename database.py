import sqlite3
import csv
from datetime import datetime
from contextlib import contextmanager
from werkzeug.security import generate_password_hash

DB_NAME = 'warehouse.db'


class Database:
    """Репозиторий для работы с БД склада."""

    def __init__(self, db_path=DB_NAME):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для работы с БД."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        """Инициализация базы данных."""
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'viewer',
                    created_at TEXT NOT NULL
                );
                
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK(quantity >= 0),
                    price REAL NOT NULL CHECK(price >= 0),
                    image_path TEXT,
                    created_at TEXT NOT NULL
                );
                
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER,
                    product_name TEXT,
                    operation TEXT NOT NULL,
                    quantity_change INTEGER DEFAULT 0,
                    note TEXT,
                    user_id INTEGER,
                    timestamp TEXT NOT NULL
                );
                
                CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
                CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
                CREATE INDEX IF NOT EXISTS idx_transactions_ts ON transactions(timestamp);
                CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
            ''')

    # ========== ПОЛЬЗОВАТЕЛИ ==========
    def get_user_by_username(self, username):
        """Получить пользователя по имени."""
        with self.get_connection() as conn:
            row = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
            if row:
                return {
                    'id': row['id'],
                    'username': row['username'],
                    'password_hash': row['password_hash'],
                    'role': row['role']
                }
            return None

    def get_user_by_id(self, user_id):
        """Получить пользователя по ID."""
        with self.get_connection() as conn:
            row = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
            if row:
                return {
                    'id': row['id'],
                    'username': row['username'],
                    'password_hash': row['password_hash'],
                    'role': row['role']
                }
            return None

    def create_user(self, username, password, role='viewer'):
        """Создать нового пользователя."""
        with self.get_connection() as conn:
            conn.execute(
                'INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)',
                (username, generate_password_hash(password), role,
                 datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            )

    def get_all_users(self):
        """Получить всех пользователей."""
        with self.get_connection() as conn:
            rows = conn.execute('SELECT id, username, role, created_at FROM users ORDER BY id').fetchall()
            return [dict(r) for r in rows]

    def delete_user(self, user_id):
        """Удалить пользователя."""
        with self.get_connection() as conn:
            conn.execute('DELETE FROM users WHERE id = ?', (user_id,))

    # ========== ТОВАРЫ ==========
    def get_all(self, category=None, sort_by='id', order='asc'):
        """Получить все товары."""
        allowed_sort = {'id': 'id', 'name': 'name', 'category': 'category',
                        'quantity': 'quantity', 'price': 'price'}
        sort_col = allowed_sort.get(sort_by, 'id')
        order_dir = 'DESC' if order.lower() == 'desc' else 'ASC'

        with self.get_connection() as conn:
            if category:
                rows = conn.execute(
                    f'SELECT * FROM products WHERE category = ? ORDER BY {sort_col} {order_dir}',
                    (category,)
                ).fetchall()
            else:
                rows = conn.execute(
                    f'SELECT * FROM products ORDER BY {sort_col} {order_dir}'
                ).fetchall()
            return [dict(r) for r in rows]

    def get_by_id(self, product_id):
        """Получить товар по ID."""
        with self.get_connection() as conn:
            row = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
            return dict(row) if row else None

    def get_categories(self):
        """Получить все категории."""
        with self.get_connection() as conn:
            rows = conn.execute('SELECT DISTINCT category FROM products ORDER BY category').fetchall()
            return [r['category'] for r in rows]

    def add(self, name, category, quantity, price, image_path=None, user_id=None):
        """Добавить новый товар."""
        with self.get_connection() as conn:
            cur = conn.execute(
                '''INSERT INTO products (name, category, quantity, price, image_path, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (name, category, quantity, price, image_path,
                 datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            )
            self._log(conn, cur.lastrowid, name, 'Добавлен', quantity,
                      f'Цена: {price:.2f} руб.', user_id)
            return cur.lastrowid

    def update(self, product_id, name, category, quantity, price, image_path=None, user_id=None):
        """Обновить товар."""
        with self.get_connection() as conn:
            old = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
            if not old:
                return False
            
            if image_path:
                conn.execute(
                    '''UPDATE products SET name=?, category=?, quantity=?, price=?, image_path=?
                       WHERE id=?''',
                    (name, category, quantity, price, image_path, product_id)
                )
            else:
                conn.execute(
                    '''UPDATE products SET name=?, category=?, quantity=?, price=?
                       WHERE id=?''',
                    (name, category, quantity, price, product_id)
                )
            
            self._log(conn, product_id, name, 'Изменён', quantity - old['quantity'],
                      f'Старая цена: {old["price"]:.2f} → Новая: {price:.2f}', user_id)
            return True

    def change_stock(self, product_id, delta, note=None, user_id=None):
        """Изменить количество товара."""
        with self.get_connection() as conn:
            row = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
            if not row:
                return None, 'Товар не найден'
            new_qty = row['quantity'] + delta
            if new_qty < 0:
                return None, f'Нельзя списать больше, чем есть (остаток: {row["quantity"]})'
            conn.execute('UPDATE products SET quantity = ? WHERE id = ?', (new_qty, product_id))
            op = 'Приход' if delta > 0 else 'Расход'
            self._log(conn, product_id, row['name'], op, delta, note, user_id)
            return new_qty, None

    def delete(self, product_id, user_id=None):
        """Удалить товар."""
        with self.get_connection() as conn:
            row = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
            if not row:
                return False
            conn.execute('DELETE FROM products WHERE id = ?', (product_id,))
            self._log(conn, product_id, row['name'], 'Удалён', -row['quantity'], user_id=user_id)
            return True

    # ========== ЛОГИРОВАНИЕ ==========
    def _log(self, conn, product_id, product_name, operation, quantity_change=0, note=None, user_id=None):
        """Записать операцию в лог."""
        conn.execute(
            '''INSERT INTO transactions
               (product_id, product_name, operation, quantity_change, note, user_id, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (product_id, product_name, operation, quantity_change, note, user_id,
             datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )

    # ========== ПОИСК ==========
    def search(self, keyword):
        """Поиск товаров."""
        with self.get_connection() as conn:
            rows = conn.execute(
                'SELECT * FROM products WHERE name LIKE ? OR category LIKE ?',
                (f'%{keyword}%', f'%{keyword}%')
            ).fetchall()
            return [dict(r) for r in rows]

    # ========== СТАТИСТИКА ==========
    def get_statistics(self):
        """Получить статистику склада."""
        with self.get_connection() as conn:
            total = conn.execute(
                'SELECT COUNT(*), COALESCE(SUM(quantity),0), COALESCE(SUM(quantity*price),0) FROM products'
            ).fetchone()
            low = conn.execute(
                'SELECT name, quantity FROM products WHERE quantity BETWEEN 1 AND 5'
            ).fetchall()
            out = conn.execute(
                'SELECT name FROM products WHERE quantity = 0'
            ).fetchall()
            by_cat = conn.execute('''
                SELECT category, COUNT(*) as cnt, SUM(quantity*price) as value
                FROM products GROUP BY category ORDER BY value DESC
            ''').fetchall()
            return {
                'count': total[0],
                'total_qty': total[1],
                'total_value': total[2],
                'low_stock': [dict(r) for r in low],
                'out_of_stock': [r[0] for r in out],
                'by_category': [dict(r) for r in by_cat],
            }

    # ========== ИСТОРИЯ ==========
    def get_transactions(self, limit=100):
        """Получить историю операций."""
        with self.get_connection() as conn:
            rows = conn.execute('''
                SELECT t.*, u.username
                FROM transactions t
                LEFT JOIN users u ON t.user_id = u.id
                ORDER BY t.timestamp DESC LIMIT ?
            ''', (limit,)).fetchall()
            return [dict(r) for r in rows]

    def clear_transactions(self):
        """Очистить историю операций."""
        with self.get_connection() as conn:
            conn.execute('DELETE FROM transactions')

    # ========== ЭКСПОРТ ==========
    def export_to_csv(self, filepath):
        """Экспорт товаров в CSV."""
        with self.get_connection() as conn:
            rows = conn.execute('SELECT * FROM products').fetchall()
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(['ID', 'Название', 'Категория', 'Количество', 'Цена'])
            for r in rows:
                writer.writerow([r['id'], r['name'], r['category'], r['quantity'], f"{r['price']:.2f}"])
        return len(rows)