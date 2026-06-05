import aiohttp
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any

# CryptoBot API Configuration
CRYPTO_BOT_API_TOKEN = "592112:AASlTwWTtU8pZMTxNY3u9P5bXAL1XYVG3YY"
CRYPTO_BOT_API_URL = "https://pay.crypt.bot/api"
RUB_TO_USD_RATE = 70  # Курс: 70 рублей = 1 USD

async def create_crypto_invoice(
    amount_rub: float,
    description: str,
    user_id: int,
    time_months: int,
    is_renewal: bool = False
) -> Dict[str, Any]:
    """Создаёт инвойс в CryptoBot (оплата в USDT)"""
    
    # Конвертируем рубли в USDT
    amount_usd = round(amount_rub / RUB_TO_USD_RATE, 2)
    
    # Генерируем уникальный ID для инвойса
    import uuid
    invoice_id = f"vpn_{user_id}_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:8]}"
    
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_BOT_API_TOKEN,
        "Content-Type": "application/json"
    }
    
    # Параметры для создания инвойса
    # Документация: https://help.send.tg/en/articles/10279948-crypto-pay-api
    data = {
        "asset": "USDT",  # Валюта оплаты
        "amount": amount_usd,  # Сумма в USDT
        "description": description,
        "hidden_message": f"Оплата VPN подписки для пользователя {user_id}",
        "paid_btn_name": "openBot",  # Кнопка после оплаты - открыть бота
        "paid_btn_url": "https://t.me/CryptoBot",  # URL кнопки
        "payload": f"{user_id}:{time_months}:{1 if is_renewal else 0}",  # Дополнительные данные
        "allow_comments": False,
        "allow_anonymous": False
    }
    
    print(f"[CryptoBot] Creating invoice: amount_rub={amount_rub}, amount_usd={amount_usd}, user_id={user_id}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{CRYPTO_BOT_API_URL}/createInvoice",
                json=data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                result = await response.json()
                print(f"[CryptoBot] API Response: {result}")
                
                if response.status == 200 and result.get("ok"):
                    invoice_data = result.get("result", {})
                    return {
                        "success": True,
                        "invoice_id": invoice_data.get("invoice_id"),
                        "bot_invoice_url": invoice_data.get("bot_invoice_url"),  # Ссылка для оплаты через бота
                        "mini_app_invoice_url": invoice_data.get("mini_app_invoice_url"),  # Ссылка для Web App
                        "amount_usd": amount_usd,
                        "amount_rub": amount_rub,
                        "asset": "USDT",
                        "description": description,
                        "payload": data["payload"]
                    }
                else:
                    error = result.get("error", {}).get("name", "Unknown error")
                    print(f"[CryptoBot] Error creating invoice: {error}")
                    return {
                        "success": False,
                        "error": error
                    }
                    
    except asyncio.TimeoutError:
        print("[CryptoBot] Timeout error")
        return {"success": False, "error": "Timeout"}
    except Exception as e:
        print(f"[CryptoBot] Exception: {str(e)}")
        return {"success": False, "error": str(e)}

async def get_crypto_invoice_status(invoice_id: int) -> Dict[str, Any]:
    """Получает статус инвойса"""
    
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_BOT_API_TOKEN,
        "Content-Type": "application/json"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            params = {"invoice_id": invoice_id}
            async with session.get(
                f"{CRYPTO_BOT_API_URL}/getInvoices",
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                result = await response.json()
                
                if response.status == 200 and result.get("ok"):
                    invoices = result.get("result", {}).get("items", [])
                    if invoices:
                        invoice = invoices[0]
                        return {
                            "success": True,
                            "status": invoice.get("status"),  # active, paid, expired
                            "amount": invoice.get("amount"),
                            "paid_amount": invoice.get("paid_amount"),
                            "asset": invoice.get("asset"),
                            "payload": invoice.get("payload")
                        }
                    return {"success": False, "error": "Invoice not found"}
                else:
                    error = result.get("error", {}).get("name", "Unknown error")
                    return {"success": False, "error": error}
                    
    except Exception as e:
        print(f"[CryptoBot] Exception getting invoice status: {str(e)}")
        return {"success": False, "error": str(e)}

def convert_rub_to_usd(amount_rub: float) -> float:
    """Конвертирует рубли в USDT по фиксированному курсу"""
    return round(amount_rub / RUB_TO_USD_RATE, 2)
