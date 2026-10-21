from fastapi import FastAPI, HTTPException, Header, Request
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Column, Integer, String, Float, DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
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

# https://api.payuc.io/docs/ — ключ можно переопределить через PAYCORE_API_KEY
PAYCORE_API_KEY = os.getenv(
    "PAYCORE_API_KEY",
    "paycore__aoY@hgXzybD0q7R2aTr5bb/eq^8zDx#6x/lfRhp7/ww=",
)
PAYCORE_API_URL = os.getenv("PAYCORE_API_URL", "https://api.payuc.io/api/init")
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


class ProcessedSubscription(Base):
    """Идемпотентность: один платёж — одна активация подписки."""
    __tablename__ = "processed_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    payment_key = Column(String, unique=True, index=True)
    user_id = Column(Integer)
    payment_type = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

# Создаем таблицы
Base.metadata.create_all(bind=engine)


def try_claim_subscription_processing(payment_key: str, user_id: int, payment_type: str) -> bool:
    """Атомарно «занимает» платёж. True — только при первой обработке."""
    db = SessionLocal()
    try:
        record = ProcessedSubscription(
            payment_key=str(payment_key),
            user_id=user_id,
            payment_type=payment_type,
        )
        db.add(record)
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False
    finally:
        db.close()


def is_subscription_processed(payment_key: str) -> bool:
    db = SessionLocal()
    try:
        return db.query(ProcessedSubscription).filter(
            ProcessedSubscription.payment_key == str(payment_key)
        ).first() is not None
    finally:
        db.close()

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
    
    # Новый API принимает только эти поля. order_id выдаёт PayCore в ответе,
    # данные пользователя остаются в нашей БД.
    data = {
        "method": "sbp",
        "amount": amount,
        "description": description,
        "returnLink": WEBHOOK_URL,
    }
    
    print(f"[PayCore] ========== CREATING PAYMENT ==========")
    print(f"[PayCore] Webhook URL (returnLink): {WEBHOOK_URL}")
    print(f"[PayCore] Request URL: {PAYCORE_API_URL}")
    print(f"[PayCore] Request data: {data}")
    
    try:
        response = requests.post(PAYCORE_API_URL, json=data, headers=headers, timeout=30)
        print(f"[PayCore] Response status: {response.status_code}")
        print(f"[PayCore] Response body: {response.text}")
        
        try:
            response_data = response.json()
        except ValueError:
            response_data = None
        print(f"[PayCore] Parsed response: {response_data}")
        
        paycore_order_id = response_data.get("order_id") if isinstance(response_data, dict) else None
        payment_url = response_data.get("url") if isinstance(response_data, dict) else None
        
        if response.status_code == 200 and payment_url and paycore_order_id:
            print(f"[PayCore] Payment created successfully, order_id: {order_id}, paycore_order_id: {paycore_order_id}")
            # Сохраняем платёж в БД
            db = SessionLocal()
            try:
                payment = Payment(
                    order_id=order_id,
                    paycore_order_id=str(paycore_order_id),
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
            if isinstance(response_data, dict):
                error_msg = response_data.get("message") or response_data.get("error") or response.text
            else:
                error_msg = response.text
            error_msg = " ".join(str(error_msg or "Unknown error").split())[:300]
            print(f"[PayCore] Error creating payment: {error_msg}, status: {response.status_code}")
            return {
                "success": False,
                "error": error_msg,
                "status_code": response.status_code,
                "full_response": response_data if isinstance(response_data, dict) else {}
            }
            
    except requests.Timeout:
        print("[PayCore] Payment provider timed out")
        return {
            "success": False,
            "error": "платёжный сервис не отвечает"
        }
    except requests.ConnectionError as e:
        print(f"[PayCore] Connection error: {e}")
        return {
            "success": False,
            "error": "нет соединения с платёжным сервисом"
        }
    except Exception as e:
        print(f"[PayCore] Exception during payment creation: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": "не удалось создать платёж"
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



