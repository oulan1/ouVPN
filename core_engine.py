#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ouVPN Core Engine
Общий модуль:
- Парсинг конфигов ТОЛЬКО VLESS из семи источников:
  1) VlessForU (bobrinaw)
  2) BlackVlessRus (igareck)
  3) FreeVpnAntiRkn (Hidashimora)
  4) WLUnlocker (blacklist_vpn1)
  5) WhiteCidrRu (igareck)
  6) BlackVlessRusMobile (igareck)
  7) AviaMasters (verified_configs)
- Тройная проверка доступности:
  1) Google (http://www.gstatic.com/generate_204)
  2) Telegram (https://t.me)
  3) Discord (https://discord.com/)
  В пинге выводится средний пинг за 3 проверки!
- Генерация названий с #ID в начале: #ID | Country ouVPN V2 (и ⚡ для скоростных)
- Сортировка: Европа ➔ Другие страны ➔ Россия (RU) ➔ Обходы (EU)
- Надёжный авто-sync при push на GitHub без ошибок non-fast-forward
"""

import os
import sys
import re
import ssl
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

# Список источников VLESS конфигов
SOURCE_URLS = [
    "https://raw.githubusercontent.com/bobrinaw/vlessforu/refs/heads/main/working_configs.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_VLESS_RUS.txt",
    "https://raw.githubusercontent.com/Hidashimora/free-vpn-anti-rkn/refs/heads/main/configs/1.1.txt",
    "https://raw.githubusercontent.com/wlunlocker/vpn-configs/main/blacklist_vpn1.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-checked.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt",
    "https://raw.githubusercontent.com/aviamastersgh/vpn-free-russia/refs/heads/main/verified_configs.txt",
    "https://raw.githubusercontent.com/histeenn/VLESS-PO-GRIBI/refs/heads/main/deploy/subscriptions/1.txt",
    "https://raw.githubusercontent.com/histeenn/VLESS-PO-GRIBI/refs/heads/main/deploy/subscriptions/17.txt",
    "https://raw.githubusercontent.com/histeenn/VLESS-PO-GRIBI/refs/heads/main/deploy/subscriptions/24.txt"
]

# Адреса для комплексной проверки доступности (Google, Telegram, Discord, Instagram, YouTube)
PING_TEST_URL_GOOGLE = "http://www.gstatic.com/generate_204"
PING_TEST_URL_TELEGRAM = "https://t.me"
PING_TEST_URL_DISCORD = "https://discord.com/"
PING_TEST_URL_INSTAGRAM = "https://www.instagram.com/"
PING_TEST_URL_YOUTUBE = "https://www.youtube.com/generate_204"

# Регулярка для выявления серверов обхода: EU, CIDR, *CIDR, LTE, SNI, Обход (любой регистр)
BYPASS_RE = re.compile(r'(?i)(\*?cidr|\blte\b|\bsni\b|обход)')

# Заглушки-разделители категорий (с флагом Сомали 🇸🇴)
DUMMY_CATEGORY_MAIN = "vless://00000000-0000-0000-0000-000000000000@127.0.0.1:443?encryption=none&security=none&type=tcp#%F0%9F%87%B8%F0%9F%87%B4%20%D0%9E%D0%A1%D0%9D%D0%9E%D0%92%D0%9D%D0%AB%D0%95%20%D0%A1%D0%95%D0%A0%D0%92%D0%95%D0%A0%D0%90"
DUMMY_CATEGORY_RU = "vless://00000000-0000-0000-0000-000000000000@127.0.0.1:443?encryption=none&security=none&type=tcp#%F0%9F%87%B8%F0%9F%87%B4%20%D0%AE%D0%A2%D0%A3%D0%91%20%D0%91%D0%95%D0%97%20%D0%A0%D0%95%D0%9A%D0%9B%D0%90%D0%9C%D0%AB"
DUMMY_CATEGORY_BYPASS = "vless://00000000-0000-0000-0000-000000000000@127.0.0.1:443?encryption=none&security=none&type=tcp#%F0%9F%87%B8%F0%9F%87%B4%20%D0%9E%D0%91%D0%A5%D0%9E%D0%94%20%D0%94%D0%9B%D0%AF%20%D0%91%D0%A1"

# Регулярка для извлечения эмодзи-флагов стран
FLAG_RE = re.compile(r'[\U0001F1E6-\U0001F1FF]{2}')

# Оставляем ТОЛЬКО VLESS протокол
VPN_SCHEMES = ("vless://",)

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


def fetch_source_configs(urls: list[str] = None, timeout: int = 30) -> list[str]:
    """
    Скачивает VLESS конфиги из всех источников в списке,
    дедуплицирует по содержимому ссылки (без учета хеша).
    """
    if urls is None:
        urls = SOURCE_URLS

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "*/*"
    }

    all_lines = []
    seen_bases = set()

    for url in urls:
        clean_url = url
        # Автоматическая конвертация github.com/.../blob/... в raw.githubusercontent.com/...
        if "github.com/" in clean_url and "/blob/" in clean_url:
            clean_url = clean_url.replace("github.com/", "raw.githubusercontent.com/").replace("/blob/", "/")
        if "refs/BLACK_VLESS_RUS.txt" in clean_url:
            clean_url = clean_url.replace("refs/BLACK_VLESS_RUS.txt", "main/BLACK_VLESS_RUS.txt")

        for attempt in range(1, 4):
            try:
                req = urllib.request.Request(clean_url, headers=headers)
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    content = resp.read().decode("utf-8", errors="ignore")
                    lines = [line.strip() for line in content.splitlines() if line.strip()]
                    
                    for line in lines:
                        if line.startswith("vless://"):
                            base = line.split("#", 1)[0].strip()
                            if base not in seen_bases:
                                seen_bases.add(base)
                                all_lines.append(line)
                        elif line.startswith("#"):
                            all_lines.append(line)
                    break
            except Exception:
                if attempt == 3:
                    pass
                time.sleep(1)

    return all_lines


def parse_source_metadata(lines: list[str]) -> dict:
    """Извлекает метаданные из шапок исходных файлов."""
    meta = {
        "source_count": 0,
        "source_update_time": "Неизвестно",
        "source_title": "ouVPN VLESS Bundle"
    }
    
    for line in lines:
        if not line.startswith("#"):
            continue
        line_clean = line.lstrip("#").strip()
        if "announce:" in line_clean or "Date/Time:" in line_clean:
            m_time = re.search(r'(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}|\d{4}-\d{2}-\d{2}\s*/\s*\d{2}:\d{2})', line_clean)
            if m_time:
                meta["source_update_time"] = m_time.group(1)

    meta["source_count"] = sum(1 for l in lines if l.startswith("vless://"))
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
    """Класс представления одного VPN-сервера (только VLESS)."""
    def __init__(self, raw_url: str, source_id: int):
        self.raw_url = raw_url
        self.source_id = source_id
        self.scheme = "vless"
        
        self.old_name = self._extract_old_name()
        self.flag, self.country_code = extract_flag_and_country(self.old_name)
        
        # Обходы: EU, CIDR, *CIDR, LTE, SNI (в любом регистре) или слово обход
        self.is_bypass = (self.country_code == "EU" or bool(BYPASS_RE.search(self.old_name)))
        if self.is_bypass:
            self.flag = "🇪🇺"
            self.country_code = "EU"

        self.eu_num = 0
        
        self.selected = True
        self.is_fast = False
        
        # Данные проверки
        self.ping_ms = None
        self.ping_status = "не проверен"
        
    def _extract_old_name(self) -> str:
        if "#" in self.raw_url:
            return urllib.parse.unquote(self.raw_url.split("#", 1)[1])
        return ""

    def get_display_name(self) -> str:
        fast_mark = " ⚡" if self.is_fast else ""
        if self.is_bypass:
            num = self.eu_num if self.eu_num > 0 else self.source_id
            return f"#{self.source_id} | 🇪🇺 Обход №{num}{fast_mark}"
        elif self.country_code and self.flag:
            return f"#{self.source_id} | {self.country_code} {self.flag} ouVPN V2{fast_mark}"
        else:
            return f"#{self.source_id} | 🌐 ouVPN V2{fast_mark}"

    def build_export_url(self) -> str:
        new_name = self.get_display_name()
        encoded_name = new_name.replace(" ", "%20").replace("#", "%23")
        base_url = self.raw_url.split("#", 1)[0]
        return f"{base_url}#{encoded_name}"

    def get_category_priority(self) -> int:
        if self.is_bypass:
            return 4
        if self.country_code == "RU":
            return 3
        if self.country_code in EUROPEAN_COUNTRIES:
            return 1
        return 2


def parse_all_servers(lines: list[str]) -> list[ServerItem]:
    """Парсит строки в список объектов ServerItem (ТОЛЬКО VLESS, с дедупликацией)."""
    servers = []
    source_counter = 0
    eu_counter = 0
    seen_bases = set()

    for line in lines:
        if line.startswith("#"):
            continue
        if not line.startswith("vless://"):
            continue
            
        base = line.split("#", 1)[0].strip()
        if base in seen_bases:
            continue
        seen_bases.add(base)

        source_counter += 1
        item = ServerItem(line, source_counter)
        if item.is_bypass:
            eu_counter += 1
            item.eu_num = eu_counter
        servers.append(item)

    return servers


def convert_item_to_xray_outbound(item: ServerItem, tag: str) -> dict | None:
    """Конвертирует VLESS ServerItem в исходящий узел Xray (outbound)."""
    link = item.raw_url
    p = urllib.parse.urlparse(link)

    try:
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
    except Exception:
        return None


def _probe_targets(opener, timeout: int) -> tuple[bool, int, str]:
    """
    Проверяет 5 ключевых сервисов: Google, Telegram, Discord, Instagram, YouTube.
    Возвращает (успех, средний_пинг, статус/ошибка).
    """
    # 1. Google
    t0 = time.time()
    try:
        req = urllib.request.Request(PING_TEST_URL_GOOGLE, headers={"User-Agent": "Mozilla/5.0"})
        with opener.open(req, timeout=timeout) as resp:
            if resp.status not in (200, 204):
                return False, 0, "Таймаут (Google)"
            g_ms = int(round((time.time() - t0) * 1000))
    except Exception:
        return False, 0, "Таймаут (Google)"

    # 2. Telegram
    t1 = time.time()
    try:
        req = urllib.request.Request(PING_TEST_URL_TELEGRAM, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with opener.open(req, timeout=timeout) as resp:
            if resp.status not in (200, 204, 301, 302, 307, 308):
                return False, 0, "TG недоступен"
            tg_ms = int(round((time.time() - t1) * 1000))
    except Exception:
        return False, 0, "TG недоступен"

    # 3. Discord
    t2 = time.time()
    try:
        req = urllib.request.Request(PING_TEST_URL_DISCORD, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0.0.0"})
        with opener.open(req, timeout=timeout) as resp:
            if resp.status not in (200, 204, 301, 302, 307, 308):
                return False, 0, "Discord недоступен"
            dc_ms = int(round((time.time() - t2) * 1000))
    except Exception:
        return False, 0, "Discord недоступен"

    # 4. Instagram
    t3 = time.time()
    try:
        req = urllib.request.Request(PING_TEST_URL_INSTAGRAM, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0.0.0"})
        with opener.open(req, timeout=timeout) as resp:
            if resp.status not in (200, 204, 301, 302, 307, 308):
                return False, 0, "Instagram недоступен"
            ig_ms = int(round((time.time() - t3) * 1000))
    except Exception:
        return False, 0, "Instagram недоступен"

    # 5. YouTube
    t4 = time.time()
    try:
        req = urllib.request.Request(PING_TEST_URL_YOUTUBE, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with opener.open(req, timeout=timeout) as resp:
            if resp.status not in (200, 204, 301, 302, 307, 308):
                return False, 0, "YouTube недоступен"
            yt_ms = int(round((time.time() - t4) * 1000))
    except Exception:
        return False, 0, "YouTube недоступен"

    avg_round = int(round((g_ms + tg_ms + dc_ms + ig_ms + yt_ms) / 5.0))
    return True, avg_round, "OK"


def test_servers_ping_xray(
    servers: list[ServerItem],
    on_progress=None,
    on_status=None,
    timeout: int = 8,
    batch_size: int = 35,
    stop_event: threading.Event = None
):
    """
    Комплексная двойная проверка доступности через Xray (2 раунда с интервалом 15 секунд):
    В каждом раунде проверяются 5 сервисов:
    1) HTTP GET на Google (gstatic generate_204)
    2) HTTPS GET на Telegram (https://t.me)
    3) HTTPS GET на Discord (https://discord.com/)
    4) HTTPS GET на Instagram (https://www.instagram.com/)
    5) HTTPS GET на YouTube (https://www.youtube.com/generate_204)
    В поле ping выводится средний пинг из двух средних пингов проверок!
    """
    xray_path = ensure_xray_binary()
    core_dir = get_core_dir()
    
    total = len(servers)
    completed = 0
    base_port = 25000

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

        proc = subprocess.Popen(
            [xray_path, "run", "-c", cfg_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(0.8)

        round1_results = {}

        def run_round1(srv: ServerItem, port_num: int):
            if stop_event and stop_event.is_set():
                return
            proxy_handler = urllib.request.ProxyHandler({
                "http": f"http://127.0.0.1:{port_num}",
                "https": f"http://127.0.0.1:{port_num}"
            })
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
            opener = urllib.request.build_opener(
                proxy_handler,
                urllib.request.HTTPSHandler(context=ssl_ctx)
            )
            ok, avg1, err = _probe_targets(opener, timeout)
            if ok:
                round1_results[srv] = (avg1, opener)
                srv.ping_status = f"Раунд 1: {avg1} ms"
            else:
                srv.ping_ms = None
                srv.ping_status = err

        with ThreadPoolExecutor(max_workers=min(30, len(port_map))) as executor:
            futures = [executor.submit(run_round1, srv, port_map[srv]) for srv in port_map]
            for fut in as_completed(futures):
                if stop_event and stop_event.is_set():
                    break

        # Пауза 15 секунд перед вторым раундом для проверки стабильности соединения
        if round1_results and not (stop_event and stop_event.is_set()):
            for sec in range(15, 0, -1):
                if stop_event and stop_event.is_set():
                    break
                if on_status:
                    on_status(f"Интервал 15 сек перед Раундом 2 (осталось {sec} сек)...")
                time.sleep(1)

        # Раунд 2
        def run_round2(srv: ServerItem):
            if stop_event and stop_event.is_set():
                return
            avg1, opener = round1_results[srv]
            ok2, avg2, err2 = _probe_targets(opener, timeout)
            if ok2:
                final_avg = int(round((avg1 + avg2) / 2.0))
                srv.ping_ms = final_avg
                srv.ping_status = f"{final_avg} ms"
            else:
                srv.ping_ms = None
                srv.ping_status = f"Сбой раунда 2 ({err2})"

        if round1_results and not (stop_event and stop_event.is_set()):
            with ThreadPoolExecutor(max_workers=min(25, len(round1_results))) as executor2:
                futures2 = [executor2.submit(run_round2, srv) for srv in round1_results]
                for fut in as_completed(futures2):
                    pass

        completed += len(port_map)
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


def save_and_push_servers(selected_servers: list[ServerItem], on_status=None, preserve_order: bool = False) -> tuple[bool, str]:
    """
    Формирует ouvpn.txt с заглушками-категориями (🇸🇴), коммитит и пушит на GitHub.
    Автоматически синхронизирует ветку с origin/main перед записью, предотвращая ошибки non-fast-forward.
    """
    base_dir = get_base_dir()
    heading_file = os.path.join(base_dir, "heading.txt")
    output_file = os.path.join(base_dir, "ouvpn.txt")

    if not selected_servers:
        return False, "Не выбрано ни одного сервера для сохранения!"

    if on_status:
        on_status("Синхронизация с GitHub перед публикацией...")

    # 1. Отменяем любые зависшие rebase / merge в локальном репозитории
    try:
        subprocess.run(["git", "rebase", "--abort"], cwd=base_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "merge", "--abort"], cwd=base_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

    # 2. Получаем актуальный origin/main и аккуратно выравниваем HEAD
    try:
        subprocess.run(["git", "fetch", "origin", "main"], cwd=base_dir, check=True)
        subprocess.run(["git", "reset", "--mixed", "origin/main"], cwd=base_dir, check=True)
    except Exception as ex:
        return False, f"Ошибка синхронизации с GitHub (fetch/reset): {ex}"

    if on_status:
        on_status("Формирование разделов с заглушками категорий 🇸🇴...")

    if preserve_order:
        active_list = list(selected_servers)
    else:
        active_list = sort_servers_by_user_rules(selected_servers)

    # 3. Разделение на 3 категории с заглушками:
    # 1. 🇸🇴 ОСНОВНЫЕ СЕРВЕРА (Европейские и международные)
    # 2. 🇸🇴 ЮТУБ БЕЗ РЕКЛАМЫ (Россия RU)
    # 3. 🇸🇴 ОБХОД ДЛЯ БС (Обходы EU, CIDR, LTE, SNI)
    main_servers = [s for s in active_list if not s.is_bypass and s.country_code != "RU"]
    ru_servers = [s for s in active_list if not s.is_bypass and s.country_code == "RU"]
    bypass_servers = [s for s in active_list if s.is_bypass]

    export_lines = []
    if main_servers:
        export_lines.append(DUMMY_CATEGORY_MAIN)
        export_lines.extend([s.build_export_url() for s in main_servers])
    if ru_servers:
        export_lines.append(DUMMY_CATEGORY_RU)
        export_lines.extend([s.build_export_url() for s in ru_servers])
    if bypass_servers:
        export_lines.append(DUMMY_CATEGORY_BYPASS)
        export_lines.extend([s.build_export_url() for s in bypass_servers])

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

    rendered_head = render_heading_text(template, count=len(active_list), interval=1)
    content = rendered_head + "\n\n\n" + "\n".join(export_lines) + "\n"

    with open(output_file, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)

    if on_status:
        on_status(f"Файл ouvpn.txt записан ({len(active_list)} серв.). Отправка на GitHub...")

    try:
        subprocess.run(["git", "add", "ouvpn.txt"], cwd=base_dir, check=True)
        commit_msg = f"Ручное обновление рабочих серверов ouVPN [{len(active_list)} шт.] [skip ci]"
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=base_dir, check=True)
        
        # Отправляем в репозиторий
        push_res = subprocess.run(["git", "push", "origin", "main"], cwd=base_dir, capture_output=True, text=True)
        if push_res.returncode != 0:
            # На случай конкурентного коммита — выполняем rebase с приоритетом нашего ouvpn.txt
            subprocess.run(["git", "pull", "--rebase", "-X", "theirs", "origin", "main"], cwd=base_dir)
            push_res2 = subprocess.run(["git", "push", "origin", "main"], cwd=base_dir, capture_output=True, text=True)
            if push_res2.returncode != 0:
                return False, f"Ошибка при push на GitHub:\n{push_res2.stderr.strip()}"

        return True, f"Успешно сохранено и отправлено на GitHub! Всего активных серверов: {len(active_list)}"
    except Exception as ex:
        return False, f"Ошибка Git: {ex}"
