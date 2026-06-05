"""
Webhook API для добавления клиентов на отдельном сервере.
Запускается на портах 2500/2501 (HTTPS/HTTP).
"""

import sys
import os

# Add parent directory to path ПЕРЕД импортом других модулей
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ============================================================================
# КОНФИГУРАЦИЯ ЭТОГО СЕРВЕРА (локальные переменные)
# ============================================================================
WEBHOOK_PANEL_DOMAIN = "www.ezh-dev.ru"
WEBHOOK_PANEL_PORT = 18869
WEBHOOK_PANEL_PATH = "17yIzDBi5K2d8nr6Vt"
WEBHOOK_PANEL_SCHEME = "https"
WEBHOOK_PANEL_BASE_URL = f"{WEBHOOK_PANEL_SCHEME}://{WEBHOOK_PANEL_DOMAIN}:{WEBHOOK_PANEL_PORT}/{WEBHOOK_PANEL_PATH}"

WEBHOOK_HTTPS_PORT = 2500
WEBHOOK_HTTP_PORT = 2501

# Переопределяем конфиг перед импортом других модулей
import config as cfg
cfg.PANEL_DOMAIN = WEBHOOK_PANEL_DOMAIN
cfg.PANEL_PORT = WEBHOOK_PANEL_PORT
cfg.PANEL_PATH = WEBHOOK_PANEL_PATH
cfg.PANEL_SCHEME = WEBHOOK_PANEL_SCHEME
cfg.PANEL_BASE_URL = WEBHOOK_PANEL_BASE_URL

# ============================================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="Webhook Client API")

# CORS для доступа из других сервисов
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


@app.post("/add_client")
async def add_client_webhook(request: dict):
    """
    Вебхук для добавления клиента на этот сервер.
    Ожидает: {"tg_id": int, "sub_id": str}
    Создает клиента на всех инбаундах этого сервера.
    """
    try:
        tg_id = request.get('tg_id')
        sub_id = request.get('sub_id')
        
        if not tg_id or not sub_id:
            return {
                "success": False,
                "error": "Missing required fields: tg_id and sub_id"
            }
        
        print(f"[WEBHOOK add_client] Received: tg_id={tg_id}, sub_id={sub_id}")
        print(f"[WEBHOOK add_client] Using panel: {cfg.PANEL_BASE_URL}")
        
        # Импортируем функции API
        from api_extended import add_client_to_all_inbounds
        import datetime
        
        # Генерируем дату окончания подписки на 30 дней
        current_date = datetime.datetime.now()
        end_date = (current_date + datetime.timedelta(days=30)).strftime("%d.%m.%Y")
        
        print(f"[WEBHOOK add_client] Creating client with end_date={end_date}")
        
        # Извлекаем prefix из sub_id
        parts = sub_id.rsplit('_', 1)
        prefix = parts[0] if len(parts) > 1 else sub_id
        
        print(f"[WEBHOOK add_client] Extracted prefix: {prefix}")
        
        # Добавляем клиента на все инбаунды
        result = add_client_to_all_inbounds(prefix, int(tg_id), end_date)
        
        print(f"[WEBHOOK add_client] Result: {result}")
        
        if result.get("success"):
            return {
                "success": True,
                "message": f"Client tg_id={tg_id} created successfully",
                "tg_id": tg_id,
                "sub_id": sub_id,
                "end_date": end_date,
                "details": result
            }
        else:
            return {
                "success": False,
                "error": result.get("message", "Failed to create client"),
                "tg_id": tg_id,
                "sub_id": sub_id,
                "details": result
            }
        
    except Exception as e:
        print(f"[WEBHOOK add_client] Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "webhook_client_api",
        "panel": WEBHOOK_PANEL_BASE_URL
    }


@app.get("/")
async def root():
    """Корневой endpoint"""
    return {
        "status": "Webhook Client API is running",
        "panel": {
            "domain": WEBHOOK_PANEL_DOMAIN,
            "port": WEBHOOK_PANEL_PORT,
            "base_url": WEBHOOK_PANEL_BASE_URL
        },
        "endpoints": {
            "add_client": "POST /add_client",
            "health": "GET /health"
        }
    }


if __name__ == "__main__":
    print("[Webhook Client API] Starting server...")
    print(f"[Webhook Client API] Panel: {WEBHOOK_PANEL_BASE_URL}")
    print(f"[Webhook Client API] HTTPS server on port {WEBHOOK_HTTPS_PORT}")
    print(f"[Webhook Client API] HTTP server on port {WEBHOOK_HTTP_PORT} (for testing)")
    
    # Запускаем оба сервера - сначала HTTPS
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=WEBHOOK_HTTPS_PORT,
        ssl_keyfile=f"/etc/letsencrypt/live/{WEBHOOK_PANEL_DOMAIN}/privkey.pem",
        ssl_certfile=f"/etc/letsencrypt/live/{WEBHOOK_PANEL_DOMAIN}/fullchain.pem",
        log_level="info"
    )
