from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Float, DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import asyncio
import requests
import os

# Получаем токен из переменной окружения или используем дефолтный
PAYCORE_API_KEY = os.getenv("PAYCORE_API_KEY", "paycore__kzCrJ9vpN0pF7dkM%lc2D5V7/rKfbbV^ftafi%PXhH^=")
PAYCORE_API_URL = "https://pay.pay-core.ru/api/init"
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://ezh-dev.ru:2556/payment/webhook")

# Настройка БД
Base = declarative_base()
engine = create_engine("sqlite:///payments.db", echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, unique=True, index=True)
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
async def payment_webhook(data: PaymentWebhook):
    """Endpoint для приёма уведомлений от PayCore"""
    db = SessionLocal()
    try:
        # Ищем платёж в БД
        payment = db.query(Payment).filter(Payment.order_id == data.order_id).first()
        
        if not payment:
            raise HTTPException(status_code=404, detail="Payment not found")
        
        # Обновляем информацию о платеже
        payment.final_amount = data.final_amount
        payment.commission_amount = data.commission_amount
        payment.status = "completed"
        payment.updated_at = datetime.utcnow()
        
        db.commit()
        
        # Уведомляем оператора
        if bot_instance:
            profit = data.final_amount - data.commission_amount
            message = (
                f"<tg-emoji emoji-id='5416081784641168838'>💰</tg-emoji> <b>Новая оплата через СБП!</b>\n\n"
                f"<tg-emoji emoji-id='5440621591387980068'>👤</tg-emoji> Пользователь: @{payment.username or 'N/A'} (ID: {payment.user_id})\n"
                f"<tg-emoji emoji-id='5440621591387980068'>⏰</tg-emoji> Тип: {'Продление' if payment.is_renewal else 'Покупка'}\n"
                f"<tg-emoji emoji-id='5440621591387980068'>📅</tg-emoji> Период: {payment.time_months} мес.\n\n"
                f"<tg-emoji emoji-id='5417924076503062111'>💵</tg-emoji> Сумма: {data.amount}₽\n"
                f"<tg-emoji emoji-id='5416081784641168838'>📉</tg-emoji> Комиссия: {data.commission_amount}₽\n"
                f"<tg-emoji emoji-id='5282843764451195532'>💎</tg-emoji> <b>Прибыль: {profit}₽</b>\n\n"
                f"Order ID: <code>{data.order_id}</code>"
            )
            
            from aiogram.enums import ParseMode
            asyncio.create_task(
                bot_instance.send_message(
                    chat_id=payment.user_id,  # или OPERATOR_CHAT_ID
                    text=message,
                    parse_mode=ParseMode.HTML
                )
            )
        
        return {"status": "success", "message": "Payment processed"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

def create_paycore_payment(amount: float, description: str, user_id: int, username: str = None, time_months: int = 1, is_renewal: bool = False):
    """Создаёт платёж через PayCore API"""
    
    # Генерируем уникальный order_id
    import uuid
    order_id = f"vpn_{user_id}_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:8]}"
    
    headers = {
        "Content-Type": "application/json",
        "X-Api-Key": PAYCORE_API_KEY
    }
    
    data = {
        "method": "sbp",  # или "card" для карт
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
    
    try:
        response = requests.post(PAYCORE_API_URL, json=data, headers=headers, timeout=30)
        response_data = response.json()
        
        if response.status_code == 200 and response_data.get("success"):
            # Сохраняем платёж в БД
            db = SessionLocal()
            try:
                payment = Payment(
                    order_id=order_id,
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
                
                return {
                    "success": True,
                    "order_id": order_id,
                    "payment_url": response_data.get("paymentUrl"),
                    "message": "Payment created"
                }
            finally:
                db.close()
        else:
            return {
                "success": False,
                "error": response_data.get("message", "Unknown error"),
                "status_code": response.status_code
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

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
                "created_at": payment.created_at.isoformat() if payment.created_at else None
            }
        return {"exists": False}
    finally:
        db.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=2556, ssl_keyfile='/etc/letsencrypt/live/ezh-dev.ru/privkey.pem', ssl_certfile='/etc/letsencrypt/live/ezh-dev.ru/cert.pem')
