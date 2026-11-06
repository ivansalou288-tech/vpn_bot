"""Поднимает новый VPN-сервер по образцу дополнительного и копирует клиентов с основного.

Запускается на основном сервере (там лежит /etc/x-ui/x-ui.db и админ-бот).
Доступы к образцу — в provision_sources.json рядом со скриптом.
"""

import json
import os
import re
import secrets
import shlex
import socket
import sqlite3
import string
import subprocess
import tempfile
import threading
import time
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import requests

_LOCK = threading.Lock()

COUNTRIES = {
    "австралия": ("🇦🇺", "Австралия", "au"),
    "австрия": ("🇦🇹", "Австрия", "at"),
    "армения": ("🇦🇲", "Армения", "am"),
    "бельгия": ("🇧🇪", "Бельгия", "be"),
    "болгария": ("🇧🇬", "Болгария", "bg"),
    "бразилия": ("🇧🇷", "Бразилия", "br"),
    "великобритания": ("🇬🇧", "Великобритания", "gb"),
    "англия": ("🇬🇧", "Великобритания", "gb"),
    "венгрия": ("🇭🇺", "Венгрия", "hu"),
    "германия": ("🇩🇪", "Германия", "de"),
    "гонконг": ("🇭🇰", "Гонконг", "hk"),
    "грузия": ("🇬🇪", "Грузия", "ge"),
    "дания": ("🇩🇰", "Дания", "dk"),
    "израиль": ("🇮🇱", "Израиль", "il"),
    "индия": ("🇮🇳", "Индия", "in"),
    "ирландия": ("🇮🇪", "Ирландия", "ie"),
    "исландия": ("🇮🇸", "Исландия", "is"),
    "испания": ("🇪🇸", "Испания", "es"),
    "италия": ("🇮🇹", "Италия", "it"),
    "казахстан": ("🇰🇿", "Казахстан", "kz"),
    "канада": ("🇨🇦", "Канада", "ca"),
    "кипр": ("🇨🇾", "Кипр", "cy"),
    "корея": ("🇰🇷", "Корея", "kr"),
    "латвия": ("🇱🇻", "Латвия", "lv"),
    "литва": ("🇱🇹", "Литва", "lt"),
    "люксембург": ("🇱🇺", "Люксембург", "lu"),
    "молдова": ("🇲🇩", "Молдова", "md"),
    "нидерланды": ("🇳🇱", "Нидерланды", "nl"),
    "голландия": ("🇳🇱", "Нидерланды", "nl"),
    "норвегия": ("🇳🇴", "Норвегия", "no"),
    "оаэ": ("🇦🇪", "ОАЭ", "ae"),
    "польша": ("🇵🇱", "Польша", "pl"),
    "португалия": ("🇵🇹", "Португалия", "pt"),
    "румыния": ("🇷🇴", "Румыния", "ro"),
    "сербия": ("🇷🇸", "Сербия", "rs"),
    "сингапур": ("🇸🇬", "Сингапур", "sg"),
    "сша": ("🇺🇸", "США", "us"),
    "америка": ("🇺🇸", "США", "us"),
    "турция": ("🇹🇷", "Турция", "tr"),
    "украина": ("🇺🇦", "Украина", "ua"),
    "финляндия": ("🇫🇮", "Финляндия", "fi"),
    "франция": ("🇫🇷", "Франция", "fr"),
    "чехия": ("🇨🇿", "Чехия", "cz"),
    "швейцария": ("🇨🇭", "Швейцария", "ch"),
    "швеция": ("🇸🇪", "Швеция", "se"),
    "эстония": ("🇪🇪", "Эстония", "ee"),
    "япония": ("🇯🇵", "Япония", "jp"),
    "nl": ("🇳🇱", "Нидерланды", "nl"),
    "fi": ("🇫🇮", "Финляндия", "fi"),
    "de": ("🇩🇪", "Германия", "de"),
    "se": ("🇸🇪", "Швеция", "se"),
    "us": ("🇺🇸", "США", "us"),
    "gb": ("🇬🇧", "Великобритания", "gb"),
    "pl": ("🇵🇱", "Польша", "pl"),
    "fr": ("🇫🇷", "Франция", "fr"),
    "tr": ("🇹🇷", "Турция", "tr"),
    "kz": ("🇰🇿", "Казахстан", "kz"),
    "lv": ("🇱🇻", "Латвия", "lv"),
    "lt": ("🇱🇹", "Литва", "lt"),
    "ee": ("🇪🇪", "Эстония", "ee"),
}

SETTING_SKIP = {
    "secret",
    "tgBotToken",
    "tgBotChatId",
    "tgBotProxy",
    "tgBotEnable",
    "webPort",
    "webBasePath",
    "webCertFile",
    "webKeyFile",
    "webListen",
    "webDomain",
    "panelGuid",
    "twoFactorToken",
    "twoFactorEnable",
    "ldapPassword",
    "smtpPassword",
    "subCertFile",
    "subKeyFile",
    "subDomain",
    "subListen",
    "subURI",
    "subJsonURI",
    "subClashURI",
}


class ProvisionError(Exception):
    pass


def resolve_country(text: str):
    raw = (text or "").strip()
    letters = "".join(ch for ch in raw.lower().replace("ё", "е") if ch.isalpha() or ch == " ").strip()
    if letters in COUNTRIES:
        return COUNTRIES[letters]
    compact = letters.replace(" ", "")
    if compact in COUNTRIES:
        return COUNTRIES[compact]
    if 2 <= len(raw) <= 40 and "<" not in raw and ">" not in raw:
        slug = re.sub(r"[^a-z0-9]+", "", letters)[:12] or "node"
        return "🌍", raw, slug
    raise ValueError("Напишите страну, например Нидерланды")


def load_sources():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "provision_sources.json")
    if not os.path.isfile(path):
        path = "/etc/vpn-bot/provision_sources.json"
    if not os.path.isfile(path):
        raise ProvisionError("Нет файла provision_sources.json с доступом к серверу-образцу")
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    template = data.get("template") or {}
    for key in ("host", "user", "password"):
        if not str(template.get(key) or "").strip():
            raise ProvisionError("В provision_sources.json не заполнен образец 3x-ui")
    data["main_db"] = data.get("main_db") or "/etc/x-ui/x-ui.db"
    data["project_dir"] = data.get("project_dir") or os.path.dirname(os.path.abspath(__file__))
    data["subscription_proxy_dir"] = data.get("subscription_proxy_dir") or "/root/nginx-3x-ui-subscription-proxy"
    return data


def _q(value) -> str:
    return shlex.quote(str(value))


class Ssh:
    def __init__(self, host, user, password, port=22, jump=None):
        self.host = host
        self.user = user
        self.password = password
        self.port = int(port or 22)
        self.jump = jump or None
        self._dir = tempfile.mkdtemp(prefix="vpn-ssh-")
        self._pass = os.path.join(self._dir, "pass")
        self._jump_pass = os.path.join(self._dir, "jump")
        self._ask = os.path.join(self._dir, "askpass")
        with open(self._pass, "w", encoding="utf-8") as fh:
            fh.write(password)
        os.chmod(self._pass, 0o600)
        jump_host = ""
        if self.jump:
            jump_host = str(self.jump.get("host") or "")
            with open(self._jump_pass, "w", encoding="utf-8") as fh:
                fh.write(str(self.jump.get("password") or ""))
            os.chmod(self._jump_pass, 0o600)
        with open(self._ask, "w", encoding="utf-8") as fh:
            fh.write(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                f"prompt = ' '.join(sys.argv[1:])\n"
                f"jump_host = {jump_host!r}\n"
                f"path = {self._jump_pass!r} if jump_host and jump_host in prompt else {self._pass!r}\n"
                "sys.stdout.write(open(path, encoding='utf-8').read())\n"
            )
        os.chmod(self._ask, 0o700)

    def close(self):
        for path in (self._pass, self._jump_pass, self._ask):
            try:
                os.remove(path)
            except OSError:
                pass
        try:
            os.rmdir(self._dir)
        except OSError:
            pass

    def _env(self):
        env = os.environ.copy()
        env["SSH_ASKPASS"] = self._ask
        env["SSH_ASKPASS_REQUIRE"] = "force"
        env["DISPLAY"] = "none"
        env.pop("SSH_AUTH_SOCK", None)
        return env

    def _opts(self, scp=False):
        opts = [
            "-4",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "PreferredAuthentications=password",
            "-o", "PubkeyAuthentication=no",
            "-o", "NumberOfPasswordPrompts=1",
            "-o", "ConnectTimeout=30",
        ]
        if self.jump:
            jump = self.jump
            dest = f"{jump['user']}@{jump['host']}:{int(jump['port'])}"
            opts += ["-J" if not scp else "-o", dest if not scp else f"ProxyJump={dest}"]
        if self.port != 22:
            opts += ["-P" if scp else "-p", str(self.port)]
        return opts

    def _base(self):
        return ["ssh", *self._opts(), f"{self.user}@{self.host}"]

    def run(self, command, timeout=180, input_bytes=None):
        proc = subprocess.run(
            self._base() + [command],
            input=input_bytes,
            capture_output=True,
            timeout=timeout,
            env=self._env(),
        )
        out = proc.stdout.decode("utf-8", "replace")
        err = proc.stderr.decode("utf-8", "replace")
        if proc.returncode != 0:
            tail = (err or out)[-1200:]
            raise ProvisionError(f"{self.host}: команда завершилась с кодом {proc.returncode}\n{tail}")
        return out

    def bash(self, script, timeout=900):
        return self.run("bash -s", timeout=timeout, input_bytes=script.encode())

    def push(self, local_path, remote_path):
        cmd = ["scp", *self._opts(scp=True), local_path, f"{self.user}@{self.host}:{remote_path}"]
        proc = subprocess.run(cmd, capture_output=True, timeout=180, env=self._env())
        if proc.returncode != 0:
            raise ProvisionError(proc.stderr.decode("utf-8", "replace")[-800:])


def _progress(callback, text):
    if callback:
        callback(text)


def _domain_ok(domain, ip):
    try:
        infos = socket.getaddrinfo(domain, None)
    except socket.gaierror as exc:
        raise ProvisionError(
            f"Домен {domain} пока не открывается. В reg.ru поставьте A-запись на {ip}. ({exc})"
        )
    found = {item[4][0] for item in infos}
    if ip not in found:
        raise ProvisionError(
            f"Домен {domain} смотрит на {', '.join(sorted(found))}, а сервер — {ip}. "
            f"В reg.ru поставьте A-запись и подождите, пока она откроется."
        )


def _retitle(remark, flag, country):
    match = re.match(r"^\S+\s+.+?\s*(\([^)]+\))\s*$", remark or "")
    if match:
        return f"{flag} {country} {match.group(1)}"
    return f"{flag} {country}"


def _rewrite_stream(stream, domain, cert, key, ech_config, ech_keys):
    tls = stream.get("tlsSettings")
    if not isinstance(tls, dict):
        return stream
    if tls.get("serverName"):
        tls["serverName"] = domain
    for item in tls.get("certificates") or []:
        if isinstance(item, dict):
            if item.get("certificateFile"):
                item["certificateFile"] = cert
            if item.get("keyFile"):
                item["keyFile"] = key
    if tls.get("echServerKeys"):
        tls["echServerKeys"] = ech_keys
        tls.setdefault("settings", {})["echConfigList"] = ech_config
    return stream


def _random_path(length=18):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _dump_template(ssh):
    script = r'''
import json, sqlite3
con = sqlite3.connect("/etc/x-ui/x-ui.db")
con.row_factory = sqlite3.Row
settings = {row["key"]: row["value"] for row in con.execute("select key, value from settings")}
inbounds = []
for row in con.execute("select * from inbounds order by id"):
    item = dict(row)
    settings_obj = json.loads(item.get("settings") or "{}")
    settings_obj.pop("clients", None)
    stream = json.loads(item.get("stream_settings") or "{}")
    sniff = json.loads(item.get("sniffing") or "{}")
    inbounds.append({
        "remark": item.get("remark") or "",
        "port": item.get("port"),
        "protocol": item.get("protocol"),
        "listen": item.get("listen") or "",
        "enable": bool(item.get("enable")),
        "tag": item.get("tag") or "",
        "settings": settings_obj,
        "stream": stream,
        "sniffing": sniff,
    })
print("JSON_START")
print(json.dumps({"settings": settings, "inbounds": inbounds}, ensure_ascii=False))
print("JSON_END")
'''
    out = ssh.run("python3 -", timeout=60, input_bytes=script.encode())
    start = out.find("JSON_START")
    end = out.find("JSON_END")
    if start < 0 or end < 0:
        raise ProvisionError("Не удалось прочитать настройки 3x-ui с сервера-образца")
    return json.loads(out[start + len("JSON_START"):end])


def _load_main_clients(db_path):
    if not os.path.isfile(db_path):
        raise ProvisionError(f"База клиентов не найдена: {db_path}")
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = []
    for row in con.execute(
        "select email, sub_id, uuid, password, auth, flow, security, limit_ip, total_gb, "
        "expiry_time, enable, tg_id, comment, reset from clients"
    ):
        email = (row["email"] or "").strip()
        sub_id = (row["sub_id"] or "").strip()
        if not email or not sub_id:
            continue
        client = {
            "id": row["uuid"] or "",
            "email": email,
            "subId": sub_id,
            "flow": row["flow"] or "",
            "auth": row["auth"] or "",
            "security": row["security"] or "",
            "limitIp": int(row["limit_ip"] or 0),
            "totalGB": int(row["total_gb"] or 0),
            "expiryTime": int(row["expiry_time"] or 0),
            "enable": bool(row["enable"]),
            "tgId": int(row["tg_id"] or 0),
            "comment": row["comment"] or "",
            "reset": int(row["reset"] or 0),
        }
        if row["password"]:
            client["password"] = row["password"]
        rows.append(client)
    con.close()
    if not rows:
        raise ProvisionError("В базе основного сервера нет клиентов для копирования")
    return rows


def _panel_call(base, token, method, path, body=None):
    url = base.rstrip("/") + path
    response = requests.request(
        method,
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        json=body,
        verify=False,
        timeout=60,
    )
    try:
        payload = response.json()
    except ValueError:
        payload = {"success": False, "msg": response.text[:500]}
    if response.status_code != 200 or not payload.get("success"):
        message = payload.get("msg") or payload.get("error") or response.text[:500]
        raise ProvisionError(f"Панель {path}: {message}")
    return payload


def _parse_api_token(text):
    for line in text.splitlines():
        if "apiToken:" in line:
            token = line.split("apiToken:", 1)[1].strip()
            if token:
                return token
    for line in reversed(text.splitlines()):
        parts = line.strip().split()
        if parts and re.fullmatch(r"[A-Za-z0-9_-]{20,}", parts[-1]):
            return parts[-1]
    raise ProvisionError("Панель не выдала API-токен")


def _generate_ech(ssh, domain):
    out = ssh.run(
        "/usr/local/x-ui/bin/xray-linux-amd64 tls ech --serverName " + _q(domain),
        timeout=30,
    )
    blobs = [line.strip() for line in out.splitlines() if len(line.strip()) > 40]
    if len(blobs) < 2:
        raise ProvisionError("Не удалось выпустить ECH для домена")
    return blobs[0], blobs[1]


def _read_servers_line(env_text):
    for line in env_text.splitlines():
        if line.startswith("SERVERS="):
            raw = line.split("=", 1)[1].strip().strip('"').strip("'")
            return [part for part in raw.split() if part]
    return []


def _write_servers_line(env_text, urls):
    line = 'SERVERS="' + " ".join(urls) + '"'
    lines = env_text.splitlines()
    found = False
    for index, current in enumerate(lines):
        if current.startswith("SERVERS="):
            lines[index] = line
            found = True
            break
    if not found:
        lines.append(line)
    return "\n".join(lines) + "\n"


def _recreate_proxy(ssh, directory):
    script = f"""
set -euo pipefail
cd {_q(directory)}
if docker compose version >/dev/null 2>&1; then
  docker compose up -d --force-recreate
elif command -v docker-compose >/dev/null 2>&1; then
  docker-compose up -d --force-recreate
else
  echo "docker compose не установлен" >&2
  exit 1
fi
"""
    ssh.bash(script, timeout=300)


def provision(domain, host, user, password, country, progress=None, register=False):
    if not _LOCK.acquire(blocking=False):
        raise ProvisionError("Уже идёт создание другого сервера")
    holders = []
    try:
        return _provision(domain, host, user, password, country, progress, register, holders)
    finally:
        for item in holders:
            item.close()
        _LOCK.release()


def _provision(domain, host, user, password, country, progress, register, holders):
    domain = (domain or "").strip().lower().rstrip(".")
    host = (host or "").strip()
    user = (user or "").strip()
    if not re.fullmatch(r"[a-z0-9.-]{1,253}", domain) or "." not in domain:
        raise ProvisionError("Нужен домен, например panel.example.ru")
    if not re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", host):
        raise ProvisionError("Нужен IPv4 сервера")
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,32}", user):
        raise ProvisionError("Логин SSH: латиница, цифры, точка, _ и -")
    if not password:
        raise ProvisionError("Пустой пароль SSH")

    flag, country_name, slug = resolve_country(country)
    sources = load_sources()
    warnings = []

    _progress(progress, f"Проверяю DNS {domain} и вход на {host}")
    _domain_ok(domain, host)
    jump = sources.get("jump") or None
    target = Ssh(host, user, password, jump=jump)
    holders.append(target)
    template_cfg = sources["template"]
    template = Ssh(
        template_cfg["host"],
        template_cfg["user"],
        template_cfg["password"],
        port=template_cfg.get("port") or 48222,
    )
    holders.append(template)
    try:
        probe = target.run("uname -m && test -d / || true", timeout=40)
    except ProvisionError as exc:
        raise ProvisionError(f"Не удалось войти на {host}: {exc}") from exc
    if "x86_64" not in probe:
        raise ProvisionError(f"Нужна архитектура x86_64, на сервере: {probe.strip()}")

    _progress(progress, "Читаю подключения 3x-ui с дополнительного сервера")
    sample = _dump_template(template)
    if not sample.get("inbounds"):
        raise ProvisionError("На сервере-образце нет подключений")

    _progress(progress, "Ставлю Apache, certbot, Docker и Python")
    target.bash(
        r"""
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a
apt-get update -qq
apt-get install -y -qq apache2 certbot python3-certbot-apache python3-venv python3 curl ca-certificates sqlite3 rsync fail2ban cron docker.io docker-compose-v2 || apt-get install -y -qq apache2 certbot python3-certbot-apache python3-venv python3 curl ca-certificates sqlite3 rsync fail2ban cron docker.io
a2enmod ssl rewrite >/dev/null
systemctl enable --now apache2
""",
        timeout=900,
    )

    web_root = f"/var/www/{domain}"
    cert_file = f"/etc/letsencrypt/live/{domain}/fullchain.pem"
    key_file = f"/etc/letsencrypt/live/{domain}/privkey.pem"
    _progress(progress, f"Выпускаю сертификат для {domain}")
    target.bash(
        f"""
set -euo pipefail
mkdir -p {_q(web_root)}
cat > /etc/apache2/sites-available/{domain}.conf << 'EOF'
<VirtualHost *:80>
    ServerName {domain}
    DocumentRoot {web_root}
    <Directory {web_root}>
        Require all granted
    </Directory>
</VirtualHost>
EOF
a2ensite {domain}.conf >/dev/null
systemctl reload apache2
if [ ! -f {_q(cert_file)} ]; then
  certbot certonly --webroot -w {_q(web_root)} -d {_q(domain)} --non-interactive --agree-tos --register-unsafely-without-email
fi
if [ ! -f /etc/letsencrypt/options-ssl-apache.conf ]; then
  printf '%s\n' 'SSLEngine on' 'SSLProtocol all -SSLv2 -SSLv3' > /etc/letsencrypt/options-ssl-apache.conf
fi
cat > /etc/apache2/sites-available/{domain}.conf << 'EOF'
<VirtualHost *:80>
    ServerName {domain}
    RewriteEngine on
    RewriteRule ^ https://%{{SERVER_NAME}}%{{REQUEST_URI}} [END,NE,R=permanent]
</VirtualHost>
<IfModule mod_ssl.c>
<VirtualHost *:443>
    ServerName {domain}
    DocumentRoot {web_root}
    SSLEngine on
    SSLCertificateFile {cert_file}
    SSLCertificateKeyFile {key_file}
    Include /etc/letsencrypt/options-ssl-apache.conf
</VirtualHost>
</IfModule>
EOF
systemctl reload apache2
if command -v crontab >/dev/null 2>&1; then
  (crontab -l 2>/dev/null | grep -v "certbot renew" || true; echo "17 4 * * * certbot renew --quiet --deploy-hook \\"systemctl reload apache2\\"") | crontab -
fi
""",
        timeout=300,
    )

    _progress(progress, "Копирую 3x-ui той же версии, что на дополнительном сервере")
    tar_from = subprocess.Popen(
        template._base() + ["tar -C / -cf - usr/local/x-ui"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=template._env(),
    )
    tar_to = subprocess.Popen(
        target._base() + ["tar -C / -xf -"],
        stdin=tar_from.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=target._env(),
    )
    tar_from.stdout.close()
    to_out, to_err = tar_to.communicate(timeout=180)
    from_err = tar_from.stderr.read() if tar_from.stderr else b""
    tar_from.wait(timeout=30)
    if tar_from.returncode != 0 or tar_to.returncode != 0:
        raise ProvisionError(
            "Не удалось скопировать 3x-ui: "
            + (to_err or from_err or to_out).decode("utf-8", "replace")[-800:]
        )

    panel_user = "ezh"
    panel_password = secrets.token_urlsafe(16)
    web_path = _random_path()
    used_ports = {22, 80, 443, 2096, 2500, 4567}
    used_ports.update(int(item["port"]) for item in sample["inbounds"] if item.get("port"))
    web_port = secrets.randbelow(20000) + 20000
    while web_port in used_ports:
        web_port += 1

    _progress(progress, "Настраиваю панель и названия подключений под страну")
    ech_config, ech_keys = _generate_ech(target, domain)
    prepared = []
    for item in sample["inbounds"]:
        stream = _rewrite_stream(json.loads(json.dumps(item["stream"])), domain, cert_file, key_file, ech_config, ech_keys)
        settings_obj = json.loads(json.dumps(item["settings"]))
        settings_obj["clients"] = []
        prepared.append({
            "remark": _retitle(item["remark"], flag, country_name),
            "port": int(item["port"]),
            "protocol": item["protocol"],
            "listen": item.get("listen") or "",
            "up": 0,
            "down": 0,
            "total": 0,
            "expiryTime": 0,
            "enable": True,
            "tag": item.get("tag") or "",
            "settings": json.dumps(settings_obj, ensure_ascii=False),
            "streamSettings": json.dumps(stream, ensure_ascii=False),
            "sniffing": json.dumps(item.get("sniffing") or {"enabled": False}, ensure_ascii=False),
        })

    copied_settings = {}
    for name, value in (sample.get("settings") or {}).items():
        if name in SETTING_SKIP:
            continue
        copied_settings[name] = value if isinstance(value, str) else json.dumps(value)
    copied_settings["tgBotEnable"] = "false"
    copied_settings["subEnable"] = copied_settings.get("subEnable") or "true"
    copied_settings["subPort"] = "2096"
    copied_settings["subPath"] = copied_settings.get("subPath") or "/sub/"
    copied_settings["subCertFile"] = cert_file
    copied_settings["subKeyFile"] = key_file
    copied_settings["subListen"] = ""
    copied_settings["subDomain"] = ""

    settings_blob = json.dumps(copied_settings).encode()
    target.bash(
        f"""
set -euo pipefail
cp /usr/local/x-ui/x-ui.service.debian /etc/systemd/system/x-ui.service
systemctl daemon-reload
systemctl enable x-ui >/dev/null
if [ ! -f /etc/x-ui/x-ui.db ]; then
  systemctl start x-ui
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    [ -f /etc/x-ui/x-ui.db ] && break
    sleep 1
  done
  systemctl stop x-ui
fi
systemctl stop x-ui || true
/usr/local/x-ui/x-ui setting -username {_q(panel_user)} -password {_q(panel_password)} -port {web_port} -webBasePath {_q(web_path)} -webCert {_q(cert_file)} -webCertKey {_q(key_file)}
""",
        timeout=180,
    )
    target.run("python3 -", timeout=60, input_bytes=_settings_loader(settings_blob))
    token_text = target.run("/usr/local/x-ui/x-ui setting -getApiToken", timeout=40)
    api_token = _parse_api_token(token_text)
    target.run("systemctl restart x-ui", timeout=40)
    _wait_port(target, web_port)
    inbound_ports = " ".join(str(item["port"]) for item in prepared)
    target.bash(
        f"""
set -euo pipefail
if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
  ufw allow 22/tcp
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw allow 2096/tcp
  ufw allow 2500/tcp
  ufw allow 4567/tcp
  ufw allow {web_port}/tcp
  for port in {inbound_ports}; do
    ufw allow "$port"
  done
fi
""",
        timeout=40,
    )

    base = f"https://{domain}:{web_port}/{web_path}"
    _progress(progress, "Создаю подключения в панели")
    existing = _safe_list(base, api_token)
    by_port = {item.get("port"): item.get("id") for item in existing if item.get("id") is not None}
    inbound_ids = []
    for item in prepared:
        if item["port"] in by_port:
            inbound_ids.append(by_port[item["port"]])
            continue
        created = _panel_call(base, api_token, "POST", "/panel/api/inbounds/add", item)
        obj = created.get("obj") or {}
        inbound_id = obj.get("id")
        if inbound_id is None:
            listed = _safe_list(base, api_token)
            inbound_id = next((row.get("id") for row in listed if row.get("port") == item["port"]), None)
        if inbound_id is None:
            raise ProvisionError(f"Панель не вернула id подключения {item['remark']}")
        inbound_ids.append(inbound_id)

    _progress(progress, "Копирую клиентов с основного сервера")
    clients = _load_main_clients(sources["main_db"])
    added = 0
    failed = 0
    for client in clients:
        try:
            _panel_call(
                base,
                api_token,
                "POST",
                "/panel/api/clients/add",
                {"client": client, "inboundIds": inbound_ids},
            )
            added += 1
        except ProvisionError as exc:
            text = str(exc).lower()
            if "exist" in text or "duplicate" in text or "уже" in text:
                added += 1
            else:
                failed += 1
    if added == 0:
        raise ProvisionError("Ни один клиент не скопировался на новую панель")
    if failed:
        warnings.append(f"Не скопировалось клиентов: {failed} из {len(clients)}")

    _progress(progress, "Ставлю бота-webhook и прокси подписки")
    _deploy_project(target, sources["project_dir"], domain, web_port, web_path, api_token, panel_user, panel_password)
    sub_url = f"https://{domain}:2096/sub/"
    all_urls = _merge_subscription_urls(sources, template, target, sub_url, warnings)

    _progress(progress, "Проверяю, что webhook отвечает")
    try:
        health = requests.get(f"https://{domain}:2500/health", verify=False, timeout=20)
        if health.status_code != 200:
            warnings.append(f"Webhook ответил кодом {health.status_code}")
    except requests.RequestException as exc:
        warnings.append(f"Webhook пока не открывается: {exc}")

    result = {
        "ok": True,
        "domain": domain,
        "host": host,
        "flag": flag,
        "country": country_name,
        "slug": slug,
        "panel_url": base,
        "panel_user": panel_user,
        "panel_password": panel_password,
        "webhook_url": f"https://{domain}:2500",
        "clients_added": added,
        "clients_total": len(clients),
        "inbounds": len(inbound_ids),
        "subscription_urls": all_urls,
        "warnings": warnings,
    }
    if register:
        _register(result)
    return result


def _settings_loader(blob: bytes) -> bytes:
    prefix = b"""import json, sqlite3, sys
data = json.load(sys.stdin)
con = sqlite3.connect("/etc/x-ui/x-ui.db")
for key, value in data.items():
    cur = con.execute("update settings set value=? where key=?", (value, key))
    if cur.rowcount == 0:
        con.execute("insert into settings(key, value) values(?, ?)", (key, value))
con.commit()
print("settings", len(data))
"""
    # The remote python reads JSON from stdin, but stdin is the script itself.
    # Split: script, then a marker line is not available. Embed JSON in the script.
    return (
        b"import json, sqlite3\n"
        b"data = json.loads(" + json.dumps(blob.decode()).encode() + b")\n"
        b"con = sqlite3.connect('/etc/x-ui/x-ui.db')\n"
        b"for key, value in data.items():\n"
        b"    cur = con.execute('update settings set value=? where key=?', (value, key))\n"
        b"    if cur.rowcount == 0:\n"
        b"        con.execute('insert into settings(key, value) values(?, ?)', (key, value))\n"
        b"con.commit()\n"
        b"print('settings', len(data))\n"
    )


def _wait_port(ssh, port):
    ssh.bash(
        f"""
set -euo pipefail
for i in $(seq 1 30); do
  if ss -lnt | grep -q ':{port} '; then
    exit 0
  fi
  sleep 1
done
echo "порт {port} не открылся" >&2
exit 1
""",
        timeout=40,
    )


def _safe_list(base, token):
    try:
        payload = _panel_call(base, token, "GET", "/panel/api/inbounds/list")
    except ProvisionError:
        return []
    return payload.get("obj") or []


def _deploy_project(ssh, project_dir, domain, web_port, web_path, api_token, panel_user, panel_password):
    remote_dir = f"/var/www/{domain}/vpn_bot"
    ssh.run(f"mkdir -p { _q(remote_dir) }", timeout=20)
    rsync = [
        "rsync", "-az",
        "--exclude", "venv",
        "--exclude", "__pycache__",
        "--exclude", "*.db",
        "--exclude", "nohup.out",
        "--exclude", "bot_settings.json",
        "--exclude", "secret.py",
        "--exclude", "provision_sources.json",
        "--exclude", ".git",
        "-e",
        " ".join(shlex.quote(part) for part in ["ssh", *ssh._opts()]),
        project_dir.rstrip("/") + "/",
        f"{ssh.user}@{ssh.host}:{remote_dir}/",
    ]
    proc = subprocess.run(rsync, capture_output=True, timeout=180, env=ssh._env())
    if proc.returncode != 0:
        raise ProvisionError("Не удалось скопировать проект: " + proc.stderr.decode("utf-8", "replace")[-800:])

    secret_py = (
        "user = " + json.dumps(panel_user) + "\n"
        "password = " + json.dumps(panel_password) + "\n"
        "api_token = " + json.dumps(api_token) + "\n"
    )
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as fh:
        fh.write(secret_py)
        local_secret = fh.name
    try:
        ssh.push(local_secret, remote_dir + "/secret.py")
    finally:
        os.remove(local_secret)

    unit = f"""[Unit]
Description=VPN webhook client API
After=network.target x-ui.service

[Service]
WorkingDirectory={remote_dir}
Environment=WEBHOOK_PANEL_DOMAIN={domain}
Environment=WEBHOOK_PANEL_PORT={web_port}
Environment=WEBHOOK_PANEL_PATH={web_path}
ExecStart={remote_dir}/venv/bin/python webhook_client_api.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
"""
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as fh:
        fh.write(unit)
        local_unit = fh.name
    try:
        ssh.push(local_unit, "/etc/systemd/system/vpn-webhook.service")
    finally:
        os.remove(local_unit)

    ssh.bash(
        f"""
set -euo pipefail
cd {_q(remote_dir)}
python3 -m venv venv
./venv/bin/pip install -q -r requirements.txt
systemctl daemon-reload
systemctl enable --now vpn-webhook
systemctl restart vpn-webhook
""",
        timeout=900,
    )


def _merge_subscription_urls(sources, template, target, new_url, warnings):
    proxy_dir = sources["subscription_proxy_dir"]
    try:
        with open(os.path.join(proxy_dir, ".env"), "r", encoding="utf-8") as fh:
            current = fh.read()
    except OSError as exc:
        warnings.append(f"Прокси подписки на основном сервере не обновлён: {exc}")
        current = ""
    urls = _read_servers_line(current)
    if new_url not in urls:
        urls.append(new_url)
    if not urls:
        urls = [new_url]
    if current:
        updated = _write_servers_line(current, urls)
        with open(os.path.join(proxy_dir, ".env"), "w", encoding="utf-8") as fh:
            fh.write(updated)
        proc = subprocess.run(
            ["bash", "-lc", f"cd {shlex.quote(proxy_dir)} && (docker compose up -d --force-recreate || docker-compose up -d --force-recreate)"],
            capture_output=True,
            timeout=300,
        )
        if proc.returncode != 0:
            warnings.append("Прокси подписки на основном сервере не перезапустился")
    for extra in sources.get("also_update_proxy") or []:
        try:
            remote = Ssh(
                extra["host"],
                extra["user"],
                extra["password"],
                port=extra.get("port") or 48222,
            )
            try:
                env_text = remote.run(f"cat {_q(extra.get('dir') or proxy_dir)}/.env", timeout=30)
                remote_urls = _read_servers_line(env_text)
                for item in urls:
                    if item not in remote_urls:
                        remote_urls.append(item)
                new_env = _write_servers_line(env_text, remote_urls)
                remote.run(
                    f"cat > {_q(extra.get('dir') or proxy_dir)}/.env",
                    timeout=30,
                    input_bytes=new_env.encode(),
                )
                _recreate_proxy(remote, extra.get("dir") or proxy_dir)
            finally:
                remote.close()
        except Exception as exc:
            warnings.append(f"Прокси на {extra.get('host')} не обновлён: {exc}")
    _install_new_proxy(target, sources, urls, warnings)
    return urls


def _install_new_proxy(ssh, sources, urls, warnings):
    source_dir = sources["subscription_proxy_dir"]
    remote_dir = "/root/nginx-3x-ui-subscription-proxy"
    ssh.run(f"mkdir -p {_q(remote_dir)}", timeout=20)
    rsync = [
        "rsync", "-az",
        "--exclude", ".git",
        "-e",
        " ".join(shlex.quote(part) for part in ["ssh", *ssh._opts()]),
        source_dir.rstrip("/") + "/",
        f"{ssh.user}@{ssh.host}:{remote_dir}/",
    ]
    proc = subprocess.run(rsync, capture_output=True, timeout=180, env=ssh._env())
    if proc.returncode != 0:
        warnings.append("Прокси подписки на новом сервере не скопировался")
        return
    domain = urls[-1].split("/")[2].split(":")[0] if urls else ""
    env = "\n".join([
        f"PATH_SSL_KEY=/etc/letsencrypt/live/{domain}",
        f"SITE_HOST={domain}",
        "SITE_PORT=4567",
        'SERVERS="' + " ".join(urls) + '"',
        "SUB=sub",
        "TLS_MODE=on",
        "",
    ])
    ssh.run(f"cat > {_q(remote_dir)}/.env", timeout=20, input_bytes=env.encode())
    try:
        ssh.bash(
            f"""
set -euo pipefail
cd {_q(remote_dir)}
if docker compose version >/dev/null 2>&1; then
  docker compose up -d --build
else
  docker-compose up -d --build
fi
""",
            timeout=900,
        )
    except ProvisionError as exc:
        warnings.append(f"Прокси подписки на новом сервере не собрался: {exc}")


def _register(result):
    import runtime_settings as settings

    name = result["slug"]
    data = settings.get()
    taken = {item["name"] for item in data["servers"]}
    candidate = name
    index = 2
    while candidate in taken:
        candidate = f"{name}-{index}"
        index += 1
    result["name"] = candidate

    def mutate(saved):
        saved["servers"].append({
            "name": candidate,
            "label": f"{result['flag']} {result['country']}",
            "panel_url": result["panel_url"],
            "panel_user": result.get("panel_user") or "",
            "panel_password": result.get("panel_password") or "",
            "webhook_url": result["webhook_url"],
            "is_primary": False,
        })

    settings.update(mutate)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Поднять новый VPN-сервер")
    parser.add_argument("domain")
    parser.add_argument("host")
    parser.add_argument("user")
    parser.add_argument("password")
    parser.add_argument("country")
    args = parser.parse_args()
    result = provision(
        args.domain,
        args.host,
        args.user,
        args.password,
        args.country,
        progress=print,
        register=True,
    )
    public = dict(result)
    print(json.dumps(public, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
