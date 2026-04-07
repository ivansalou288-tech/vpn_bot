from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
import api
import sys
import os

# Add parent directory to path to import main
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from main import get_all_prices
import asyncio

# Import payment functions
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from payment_api import create_paycore_payment, SessionLocal, Payment

# Импорты для webhook
from sqlalchemy import create_engine
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Константы для webhook
BOT_TOKEN = "8358697144:AAGppsqXjG9S08nGLUpghL-jUfTz9H4gj58"
OPERATOR_CHAT_ID = [1240656726, 1401086794]
WEBHOOK_PATH = "/payment/webhook"

app = FastAPI(title="VPN Subscription API")

# CORS для доступа из миниаппа
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)


@app.options("/{path:path}")
async def options_handler(path: str):
    from fastapi.responses import Response
    return Response(status_code=200, headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "*",
        "Access-Control-Allow-Headers": "*"
    })


@app.get("/subscription/{telegram_id}")
async def get_subscription_info(telegram_id: int):
    """
    Получает информацию о подписке пользователя по Telegram ID
    """
    try:
        result = api.getSubById(telegram_id)
        
        if result.get("success"):
            client_info = result.get("client_info", {})
            expiry_time = client_info.get("expiryTime", 0)
            
            # Конвертируем timestamp в читаемый формат
            expiry_date = api.convert_timestamp_to_human_readable(expiry_time)
            
            return {
                "success": True,
                "subscription": {
                    "id": client_info.get("id"),
                    "email": client_info.get("email"),
                    "enabled": client_info.get("enable"),
                    "expiry_timestamp": expiry_time,
                    "expiry_date": expiry_date,
                    "total_gb": client_info.get("totalGB", 0),
                    "sub_id": result.get("subId")
                }
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Subscription not found"),
                "message": "У вас нет активной подписки"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/prices")
async def get_prices():
    """
    Получает все доступные цены на подписку
    """
    try:
        prices = await get_all_prices()
        return {
            "success": True,
            "prices": [
                {"months": p.time, "price": p.price} for p in prices
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/payment/create")
async def create_payment(data: dict):
    """
    Создаёт платёж через PayCore и возвращает URL для оплаты
    """
    try:
        user_id = data.get('user_id')
        username = data.get('username', '')
        months = data.get('months')
        price = data.get('price')
        is_renewal = data.get('is_renewal', False)
        
        if not all([user_id, months, price]):
            raise HTTPException(status_code=400, detail="Missing required fields: user_id, months, price")
        
        # Операторы получают тестовую цену 1 рубль
        OPERATOR_IDS = [8489038592, 1401086794]
        if user_id in OPERATOR_IDS:
            price = 1
        
        months_text = "год" if months == 12 else f"{months} мес."
        operation_type = "Продление" if is_renewal else "Покупка"
        
        result = create_paycore_payment(
            amount=float(price),
            description=f"{operation_type} VPN на {months_text}",
            user_id=user_id,
            username=username,
            time_months=months,
            is_renewal=is_renewal
        )
        
        if result.get("success"):
            return {
                "success": True,
                "payment_url": result.get("payment_url"),
                "order_id": result.get("order_id")
            }
        else:
            return {
                "success": False,
                "error": result.get("error", "Failed to create payment")
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/payment/webhook")
async def payment_webhook(request: Request):
    """Endpoint для приёма уведомлений от PayCore - автоматически создаёт подписку"""
    try:
        data = await request.json()
        print(f"[PayCore Webhook] ========== WEBHOOK RECEIVED ==========")
        print(f"[PayCore Webhook] Data: {data}")
        
        order_id = data.get("order_id")
        amount = data.get("amount")
        final_amount = data.get("final_amount")
        commission_amount = data.get("commission_amount", 0)
        
        if not order_id:
            print(f"[PayCore Webhook] ERROR: Missing order_id")
            raise HTTPException(status_code=400, detail="Missing order_id")
        
        print(f"[PayCore Webhook] order_id: {order_id}, amount: {amount}")
        
        db = SessionLocal()
        try:
            # Ищем платёж в БД по paycore_order_id или нашему order_id
            payment = db.query(Payment).filter(Payment.paycore_order_id == order_id).first()
            if not payment:
                payment = db.query(Payment).filter(Payment.order_id == order_id).first()
            
            if not payment:
                print(f"[PayCore Webhook] ERROR: Payment not found for order_id: {order_id}")
                raise HTTPException(status_code=404, detail="Payment not found")
            
            # Обновляем информацию о платеже
            payment.final_amount = final_amount or amount
            payment.commission_amount = commission_amount
            payment.status = "completed"
            payment.updated_at = datetime.utcnow()
            db.commit()
            print(f"[PayCore Webhook] Payment updated: {order_id} -> status=completed")
            
            # Получаем данные для создания/продления подписки
            user_id = payment.user_id
            time_months = payment.time_months
            is_renewal = bool(payment.is_renewal)
            username = payment.username or f"user_{user_id}"
            
            # Рассчитываем дату окончания
            current_time = datetime.now()
            end_time = current_time + timedelta(days=time_months * 31)
            end_date_str = end_time.strftime("%d.%m.%Y")
            
            print(f"[PayCore Webhook] Processing subscription: user={user_id}, months={time_months}, renewal={is_renewal}")
            
            subscription_result = None
            
            # Продлеваем или создаём подписку
            if is_renewal:
                subscription_result = api.renew_subscription(user_id, time_months)
            else:
                subscription_result = api.add_client(21, username, user_id, end_date_str)
            
            print(f"[PayCore Webhook] Subscription result: {subscription_result}")
            
            # Записываем в Google Sheets
            try:
                from api_sheets import add_vpn_sale
                add_vpn_sale(user_id, username, time_months, final_amount or amount)
                print(f"[PayCore Webhook] Sale recorded in sheets")
            except Exception as e:
                print(f"[PayCore Webhook] Failed to record sale: {e}")
            
            # Отправляем уведомления
            await send_payment_notifications(payment, data, subscription_result, end_date_str)
            
            return {"status": "success", "message": "Payment processed"}
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"[PayCore Webhook] ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


async def send_payment_notifications(payment, data, subscription_result, end_date_str):
    """Отправляет уведомления пользователю и операторам об успешной оплате"""
    try:
        bot = Bot(token=BOT_TOKEN)
        
        amount = data.get("amount")
        final_amount = data.get("final_amount", amount)
        commission_amount = data.get("commission_amount", 0)
        time_months = payment.time_months
        is_renewal = bool(payment.is_renewal)
        user_id = payment.user_id
        
        # Сообщение пользователю
        if subscription_result and subscription_result.get('success'):
            user_message = (
                f"✅ <b>Оплата успешно завершена!</b>\n\n"
                f"⏰ Период: {time_months} мес.\n"
                f"💰 Оплачено: {amount}₽\n"
                f"📅 Действует до: {end_date_str}\n\n"
                f"{'Подписка продлена' if is_renewal else 'Подписка активирована'}! 🎉"
            )
        else:
            user_message = (
                f"✅ <b>Оплата получена!</b>\n\n"
                f"Ваша оплата на {amount}₽ получена.\n"
                f"Оператор скоро активирует вашу подписку."
            )
        
        user_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Моя подписка", callback_data="subscription")]
            ]
        )
        
        # Отправляем пользователю
        await bot.send_message(
            chat_id=user_id,
            text=user_message,
            reply_markup=user_keyboard,
            parse_mode=ParseMode.HTML
        )
        print(f"[PayCore Webhook] Notification sent to user {user_id}")
        
        # Удаляем старое сообщение об оплате
        if payment.message_id:
            try:
                await bot.delete_message(chat_id=user_id, message_id=payment.message_id)
                print(f"[PayCore Webhook] Deleted old payment message")
            except Exception as e:
                print(f"[PayCore Webhook] Could not delete old message: {e}")
        
        # Сообщение операторам
        operator_message = (
            f"💰 <b>Новая оплата через СБП!</b>\n\n"
            f"👤 Пользователь: @{payment.username or 'N/A'} (ID: {payment.user_id})\n"
            f"⏰ Тип: {'Продление' if is_renewal else 'Покупка'}\n"
            f"📅 Период: {payment.time_months} мес.\n\n"
            f"💵 Сумма: {amount}₽\n"
            f"📉 Комиссия: {commission_amount}₽\n"
            f"💎 <b>Прибыль: {final_amount}₽</b>\n\n"
            f"✅ Подписка {'продлена' if is_renewal else 'создана'} автоматически\n"
            f"Order ID: <code>{payment.order_id}</code>"
        )
        
        # Отправляем всем операторам
        for chat_id in OPERATOR_CHAT_ID:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=operator_message,
                    parse_mode=ParseMode.HTML
                )
                print(f"[PayCore Webhook] Operator notification sent to {chat_id}")
            except Exception as e:
                print(f"[PayCore Webhook] Failed to notify operator {chat_id}: {e}")
        
        await bot.session.close()
        
    except Exception as e:
        print(f"[PayCore Webhook] Failed to send notifications: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=2500, ssl_keyfile='/etc/letsencrypt/live/ezh-dev.ru/privkey.pem', ssl_certfile='/etc/letsencrypt/live/ezh-dev.ru/cert.pem')