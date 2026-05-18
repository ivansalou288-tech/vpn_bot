import sqlite3

# Подключаемся к базе данных
conn = sqlite3.connect(r'd:\vpn_bot\x-ui.db')
cursor = conn.cursor()

# Получаем структуру таблицы client_traffics
print("=== Структура таблицы client_traffics ===")
cursor.execute("PRAGMA table_info(client_traffics)")
columns = cursor.fetchall()
for col in columns:
    print(col)

print("\n=== Пример данных из client_traffics ===")
cursor.execute("SELECT * FROM client_traffics LIMIT 10")
rows = cursor.fetchall()
for row in rows:
    print(row)

conn.close()
