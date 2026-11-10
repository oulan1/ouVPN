#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ouVPN Verified Updater (Категория 2: Обновление только РАБОЧИХ серверов с проверкой пинга)
Скачивает серверы, выполняет реальный HTTP GET запрос к gstatic.com/generate_204 через Xray,
отсеивает все неработающие серверы, сортирует оставшиеся и обновляет ouvpn.txt.
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import core_engine


def main():
    print("[*] Запуск обновления проверенных серверов ouVPN (с проверкой пинга HTTP 204)...")

    # 1. Загрузка исходных конфигов
    lines = core_engine.fetch_source_configs()
    print(f"[+] Скачано {len(lines)} строк из источника.")

    # 2. Парсинг серверов
    servers = core_engine.parse_all_servers(lines)
    print(f"[+] Распознано серверов: {len(servers)}")

    if not servers:
        print("[-] Ошибка: Сервера не найдены!")
        sys.exit(1)

    # 3. Гарантируем наличие Xray
    print("[*] Подготовка Xray-core...")
    core_engine.ensure_xray_binary()

    # 4. Проверка пинга через HTTP GET generate_204
    print("[*] Запуск параллельной проверки пинга через Xray (таймаут 10 сек)...")
    def on_prog(done, total):
        if done % 20 == 0 or done == total:
            print(f"    Проверено {done}/{total}...")

    core_engine.test_servers_ping_xray(servers, on_progress=on_prog, timeout=10, batch_size=40)

    # 5. Отбор только работающих серверов
    working_servers = [s for s in servers if s.ping_ms is not None]
    print(f"[+] Результат проверки: Онлайн = {len(working_servers)}, Не работают = {len(servers) - len(working_servers)}")

    if not working_servers:
        print("[-] Предупреждение: Ни один сервер не ответил на проверку пинга! ouvpn.txt не будет очищен.")
        sys.exit(1)

    # 6. Сортировка по правилам (Европа с минимальным пингом ➔ Другие ➔ РФ ➔ Обходы)
    sorted_servers = core_engine.sort_servers_by_user_rules(working_servers)

    # 7. Чтение шаблона шапки и сохранение ouvpn.txt
    heading_file = os.path.join(BASE_DIR, "heading.txt")
    output_file = os.path.join(BASE_DIR, "ouvpn.txt")

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

    rendered_head = core_engine.render_heading_text(template, count=len(sorted_servers), interval=1)
    export_lines = [s.build_export_url() for s in sorted_servers]
    content = rendered_head + "\n\n\n" + "\n".join(export_lines) + "\n"

    with open(output_file, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)

    print(f"[+] Файл ouvpn.txt успешно обновлен! Записано ТОЛЬКО рабочих серверов: {len(sorted_servers)}")


if __name__ == "__main__":
    main()
