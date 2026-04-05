from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import api
import sys
import os

# Add parent directory to path to import main
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from main import get_all_prices
import asyncio

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


@app.get("/health")
async def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=2500, ssl_keyfile='/etc/letsencrypt/live/ezh-dev.ru/privkey.pem', ssl_certfile='/etc/letsencrypt/live/ezh-dev.ru/cert.pem')