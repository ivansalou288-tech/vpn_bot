import sqlite3
import sys
import os
from datetime import datetime

# Добавляем текущую директорию в path для импорта модулей
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api import add_client

def parse_tg_id_from_email(email):
    """
    Парсит tg_id из email формата: {prefix}_{tg_id}_{inbound_id}
    Например: "abc123_123456789_1" -> tg_id = 123456789
    """
    if not email:
        return None
    
    try:
        parts = email.split('_')
        if len(parts) >= 2:
            # tg_id - это вторая часть (индекс 1)
            tg_id = int(parts[1])
            return tg_id
    except (ValueError, IndexError):
        pass
    
    return None

def parse_prefix_from_email(email):
    """
    Парсит prefix из email формата: {prefix}_{tg_id}_{inbound_id}
    Например: "abc123_123456789_1" -> prefix = "abc123"
    """
    if not email:
        return ""
    
    try:
        parts = email.split('_')
        if len(parts) >= 1:
            return parts[0]
    except IndexError:
        pass
    
    return ""

def convert_expiry_to_date(expiry_time_ms):
    """
    Конвертирует expiry_time из миллисекунд в формат DD.MM.YYYY
    """
    if not expiry_time_ms or expiry_time_ms == 0:
        # Если срок не ограничен, ставим дату через 1 год
        from datetime import timedelta
        future_date = datetime.now() + timedelta(days=365)
        return future_date.strftime("%d.%m.%Y")
    
    try:
        # expiry_time в миллисекундах
        timestamp_s = expiry_time_ms / 1000
        dt = datetime.fromtimestamp(timestamp_s)
        return dt.strftime("%d.%m.%Y")
    except (ValueError, OSError):
        # Если конвертация не удалась, ставим дату через 1 год
        from datetime import timedelta
        future_date = datetime.now() + timedelta(days=365)
        return future_date.strftime("%d.%m.%Y")

def migrate_clients_from_db(db_path):
    """
    Читает базу данных x-ui.db и добавляет клиентов через add_client
    """
    print(f"[MIGRATE] Чтение базы данных: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Проверяем структуру таблицы
    cursor.execute("PRAGMA table_info(client_traffics)")
    columns = cursor.fetchall()
    print(f"[MIGRATE] Структура таблицы client_traffics:")
    for col in columns:
        print(f"  - {col}")
    
    # Получаем все данные из client_traffics
    cursor.execute("SELECT * FROM client_traffics")
    rows = cursor.fetchall()
    
    print(f"[MIGRATE] Найдено записей: {len(rows)}")
    
    # Получаем имена колонок
    column_names = [description[0] for description in cursor.description]
    print(f"[MIGRATE] Колонки: {column_names}")
    
    # Находим индексы нужных колонок
    try:
        email_index = column_names.index('email')
        expiry_time_index = column_names.index('expiry_time')
    except ValueError as e:
        print(f"[MIGRATE] Ошибка: не найдены нужные колонки: {e}")
        conn.close()
        return
    
    success_count = 0
    error_count = 0
    
    for row in rows:
        email = row[email_index]
        expiry_time = row[expiry_time_index]
        
        # Парсим tg_id из email
        tg_id = parse_tg_id_from_email(email)
        if not tg_id:
            print(f"[MIGRATE] Пропуск: не удалось парсить tg_id из email: {email}")
            error_count += 1
            continue
        
        # Парсим prefix из email
        prefix = parse_prefix_from_email(email)
        
        # Определяем inbound_id из email (последняя часть)
        try:
            parts = email.split('_')
            inbound_id = int(parts[-1]) if len(parts) >= 3 else 1
        except (ValueError, IndexError):
            inbound_id = 1
        
        # Конвертируем expiry_time в дату
        end_date = convert_expiry_to_date(expiry_time)
        
        print(f"[MIGRATE] Обработка: email={email}, tg_id={tg_id}, prefix={prefix}, inbound_id={inbound_id}, end_date={end_date}")
        
        # Добавляем клиента через add_client
        try:
            result = add_client(inbound_id, prefix, tg_id, end_date)
            if result.get('success'):
                print(f"[MIGRATE] ✓ Успешно добавлен клиент: tg_id={tg_id}, inbound_id={inbound_id}")
                success_count += 1
            else:
                print(f"[MIGRATE] ✗ Ошибка добавления клиента: tg_id={tg_id}, error={result.get('error')}")
                error_count += 1
        except Exception as e:
            print(f"[MIGRATE] ✗ Исключение при добавлении клиента: tg_id={tg_id}, error={e}")
            error_count += 1
    
    conn.close()
    
    print(f"\n[MIGRATE] Итого: успешно={success_count}, ошибок={error_count}")

if __name__ == "__main__":
    db_path = r'x-ui.db'
    migrate_clients_from_db(db_path)
