"""Настройки, которые админ меняет из бота. Файл bot_settings.json не коммитится."""

import copy
import json
import os
import re
import sys
import threading
from urllib.parse import urlparse

_LOCK = threading.Lock()
_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot_settings.json")
_DEFAULTS = None
_ORIGINALS = {}
_APPLIED_MTIME = None

TOKEN_KEYS = ("telegram_bot", "crypto_pay", "panel_api", "paycore")
TOKEN_LABELS = {
    "telegram_bot": "Telegram-бот",
    "crypto_pay": "Crypto Pay",
    "panel_api": "API панели 3x-ui",
    "paycore": "PayCore",
}

_SUB_URL_RE = re.compile(r"https?://[^`\s\"'<>]+/sub/")
_FOLDER_RE = re.compile(r"[A-Za-z0-9._-]{1,253}")


def _capture_originals():
    if "main" in sys.modules and "telegram_bot" not in _ORIGINALS:
        _ORIGINALS["telegram_bot"] = sys.modules["main"].TOKEN
    if "crypto_pay_api" in sys.modules and "crypto_pay" not in _ORIGINALS:
        _ORIGINALS["crypto_pay"] = sys.modules["crypto_pay_api"].CRYPTO_BOT_API_TOKEN
    if "payment_api" in sys.modules and "paycore" not in _ORIGINALS:
        _ORIGINALS["paycore"] = sys.modules["payment_api"].PAYCORE_API_KEY
    if "api" in sys.modules and "panel_api" not in _ORIGINALS:
        _ORIGINALS["panel_api"] = sys.modules["api"].api_token
    if "subscription_api" in sys.modules and "subscription_bot" not in _ORIGINALS:
        _ORIGINALS["subscription_bot"] = sys.modules["subscription_api"].BOT_TOKEN


def get_defaults():
    global _DEFAULTS
    if _DEFAULTS is not None:
        return copy.deepcopy(_DEFAULTS)

    import config

    panel_url = str(config.PANEL_BASE_URL).rstrip("/")
    servers = [
        {
            "name": "main",
            "label": config.PANEL_DOMAIN,
            "panel_url": panel_url,
            "webhook_url": "",
            "is_primary": True,
        }
    ]
    for item in list(config.REMOTE_SERVERS or []):
        servers.append(
            {
                "name": item.get("name") or item.get("label") or "server",
                "label": item.get("label") or item.get("name") or "server",
                "panel_url": "",
                "webhook_url": str(item.get("base_url") or "").rstrip("/"),
                "is_primary": False,
            }
        )
    _DEFAULTS = {
        "subscription_base": "https://panel.ezhqpy.ru:4567/sub",
        "web_domain": config.PUBLIC_DOMAIN or config.PANEL_DOMAIN,
        "servers": servers,
        "tokens": {key: "" for key in TOKEN_KEYS},
    }
    return copy.deepcopy(_DEFAULTS)


def _read_file():
    if not os.path.isfile(_PATH):
        return {}
    try:
        with open(_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _normalize_servers(servers):
    clean = []
    for item in servers or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        clean.append(
            {
                "name": name,
                "label": str(item.get("label") or name).strip() or name,
                "panel_url": str(item.get("panel_url") or "").strip().rstrip("/"),
                "webhook_url": str(item.get("webhook_url") or "").strip().rstrip("/"),
                "is_primary": bool(item.get("is_primary")),
            }
        )
    if not clean:
        return clean
    primary_seen = False
    for item in clean:
        if item["is_primary"] and not primary_seen:
            primary_seen = True
        else:
            item["is_primary"] = False
    if not primary_seen:
        for item in clean:
            if item["panel_url"]:
                item["is_primary"] = True
                primary_seen = True
                break
        if not primary_seen:
            clean[0]["is_primary"] = True
    return clean


def _merge(saved):
    data = get_defaults()
    if not saved:
        return data
    base = str(saved.get("subscription_base") or "").strip()
    if base:
        data["subscription_base"] = base.rstrip("/")
    domain = str(saved.get("web_domain") or "").strip()
    if domain:
        data["web_domain"] = domain
    if isinstance(saved.get("servers"), list) and saved["servers"]:
        data["servers"] = _normalize_servers(saved["servers"])
    tokens = saved.get("tokens") if isinstance(saved.get("tokens"), dict) else {}
    for key in TOKEN_KEYS:
        value = str(tokens.get(key) or "").strip()
        if value:
            data["tokens"][key] = value
    return data


def _load_merged():
    return _merge(_read_file())


def _apply(data):
    _capture_originals()
    import config

    servers = data.get("servers") or []
    primary = next((item for item in servers if item.get("is_primary")), None)
    if primary and primary.get("panel_url"):
        try:
            parsed = parse_panel_url(primary["panel_url"])
        except ValueError:
            parsed = None
        if parsed:
            config.PANEL_SCHEME = parsed["scheme"]
            config.PANEL_DOMAIN = parsed["domain"]
            config.PANEL_PORT = parsed["port"]
            config.PANEL_PATH = parsed["path"]
            config.PANEL_BASE_URL = parsed["base"]

    remotes = []
    for item in servers:
        if item.get("is_primary"):
            continue
        url = item.get("webhook_url") or ""
        if not url:
            continue
        remotes.append(
            {
                "name": item["name"],
                "label": item.get("label") or item["name"],
                "base_url": url,
            }
        )
    config.REMOTE_SERVERS.clear()
    config.REMOTE_SERVERS.extend(remotes)

    api_mod = sys.modules.get("api")
    if api_mod is not None:
        if primary and primary.get("panel_url"):
            api_mod.BASE_URL = config.PANEL_BASE_URL
        if api_mod.REMOTE_SERVERS is not config.REMOTE_SERVERS:
            api_mod.REMOTE_SERVERS.clear()
            api_mod.REMOTE_SERVERS.extend(remotes)
        panel_token = data["tokens"].get("panel_api") or _ORIGINALS.get("panel_api") or ""
        if panel_token:
            api_mod.api_token = panel_token
        bot_token = data["tokens"].get("telegram_bot") or _ORIGINALS.get("telegram_bot") or ""
        if bot_token:
            api_mod.BOT_TOKEN = bot_token

    crypto_mod = sys.modules.get("crypto_pay_api")
    if crypto_mod is not None:
        token = data["tokens"].get("crypto_pay") or _ORIGINALS.get("crypto_pay") or ""
        if token:
            crypto_mod.CRYPTO_BOT_API_TOKEN = token

    pay_mod = sys.modules.get("payment_api")
    if pay_mod is not None:
        token = data["tokens"].get("paycore") or _ORIGINALS.get("paycore") or ""
        if token:
            pay_mod.PAYCORE_API_KEY = token
        bot_token = data["tokens"].get("telegram_bot") or _ORIGINALS.get("telegram_bot") or ""
        if bot_token:
            pay_mod.BOT_TOKEN = bot_token

    sub_mod = sys.modules.get("subscription_api")
    if sub_mod is not None:
        bot_token = data["tokens"].get("telegram_bot") or _ORIGINALS.get("telegram_bot") or ""
        if bot_token:
            sub_mod.BOT_TOKEN = bot_token
            sub_mod.CRYPTOBOT_BOT_TOKEN = bot_token

    main_mod = sys.modules.get("main")
    if main_mod is not None:
        bot_token = data["tokens"].get("telegram_bot") or _ORIGINALS.get("telegram_bot") or ""
        if bot_token:
            main_mod.TOKEN = bot_token
            bot = getattr(main_mod, "bot", None)
            if bot is not None:
                _apply_live_bot_token(bot, bot_token)


def _apply_live_bot_token(bot, token: str) -> None:
    """Токен у Bot в aiogram 3.26 только для чтения. Пишем в закрытое поле и не роняем сохранение настроек."""
    try:
        if bot.token == token:
            return
    except Exception:
        pass
    for attr in ("_Bot__token", "_token"):
        try:
            setattr(bot, attr, token)
        except Exception:
            continue
        try:
            if bot.token == token:
                return
        except Exception:
            continue


def apply_if_stale():
    global _APPLIED_MTIME
    with _LOCK:
        mtime = os.path.getmtime(_PATH) if os.path.isfile(_PATH) else 0
        if _APPLIED_MTIME == mtime:
            return
        _apply(_load_merged())
        _APPLIED_MTIME = mtime


def get():
    apply_if_stale()
    with _LOCK:
        return _load_merged()


def save(data):
    global _APPLIED_MTIME
    data = copy.deepcopy(data)
    data["servers"] = _normalize_servers(data.get("servers") or [])
    data["subscription_base"] = str(data.get("subscription_base") or "").rstrip("/")
    data["web_domain"] = str(data.get("web_domain") or "").strip()
    tokens = data.get("tokens") if isinstance(data.get("tokens"), dict) else {}
    data["tokens"] = {key: str(tokens.get(key) or "").strip() for key in TOKEN_KEYS}
    with _LOCK:
        tmp = _PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, _PATH)
        _apply(data)
        _APPLIED_MTIME = os.path.getmtime(_PATH)
    return copy.deepcopy(data)


def update(mutator):
    data = get()
    mutator(data)
    return save(data)


def effective_token(key: str) -> str:
    _capture_originals()
    saved = get()["tokens"].get(key) or ""
    if saved:
        return saved
    return _ORIGINALS.get(key) or ""


def mask_token(value: str) -> str:
    value = value or ""
    if not value:
        return "не задан"
    if len(value) <= 8:
        return "••••"
    return f"{value[:4]}…{value[-4:]}"


def subscription_link(sub_id: str) -> str:
    base = get()["subscription_base"].rstrip("/")
    return f"{base}/{sub_id}"


def happ_link(sub_id: str) -> str:
    domain = get()["web_domain"]
    return f"https://{domain}/index.html?sub={sub_id}"


def normalize_subscription_base(text: str) -> str:
    text = (text or "").strip()
    if any(ch in text for ch in " \n\t`'\"<>{}$"):
        raise ValueError("В ссылке не должно быть пробелов, кавычек и скобок")
    if not text.startswith(("http://", "https://")):
        raise ValueError("Ссылка должна начинаться с https://")
    parsed = urlparse(text)
    if not parsed.hostname:
        raise ValueError("Не получилось разобрать домен")
    parts = [part for part in (parsed.path or "").split("/") if part]
    if "sub" in parts:
        parts = parts[: parts.index("sub") + 1]
    elif not parts or parts[-1] != "sub":
        parts.append("sub")
    path = "/" + "/".join(parts)
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{parsed.hostname}{port}{path}"


def parse_panel_url(url: str) -> dict:
    raw = (url or "").strip()
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    if any(ch in raw for ch in " \t`'\"<>"):
        raise ValueError("В ссылке панели не должно быть пробелов и кавычек")
    parsed = urlparse(raw)
    if not parsed.hostname:
        raise ValueError("Нужен адрес вида https://домен:порт/путь")
    path = (parsed.path or "").strip("/")
    if not path:
        raise ValueError("В ссылке панели нет секретного пути")
    scheme = parsed.scheme or "https"
    port = parsed.port if parsed.port else (443 if scheme == "https" else 80)
    base = f"{scheme}://{parsed.hostname}:{port}/{path}"
    return {
        "scheme": scheme,
        "domain": parsed.hostname,
        "port": port,
        "path": path,
        "base": base,
    }


def clean_webhook_url(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        raise ValueError("Ссылка должна начинаться с https://")
    if any(ch in url for ch in " \t`'\"<>"):
        raise ValueError("В ссылке не должно быть пробелов и кавычек")
    parsed = urlparse(url)
    if not parsed.hostname:
        raise ValueError("Не получилось разобрать адрес")
    return url


def clean_server_name(name: str) -> str:
    name = (name or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", name):
        raise ValueError("Имя: латиница, цифры, _ и -, до 32 символов")
    return name


def clean_web_folder(name: str) -> str:
    name = (name or "").strip().strip("/")
    if name in {".", ".."} or ".." in name or not _FOLDER_RE.fullmatch(name):
        raise ValueError("Имя папки: буквы, цифры, точка и дефис, без слэшей")
    return name


def clean_token(value: str) -> str:
    value = (value or "").strip()
    if any(ch.isspace() for ch in value):
        raise ValueError("Токен нужен одной строкой, без пробелов")
    if len(value) < 8 or len(value) > 2000:
        raise ValueError("Непохожая длина токена")
    return value


FALLBACK_INDEX_PATH = "/var/www/html/index.html"


def index_html_path(domain: str) -> str:
    folder = clean_web_folder(domain)
    return f"/var/www/{folder}/index.html"


def resolve_index_path(domain: str, path: str = None):
    """Сначала /var/www/домен/index.html, если его нет — /var/www/html/index.html."""
    if path:
        if os.path.isfile(path):
            return path, None
        return None, f"Файл не найден: {path}"
    primary = index_html_path(domain)
    if os.path.isfile(primary):
        return primary, None
    if os.path.isfile(FALLBACK_INDEX_PATH):
        return FALLBACK_INDEX_PATH, None
    return None, f"Файл не найден: {primary} и {FALLBACK_INDEX_PATH}"


def active_index_path(domain: str) -> str:
    found, _error = resolve_index_path(domain)
    return found or index_html_path(domain)


def read_index_subscription_base(domain: str, path: str = None):
    file_path, error = resolve_index_path(domain, path)
    if not file_path:
        return False, error
    try:
        with open(file_path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        return False, f"Не удалось прочитать {file_path}: {exc}"
    match = _SUB_URL_RE.search(text)
    if not match:
        return False, f"В {file_path} нет ссылки вида https://…/sub/"
    return True, match.group(0).rstrip("/")


def write_index_subscription_base(domain: str, new_base: str, path: str = None):
    file_path, error = resolve_index_path(domain, path)
    base = normalize_subscription_base(new_base).rstrip("/") + "/"
    if not file_path:
        return False, error
    try:
        with open(file_path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as exc:
        return False, f"Не удалось прочитать {file_path}: {exc}"
    if not _SUB_URL_RE.search(text):
        return False, f"В {file_path} нет ссылки вида https://…/sub/"
    updated, count = _SUB_URL_RE.subn(base, text)
    tmp = file_path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(updated)
        os.replace(tmp, file_path)
    except OSError as exc:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return False, f"Не удалось записать {file_path}: {exc}"
    return True, f"Обновлено вхождений: {count}. Файл: {file_path}"
