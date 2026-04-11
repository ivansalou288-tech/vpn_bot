from fastapi import FastAPI, HTTPException, Header, Request
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Float, DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import asyncio
import requests
import os
import sys

# Добавляем путь для импорта api.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from api import add_client, renew_subscription
from api_sheets import add_vpn_sale

# Импортируем aiogram для отправки сообщений
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Получаем токен из переменной окружения или используем дефолтный
PAYCORE_API_KEY ='paycore__kzCrJ9vpN0pF7dkM%lc2D5V7/rKfbbV^ftafi%PXhH^='
PAYCORE_API_URL = "https://pay.pay-core.ru/api/init"
WEBHOOK_URL = 'https://www.ezhqpy.ru:2500/payment/webhook'
BOT_TOKEN = "8358697144:AAGppsqXjG9S08nGLUpghL-jUfTz9H4gj58"
OPERATOR_CHAT_ID = [1240656726, 1401086794]

# Настройка БД
Base = declarative_base()
engine = create_engine("sqlite:///payments.db", echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, unique=True, index=True)  # Наш внутренний ID
    paycore_order_id = Column(String, unique=True, index=True, nullable=True)  # ID от PayCore
    message_id = Column(Integer, nullable=True)  # ID сообщения в Telegram для редактирования
    amount = Column(Float)
    final_amount = Column(Float, nullable=True)
    commission_amount = Column(Float, nullable=True)
    method = Column(String)
    user_id = Column(Integer)
    username = Column(String, nullable=True)
    time_months = Column(Integer)
    is_renewal = Column(Integer, default=0)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True)

# Создаем таблицы
Base.metadata.create_all(bind=engine)

# Pydantic модели
class PaymentWebhook(BaseModel):
    order_id: str
    amount: float
    final_amount: float
    commission_amount: float
    method: str

class PaymentInit(BaseModel):
    method: str
    amount: float
    description: str
    user_id: int
    username: str = None
    time_months: int
    is_renewal: bool = False

# FastAPI приложение
app = FastAPI(title="VPN Bot Payment API")

# Ссылка на бот для уведомлений
bot_instance = None

def set_bot_instance(bot):
    global bot_instance
    bot_instance = bot

@app.post("/payment/webhook")
async def payment_webhook(data: PaymentWebhook, request: Request):
    """Endpoint для приёма уведомлений от PayCore - автоматически создаёт подписку"""
    print(f"[PayCore] ========== WEBHOOK RECEIVED ==========")
    print(f"[PayCore] Webhook received: {data}")
    print(f"[PayCore] order_id: {data.order_id}")
    print(f"[PayCore] amount: {data.amount}")
    print(f"[PayCore] status: completed (implicit)")
    print(f"[PayCore] Request headers: {dict(data.__dict__)}")
    print(f"[PayCore] Request IP: {request.client.host if hasattr(request, 'client') else 'unknown'}")
    db = SessionLocal()
    try:
        # Ищем платёж в БД по paycore_order_id
        payment = db.query(Payment).filter(Payment.paycore_order_id == data.order_id).first()
        
        if not payment:
            # Fallback: попробуем найти по нашему order_id (на всякий случай)
            payment = db.query(Payment).filter(Payment.order_id == data.order_id).first()
        
        if not payment:
            print(f"[PayCore] Payment not found for order_id: {data.order_id}")
            raise HTTPException(status_code=404, detail="Payment not found")
        
        # Обновляем информацию о платеже
        payment.final_amount = data.final_amount
        payment.commission_amount = data.commission_amount
        payment.status = "completed"
        payment.updated_at = datetime.utcnow()
        
        db.commit()
        
        # Автоматически создаём или продлеваем подписку
        user_id = payment.user_id
        time_months = payment.time_months
        is_renewal = bool(payment.is_renewal)
        username = payment.username or f"user_{user_id}"
        
        # Рассчитываем дату окончания подписки
        from datetime import timedelta
        current_time = datetime.now()
        end_time = current_time + timedelta(days=time_months * 31)
        end_date_str = end_time.strftime("%d.%m.%Y")
        
        subscription_result = None
        
        if is_renewal:
            # Продлеваем существующую подписку
            subscription_result = renew_subscription(user_id, time_months)
        else:
            # Создаём новую подписку
            for i in range(1, 4):
                subscription_result = add_client(i, username, user_id, end_date_str)
        
        # Записываем продажу в Google Sheets (чистый заработок за вычетом комиссии)
        try:
            add_vpn_sale(user_id, username, time_months, data.final_amount)
            print(f"[PayCore] Sale recorded in sheets: user={user_id}, profit={data.final_amount}")
        except Exception as e:
            print(f"[PayCore] Failed to record sale in sheets: {e}")
        
        # Уведомляем пользователя и оператора
        try:
            # Создаём бота для отправки сообщений
            bot = Bot(token=BOT_TOKEN)
            # final_amount - это сумма после комиссии (прибыль)
            # commission_amount - комиссия PayCore
            profit = data.final_amount
            
            if subscription_result and subscription_result.get('success'):
                user_message = (
                    f"<tg-emoji emoji-id='5416081784641168838'>✅</tg-emoji> <b>Оплата успешно завершена!</b>\n\n"
                    f"<tg-emoji emoji-id='5440621591387980068'>⏰</tg-emoji> Период: {time_months} мес.\n"
                    f"<tg-emoji emoji-id='5417924076503062111'>💰</tg-emoji> Оплачено: {data.amount}₽\n"
                    f"<tg-emoji emoji-id='5440621591387980068'>📅</tg-emoji> Действует до: {end_date_str}\n\n"
                    f"{'Подписка продлена' if is_renewal else 'Подписка активирована'}! 🎉"
                )
            else:
                user_message = (
                    f"<tg-emoji emoji-id='5416081784641168838'>✅</tg-emoji> <b>Оплата получена!</b>\n\n"
                    f"Ваша оплата на {data.amount}₽ получена.\n"
                    f"Оператор скоро активирует вашу подписку."
                )
            
            user_keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="Моя подписка", callback_data="subscription", style="primary")]
                ]
            )
            
            # Отправляем сообщение пользователю
            await bot.send_message(
                chat_id=user_id,
                text=user_message,
                reply_markup=user_keyboard,
                parse_mode=ParseMode.HTML
            )
            print(f"[PayCore] Success message sent to user {user_id}")
            
            # Удаляем старое сообщение об оплате, если есть message_id
            if payment.message_id:
                try:
                    await bot.delete_message(chat_id=user_id, message_id=payment.message_id)
                    print(f"[PayCore] Deleted old payment message {payment.message_id}")
                except Exception as e:
                    print(f"[PayCore] Could not delete old message: {e}")
            
            # Уведомление оператору
            operator_message = (
                f"<tg-emoji emoji-id='5416081784641168838'>💰</tg-emoji> <b>Новая оплата через СБП!</b>\n\n"
                f"<tg-emoji emoji-id='5440621591387980068'>👤</tg-emoji> Пользователь: @{payment.username or 'N/A'} (ID: {payment.user_id})\n"
                f"<tg-emoji emoji-id='5440621591387980068'>⏰</tg-emoji> Тип: {'Продление' if is_renewal else 'Покупка'}\n"
                f"<tg-emoji emoji-id='5440621591387980068'>📅</tg-emoji> Период: {payment.time_months} мес.\n\n"
                f"<tg-emoji emoji-id='5417924076503062111'>💵</tg-emoji> Сумма: {data.amount}₽\n"
                f"<tg-emoji emoji-id='5416081784641168838'>📉</tg-emoji> Комиссия: {data.commission_amount}₽\n"
                f"<tg-emoji emoji-id='5282843764451195532'>💎</tg-emoji> <b>Прибыль: {profit}₽</b>\n\n"
                f"<tg-emoji emoji-id='5416081784641168838'>✅</tg-emoji> Подписка {'продлена' if is_renewal else 'создана'} автоматически\n"
                f"Order ID: <code>{data.order_id}</code>"
            )
            
            for chat_id in OPERATOR_CHAT_ID:
                await bot.send_message(
                    chat_id=chat_id,
                    text=operator_message,
                    parse_mode=ParseMode.HTML
                )
                print(f"[PayCore] Operator notification sent to {chat_id}")
            
            # Закрываем сессию бота
            await bot.session.close()
            
        except Exception as e:
            print(f"[PayCore] Failed to send notifications: {e}")
            import traceback
            traceback.print_exc()
        
        return {"status": "success", "message": "Payment processed and subscription created"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

def create_paycore_payment(amount: float, description: str, user_id: int, username: str = None, time_months: int = 1, is_renewal: bool = False):
    """Создаёт платёж через PayCore API"""
    
    print(f"[PayCore] Creating payment: amount={amount}, user_id={user_id}, username={username}")
    
    # Генерируем уникальный order_id
    import uuid
    order_id = f"vpn_{user_id}_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:8]}"
    
    print(f"[PayCore] Generated order_id: {order_id}")
    
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": PAYCORE_API_KEY
    }
    
    data = {
        "method": "sbp",
        "amount": amount,
        "description": description,
        "returnLink": WEBHOOK_URL,
        "orderId": order_id,
        "metadata": {
            "user_id": user_id,
            "username": username,
            "time_months": time_months,
            "is_renewal": is_renewal
        }
    }
    
    print(f"[PayCore] Request URL: {PAYCORE_API_URL}")
    print(f"[PayCore] Request headers: {headers}")
    print(f"[PayCore] Request data: {data}")
    
    try:
        response = requests.post(PAYCORE_API_URL, json=data, headers=headers, timeout=30)
        print(f"[PayCore] Response status: {response.status_code}")
        print(f"[PayCore] Response body: {response.text}")
        
        response_data = response.json()
        print(f"[PayCore] Parsed response: {response_data}")
        
        if response.status_code == 200 and response_data.get("url"):
            print(f"[PayCore] Payment created successfully, order_id: {order_id}")
            # Сохраняем платёж в БД
            db = SessionLocal()
            try:
                payment = Payment(
                    order_id=order_id,
                    paycore_order_id=response_data.get("order_id"),  # Сохраняем PayCore ID
                    amount=amount,
                    method="sbp",
                    user_id=user_id,
                    username=username,
                    time_months=time_months,
                    is_renewal=1 if is_renewal else 0,
                    status="pending"
                )
                db.add(payment)
                db.commit()
                print(f"[PayCore] Payment saved to DB: {order_id}")
                
                return {
                    "success": True,
                    "order_id": order_id,
                    "payment_url": response_data.get("url"),
                    "message": "Payment created"
                }
            finally:
                db.close()
        else:
            error_msg = response_data.get("message", response_data.get("error", "Unknown error"))
            print(f"[PayCore] Error creating payment: {error_msg}, status: {response.status_code}")
            return {
                "success": False,
                "error": error_msg,
                "status_code": response.status_code,
                "full_response": response_data
            }
            
    except Exception as e:
        print(f"[PayCore] Exception during payment creation: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }

def update_payment_message_id(order_id: str, message_id: int):
    """Обновляет ID сообщения в Telegram для платежа"""
    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.order_id == order_id).first()
        if payment:
            payment.message_id = message_id
            db.commit()
            print(f"[PayCore] Message ID {message_id} saved for order {order_id}")
            return True
        return False
    finally:
        db.close()

def get_payment_status(order_id: str):
    """Получает статус платежа из БД"""
    db = SessionLocal()
    try:
        payment = db.query(Payment).filter(Payment.order_id == order_id).first()
        if payment:
            return {
                "exists": True,
                "status": payment.status,
                "amount": payment.amount,
                "final_amount": payment.final_amount,
                "commission": payment.commission_amount,
                "message_id": payment.message_id,
                "created_at": payment.created_at.isoformat() if payment.created_at else None
            }
        return {"exists": False}
    finally:
        db.close()

@app.get("/payment/test")
def test_webhook():
    """Тестовый endpoint для проверки доступности webhook"""
    return {"status": "webhook is accessible", "url": "/payment/webhook"}

if __name__ == "__main__":
    import uvicorn
    print("[PayCore] Starting payment API server...")
    print(f"[PayCore] Webhook URL: https://www.ezhqpy.ru:2556/payment/webhook")
    print(f"[PayCore] Test URL: https://www.ezhqpy.ru:2556/payment/test")
    
    # Используем fullchain.pem вместо cert.pem для полной цепочки сертификатов
    uvicorn.run(app, host="0.0.0.0", port=2556, 
                ssl_keyfile='/etc/letsencrypt/live/www.ezhqpy.ru/privkey.pem', 
                ssl_certfile='/etc/letsencrypt/live/www.ezhqpy.ru/fullchain.pem')
