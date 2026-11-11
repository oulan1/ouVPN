#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ouVPN Server Updater (Категория 1: Быстрое обновление всех серверов)
Скачивает все серверы из источника, форматирует по правилам с индексами | #N,
сортирует (Европа ➔ Другие ➔ РФ ➔ Обходы) и сохраняет в ouvpn.txt.
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import core_engine


def main():
    print("[*] Запуск быстрого обновления ВСЕХ серверов ouVPN...")

    # 1. Загрузка исходных конфигов
    lines = core_engine.fetch_source_configs()
    print(f"[+] Скачано {len(lines)} строк из источника.")

    # 2. Парсинг серверов
    servers = core_engine.parse_all_servers(lines)
    print(f"[+] Распознано серверов: {len(servers)}")

    if not servers:
        print("[-] Ошибка: Сервера не найдены!")
        sys.exit(1)

    # 3. Сортировка по правилам пользователя
    sorted_servers = core_engine.sort_servers_by_user_rules(servers)

    # 4. Чтение шаблона шапки
    heading_file = os.path.join(BASE_DIR, "heading.txt")
    output_file = os.path.join(BASE_DIR, "ouvpn.txt")

    default_template = (
        "# profile-title: ouVPN V2\n"
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

    print(f"[+] Файл ouvpn.txt успешно обновлен! Всего серверов: {len(sorted_servers)}")


if __name__ == "__main__":
    main()
