#!/usr/bin/env python3
"""
HTTP сервер для тестирования webhook без SSL
Запускается на порту 2501 для отладки webhook с внешних IP
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import sys
import os

# Add parent directory to path to import main
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from subscription_api import SessionLocal, Payment

app = FastAPI(title="VPN Webhook Test Server")

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
    print(f"[TEST WEBHOOK] {request.method} {request.url.path} - Headers: {dict(request.headers)}")
    try:
        body = await request.body()
        if body:
            print(f"[TEST WEBHOOK] Body: {body.decode()[:500]}")
    except:
        pass
    response = await call_next(request)
    print(f"[TEST WEBHOOK] Response: {response.status_code}")
    return response

@app.get("/")
async def root():
    return {
        "status": "Webhook Test Server is running",
        "port": 2501,
        "protocol": "HTTP (no SSL)",
        "purpose": "Testing webhook from external IPs"
    }

@app.post("/payment/webhook")
async def test_webhook(request: Request):
    """HTTP webhook endpoint для тестирования без SSL"""
    print(f"[TEST WEBHOOK] ========== WEBHOOK RECEIVED (HTTP) ==========")
    print(f"[TEST WEBHOOK] Timestamp: {datetime.now()}")
    print(f"[TEST WEBHOOK] Request IP: {request.client.host if hasattr(request, 'client') else 'unknown'}")
    print(f"[TEST WEBHOOK] Request headers: {dict(request.headers)}")
    print(f"[TEST WEBHOOK] Request method: {request.method}")
    print(f"[TEST WEBHOOK] Request URL: {request.url}")
    
    try:
        # Получаем raw body для логирования
        body = await request.body()
        print(f"[TEST WEBHOOK] Raw body: {body.decode()[:500]}")
        
        data = await request.json()
        print(f"[TEST WEBHOOK] ========== PARSED WEBHOOK DATA ==========")
        print(f"[TEST WEBHOOK] Data: {data}")
        
        order_id = data.get("order_id")
        amount = data.get("amount")
        final_amount = data.get("final_amount")
        commission_amount = data.get("commission_amount", 0)
        
        if not order_id:
            print(f"[TEST WEBHOOK] ERROR: Missing order_id")
            raise HTTPException(status_code=400, detail="Missing order_id")
        
        print(f"[TEST WEBHOOK] order_id: {order_id}, amount: {amount}")
        
        db = SessionLocal()
        try:
            # Ищем платёж в БД
            payment = db.query(Payment).filter(Payment.paycore_order_id == order_id).first()
            if not payment:
                payment = db.query(Payment).filter(Payment.order_id == order_id).first()
            
            if not payment:
                print(f"[TEST WEBHOOK] ERROR: Payment not found for order_id: {order_id}")
                raise HTTPException(status_code=404, detail="Payment not found")
            
            # Обновляем информацию о платеже
            payment.final_amount = final_amount or amount
            payment.commission_amount = commission_amount
            payment.status = "completed"
            payment.updated_at = datetime.utcnow()
            db.commit()
            print(f"[TEST WEBHOOK] Payment updated: {order_id} -> status=completed")
            
            return {"status": "success", "message": "Webhook processed successfully (HTTP)"}
            
        finally:
            db.close()
            
    except Exception as e:
        print(f"[TEST WEBHOOK] ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    print("[TEST WEBHOOK] Starting HTTP webhook test server...")
    print("[TEST WEBHOOK] Server: http://0.0.0.0:2501")
    print("[TEST WEBHOOK] Webhook: http://www.ezhqpy.ru:2501/payment/webhook")
    print("[TEST WEBHOOK] Use this for testing webhook from external IPs without SSL issues")
    
    uvicorn.run(app, host="0.0.0.0", port=2501)
