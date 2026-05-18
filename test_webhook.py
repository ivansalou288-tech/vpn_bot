import requests
import json

# Тестовые данные для webhook
webhook_data = {
    "order_id": "test_123",
    "amount": 100,
    "final_amount": 100,
    "commission_amount": 0,
    "status": "completed"
}

url = "https://www.ezh-dev.ru:2500/payment/webhook"

print(f"[TEST] Отправка POST запроса на: {url}")
print(f"[TEST] Данные: {json.dumps(webhook_data, indent=2)}")

try:
    response = requests.post(url, json=webhook_data, verify=False, timeout=10)
    print(f"[TEST] Статус код: {response.status_code}")
    print(f"[TEST] Ответ: {response.text}")
except Exception as e:
    print(f"[TEST] Ошибка: {e}")
