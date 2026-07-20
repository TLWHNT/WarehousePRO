#!/usr/bin/env python3
"""
Скрипт создания первого администратора.
Запускается ОДИН РАЗ при первоначальной настройке.
"""
from database import Database
from getpass import getpass

def create_first_admin():
    db = Database()
    
    print("🔐 Создание первого администратора")
    print("=" * 40)
    
    username = input("Имя пользователя: ").strip()
    if not username:
        print("❌ Имя пользователя не может быть пустым!")
        return
    
    # Проверяем, существует ли пользователь
    if db.get_user_by_username(username):
        print(f"❌ Пользователь '{username}' уже существует!")
        return
    
    # Ввод пароля с подтверждением
    while True:
        password = getpass("Пароль: ")
        if len(password) < 8:
            print("❌ Пароль должен быть не менее 8 символов!")
            continue
        
        password_confirm = getpass("Подтвердите пароль: ")
        if password != password_confirm:
            print("❌ Пароли не совпадают!")
            continue
        
        break
    
    # Создаём пользователя
    db.create_user(username, password, 'admin')
    print(f"\n✅ Администратор '{username}' успешно создан!")
    print(" Теперь удалите этот файл (create_admin.py) для безопасности!")

if __name__ == '__main__':
    create_first_admin()