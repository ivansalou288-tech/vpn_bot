from fastapi import FastAPI, HTTPException, Header, Request
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Column, Integer, String, Float, DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import asyncio
import requests
import os
import sys

# Добавляем путь для импорта api.py
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from api import add_client, renew_subscription
from api_sheets import add_vpn_sale
from config import webhook_url

# Импортируем aiogram для отправки сообщений
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Получаем токен из переменной окружения или используем дефолтный
PAYCORE_API_KEY ='paycore__kzCrJ9vpN0pF7dkM%lc2D5V7/rKfbbV^ftafi%PXhH^='
PAYCORE_API_URL = "https://pay.pay-core.ru/api/init"
WEBHOOK_URL = webhook_url()
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




# Ссылка на бот для уведомлений
bot_instance = None

def set_bot_instance(bot):
    global bot_instance
    bot_instance = bot


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
    
    print(f"[PayCore] ========== CREATING PAYMENT ==========")
    print(f"[PayCore] Webhook URL (returnLink): {WEBHOOK_URL}")
    print(f"[PayCore] Request URL: {PAYCORE_API_URL}")
    print(f"[PayCore] Request headers: {headers}")
    print(f"[PayCore] Request data: {data}")
    print(f"[PayCore] Webhook accessibility check: {webhook_url()}")
    
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
                "time_months": payment.time_months,
                "created_at": payment.created_at.isoformat() if payment.created_at else None
            }
        return {"exists": False}
    finally:
        db.close()


# ============================================================================
# CRYPTOBOT WEBHOOK - АВТОМАТИЧЕСКАЯ ОБРАБОТКА ОПЛАТЫ
# ============================================================================

CRYPTOBOT_BOT_TOKEN = "8358697144:AAGppsqXjG9S08nGLUpghL-jUfTz9H4gj58"
CRYPTOBOT_OPERATOR_CHAT_ID = 1240656726
RUB_TO_USD_RATE = 70


async def send_crypto_notifications(user_id: int, username: str, time_months: int, amount_rub: int, is_renewal: bool, end_date_str: str, subscription_result):
    """Отправляет уведомления об оплате CryptoBot"""
    try:
        bot = Bot(token=CRYPTOBOT_BOT_TOKEN)
        
        months_text = "год" if time_months == 12 else f"{time_months} мес."
        amount_usd = round(amount_rub / RUB_TO_USD_RATE, 2)
        
        if subscription_result and subscription_result.get('success'):
            user_message = (
                f"💎 <b>Оплата успешно завершена!</b>\n\n"
                f"⏰ Период: {months_text}\n"
                f"💰 Оплачено: {amount_rub}₽ ({amount_usd} USDT)\n"
                f"📅 Действует до: {end_date_str}\n\n"
                f"{'Подписка продлена' if is_renewal else 'Подписка активирована'}! 🎉"
            )
        else:
            user_message = (
                f"💎 <b>Оплата получена!</b>\n\n"
                f"Ваша оплата на {amount_rub}₽ ({amount_usd} USDT) получена."
            )
        
        user_keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Моя подписка", callback_data="subscription")]])
        
        try:
            await bot.send_message(chat_id=user_id, text=user_message, reply_markup=user_keyboard, parse_mode=ParseMode.HTML)
        except:
            await bot.send_message(chat_id=user_id, text=f"✅ Оплата успешна! Период: {months_text}")
        
        operator_message = (
            f"💎 <b>Новая оплата через CryptoBot!</b>\n\n"
            f"👤 Пользователь: @{username or 'N/A'} (ID: {user_id})\n"
            f"⏰ Тип: {'Продление' if is_renewal else 'Покупка'}\n"
            f"📅 Период: {time_months} мес.\n\n"
            f"💵 Сумма: {amount_rub}₽ ({amount_usd} USDT)\n"
            f"✅ Подписка {'продлена' if is_renewal else 'создана'} автоматически"
        )
        
        await bot.send_message(chat_id=CRYPTOBOT_OPERATOR_CHAT_ID, text=operator_message, parse_mode=ParseMode.HTML)
        await bot.session.close()
    except Exception as e:
        print(f"[CryptoBot] Ошибка отправки уведомлений: {e}")


@app.post("/crypto/webhook")
async def crypto_webhook(request: Request):
    """Вебхук от CryptoBot - автоматическая обработка платежа"""
    print(f"[CryptoBot Webhook] ========== WEBHOOK RECEIVED ==========")
    
    try:
        body = await request.json()
        print(f"[CryptoBot Webhook] Data: {body}")
        
        update_type = body.get("update_type")
        print(f"[CryptoBot Webhook] Update type: {update_type}")
        
        if update_type == "invoice_paid":
            user_id = None
            time_months = 1
            is_renewal = False
            amount_usd = 0
            
            custom_data = body.get("custom_data", {})
            if custom_data:
                user_id = custom_data.get("user_id")
                time_months = custom_data.get("time_months", 1)
                is_renewal = custom_data.get("is_renewal", False)
            
            if not user_id:
                cryptobot_payload = body.get("payload", {})
                if isinstance(cryptobot_payload, dict):
                    payload_str = cryptobot_payload.get("payload", "")
                else:
                    payload_str = str(cryptobot_payload)
                
                if payload_str:
                    parts = payload_str.split(":")
                    if len(parts) >= 2:
                        try:
                            user_id = int(parts[0])
                            time_months = int(parts[1])
                            is_renewal = len(parts) > 2 and parts[2] == "1"
                        except (ValueError, IndexError):
                            pass
            
            amount_obj = body.get("amount")
            if amount_obj:
                amount_usd = float(amount_obj) if isinstance(amount_obj, (int, float, str)) else 0
            
            amount_rub = int(float(amount_usd) * RUB_TO_USD_RATE)
            
            if not user_id:
                print(f"[CryptoBot Webhook] ERROR: Не удалось извлечь user_id")
                return {"ok": False, "error": "Missing user_id"}
            
            print(f"[CryptoBot Webhook] Processing: user_id={user_id}, months={time_months}, amount_usd={amount_usd}, amount_rub={amount_rub}")
            
            current_time = datetime.now()
            end_time = current_time + timedelta(days=time_months * 31)
            end_date_str = end_time.strftime("%d.%m.%Y")
            
            subscription_result = None
            
            if is_renewal:
                from api_extended import renew_subscription_all_inbounds
                subscription_result = renew_subscription_all_inbounds(user_id, time_months)
            else:
                from api_extended import add_client_to_all_inbounds
                subscription_result = add_client_to_all_inbounds(f"user_{user_id}", user_id, end_date_str)
            
            try:
                from api_sheets import add_vpn_sale
                add_vpn_sale(user_id, f"user_{user_id}", time_months, amount_rub)
            except Exception as e:
                print(f"[CryptoBot Webhook] Ошибка записи в Google Sheets: {e}")
            
            await send_crypto_notifications(user_id, f"user_{user_id}", time_months, amount_rub, is_renewal, end_date_str, subscription_result)
            
            print(f"[CryptoBot Webhook] Платёж обработан успешно!")
            return {"ok": True, "status": "paid"}
        
        return {"ok": True, "message": f"Update type {update_type} not processed"}
            
    except Exception as e:
        print(f"[CryptoBot Webhook] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(e)}
