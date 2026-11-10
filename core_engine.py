#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ouVPN Core Engine
Общий модуль: парсинг конфигов, извлечение метаданных, генерация имен,
проверка пинга через Xray (HTTP GET generate_204) и сортировка серверов.
"""

import os
import sys
import re
import json
import base64
import time
import zipfile
import io
import subprocess
import threading
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

SOURCE_URL = "https://raw.githubusercontent.com/bobrinaw/vlessforu/refs/heads/main/working_configs.txt"
PING_TEST_URL = "http://www.gstatic.com/generate_204"

# Регулярка для извлечения эмодзи-флагов стран
FLAG_RE = re.compile(r'[\U0001F1E6-\U0001F1FF]{2}')

VPN_SCHEMES = ("vless://", "vmess://", "trojan://", "ss://", "ssr://", "hysteria2://", "hy2://", "tuic://")

# Список двухбуквенных кодов европейских государств (без России и без условного "EU")
EUROPEAN_COUNTRIES = {
    'AL', 'AD', 'AT', 'BY', 'BE', 'BA', 'BG', 'HR', 'CY', 'CZ',
    'DK', 'EE', 'FI', 'FR', 'DE', 'GR', 'HU', 'IS', 'IE', 'IT',
    'XK', 'LV', 'LI', 'LT', 'LU', 'MT', 'MD', 'MC', 'ME', 'NL',
    'MK', 'NO', 'PL', 'PT', 'RO', 'SM', 'RS', 'SK', 'SI', 'ES',
    'SE', 'CH', 'UA', 'GB', 'VA'
}


def get_base_dir() -> str:
    """Возвращает папку репозитория ouVPN."""
    return os.path.dirname(os.path.abspath(__file__))


def get_core_dir() -> str:
    """Возвращает папку для бинарников (xray)."""
    core_dir = os.path.join(get_base_dir(), "core")
    os.makedirs(core_dir, exist_ok=True)
    return core_dir


def get_xray_path() -> str:
    """Возвращает путь к исполняемому файлу xray."""
    name = "xray.exe" if sys.platform == "win32" else "xray"
    return os.path.join(get_core_dir(), name)


def ensure_xray_binary(on_status=None) -> str:
    """
    Проверяет наличие бинарника xray, если нет — скачивает официальный релиз.
    """
    xray_path = get_xray_path()
    if os.path.exists(xray_path):
        return xray_path

    if on_status:
        on_status("Загрузка Xray-core для проверки пинга...")

    is_win = sys.platform == "win32"
    asset_name = "Xray-windows-64.zip" if is_win else "Xray-linux-64.zip"
    download_url = f"https://github.com/XTLS/Xray-core/releases/download/v26.11.9/{asset_name}"

    req = urllib.request.Request(download_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        zip_data = resp.read()

    binary_target = "xray.exe" if is_win else "xray"
    with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
        for item in z.namelist():
            if item.lower() == binary_target:
                with open(xray_path, "wb") as f:
                    f.write(z.read(item))
                break

    if not is_win:
        os.chmod(xray_path, 0o755)

    if on_status:
        on_status("Xray-core успешно установлен.")

    return xray_path


def fetch_source_configs(url: str = SOURCE_URL, timeout: int = 30) -> list[str]:
    """Скачивает строки конфигов из источника."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "*/*"
    }
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                content = resp.read().decode("utf-8", errors="ignore")
                return [line.strip() for line in content.splitlines() if line.strip()]
        except Exception as e:
            if attempt == 3:
                raise RuntimeError(f"Не удалось скачать конфиги: {e}")
            time.sleep(1)
    return []


def parse_source_metadata(lines: list[str]) -> dict:
    """Извлекает метаданные из шапки исходного файла (количество серверов, время обновления)."""
    meta = {
        "source_count": 0,
        "source_update_time": "Неизвестно",
        "source_title": ""
    }
    for line in lines:
        if not line.startswith("#"):
            continue
        line_clean = line.lstrip("#").strip()
        if line_clean.startswith("announce:"):
            text = line_clean.split("announce:", 1)[1].strip()
            # Поиск даты и времени в анонсе
            m_time = re.search(r'(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2})', text)
            if m_time:
                meta["source_update_time"] = m_time.group(1)
            else:
                meta["source_update_time"] = text[:60]
            m_count = re.search(r'Серверов:\s*(\d+)', text)
            if m_count:
                meta["source_count"] = int(m_count.group(1))
        elif line_clean.startswith("profile-title:"):
            meta["source_title"] = line_clean.split("profile-title:", 1)[1].strip()

    # Если в анонсе не нашли количество, считаем VPN строки
    if meta["source_count"] == 0:
        meta["source_count"] = sum(1 for l in lines if any(l.startswith(s) for s in VPN_SCHEMES))

    return meta


def extract_flag_and_country(raw_name: str) -> tuple[str | None, str | None]:
    """Извлекает эмодзи флага и двухбуквенный ISO код страны."""
    m = FLAG_RE.search(raw_name)
    if not m:
        return None, None
    flag = m.group(0)
    country_code = "".join(chr(ord(c) - 0x1F1E6 + ord("A")) for c in flag)
    return flag, country_code


class ServerItem:
    """Класс представления одного VPN-сервера."""
    def __init__(self, raw_url: str, source_id: int):
        self.raw_url = raw_url
        self.source_id = source_id  # 1-based порядковый номер в источнике
        self.scheme = raw_url.split("://", 1)[0].lower() if "://" in raw_url else "unknown"
        
        # Извлечение старого названия
        self.old_name = self._extract_old_name()
        self.flag, self.country_code = extract_flag_and_country(self.old_name)
        
        # ЕС обход?
        self.is_bypass = (self.country_code == "EU" or "обход" in self.old_name.lower())
        self.eu_num = 0  # Присваивается при упорядочивании
        
        # Пользовательские свойства в GUI
        self.selected = True
        self.is_fast = False  # Отметка ⚡ (золотая строка)
        
        # Данные пинга
        self.ping_ms = None
        self.ping_status = "не проверен"
        
    def _extract_old_name(self) -> str:
        if "#" in self.raw_url:
            return urllib.parse.unquote(self.raw_url.split("#", 1)[1])
        if self.raw_url.startswith("vmess://"):
            b64 = self.raw_url[8:].split("#", 1)[0]
            pad = len(b64) % 4
            if pad:
                b64 += "=" * (4 - pad)
            try:
                d = json.loads(base64.b64decode(b64).decode("utf-8", errors="ignore"))
                return d.get("ps", "")
            except Exception:
                pass
        return ""

    def get_display_name(self) -> str:
        """Возвращает отформатированное имя по шаблону пользователя."""
        fast_mark = " ⚡" if self.is_fast else ""
        if self.is_bypass:
            num = self.eu_num if self.eu_num > 0 else self.source_id
            flag = self.flag or "🇪🇺"
            return f"{flag} Обход №{num}{fast_mark} | #{self.source_id}"
        elif self.country_code and self.flag:
            return f"{self.country_code} {self.flag} ouVPN V2{fast_mark} | #{self.source_id}"
        else:
            return f"🌐 ouVPN V2{fast_mark} | #{self.source_id}"

    def build_export_url(self) -> str:
        """Собирает итоговый URL конфига с новым именем."""
        new_name = self.get_display_name()
        # Для URL фрагмента: пробелы в %20, решетку в %23 для корректности
        encoded_name = new_name.replace(" ", "%20").replace("#", "%23")
        
        if self.raw_url.startswith("vmess://"):
            b64_part = self.raw_url[8:].split("#", 1)[0]
            pad = len(b64_part) % 4
            if pad:
                b64_part += "=" * (4 - pad)
            try:
                d = json.loads(base64.b64decode(b64_part).decode("utf-8", errors="ignore"))
                d["ps"] = new_name
                new_b64 = base64.b64encode(json.dumps(d, ensure_ascii=False).encode("utf-8")).decode("ascii")
                return f"vmess://{new_b64}#{encoded_name}"
            except Exception:
                pass

        base_url = self.raw_url.split("#", 1)[0]
        return f"{base_url}#{encoded_name}"

    def get_category_priority(self) -> int:
        """
        Категория расположения серверов:
        1 - Европейские страны (не Россия)
        2 - Другие страны мира (US, CA, TR, AE и т.д.)
        3 - Россия (RU)
        4 - Обходы (EU / Обход)
        """
        if self.is_bypass:
            return 4
        if self.country_code == "RU":
            return 3
        if self.country_code in EUROPEAN_COUNTRIES:
            return 1
        return 2


def parse_all_servers(lines: list[str]) -> list[ServerItem]:
    """Парсит строки в список объектов ServerItem."""
    servers = []
    source_counter = 0
    eu_counter = 0

    for line in lines:
        if line.startswith("#"):
            continue
        if not any(line.startswith(s) for s in VPN_SCHEMES):
            continue
        source_counter += 1
        item = ServerItem(line, source_counter)
        if item.is_bypass:
            eu_counter += 1
            item.eu_num = eu_counter
        servers.append(item)

    return servers


def convert_item_to_xray_outbound(item: ServerItem, tag: str) -> dict | None:
    """Конвертирует ServerItem в исходящий узел Xray (outbound)."""
    link = item.raw_url
    scheme = item.scheme
    p = urllib.parse.urlparse(link)

    try:
        if scheme == "vless":
            userinfo, hostport = p.netloc.split("@", 1)
            host, port = (hostport.split(":", 1) if ":" in hostport else (hostport, "443"))
            q = urllib.parse.parse_qs(p.query)
            getq = lambda k, d="": q.get(k, [d])[0]

            outbound = {
                "tag": tag,
                "protocol": "vless",
                "settings": {
                    "vnext": [{
                        "address": host,
                        "port": int(port),
                        "users": [{
                            "id": userinfo,
                            "encryption": getq("encryption", "none"),
                            "flow": getq("flow", "")
                        }]
                    }]
                },
                "streamSettings": {
                    "network": getq("type", "tcp"),
                    "security": getq("security", "none")
                }
            }
            sec = getq("security")
            if sec == "reality":
                outbound["streamSettings"]["realitySettings"] = {
                    "serverName": getq("sni"),
                    "fingerprint": getq("fp", "chrome"),
                    "publicKey": getq("pbk"),
                    "shortId": getq("sid"),
                    "spiderX": getq("spx")
                }
            elif sec == "tls":
                outbound["streamSettings"]["tlsSettings"] = {
                    "serverName": getq("sni"),
                    "fingerprint": getq("fp", "chrome")
                }

            net = getq("type", "tcp")
            if net == "ws":
                outbound["streamSettings"]["wsSettings"] = {
                    "path": getq("path", "/"),
                    "headers": {"Host": getq("host", "")}
                }
            elif net == "grpc":
                outbound["streamSettings"]["grpcSettings"] = {
                    "serviceName": getq("serviceName", ""),
                    "multiMode": getq("mode", "") == "multi"
                }
            elif net in ("xhttp", "http"):
                outbound["streamSettings"]["httpSettings"] = {
                    "path": getq("path", "/"),
                    "host": [getq("host", "")] if getq("host") else []
                }
            return outbound

        elif scheme == "vmess":
            b64 = link[8:].split("#", 1)[0]
            pad = len(b64) % 4
            if pad:
                b64 += "=" * (4 - pad)
            d = json.loads(base64.b64decode(b64).decode("utf-8", errors="ignore"))

            outbound = {
                "tag": tag,
                "protocol": "vmess",
                "settings": {
                    "vnext": [{
                        "address": d.get("add", ""),
                        "port": int(d.get("port", 443)),
                        "users": [{
                            "id": d.get("id", ""),
                            "alterId": int(d.get("aid", 0)),
                            "security": d.get("scy", "auto")
                        }]
                    }]
                },
                "streamSettings": {
                    "network": d.get("net", "tcp"),
                    "security": d.get("tls", "none")
                }
            }
            if d.get("tls") == "tls":
                outbound["streamSettings"]["tlsSettings"] = {
                    "serverName": d.get("sni", ""),
                    "fingerprint": "chrome"
                }
            net = d.get("net", "tcp")
            if net == "ws":
                outbound["streamSettings"]["wsSettings"] = {
                    "path": d.get("path", "/"),
                    "headers": {"Host": d.get("host", "")}
                }
            elif net == "grpc":
                outbound["streamSettings"]["grpcSettings"] = {
                    "serviceName": d.get("path", "")
                }
            return outbound

        elif scheme == "trojan":
            userinfo, hostport = p.netloc.split("@", 1)
            host, port = (hostport.split(":", 1) if ":" in hostport else (hostport, "443"))
            q = urllib.parse.parse_qs(p.query)
            getq = lambda k, d="": q.get(k, [d])[0]
            return {
                "tag": tag,
                "protocol": "trojan",
                "settings": {
                    "servers": [{"address": host, "port": int(port), "password": userinfo}]
                },
                "streamSettings": {
                    "network": getq("type", "tcp"),
                    "security": getq("security", "tls"),
                    "tlsSettings": {"serverName": getq("sni", host)}
                }
            }
    except Exception:
        return None
    return None


def test_servers_ping_xray(
    servers: list[ServerItem],
    on_progress=None,
    timeout: int = 10,
    batch_size: int = 40,
    stop_event: threading.Event = None
):
    """
    Проверяет список серверов через настоящий Xray HTTP GET запрос на gstatic.com/generate_204.
    Тестирование происходит параллельно пачками для высокой скорости.
    """
    xray_path = ensure_xray_binary()
    core_dir = get_core_dir()
    
    total = len(servers)
    completed = 0
    base_port = 25000

    # Обработка пакетами по batch_size
    for start_idx in range(0, total, batch_size):
        if stop_event and stop_event.is_set():
            break

        chunk = servers[start_idx:start_idx + batch_size]
        inbounds = []
        outbounds = []
        routing_rules = []
        port_map = {}

        for i, item in enumerate(chunk):
            p = base_port + (start_idx + i) % 15000
            tag = f"proxy_{p}"
            out = convert_item_to_xray_outbound(item, tag)
            if not out:
                item.ping_status = "Ошибка формата"
                item.ping_ms = None
                continue

            inbounds.append({
                "tag": f"in_{p}",
                "port": p,
                "listen": "127.0.0.1",
                "protocol": "http"
            })
            outbounds.append(out)
            routing_rules.append({
                "type": "field",
                "inboundTag": [f"in_{p}"],
                "outboundTag": tag
            })
            port_map[item] = p

        if not inbounds:
            continue

        cfg_name = f"test_cfg_{start_idx}.json"
        cfg_path = os.path.join(core_dir, cfg_name)
        cfg_data = {
            "log": {"loglevel": "none"},
            "inbounds": inbounds,
            "outbounds": outbounds,
            "routing": {"rules": routing_rules}
        }
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg_data, f)

        # Запуск экземпляра Xray для этой пачки
        proc = subprocess.Popen(
            [xray_path, "run", "-c", cfg_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(0.7)  # Пауза на инициализацию портов

        def probe_single(srv: ServerItem, port_num: int):
            if stop_event and stop_event.is_set():
                return
            proxy_handler = urllib.request.ProxyHandler({"http": f"http://127.0.0.1:{port_num}"})
            opener = urllib.request.build_opener(proxy_handler)
            req = urllib.request.Request(
                PING_TEST_URL,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            t0 = time.time()
            try:
                with opener.open(req, timeout=timeout) as resp:
                    if resp.status in (204, 200):
                        ms = int(round((time.time() - t0) * 1000))
                        srv.ping_ms = ms
                        srv.ping_status = f"{ms} ms"
                    else:
                        srv.ping_ms = None
                        srv.ping_status = f"HTTP {resp.status}"
            except Exception as ex:
                srv.ping_ms = None
                err_str = str(ex).lower()
                if "timed out" in err_str:
                    srv.ping_status = "Таймаут"
                elif "503" in err_str:
                    srv.ping_status = "503 Ошибка"
                else:
                    srv.ping_status = "Не отвечает"

        # Параллельный HTTP запрос ко всем серверам пачки
        with ThreadPoolExecutor(max_workers=min(30, len(port_map))) as executor:
            futures = [executor.submit(probe_single, srv, port_map[srv]) for srv in port_map]
            for fut in as_completed(futures):
                completed += 1
                if on_progress:
                    on_progress(completed, total)

        proc.terminate()
        try:
            proc.wait(timeout=2)
        except Exception:
            proc.kill()
        try:
            os.remove(cfg_path)
        except Exception:
            pass


def sort_servers_by_user_rules(servers: list[ServerItem]) -> list[ServerItem]:
    """
    Сортировка серверов по правилу:
    1. Наверху — европейские страны (кроме РФ), отсортированные по пингу (наименьший пинг первым).
    2. Затем — другие страны мира (US, CA и т.д.).
    3. Ниже — российские сервера (RU).
    4. В самом низу — обходы (EU Обход №...).
    """
    def sort_key(s: ServerItem):
        cat = s.get_category_priority()
        # Для пинга: серверам с пингом отдаём приоритет, серверам без пинга ставим 999999
        ping_val = s.ping_ms if s.ping_ms is not None else 999999
        return (cat, ping_val, s.source_id)

    return sorted(servers, key=sort_key)


def render_heading_text(heading_template: str, count: int, interval: int = 1) -> str:
    """Подставляет переменные времени МСК и количества серверов в шаблон шапки."""
    msk_tz = timezone(timedelta(hours=3))
    now = datetime.now(msk_tz)

    vars_dict = {
        "count": str(count),
        "servers_count": str(count),
        "interval": str(interval),
        "date": now.strftime("%Y-%m-%d"),
        "date_dot": now.strftime("%d.%m.%Y"),
        "time": now.strftime("%H:%M"),
        "hh:mm": now.strftime("%H:%M"),
        "time_full": now.strftime("%H:%M:%S"),
        "datetime": f"{now.strftime('%Y-%m-%d')} / {now.strftime('%H:%M')} (Moscow)",
        "year": now.strftime("%Y"),
        "month": now.strftime("%m"),
        "day": now.strftime("%d"),
        "hour": now.strftime("%H"),
        "minute": now.strftime("%M"),
    }

    lines = heading_template.splitlines()
    clean_lines = []
    for line in lines:
        if "---" in line and ("ИНСТРУКЦИЯ" in line or "VARIABLES" in line or "ДОСТУПНЫЕ ПЕРЕМЕННЫЕ" in line):
            break
        clean_lines.append(line)

    heading_text = "\n".join(clean_lines).strip()
    for key, val in vars_dict.items():
        heading_text = heading_text.replace(f"{{{key}}}", val)
        heading_text = heading_text.replace(f"{{{key.upper()}}}", val)

    return heading_text


def save_and_push_servers(selected_servers: list[ServerItem], on_status=None) -> tuple[bool, str]:
    """
    Сортирует выбранные сервера, формирует ouvpn.txt, коммитит и пушит на GitHub.
    """
    base_dir = get_base_dir()
    heading_file = os.path.join(base_dir, "heading.txt")
    output_file = os.path.join(base_dir, "ouvpn.txt")

    if not selected_servers:
        return False, "Не выбрано ни одного сервера для сохранения!"

    if on_status:
        on_status("Сортировка серверов по правилам (Европа ➔ Другие ➔ РФ ➔ Обходы)...")

    sorted_list = sort_servers_by_user_rules(selected_servers)

    # Чтение шаблона шапки
    default_template = (
        "# profile-title: 🟢 𝗼𝘂𝗩𝗣𝗡 V2\n"
        "# profile-update-interval: {interval}\n"
        "#subscription-userinfo: download=0; total=0;\n"
        "# Date/Time: {date} / {time} (Moscow)\n"
        "# Количество: {count}\n"
        "# profile-web-page-url: https://oulan1.github.io/ouVPN/\n"
        "# support-url: https://t.me/oulanGift\n"
        "# announce: Обновлено: {date} {time} (МСК)\n"
    )
    try:
        with open(heading_file, "r", encoding="utf-8") as f:
            template = f.read()
    except Exception:
        template = default_template

    rendered_head = render_heading_text(template, count=len(sorted_list), interval=1)
    export_lines = [s.build_export_url() for s in sorted_list]
    content = rendered_head + "\n\n\n" + "\n".join(export_lines) + "\n"

    with open(output_file, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)

    if on_status:
        on_status(f"Файл ouvpn.txt записан ({len(sorted_list)} серв.). Отправка на GitHub...")

    # Git commit & push
    try:
        subprocess.run(["git", "add", "ouvpn.txt"], cwd=base_dir, check=True)
        # Проверяем наличие изменений
        diff_res = subprocess.run(["git", "diff", "--staged", "--quiet"], cwd=base_dir)
        if diff_res.returncode != 0:
            commit_msg = f"Обновление рабочих серверов ouVPN [{len(sorted_list)} шт.] [skip ci]"
            subprocess.run(["git", "commit", "-m", commit_msg], cwd=base_dir, check=True)
            subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=base_dir)
            push_res = subprocess.run(["git", "push", "origin", "main"], cwd=base_dir, capture_output=True, text=True)
            if push_res.returncode != 0:
                return False, f"Ошибка при push на GitHub: {push_res.stderr.strip()}"
        else:
            return True, f"Сервера ({len(sorted_list)} шт.) сохранены. Файл ouvpn.txt уже актуален на GitHub."

        return True, f"Успешно сохранено и отправлено на GitHub! Всего серверов: {len(sorted_list)}"
    except Exception as ex:
        return False, f"Ошибка Git: {ex}"
