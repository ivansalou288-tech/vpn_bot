#!/usr/bin/env python3
"""
Webhook Proxy Server - redirects external webhooks to local server
Runs on accessible port and forwards to local webhook
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import requests
import json
import sys
import os

# Add parent directory to path to import main
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from subscription_api import SessionLocal, Payment

app = FastAPI(title="Webhook Proxy Server")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Middleware untuk logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"[WEBHOOK PROXY] {request.method} {request.url.path} - Headers: {dict(request.headers)}")
    try:
        body = await request.body()
        if body:
            print(f"[WEBHOOK PROXY] Body: {body.decode()[:500]}")
    except:
        pass
    response = await call_next(request)
    print(f"[WEBHOOK PROXY] Response: {response.status_code}")
    return response

@app.get("/")
async def root():
    return {
        "status": "Webhook Proxy Server is running",
        "purpose": "Forwards external webhooks to local server",
        "local_webhook": "http://localhost:2502/payment/webhook",
        "note": "Use this URL for PayCore webhook"
    }

@app.post("/payment/webhook")
async def webhook_proxy(request: Request):
    """Proxy webhook endpoint - forwards to local server"""
    print(f"[WEBHOOK PROXY] ========== WEBHOOK PROXY RECEIVED ==========")
    print(f"[WEBHOOK PROXY] Timestamp: {datetime.now()}")
    print(f"[WEBHOOK PROXY] Request IP: {request.client.host if hasattr(request, 'client') else 'unknown'}")
    print(f"[WEBHOOK PROXY] Request headers: {dict(request.headers)}")
    
    try:
        # Get webhook data
        body = await request.body()
        data = await request.json()
        
        print(f"[WEBHOOK PROXY] Parsed data: {data}")
        
        # Forward to local webhook server
        try:
            local_response = requests.post(
                "http://localhost:2502/payment/webhook",
                json=data,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            print(f"[WEBHOOK PROXY] Local server response: {local_response.status_code}")
            print(f"[WEBHOOK PROXY] Local server response body: {local_response.text}")
            
            if local_response.status_code == 200:
                return {"status": "success", "message": "Webhook forwarded and processed"}
            else:
                print(f"[WEBHOOK PROXY] Error from local server: {local_response.text}")
                return {"status": "error", "message": "Local server error"}
                
        except requests.exceptions.RequestException as e:
            print(f"[WEBHOOK PROXY] Failed to connect to local server: {e}")
            
            # Fallback: process directly
            return await process_webhook_directly(data)
            
    except Exception as e:
        print(f"[WEBHOOK PROXY] ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

async def process_webhook_directly(data):
    """Fallback: process webhook directly if local server is not available"""
    print(f"[WEBHOOK PROXY] ========== FALLBACK DIRECT PROCESSING ==========")
    
    order_id = data.get("order_id")
    amount = data.get("amount")
    final_amount = data.get("final_amount")
    commission_amount = data.get("commission_amount", 0)
    
    if not order_id:
        raise HTTPException(status_code=400, detail="Missing order_id")
    
    db = SessionLocal()
    try:
        # Find payment
        payment = db.query(Payment).filter(Payment.paycore_order_id == order_id).first()
        if not payment:
            payment = db.query(Payment).filter(Payment.order_id == order_id).first()
        
        if not payment:
            print(f"[WEBHOOK PROXY] Payment not found: {order_id}")
            raise HTTPException(status_code=404, detail="Payment not found")
        
        # Update payment
        payment.final_amount = final_amount or amount
        payment.commission_amount = commission_amount
        payment.status = "completed"
        payment.updated_at = datetime.utcnow()
        db.commit()
        print(f"[WEBHOOK PROXY] Payment updated: {order_id}")
        
        # Create subscription
        try:
            from api import add_client
            from datetime import timedelta
            
            user_id = payment.user_id
            time_months = payment.time_months
            is_renewal = bool(payment.is_renewal)
            username = payment.username or f"user_{user_id}"
            
            current_time = datetime.now()
            end_time = current_time + timedelta(days=time_months * 31)
            end_date_str = end_time.strftime("%d.%m.%Y")
            
            subscription_result = add_client(1, username, user_id, end_date_str)
            print(f"[WEBHOOK PROXY] Subscription created: {subscription_result}")
            
            # Record in sheets
            try:
                from api_sheets import add_vpn_sale
                add_vpn_sale(user_id, username, time_months, final_amount or amount)
                print(f"[WEBHOOK PROXY] Sale recorded")
            except Exception as e:
                print(f"[WEBHOOK PROXY] Failed to record sale: {e}")
            
            # Send notifications
            try:
                from aiogram import Bot
                from aiogram.enums import ParseMode
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                
                bot = Bot(token="8358697144:AAGppsqXjG9S08nGLUpghL-jUfTz9H4gj58")
                
                if subscription_result and subscription_result.get('success'):
                    user_message = (
                        f"**<tg-emoji emoji-id='5416081784641168838'>**</tg-emoji> <b>Payment completed!</b>\n\n"
                        f"<tg-emoji emoji-id='5440621591387980068'>**</tg-emoji> Period: {time_months} months\n"
                        f"<tg-emoji emoji-id='5417924076503062111'>**</tg-emoji> Paid: {amount} RUB\n"
                        f"<tg-emoji emoji-id='5440621591387980068'>**</tg-emoji> Valid until: {end_date_str}\n\n"
                        f"{'Subscription renewed' if is_renewal else 'Subscription activated'}! **"
                    )
                    
                    keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(text="Use", url=f"https://www.ezhqpy.ru/rUGq18rXII/{subscription_result.get('subId', 'unknown')}")]
                        ]
                    )
                    
                    await bot.send_message(
                        chat_id=user_id,
                        text=user_message,
                        reply_markup=keyboard,
                        parse_mode=ParseMode.HTML
                    )
                    print(f"[WEBHOOK PROXY] Notification sent to user {user_id}")
                    
                await bot.session.close()
                
            except Exception as e:
                print(f"[WEBHOOK PROXY] Failed to send notifications: {e}")
            
            return {"status": "success", "message": "Webhook processed directly"}
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"[WEBHOOK PROXY] ERROR in direct processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    print("[WEBHOOK PROXY] Starting webhook proxy server...")
    print("[WEBHOOK PROXY] Server: http://0.0.0.0:8080")
    print("[WEBHOOK PROXY] Webhook: http://0.0.0.0:8080/payment/webhook")
    print("[WEBHOOK PROXY] Forwards to: http://localhost:2502/payment/webhook")
    print("[WEBHOOK PROXY] Use this URL for PayCore: http://0.0.0.0:8080/payment/webhook")
    
    uvicorn.run(app, host="0.0.0.0", port=8080)
