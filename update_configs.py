#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ouVPN Server Updater
Парсер и переносчик серверов из источника в ouvpn.txt
с автоматическим переименованием по шаблону и динамической шапкой.
"""

import sys
import re
import json
import base64
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta

# Ссылка на исходную подписку с конфигами
SOURCE_URL = "https://raw.githubusercontent.com/bobrinaw/vlessforu/main/working_configs.txt"

# Пути к файлам (по умолчанию в текущей папке репозитория)
HEADING_FILE = "heading.txt"
OUTPUT_FILE = "ouvpn.txt"

# Интервал обновления профиля в часах
UPDATE_INTERVAL_HOURS = 1

# Регулярное выражение для поиска эмодзи-флагов стран (Regional Indicator Symbols)
FLAG_RE = re.compile(r'[\U0001F1E6-\U0001F1FF]{2}')

# Поддерживаемые протоколы VPN
VPN_SCHEMES = ("vless://", "vmess://", "trojan://", "ss://", "ssr://", "hysteria2://", "hy2://", "tuic://")


def fetch_source_configs(url: str, timeout: int = 30) -> list[str]:
    """Скачивает список строк из источника с повторными попытками."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "*/*"
    }
    req = urllib.request.Request(url, headers=headers)
    
    last_error = None
    for attempt in range(1, 4):
        try:
            print(f"[+] Загрузка конфигов из источника (попытка {attempt}/3)...")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                content = resp.read().decode("utf-8", errors="ignore")
                lines = [line.strip() for line in content.splitlines() if line.strip()]
                print(f"[+] Успешно скачано {len(lines)} строк.")
                return lines
        except Exception as e:
            last_error = e
            print(f"[-] Ошибка при попытке {attempt}: {e}")
            
    raise RuntimeError(f"Не удалось скачать конфиги после 3 попыток: {last_error}")


def extract_flag_and_country(raw_name: str) -> tuple[str | None, str | None]:
    """
    Извлекает эмодзи флага и двухбуквенный код страны (ISO).
    Эмодзи флага состоит из двух символов Regional Indicator (A-Z).
    """
    m = FLAG_RE.search(raw_name)
    if not m:
        return None, None
    flag = m.group(0)
    country_code = "".join(chr(ord(c) - 0x1F1E6 + ord("A")) for c in flag)
    return flag, country_code


def process_vpn_config(raw_line: str, eu_counter: int) -> tuple[str | None, int]:
    """
    Обрабатывает строку VPN:
    - определяет протокол
    - извлекает старое имя и флаг
    - формирует новое имя согласно шаблону:
      * Для ЕС: 🇪🇺 Обход №{eu_counter}
      * Для остальных: {CC} {FLAG} ouVPN V2
    - возвращает обновленную строку конфига и новое значение eu_counter.
    """
    # Пропускаем строки не являющиеся VPN (например routing rules happ://)
    is_vpn = any(raw_line.startswith(scheme) for scheme in VPN_SCHEMES)
    if not is_vpn:
        return None, eu_counter

    # Определяем старое название сервера для извлечения страны
    old_name = ""
    if "#" in raw_line:
        old_name = urllib.parse.unquote(raw_line.split("#", 1)[1])
    elif raw_line.startswith("vmess://"):
        b64 = raw_line[8:].split("#", 1)[0]
        pad = len(b64) % 4
        if pad:
            b64 += "=" * (4 - pad)
        try:
            d = json.loads(base64.b64decode(b64).decode("utf-8", errors="ignore"))
            old_name = d.get("ps", "")
        except Exception:
            pass

    flag, country_code = extract_flag_and_country(old_name)

    # Генерация нового имени
    if country_code == "EU":
        eu_counter += 1
        new_name = f"{flag} Обход №{eu_counter}"
    elif country_code and flag:
        new_name = f"{country_code} {flag} ouVPN V2"
    else:
        # Запасной вариант, если флаг не найден
        new_name = "🌐 ouVPN V2"

    # Кодируем имя для ссылки (пробелы заменяются на %20, как в эталонном ouvpn.txt)
    encoded_name = new_name.replace(" ", "%20")

    # Обработка vmess с обновлением JSON 'ps' для максимальной совместимости
    if raw_line.startswith("vmess://"):
        b64_part = raw_line[8:].split("#", 1)[0]
        pad = len(b64_part) % 4
        if pad:
            b64_part += "=" * (4 - pad)
        try:
            d = json.loads(base64.b64decode(b64_part).decode("utf-8", errors="ignore"))
            d["ps"] = new_name
            new_b64 = base64.b64encode(json.dumps(d, ensure_ascii=False).encode("utf-8")).decode("ascii")
            return f"vmess://{new_b64}#{encoded_name}", eu_counter
        except Exception:
            # Если не удалось распарсить JSON, просто заменяем hash
            pass

    # Для остальных протоколов (vless, trojan, ss и т.д.)
    base_url = raw_line.split("#", 1)[0]
    return f"{base_url}#{encoded_name}", eu_counter


def render_heading(heading_template: str, count: int, interval: int) -> str:
    """
    Подставляет переменные времени МСК и количества серверов в шаблон шапки.
    Отсекает блок документации переменных (все, что ниже разделителя).
    """
    # Московское время (UTC+3)
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

    # Отрезаем комментарии инструкции внизу шаблона
    # Разделитель: строка, содержащая '--- ИНСТРУКЦИЯ' или '--- VARIABLES'
    lines = heading_template.splitlines()
    clean_lines = []
    for line in lines:
        if "---" in line and ("ИНСТРУКЦИЯ" in line or "VARIABLES" in line or "ДОСТУПНЫЕ ПЕРЕМЕННЫЕ" in line):
            break
        clean_lines.append(line)

    heading_text = "\n".join(clean_lines).strip()

    # Заменяем все переменные {var}
    for key, val in vars_dict.items():
        heading_text = heading_text.replace(f"{{{key}}}", val)
        heading_text = heading_text.replace(f"{{{key.upper()}}}", val)

    return heading_text


def main():
    print("[*] Запуск обновления серверов ouVPN...")

    # 1. Загрузка исходных конфигов
    raw_lines = fetch_source_configs(SOURCE_URL)

    # 2. Обработка серверов
    processed_servers = []
    eu_counter = 0

    for line in raw_lines:
        if line.startswith("#"):
            continue
        new_config, eu_counter = process_vpn_config(line, eu_counter)
        if new_config:
            processed_servers.append(new_config)

    total_servers = len(processed_servers)
    print(f"[+] Обработано серверов: {total_servers} (из них ЕС обходов: {eu_counter})")

    if total_servers == 0:
        print("[-] Ошибка: Не найдено ни одного рабочего сервера! ouvpn.txt не будет перезаписан.")
        sys.exit(1)

    # 3. Чтение heading.txt или использование дефолтного шаблона
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
        with open(HEADING_FILE, "r", encoding="utf-8") as f:
            template = f.read()
            print(f"[+] Загружен шаблон шапки из {HEADING_FILE}")
    except FileNotFoundError:
        print(f"[!] Файл {HEADING_FILE} не найден. Используется шаблон по умолчанию.")
        template = default_template

    rendered_header = render_heading(template, count=total_servers, interval=UPDATE_INTERVAL_HOURS)

    # 4. Формирование и запись итогового ouvpn.txt
    output_content = rendered_header + "\n\n\n" + "\n".join(processed_servers) + "\n"

    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="\n") as f:
        f.write(output_content)

    print(f"[+] Файл {OUTPUT_FILE} успешно обновлен! Всего серверов: {total_servers}")


if __name__ == "__main__":
    main()
