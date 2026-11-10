#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ouVPN Control Panel
Графический интерфейс для ручного отбора рабочих серверов,
проверки пинга через HTTP GET generate_204 и публикации на GitHub.
"""

import sys
import os
import re
import threading
import tkinter as tk
from tkinter import ttk, messagebox

# Добавляем текущую директорию в путь импорта
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import core_engine
from core_engine import ServerItem


class OUVPNPanelApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("🛡️ ouVPN Control Panel | 🟢 ouVPN V2")
        self.root.geometry("1100x750")
        self.root.minsize(900, 600)
        self.root.configure(bg="#0b090f")

        # Список серверов в памяти
        self.servers: list[ServerItem] = []
        self.displayed_servers: list[ServerItem] = []
        
        # Потоки и остановка
        self.ping_thread = None
        self.stop_ping_event = threading.Event()
        self.is_pinging = False

        self._setup_styles()
        self._build_ui()

    def _setup_styles(self):
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        # Цветовая палитра ouVPN
        self.c_bg = "#0b090f"
        self.c_card = "#15121c"
        self.c_card_border = "#2e224d"
        self.c_primary = "#8b5cf6"
        self.c_primary_hover = "#a78bfa"
        self.c_gold = "#f59e0b"
        self.c_gold_bg = "#35290a"
        self.c_green = "#10b981"
        self.c_red = "#ef4444"
        self.c_text = "#f8fafc"
        self.c_muted = "#94a3b8"
        self.c_table_bg = "#191522"
        self.c_table_row2 = "#14111c"

        # Стили элементов TTK
        self.style.configure(".", background=self.c_bg, foreground=self.c_text)
        
        # Настройка Treeview (таблицы)
        self.style.configure(
            "Custom.Treeview",
            background=self.c_table_bg,
            foreground=self.c_text,
            fieldbackground=self.c_table_bg,
            rowheight=28,
            font=("Segoe UI", 10),
            borderwidth=0
        )
        self.style.configure(
            "Custom.Treeview.Heading",
            background="#231b33",
            foreground="#c4b5fd",
            font=("Segoe UI", 10, "bold"),
            borderwidth=1,
            relief="flat"
        )
        self.style.map(
            "Custom.Treeview.Heading",
            background=[("active", "#312647")]
        )
        self.style.map(
            "Custom.Treeview",
            background=[("selected", "#3b2b5e")],
            foreground=[("selected", "#ffffff")]
        )

        # Прогресс бар
        self.style.configure(
            "Custom.Horizontal.TProgressbar",
            troughcolor="#1e182b",
            background=self.c_primary,
            bordercolor=self.c_card_border,
            lightcolor=self.c_primary,
            darkcolor=self.c_primary
        )

    def _build_ui(self):
        # 1. Шапка (Заголовок + Карточки статистики)
        top_frame = tk.Frame(self.root, bg=self.c_bg, padx=15, pady=10)
        top_frame.pack(fill="x")

        title_box = tk.Frame(top_frame, bg=self.c_bg)
        title_box.pack(side="left")

        title_lbl = tk.Label(
            title_box,
            text="🛡️ ouVPN Control Panel",
            font=("Segoe UI", 18, "bold"),
            bg=self.c_bg,
            fg="#c4b5fd"
        )
        title_lbl.pack(anchor="w")

        sub_lbl = tk.Label(
            title_box,
            text="Ручной отбор рабочих серверов и быстрая публикация на GitHub",
            font=("Segoe UI", 9),
            bg=self.c_bg,
            fg=self.c_muted
        )
        sub_lbl.pack(anchor="w")

        # Карточки статистики справа
        stats_box = tk.Frame(top_frame, bg=self.c_bg)
        stats_box.pack(side="right")

        self.card_total = self._create_stat_card(stats_box, "Всего в источнике", "0")
        self.card_updated = self._create_stat_card(stats_box, "Обновление источника", "--")
        self.card_selected = self._create_stat_card(stats_box, "Выбрано для Push", "0", highlight=True)

        # 2. Панель основных действий (Кнопки)
        action_bar = tk.Frame(self.root, bg=self.c_card, bd=1, relief="solid", padx=12, pady=10)
        action_bar.configure(highlightbackground=self.c_card_border, highlightthickness=1)
        action_bar.pack(fill="x", padx=15, pady=(0, 10))

        # Кнопка: Извлечь сервера
        self.btn_fetch = tk.Button(
            action_bar,
            text="📥 Извлечь текущие сервера",
            font=("Segoe UI", 10, "bold"),
            bg="#2e224d",
            fg=self.c_text,
            activebackground=self.c_primary,
            activeforeground="#ffffff",
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=self.action_fetch_servers
        )
        self.btn_fetch.pack(side="left", padx=(0, 8))

        # Кнопка: Проверить пинг
        self.btn_ping = tk.Button(
            action_bar,
            text="⚡ Проверить пинг (HTTP 204)",
            font=("Segoe UI", 10, "bold"),
            bg="#3b2b5e",
            fg="#e9d5ff",
            activebackground=self.c_primary,
            activeforeground="#ffffff",
            bd=0,
            padx=14,
            pady=6,
            cursor="hand2",
            command=self.action_test_ping
        )
        self.btn_ping.pack(side="left", padx=(0, 8))

        # Кнопка: Стоп
        self.btn_stop = tk.Button(
            action_bar,
            text="⏹️ Стоп",
            font=("Segoe UI", 9, "bold"),
            bg="#451a1a",
            fg="#fca5a5",
            activebackground="#7f1d1d",
            activeforeground="#ffffff",
            bd=0,
            padx=10,
            pady=6,
            cursor="hand2",
            state="disabled",
            command=self.action_stop_ping
        )
        self.btn_stop.pack(side="left", padx=(0, 15))

        # Кнопка: Выбрать только рабочие
        self.btn_select_online = tk.Button(
            action_bar,
            text="✅ Только рабочие (с пингом)",
            font=("Segoe UI", 9, "bold"),
            bg="#064e3b",
            fg="#6ee7b7",
            activebackground="#047857",
            activeforeground="#ffffff",
            bd=0,
            padx=12,
            pady=6,
            cursor="hand2",
            command=self.action_select_online_only
        )
        self.btn_select_online.pack(side="left", padx=(0, 8))

        # Кнопка: Push на GitHub
        self.btn_push = tk.Button(
            action_bar,
            text="🚀 Опубликовать на GitHub (Push)",
            font=("Segoe UI", 10, "bold"),
            bg=self.c_primary,
            fg="#ffffff",
            activebackground=self.c_primary_hover,
            activeforeground="#ffffff",
            bd=0,
            padx=16,
            pady=6,
            cursor="hand2",
            command=self.action_push_github
        )
        self.btn_push.pack(side="right")

        # 3. Панель выбора по номерам и фильтрации
        select_bar = tk.Frame(self.root, bg=self.c_bg, padx=15, pady=0)
        select_bar.pack(fill="x", pady=(0, 8))

        # Быстрые кнопки выбора
        btn_all = tk.Button(
            select_bar, text="Выбрать все", font=("Segoe UI", 8),
            bg="#221c30", fg=self.c_muted, bd=0, padx=8, pady=3,
            cursor="hand2", command=self.action_select_all
        )
        btn_all.pack(side="left", padx=(0, 4))

        btn_none = tk.Button(
            select_bar, text="Снять все", font=("Segoe UI", 8),
            bg="#221c30", fg=self.c_muted, bd=0, padx=8, pady=3,
            cursor="hand2", command=self.action_deselect_all
        )
        btn_none.pack(side="left", padx=(0, 15))

        # Ввод номеров через запятую
        num_lbl = tk.Label(select_bar, text="Номера через запятую (напр. 1, 2, 5, 10-15):", font=("Segoe UI", 9), bg=self.c_bg, fg=self.c_text)
        num_lbl.pack(side="left", padx=(0, 6))

        self.num_entry = tk.Entry(
            select_bar, font=("Segoe UI", 9), bg="#1c1626", fg="#ffffff",
            insertbackground="#ffffff", bd=1, relief="solid", highlightthickness=0, width=28
        )
        self.num_entry.pack(side="left", padx=(0, 6), ipady=3)
        self.num_entry.bind("<Return>", lambda e: self.action_apply_numbers())

        btn_apply_num = tk.Button(
            select_bar, text="Выбрать", font=("Segoe UI", 8, "bold"),
            bg="#3b2b5e", fg="#e9d5ff", bd=0, padx=10, pady=3,
            cursor="hand2", command=self.action_apply_numbers
        )
        btn_apply_num.pack(side="left", padx=(0, 15))

        # Поиск по имени / стране
        search_lbl = tk.Label(select_bar, text="🔍 Поиск:", font=("Segoe UI", 9), bg=self.c_bg, fg=self.c_muted)
        search_lbl.pack(side="left", padx=(0, 4))

        self.search_entry = tk.Entry(
            select_bar, font=("Segoe UI", 9), bg="#1c1626", fg="#ffffff",
            insertbackground="#ffffff", bd=1, relief="solid", highlightthickness=0, width=16
        )
        self.search_entry.pack(side="left", padx=(0, 6), ipady=3)
        self.search_entry.bind("<KeyRelease>", lambda e: self.action_filter_table())

        # 4. Основная таблица серверов
        table_frame = tk.Frame(self.root, bg=self.c_bg, padx=15)
        table_frame.pack(fill="both", expand=True)

        columns = ("id", "sel", "name", "country", "ping", "fast")
        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            style="Custom.Treeview",
            selectmode="extended"
        )

        self.tree.heading("id", text="# ID", anchor="center")
        self.tree.heading("sel", text="Выбор", anchor="center")
        self.tree.heading("name", text="Название сервера для ouvpn.txt", anchor="w")
        self.tree.heading("country", text="Страна", anchor="center")
        self.tree.heading("ping", text="Пинг (HTTP 204)", anchor="center")
        self.tree.heading("fast", text="Скоростной", anchor="center")

        self.tree.column("id", width=65, anchor="center")
        self.tree.column("sel", width=75, anchor="center")
        self.tree.column("name", width=550, anchor="w")
        self.tree.column("country", width=90, anchor="center")
        self.tree.column("ping", width=140, anchor="center")
        self.tree.column("fast", width=100, anchor="center")

        # Цветовые теги строк
        self.tree.tag_configure("gold", background=self.c_gold_bg, foreground="#fef08a")
        self.tree.tag_configure("even", background=self.c_table_bg)
        self.tree.tag_configure("odd", background=self.c_table_row2)
        self.tree.tag_configure("online", foreground="#34d399")
        self.tree.tag_configure("dead", foreground="#f87171")

        # Скроллбар
        v_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=v_scroll.set)

        self.tree.pack(side="left", fill="both", expand=True)
        v_scroll.pack(side="right", fill="y")

        # Привязка событий к таблице
        self.tree.bind("<Button-1>", self._on_tree_click)
        self.tree.bind("<Double-Button-1>", self._on_tree_double_click)
        self.tree.bind("<space>", self._on_tree_space)

        # 5. Нижняя панель состояния и подсказки
        bottom_frame = tk.Frame(self.root, bg=self.c_card, bd=1, relief="solid", padx=15, pady=8)
        bottom_frame.configure(highlightbackground=self.c_card_border, highlightthickness=1)
        bottom_frame.pack(fill="x", padx=15, pady=10)

        self.lbl_status = tk.Label(
            bottom_frame,
            text="Готово к работе. Нажмите «📥 Извлечь текущие сервера», чтобы загрузить свежие конфиги.",
            font=("Segoe UI", 9),
            bg=self.c_card,
            fg=self.c_text
        )
        self.lbl_status.pack(side="left")

        # Подсказка по дабл-тапу
        hint_lbl = tk.Label(
            bottom_frame,
            text="💡 Клик / Пробел = выбор. Двойной клик = золотой ⚡ скоростной.",
            font=("Segoe UI", 8),
            bg=self.c_card,
            fg=self.c_muted
        )
        hint_lbl.pack(side="right")

        self.prog_bar = ttk.Progressbar(
            self.root,
            style="Custom.Horizontal.TProgressbar",
            orient="horizontal",
            mode="determinate"
        )
        self.prog_bar.pack(fill="x", padx=15, pady=(0, 5))

    def _create_stat_card(self, parent, label_text, val_text, highlight=False):
        f = tk.Frame(parent, bg=self.c_card, bd=1, relief="solid", padx=12, pady=4)
        f.configure(highlightbackground=self.c_primary if highlight else self.c_card_border, highlightthickness=1)
        f.pack(side="left", padx=5)

        lbl = tk.Label(f, text=label_text, font=("Segoe UI", 8), bg=self.c_card, fg=self.c_muted)
        lbl.pack(anchor="center")

        val = tk.Label(
            f, text=val_text,
            font=("Segoe UI", 11, "bold"),
            bg=self.c_card,
            fg="#c4b5fd" if highlight else "#ffffff"
        )
        val.pack(anchor="center")
        return val

    def set_status(self, text: str):
        """Устанавливает статусное сообщение безопасно для потоков."""
        self.root.after(0, lambda: self.lbl_status.configure(text=text))

    def update_selected_count(self):
        cnt = sum(1 for s in self.servers if s.selected)
        self.card_selected.configure(text=f"{cnt} из {len(self.servers)}")

    # ----------------- Обработчики событий таблицы -----------------

    def _on_tree_click(self, event):
        """Одиночный клик по строке для переключения чекбокса выбора."""
        region = self.tree.identify_region(event.x, event.y)
        item_id = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not item_id:
            return

        # Если кликнули по колонке 'sel' или прямо по строке
        if col == "#2":  # колонка sel
            self._toggle_selection_for_item_id(item_id)
            return "break"

    def _on_tree_space(self, event):
        """Нажатие Пробела переключает выбор выделенных строк."""
        selected_items = self.tree.selection()
        if not selected_items:
            return
        for item_id in selected_items:
            self._toggle_selection_for_item_id(item_id)
        return "break"

    def _on_tree_double_click(self, event):
        """
        Двойной клик переключает признак 'скоростной' (⚡)
        и выделяет строку золотым цветом.
        """
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return

        srv = self._find_server_by_item_id(item_id)
        if not srv:
            return

        # Переключаем ⚡
        srv.is_fast = not srv.is_fast
        self._refresh_tree_row(item_id, srv)
        return "break"

    def _toggle_selection_for_item_id(self, item_id):
        srv = self._find_server_by_item_id(item_id)
        if srv:
            srv.selected = not srv.selected
            self._refresh_tree_row(item_id, srv)
            self.update_selected_count()

    def _find_server_by_item_id(self, item_id) -> ServerItem | None:
        try:
            source_id = int(item_id)
            for s in self.servers:
                if s.source_id == source_id:
                    return s
        except Exception:
            pass
        return None

    def _refresh_tree_row(self, item_id, srv: ServerItem):
        sel_text = "  [ ✓ ]" if srv.selected else "  [   ]"
        fast_text = "⚡ Да" if srv.is_fast else "-"
        
        country_disp = "Обход" if srv.is_bypass else (srv.country_code or "??")
        
        ping_disp = srv.ping_status
        if srv.ping_ms is not None:
            ping_disp = f"⚡ {srv.ping_ms} ms"

        self.tree.item(
            item_id,
            values=(
                f"#{srv.source_id}",
                sel_text,
                srv.get_display_name(),
                country_disp,
                ping_disp,
                fast_text
            )
        )

        # Применение цветовых тегов
        tags = []
        if srv.is_fast:
            tags.append("gold")
        else:
            tags.append("odd" if srv.source_id % 2 == 1 else "even")

        if srv.ping_ms is not None:
            tags.append("online")
        elif srv.ping_status not in ("не проверен", ""):
            tags.append("dead")

        self.tree.item(item_id, tags=tags)

    def populate_table(self):
        """Перерисовывает строки таблицы."""
        self.tree.delete(*self.tree.get_children())
        query = self.search_entry.get().strip().lower()

        for srv in self.servers:
            # Фильтрация по поиску
            if query:
                name_low = srv.get_display_name().lower()
                c_low = (srv.country_code or "").lower()
                if query not in name_low and query not in c_low:
                    continue

            item_id = str(srv.source_id)
            sel_text = "  [ ✓ ]" if srv.selected else "  [   ]"
            fast_text = "⚡ Да" if srv.is_fast else "-"
            country_disp = "Обход" if srv.is_bypass else (srv.country_code or "??")
            
            ping_disp = srv.ping_status
            if srv.ping_ms is not None:
                ping_disp = f"⚡ {srv.ping_ms} ms"

            tags = []
            if srv.is_fast:
                tags.append("gold")
            else:
                tags.append("odd" if srv.source_id % 2 == 1 else "even")

            if srv.ping_ms is not None:
                tags.append("online")
            elif srv.ping_status not in ("не проверен", ""):
                tags.append("dead")

            self.tree.insert(
                "",
                "end",
                iid=item_id,
                values=(
                    f"#{srv.source_id}",
                    sel_text,
                    srv.get_display_name(),
                    country_disp,
                    ping_disp,
                    fast_text
                ),
                tags=tags
            )

        self.update_selected_count()

    # ----------------- Кнопки и действия -----------------

    def action_fetch_servers(self):
        """Загрузка свежих серверов из источника."""
        self.set_status("Загрузка конфигов из источника...")
        self.btn_fetch.configure(state="disabled")

        def worker():
            try:
                lines = core_engine.fetch_source_configs()
                meta = core_engine.parse_source_metadata(lines)
                servers = core_engine.parse_all_servers(lines)

                def on_done():
                    self.servers = servers
                    self.card_total.configure(text=str(meta.get("source_count", len(servers))))
                    self.card_updated.configure(text=meta.get("source_update_time", "Недавно"))
                    self.populate_table()
                    self.set_status(f"Успешно загружено {len(servers)} серверов из источника.")
                    self.btn_fetch.configure(state="normal")

                self.root.after(0, on_done)
            except Exception as ex:
                def on_err():
                    messagebox.showerror("Ошибка загрузки", f"Не удалось получить сервера:\n{ex}")
                    self.set_status("Ошибка при загрузке серверов.")
                    self.btn_fetch.configure(state="normal")
                self.root.after(0, on_err)

        threading.Thread(target=worker, daemon=True).start()

    def action_test_ping(self):
        """Запуск проверки пинга через Xray HTTP GET generate_204."""
        if not self.servers:
            messagebox.showinfo("Нет данных", "Сначала нажмите «Извлечь текущие сервера».")
            return

        if self.is_pinging:
            return

        self.is_pinging = True
        self.stop_ping_event.clear()
        self.btn_ping.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.prog_bar["maximum"] = len(self.servers)
        self.prog_bar["value"] = 0
        self.set_status("Инициализация проверки пинга через Xray...")

        def on_prog(completed, total):
            def ui_update():
                self.prog_bar["value"] = completed
                self.set_status(f"Проверка пинга: {completed} из {total}...")
                # Обновляем видимые строки в таблице
                for srv in self.servers:
                    iid = str(srv.source_id)
                    if self.tree.exists(iid):
                        self._refresh_tree_row(iid, srv)
            self.root.after(0, ui_update)

        def worker():
            try:
                # Гарантируем наличие бинарника xray
                core_engine.ensure_xray_binary(on_status=self.set_status)
                core_engine.test_servers_ping_xray(
                    self.servers,
                    on_progress=on_prog,
                    timeout=10,
                    batch_size=35,
                    stop_event=self.stop_ping_event
                )

                def on_finished():
                    self.is_pinging = False
                    self.btn_ping.configure(state="normal")
                    self.btn_stop.configure(state="disabled")
                    self.prog_bar["value"] = self.prog_bar["maximum"]
                    
                    online_count = sum(1 for s in self.servers if s.ping_ms is not None)
                    dead_count = len(self.servers) - online_count
                    self.set_status(f"Проверка завершена! Онлайн: {online_count}, Таймаут/Ошибок: {dead_count}")
                    self.populate_table()
                    
                    res = messagebox.askyesno(
                        "Проверка завершена",
                        f"Найдено живых серверов: {online_count} из {len(self.servers)}.\n\n"
                        f"Выбрать автоматически только рабочие сервера (с пингом)?"
                    )
                    if res:
                        self.action_select_online_only()

                self.root.after(0, on_finished)

            except Exception as ex:
                def on_err():
                    self.is_pinging = False
                    self.btn_ping.configure(state="normal")
                    self.btn_stop.configure(state="disabled")
                    messagebox.showerror("Ошибка проверки", f"Не удалось выполнить проверку:\n{ex}")
                    self.set_status("Ошибка проверки пинга.")
                self.root.after(0, on_err)

        self.ping_thread = threading.Thread(target=worker, daemon=True)
        self.ping_thread.start()

    def action_stop_ping(self):
        """Остановка текущей проверки пинга."""
        if self.is_pinging:
            self.stop_ping_event.set()
            self.set_status("Остановка проверки пинга...")
            self.btn_stop.configure(state="disabled")

    def action_select_online_only(self):
        """Выбирает только сервера с успешным пингом."""
        for s in self.servers:
            s.selected = (s.ping_ms is not None)
        self.populate_table()
        cnt = sum(1 for s in self.servers if s.selected)
        self.set_status(f"Выбрано {cnt} рабочих серверов с пингом.")

    def action_select_all(self):
        for s in self.servers:
            s.selected = True
        self.populate_table()

    def action_deselect_all(self):
        for s in self.servers:
            s.selected = False
        self.populate_table()

    def action_apply_numbers(self):
        """
        Выбирает сервера по номерам, введённым через запятую (напр: 1, 2, 5, 10-15).
        """
        text = self.num_entry.get().strip()
        if not text:
            return

        target_ids = set()
        parts = text.split(",")
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                # Диапазон, например 10-15
                try:
                    start_s, end_s = part.split("-", 1)
                    s_val = int(start_s.strip())
                    e_val = int(end_s.strip())
                    for i in range(min(s_val, e_val), max(s_val, e_val) + 1):
                        target_ids.add(i)
                except Exception:
                    pass
            else:
                try:
                    target_ids.add(int(part))
                except Exception:
                    pass

        if not target_ids:
            messagebox.showwarning("Неверный формат", "Введите числа через запятую или диапазоны (например: 1, 2, 5, 10-20).")
            return

        # Применяем выбор
        matched = 0
        for s in self.servers:
            if s.source_id in target_ids:
                s.selected = True
                matched += 1
            else:
                s.selected = False

        self.populate_table()
        self.set_status(f"Выбрано {matched} серверов по указанным номерам.")

    def action_filter_table(self):
        """Фильтрация строк по поисковому запросу."""
        self.populate_table()

    def action_push_github(self):
        """Сохранение ouvpn.txt и отправка на GitHub."""
        selected = [s for s in self.servers if s.selected]
        if not selected:
            messagebox.showwarning("Ничего не выбрано", "Пожалуйста, отметьте галочками хотя бы один рабочий сервер.")
            return

        confirm = messagebox.askyesno(
            "Подтверждение публикации",
            f"Будет сохранено и отправлено на GitHub серверов: {len(selected)} шт.\n\n"
            f"Порядок расположения серверов:\n"
            f"1. Европа (с сортировкой по минимальному пингу)\n"
            f"2. Другие страны мира\n"
            f"3. Россия (RU)\n"
            f"4. Обходы (🇪🇺 Обход...)\n\n"
            f"Продолжить отправку на GitHub?"
        )
        if not confirm:
            return

        self.btn_push.configure(state="disabled")
        self.set_status("Формирование ouvpn.txt и отправка на GitHub...")

        def worker():
            ok, msg = core_engine.save_and_push_servers(selected, on_status=self.set_status)

            def on_done():
                self.btn_push.configure(state="normal")
                self.set_status(msg)
                if ok:
                    messagebox.showinfo("Успешно!", msg)
                else:
                    messagebox.showerror("Ошибка публикации", msg)

            self.root.after(0, on_done)

        threading.Thread(target=worker, daemon=True).start()


def main():
    root = tk.Tk()
    app = OUVPNPanelApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
