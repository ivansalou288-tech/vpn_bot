#!/usr/bin/env python3
"""
Локальный тест webhook для проверки функциональности
Запускается на порту 2502 для локального тестирования
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import sys
import os

# Add parent directory to path to import main
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from subscription_api import SessionLocal, Payment

app = FastAPI(title="Local Webhook Test")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Middleware для логирования
@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"[LOCAL WEBHOOK] {request.method} {request.url.path} - Headers: {dict(request.headers)}")
    try:
        body = await request.body()
        if body:
            print(f"[LOCAL WEBHOOK] Body: {body.decode()[:500]}")
    except:
        pass
    response = await call_next(request)
    print(f"[LOCAL WEBHOOK] Response: {response.status_code}")
    return response

@app.get("/")
async def root():
    return {
        "status": "Local Webhook Test Server is running",
        "port": 2502,
        "protocol": "HTTP (localhost only)",
        "purpose": "Testing webhook functionality locally"
    }

@app.post("/payment/webhook")
async def local_webhook(request: Request):
    """Локальный webhook endpoint для тестирования"""
    print(f"[LOCAL WEBHOOK] ========== LOCAL WEBHOOK RECEIVED ==========")
    print(f"[LOCAL WEBHOOK] Timestamp: {datetime.now()}")
    print(f"[LOCAL WEBHOOK] Request IP: {request.client.host if hasattr(request, 'client') else 'unknown'}")
    print(f"[LOCAL WEBHOOK] Request headers: {dict(request.headers)}")
    print(f"[LOCAL WEBHOOK] Request method: {request.method}")
    print(f"[LOCAL WEBHOOK] Request URL: {request.url}")
    
    try:
        # Получаем raw body для логирования
        body = await request.body()
        print(f"[LOCAL WEBHOOK] Raw body: {body.decode()[:500]}")
        
        data = await request.json()
        print(f"[LOCAL WEBHOOK] ========== PARSED WEBHOOK DATA ==========")
        print(f"[LOCAL WEBHOOK] Data: {data}")
        
        order_id = data.get("order_id")
        amount = data.get("amount")
        final_amount = data.get("final_amount")
        commission_amount = data.get("commission_amount", 0)
        
        if not order_id:
            print(f"[LOCAL WEBHOOK] ERROR: Missing order_id")
            raise HTTPException(status_code=400, detail="Missing order_id")
        
        print(f"[LOCAL WEBHOOK] order_id: {order_id}, amount: {amount}")
        
        db = SessionLocal()
        try:
            # Ищем платёж в БД
            payment = db.query(Payment).filter(Payment.paycore_order_id == order_id).first()
            if not payment:
                payment = db.query(Payment).filter(Payment.order_id == order_id).first()
            
            if not payment:
                print(f"[LOCAL WEBHOOK] ERROR: Payment not found for order_id: {order_id}")
                raise HTTPException(status_code=404, detail="Payment not found")
            
            # Обновляем информацию о платеже
            payment.final_amount = final_amount or amount
            payment.commission_amount = commission_amount
            payment.status = "completed"
            payment.updated_at = datetime.utcnow()
            db.commit()
            print(f"[LOCAL WEBHOOK] Payment updated: {order_id} -> status=completed")
            
            # Импортируем функции для создания подписки
            from api import add_client
            from datetime import timedelta
            
            # Получаем данные для создания подписки
            user_id = payment.user_id
            time_months = payment.time_months
            is_renewal = bool(payment.is_renewal)
            username = payment.username or f"user_{user_id}"
            
            # Рассчитываем дату окончания
            current_time = datetime.now()
            end_time = current_time + timedelta(days=time_months * 31)
            end_date_str = end_time.strftime("%d.%m.%Y")
            
            print(f"[LOCAL WEBHOOK] Processing subscription: user={user_id}, months={time_months}, renewal={is_renewal}")
            
            # Создаём подписку
            subscription_result = add_client(1, username, user_id, end_date_str)
            print(f"[LOCAL WEBHOOK] Subscription result: {subscription_result}")
            
            # Записываем в Google Sheets
            try:
                from api_sheets import add_vpn_sale
                add_vpn_sale(user_id, username, time_months, final_amount or amount)
                print(f"[LOCAL WEBHOOK] Sale recorded in sheets")
            except Exception as e:
                print(f"[LOCAL WEBHOOK] Failed to record sale: {e}")
            
            # Отправляем уведомления
            try:
                from aiogram import Bot
                from aiogram.enums import ParseMode
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                
                bot = Bot(token="8358697144:AAGppsqXjG9S08nGLUpghL-jUfTz9H4gj58")
                
                if subscription_result and subscription_result.get('success'):
                    user_message = (
                        f"✅ <b>Оплата успешно завершена!</b>\n\n"
                        f"⏰ Период: {time_months} мес.\n"
                        f"💰 Оплачено: {amount}₽\n"
                        f"📅 Действует до: {end_date_str}\n\n"
                        f"{'Подписка продлена' if is_renewal else 'Подписка активирована'}! 🎉"
                    )
                    
                    keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="Использовать", url=f"https://www.ezhqpy.ru/rUGq18rXII/{subscription_result.get('subId', 'unknown')}")]
                        ]
                    )
                    
                    await bot.send_message(
                        chat_id=user_id,
                        text=user_message,
                        reply_markup=keyboard,
                        parse_mode=ParseMode.HTML
                    )
                    print(f"[LOCAL WEBHOOK] Notification sent to user {user_id}")
                    
                await bot.session.close()
                
            except Exception as e:
                print(f"[LOCAL WEBHOOK] Failed to send notifications: {e}")
            
            return {"status": "success", "message": "Local webhook processed successfully"}
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"[LOCAL WEBHOOK] ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    print("[LOCAL WEBHOOK] Starting local webhook test server...")
    print("[LOCAL WEBHOOK] Server: http://localhost:2502")
    print("[LOCAL WEBHOOK] Webhook: http://localhost:2502/payment/webhook")
    print("[LOCAL WEBHOOK] Use this for testing webhook functionality locally")
    
    uvicorn.run(app, host="127.0.0.1", port=2502)
