from fastapi import FastAPI, HTTPException, Header, Request
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
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
    print(f"[PayCore] Webhook accessibility check: https://www.ezhqpy.ru:2500/payment/webhook")
    
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
