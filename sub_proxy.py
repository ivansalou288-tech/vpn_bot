"""Список серверов в прокси сбора подписок (SERVERS в .env nginx-3x-ui-subscription-proxy)."""

import json
import os
import shlex
import subprocess
from urllib.parse import urlparse

import requests

DEFAULT_DIR = "/root/nginx-3x-ui-subscription-proxy"


def proxy_dir() -> str:
    import runtime_settings

    saved = (runtime_settings.get().get("proxy_dir") or "").strip()
    if saved:
        return saved
    sources = os.path.join(os.path.dirname(os.path.abspath(__file__)), "provision_sources.json")
    try:
        with open(sources, "r", encoding="utf-8") as fh:
            value = (json.load(fh).get("subscription_proxy_dir") or "").strip()
            if value:
                return value
    except (OSError, ValueError):
        pass
    return DEFAULT_DIR


def _env_path() -> str:
    return os.path.join(proxy_dir(), ".env")


def _read_env() -> str:
    with open(_env_path(), "r", encoding="utf-8") as fh:
        return fh.read()


def parse_servers(env_text: str):
    for line in env_text.splitlines():
        if line.startswith("SERVERS="):
            raw = line.split("=", 1)[1].strip().strip('"').strip("'")
            return [part for part in raw.split() if part]
    return []


def render_servers(env_text: str, urls):
    line = 'SERVERS="' + " ".join(urls) + '"'
    lines = env_text.splitlines()
    for index, current in enumerate(lines):
        if current.startswith("SERVERS="):
            lines[index] = line
            break
    else:
        lines.append(line)
    return "\n".join(lines) + "\n"


def list_urls():
    """(urls, error)"""
    try:
        return parse_servers(_read_env()), None
    except OSError as exc:
        return [], f"Не удалось прочитать {_env_path()}: {exc}"


def normalize_url(text: str) -> str:
    text = (text or "").strip()
    if any(ch in text for ch in " \t\n`'\"<>{}$"):
        raise ValueError("В ссылке не должно быть пробелов и кавычек")
    if not text.startswith(("http://", "https://")):
        raise ValueError("Ссылка должна начинаться с https://")
    parsed = urlparse(text)
    if not parsed.hostname:
        raise ValueError("Не получилось разобрать адрес")
    if not parsed.path or parsed.path == "/":
        text = text.rstrip("/") + "/sub/"
    elif not text.endswith("/"):
        text += "/"
    return text


def _apply(urls):
    """Записывает список и пересоздаёт контейнер. (ok, сообщение)"""
    try:
        env = _read_env()
    except OSError as exc:
        return False, f"Не удалось прочитать .env: {exc}"
    try:
        with open(_env_path(), "w", encoding="utf-8") as fh:
            fh.write(render_servers(env, urls))
    except OSError as exc:
        return False, f"Не удалось записать .env: {exc}"
    cmd = (
        f"cd {shlex.quote(proxy_dir())} && "
        "(docker compose up -d --force-recreate || docker-compose up -d --force-recreate)"
    )
    proc = subprocess.run(["bash", "-lc", cmd], capture_output=True, timeout=300)
    if proc.returncode != 0:
        tail = proc.stderr.decode("utf-8", "replace")[-300:]
        return False, f"Список сохранён, но прокси не перезапустился: {tail}"
    return True, "Прокси перезапущен"


def add_url(url: str):
    url = normalize_url(url)
    urls, err = list_urls()
    if err:
        return False, err
    if url in urls:
        return True, "Уже в списке"
    urls.append(url)
    return _apply(urls)


def remove_url(url: str):
    urls, err = list_urls()
    if err:
        return False, err
    if url not in urls:
        return True, "Этой ссылки нет в списке"
    return _apply([item for item in urls if item != url])


def is_main_url(url: str) -> bool:
    import config

    host = (urlparse(url).hostname or "").lower()
    return host in {str(config.PANEL_DOMAIN).lower(), str(config.PUBLIC_DOMAIN).lower()}


def keep_only_main():
    urls, err = list_urls()
    if err:
        return False, err
    kept = [item for item in urls if is_main_url(item)]
    if not kept:
        import runtime_settings

        main = next((item for item in runtime_settings.get()["servers"] if item.get("is_primary")), None)
        url, detect_err = detect_sub_url(main) if main else (None, "главный сервер не найден")
        if not url:
            return False, f"Ссылка главного сервера не определилась ({detect_err}), ничего не меняю"
        kept = [url]
    return _apply(kept)


def detect_sub_url(server):
    """Достаёт из панели 3x-ui порт и путь подписки. (url, error)"""
    import api

    data = None
    last = "панель не ответила"
    try:
        with api.use_server(server):
            headers = api.get_headers()
            base = api.panel_base_url()
            for path in ("/panel/api/setting/all", "/panel/setting/all"):
                r = requests.post(f"{base}{path}", headers=headers, verify=False, timeout=20)
                try:
                    data = r.json()
                    if isinstance(data, dict) and data.get("obj"):
                        break
                except ValueError:
                    last = f"{path}: HTTP {r.status_code}"
                    data = None
    except Exception as exc:
        return None, str(exc)
    if data is None:
        return None, last
    obj = data.get("obj") if isinstance(data, dict) else None
    if not obj:
        return None, "панель не отдала настройки подписки"
    if not obj.get("subEnable", True):
        return None, "в панели выключена подписка"
    host = obj.get("subDomain") or urlparse(server["panel_url"]).hostname
    port = obj.get("subPort") or 2096
    path = obj.get("subPath") or "/sub/"
    scheme = "https" if (obj.get("subCertFile") or obj.get("webCertFile")) else "http"
    return f"{scheme}://{host}:{port}{path if path.endswith('/') else path + '/'}", None
