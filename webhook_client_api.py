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
    Вебхук для добавления клиента на удалённом сервере.
    Ожидает: {"tg_id": int, "sub_id": str, "end_date": "ДД.ММ.ГГГГ"}
    Один POST /panel/api/clients/add — один client на все inbound этого сервера.
    """
    try:
        tg_id = request.get("tg_id")
        sub_id = request.get("sub_id")
        end_date = request.get("end_date")

        if not tg_id or not sub_id:
            return {
                "success": False,
                "error": "Missing required fields: tg_id and sub_id",
            }

        print(f"[WEBHOOK add_client] Received: tg_id={tg_id}, sub_id={sub_id}, end_date={end_date}")
        print(f"[WEBHOOK add_client] Using panel: {cfg.PANEL_BASE_URL}")

        from api import create_subscription_on_panel, update_subscription_on_panel, convert_date_to_timestamp
        import datetime

        if not end_date:
            end_date = (datetime.datetime.now() + datetime.timedelta(days=30)).strftime("%d.%m.%Y")

        expiry_ms = convert_date_to_timestamp(end_date)
        if isinstance(expiry_ms, str):
            return {"success": False, "error": expiry_ms}

        # Один batch-запрос: один client → все inbound на этой панели
        result = create_subscription_on_panel(int(tg_id), end_date, sub_id, cleanup=True)

        if not result.get("success"):
            print("[WEBHOOK add_client] Batch create failed, trying single update fallback...")
            update_result = update_subscription_on_panel(int(tg_id), sub_id, expiry_ms)
            if update_result.get("success"):
                result = {
                    "success": True,
                    "message": "Client updated on remote server (fallback)",
                    "subId": sub_id,
                    "method": "update",
                    "details": update_result,
                }

        print(f"[WEBHOOK add_client] Result: {result}")

        if result.get("success"):
            return {
                "success": True,
                "message": f"Client tg_id={tg_id} created on all inbounds with sub_id={sub_id}",
                "tg_id": tg_id,
                "sub_id": sub_id,
                "end_date": end_date,
                "inbound_ids": result.get("inbound_ids"),
                "details": result,
            }

        return {
            "success": False,
            "error": result.get("message") or result.get("error") or "Failed to create client",
            "tg_id": tg_id,
            "sub_id": sub_id,
            "details": result,
        }

    except Exception as e:
        print(f"[WEBHOOK add_client] Error: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "webhook_client_api",
        "panel": WEBHOOK_PANEL_BASE_URL
    }


@app.post("/dell_client")
async def dell_client_webhook(request: dict):
    """
    Вебхук для удаления клиента с этого сервера.
    Ожидает: {"tg_id": int, "sub_id": str}
    Удаляет клиента со всех инбаундов этого сервера по sub_id.
    """
    try:
        tg_id = request.get('tg_id')
        sub_id = request.get('sub_id')
        
        if not tg_id or not sub_id:
            return {
                "success": False,
                "error": "Missing required fields: tg_id and sub_id"
            }
        
        print(f"[WEBHOOK dell_client] Received: tg_id={tg_id}, sub_id={sub_id}")
        print(f"[WEBHOOK dell_client] Using panel: {cfg.PANEL_BASE_URL}")
        
        # Импортируем функции API
        from api_extended import dell_client
        
        # Удаляем клиента со всех инбаундов
        # Используем sub_id для поиска - нужно найти все email с этим sub_id
        from api import get_clients, parse_inbound_settings, panel_session, panel_del_client_by_email
        
        clients_data = get_clients()
        if not clients_data.get("success"):
            return {"success": False, "error": "Failed to get inbounds"}
        
        session, err = panel_session()
        if session is None:
            return {"success": False, "error": err or "Login failed"}
        
        results = []
        for inbound in clients_data.get("obj", []):
            iid = inbound.get("id")
            settings_obj = parse_inbound_settings(inbound)
            if not settings_obj:
                continue
            
            # Ищем клиентов с этим sub_id
            for client in settings_obj.get("clients", []):
                if client.get("subId") == sub_id:
                    email = client.get("email")
                    if email:
                        print(f"[WEBHOOK dell_client] Deleting client email={email} from inbound {iid}")
                        del_result = panel_del_client_by_email(session, iid, email)
                        results.append({"inbound_id": iid, "email": email, "result": del_result})
        
        print(f"[WEBHOOK dell_client] Results: {results}")
        
        return {
            "success": True,
            "message": f"Client with sub_id={sub_id} deleted from {len(results)} inbounds",
            "tg_id": tg_id,
            "sub_id": sub_id,
            "results": results
        }
        
    except Exception as e:
        print(f"[WEBHOOK dell_client] Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e)
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
