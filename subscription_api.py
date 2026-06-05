from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta, timezone
import api
import sys
import os
from config import PANEL_DOMAIN, webhook_url

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

# Middleware для логирования всех запросов
@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"[REQUEST] {request.method} {request.url.path} - Headers: {dict(request.headers)}")
    try:
        body = await request.body()
        if body:
            print(f"[REQUEST] Body: {body.decode()[:500]}")
    except:
        pass
    response = await call_next(request)
    print(f"[RESPONSE] {response.status_code}")
    return response

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

@app.get("/")
async def root():
    """Корневой endpoint для проверки доступности сервера"""
    return {
        "status": "VPN Subscription API is running",
        "version": "1.0",
        "endpoints": {
            "subscription": "/subscription/{telegram_id}",
            "prices": "/prices",
            "payment_create": "/payment/create",
            "payment_webhook": "/payment/webhook",
            "health": "/health"
        }
    }

# @app.get("/payment/webhook")
# def webhook_get():
#     """GET endpoint для проверки доступности webhook от PayCore"""
#     print(f"[PayCore Webhook] ========== WEBHOOK GET REQUEST ==========")
#     print(f"[PayCore Webhook] Timestamp: {datetime.now()}")
#     print(f"[PayCore Webhook] Webhook is accessible via GET request")
#     print(f"[PayCore Webhook] PayCore should use POST method for actual notifications")
#     return {
#         "status": "Webhook endpoint is accessible",
#         "method": "GET",
#         "note": "PayCore should use POST method for payment notifications",
#         "webhook_url": "https://www.ezhqpy.ru:2500/payment/webhook",
#         "timestamp": datetime.now().isoformat()
#     }

@app.post("/payment/test-webhook")
async def test_webhook_endpoint():
    """Тестовый POST endpoint для проверки webhook функциональности"""
    print(f"[PayCore Webhook] ========== TEST WEBHOOK POST ==========")
    print(f"[PayCore Webhook] Timestamp: {datetime.now()}")
    print(f"[PayCore Webhook] Test POST request received successfully")
    return {
        "status": "Test webhook POST successful",
        "message": "Webhook endpoint is working correctly",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/payment/trigger-webhook")
async def trigger_webhook_manual(order_id: str):
    """Ручной триггер webhook для симуляции оплаты PayCore"""
    print(f"[PayCore Webhook] ========== MANUAL WEBHOOK TRIGGER ==========")
    print(f"[PayCore Webhook] Timestamp: {datetime.now()}")
    print(f"[PayCore Webhook] Triggering webhook for order: {order_id}")
    
    db = SessionLocal()
    try:
        # Ищем платёж в БД
        payment = db.query(Payment).filter(Payment.order_id == order_id).first()
        if not payment:
            return {"error": f"Payment {order_id} not found"}
        
        # Симулируем данные от PayCore
        webhook_data = {
            "order_id": payment.paycore_order_id or order_id,
            "amount": payment.amount,
            "final_amount": payment.amount,
            "commission_amount": 0,
            "status": "completed"
        }
        
        print(f"[PayCore Webhook] Simulated webhook data: {webhook_data}")
        
        # Вызываем основной обработчик webhook
        from fastapi import Request
        from fastapi.testclient import TestClient
        
        # Создаем mock request
        class MockRequest:
            def __init__(self, json_data):
                self._json_data = json_data
                self.client = type('Client', (), {'host': 'manual_trigger'})()
                self.url = webhook_url()
                self.headers = {"content-type": "application/json"}
            
            async def json(self):
                return self._json_data
            
            async def body(self):
                import json
                return json.dumps(self._json_data).encode()
        
        mock_request = MockRequest(webhook_data)
        
        # Вызываем обработчик webhook
        try:
            result = await payment_webhook(mock_request)
            print(f"[PayCore Webhook] Manual webhook processed successfully")
            return {
                "success": True,
                "message": "Manual webhook triggered successfully",
                "order_id": order_id,
                "webhook_data": webhook_data,
                "result": result
            }
        except Exception as e:
            print(f"[PayCore Webhook] Error in manual webhook: {e}")
            return {"error": str(e)}
        
    except Exception as e:
        print(f"[PayCore Webhook] Error in manual trigger: {e}")
        return {"error": str(e)}
    finally:
        db.close()


@app.post("/payment/webhook")
async def payment_webhook(request: Request):
    """Endpoint для приёма уведомлений от PayCore - автоматически создаёт подписку"""
    print(f"[PayCore Webhook] ========== WEBHOOK REQUEST RECEIVED ==========")
    print(f"[PayCore Webhook] Timestamp: {datetime.now()}")
    print(f"[PayCore Webhook] Request IP: {request.client.host if hasattr(request, 'client') else 'unknown'}")
    print(f"[PayCore Webhook] Request headers: {dict(request.headers)}")
    print(f"[PayCore Webhook] Request method: {request.method}")
    print(f"[PayCore Webhook] Request URL: {request.url}")
    
    try:
        # Получаем raw body для логирования
        body = await request.body()
        print(f"[PayCore Webhook] Raw body: {body.decode()[:500]}")
        
        data = await request.json()
        print(f"[PayCore Webhook] ========== PARSED WEBHOOK DATA ==========")
        print(f"[PayCore Webhook] Data: {data}")
        print(f"[PayCore Webhook] Webhook URL validation: {webhook_url()}")
        
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
            payment.updated_at = datetime.now(timezone.utc)
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
                from api_extended import renew_subscription_all_inbounds
                subscription_result = renew_subscription_all_inbounds(user_id, time_months)
            else:
                from api_extended import add_client_to_all_inbounds
                subscription_result = add_client_to_all_inbounds(username, user_id, end_date_str)
            
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
        try:
            print(f"[PayCore Webhook] Sending message to user {user_id}...")
            await bot.send_message(
                chat_id=user_id,
                text=user_message,
                reply_markup=user_keyboard,
                parse_mode=ParseMode.HTML
            )
            print(f"[PayCore Webhook] Notification sent to user {user_id}")
        except Exception as e:
            print(f"[PayCore Webhook] FAILED to send to user {user_id}: {e}")
            import traceback
            traceback.print_exc()
            # Попробуем отправить без клавиатуры и HTML
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=f"✅ Оплата успешна! Период: {time_months} мес."
                )
                print(f"[PayCore Webhook] Simple message sent to user {user_id}")
            except Exception as e2:
                print(f"[PayCore Webhook] FAILED simple message to {user_id}: {e2}")
        
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

@app.post("/admin/add_client")
async def admin_add_client_endpoint(request: dict):
    """Админ endpoint: добавить клиента по TG ID"""
    try:
        tg_id = request.get('tg_id')
        months = request.get('months', 1)
        try:
            months = int(months)
        except (TypeError, ValueError):
            months = 1
        end_date = request.get('end_date')
        
        if not tg_id:
            return {
                "success": False,
                "error": "TG ID is required"
            }
        
        # Логирование параметров
        if end_date:
            print(f"[ADMIN API] Request to add client: TG ID={tg_id}, end_date={end_date}")
        else:
            print(f"[ADMIN API] Request to add client: TG ID={tg_id}, months={months}")
        
        # Вызываем админ функцию
        from api_extended import admin_add_client
        result = admin_add_client(int(tg_id), int(months), end_date)
        
        print(f"[ADMIN API] Result: {result}")
        
        return result
        
    except Exception as e:
        print(f"[ADMIN API] Error: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/admin/add_client/{tg_id}")
async def admin_add_client_get(tg_id: int, months: int = 1, end_date: str = None):
    """Админ endpoint: добавить клиента по TG ID (GET запрос)"""
    try:
        # Логирование параметров
        if end_date:
            print(f"[ADMIN API] GET request to add client: TG ID={tg_id}, end_date={end_date}")
        else:
            print(f"[ADMIN API] GET request to add client: TG ID={tg_id}, months={months}")
        
        # Вызываем админ функцию
        from api_extended import admin_add_client
        result = admin_add_client(tg_id, months, end_date)
        
        print(f"[ADMIN API] Result: {result}")
        
        return result
        
    except Exception as e:
        print(f"[ADMIN API] Error: {e}")
        return {
            "success": False,
            "error": str(e)
        }


if __name__ == "__main__":
    import uvicorn
    print("[Subscription API] Starting server...")
    print("[Subscription API] HTTPS server on port 2500")
    print("[Subscription API] HTTP server on port 2501 (for testing)")
    from config import PUBLIC_DOMAIN
    # Запускаем HTTPS сервер с SSL
    uvicorn.run(app, host="0.0.0.0", port=2500, 
                ssl_keyfile=f"/etc/letsencrypt/live/{PUBLIC_DOMAIN}/privkey.pem",
                ssl_certfile=f"/etc/letsencrypt/live/{PUBLIC_DOMAIN}/fullchain.pem")