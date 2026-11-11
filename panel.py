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
        
        # Таймер для устранения конфликта одиночного клика и дабл-клика
        self._single_click_timer = None
        
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
        self.c_text = "#f8fafc"
        self.c_muted = "#94a3b8"
        self.c_table_bg = "#191522"

        # Цвета состояний строк
        self.c_purple_bg = "#2e1a4d"      # Фиолетовый фон для выбранного сервера
        self.c_unsel_bg = "#131019"       # Тёмный приглушенный фон для невыбранного сервера
        self.c_unsel_fg = "#6b6478"       # Текст невыбранного сервера
        self.c_gold_bg = "#3f2e08"        # Золотой фон для скоростного ⚡ сервера
        self.c_gold_fg = "#fef08a"        # Золотой текст
        self.c_green = "#6ee7b7"          # Зелёный (онлайн)
        self.c_red = "#fca5a5"            # Красный (таймаут/ошибка)

        # Стили элементов TTK
        self.style.configure(".", background=self.c_bg, foreground=self.c_text)
        
        # Настройка Treeview (таблицы)
        self.style.configure(
            "Custom.Treeview",
            background=self.c_table_bg,
            foreground=self.c_text,
            fieldbackground=self.c_table_bg,
            rowheight=30,
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
            background=[("selected", "#442770")],
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
            text="Ручной отбор рабочих VLESS серверов и быстрая публикация на GitHub",
            font=("Segoe UI", 9),
            bg=self.c_bg,
            fg=self.c_muted
        )
        sub_lbl.pack(anchor="w")

        # Карточки статистики справа
        stats_box = tk.Frame(top_frame, bg=self.c_bg)
        stats_box.pack(side="right")

        self.card_total = self._create_stat_card(stats_box, "VLESS в источнике", "0")
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
            text="⚡ Проверить пинг (5 сайтов x2)",
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

        # 2.5. Панель авто-фильтров по пингу и ручного порядка
        filter_bar = tk.Frame(self.root, bg="#130f1c", padx=15, pady=6)
        filter_bar.configure(highlightbackground=self.c_card_border, highlightthickness=1)
        filter_bar.pack(fill="x", padx=15, pady=(0, 8))

        # Ползунок 1: Быстрые сервера (⚡ до X ms)
        lbl_fast = tk.Label(filter_bar, text="⚡ Быстрые (до ms):", font=("Segoe UI", 9, "bold"), bg="#130f1c", fg="#fef08a")
        lbl_fast.pack(side="left", padx=(0, 4))

        self.scale_fast = tk.Scale(
            filter_bar, from_=50, to=15000, resolution=50, orient="horizontal",
            bg="#130f1c", fg="#fef08a", highlightthickness=0, troughcolor="#2a1f47",
            length=160, font=("Segoe UI", 8)
        )
        self.scale_fast.set(350)
        self.scale_fast.pack(side="left", padx=(0, 14))

        # Ползунок 2: Медленные сервера (отсекать выше Y ms)
        lbl_slow = tk.Label(filter_bar, text="🚫 Отсекать (выше ms):", font=("Segoe UI", 9, "bold"), bg="#130f1c", fg="#fca5a5")
        lbl_slow.pack(side="left", padx=(0, 4))

        self.scale_slow = tk.Scale(
            filter_bar, from_=100, to=15000, resolution=100, orient="horizontal",
            bg="#130f1c", fg="#fca5a5", highlightthickness=0, troughcolor="#2a1f47",
            length=160, font=("Segoe UI", 8)
        )
        self.scale_slow.set(800)
        self.scale_slow.pack(side="left", padx=(0, 14))

        btn_apply_filters = tk.Button(
            filter_bar, text="⚙️ Применить фильтры к пингам", font=("Segoe UI", 8, "bold"),
            bg="#3b2b5e", fg="#ffffff", activebackground=self.c_primary, bd=0, padx=10, pady=4,
            cursor="hand2", command=self.action_apply_ping_filters
        )
        btn_apply_filters.pack(side="left", padx=(0, 16))

        # Кнопки перемещения строк вверх/вниз
        lbl_order = tk.Label(filter_bar, text="Порядок (⠿ перетаскивание):", font=("Segoe UI", 8), bg="#130f1c", fg=self.c_muted)
        lbl_order.pack(side="left", padx=(0, 4))

        btn_up = tk.Button(
            filter_bar, text="▲ Выше", font=("Segoe UI", 8, "bold"),
            bg="#221c30", fg="#c4b5fd", bd=0, padx=8, pady=3,
            cursor="hand2", command=self.action_move_row_up
        )
        btn_up.pack(side="left", padx=(0, 4))

        btn_down = tk.Button(
            filter_bar, text="▼ Ниже", font=("Segoe UI", 8, "bold"),
            bg="#221c30", fg="#c4b5fd", bd=0, padx=8, pady=3,
            cursor="hand2", command=self.action_move_row_down
        )
        btn_down.pack(side="left")

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

        # 3.5. Панель комментария к описанию подписки
        comment_bar = tk.Frame(self.root, bg=self.c_bg, padx=15, pady=0)
        comment_bar.pack(fill="x", pady=(0, 8))

        lbl_comment = tk.Label(
            comment_bar,
            text="💬 Комментарий в описание подписки (необязательно):",
            font=("Segoe UI", 9, "bold"),
            bg=self.c_bg,
            fg="#c4b5fd"
        )
        lbl_comment.pack(side="left", padx=(0, 8))

        self.comment_entry = tk.Entry(
            comment_bar,
            font=("Segoe UI", 9),
            bg="#1c1626",
            fg="#ffffff",
            insertbackground="#ffffff",
            bd=1,
            relief="solid",
            highlightthickness=0
        )
        self.comment_entry.pack(side="left", fill="x", expand=True, ipady=3)

        # 4. Основная таблица серверов
        table_frame = tk.Frame(self.root, bg=self.c_bg, padx=15)
        table_frame.pack(fill="both", expand=True)

        columns = ("drag", "id", "sel", "name", "country", "ping", "fast")
        self.tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            style="Custom.Treeview",
            selectmode="extended"
        )

        self.tree.heading("drag", text="⠿", anchor="center")
        self.tree.heading("id", text="# ID", anchor="center")
        self.tree.heading("sel", text="Статус выбора", anchor="center")
        self.tree.heading("name", text="Название сервера для ouvpn.txt", anchor="w")
        self.tree.heading("country", text="Страна", anchor="center")
        self.tree.heading("ping", text="Ср. пинг (5 сайтов x2)", anchor="center")
        self.tree.heading("fast", text="Скоростной", anchor="center")

        self.tree.column("drag", width=35, anchor="center")
        self.tree.column("id", width=65, anchor="center")
        self.tree.column("sel", width=120, anchor="center")
        self.tree.column("name", width=510, anchor="w")
        self.tree.column("country", width=90, anchor="center")
        self.tree.column("ping", width=175, anchor="center")
        self.tree.column("fast", width=95, anchor="center")

        # Настройка цветовых тегов подсветки строк
        # 1. Выбранные (фиолетовый фон)
        self.tree.tag_configure("selected", background=self.c_purple_bg, foreground=self.c_text)
        self.tree.tag_configure("selected_online", background=self.c_purple_bg, foreground=self.c_green)
        self.tree.tag_configure("selected_dead", background=self.c_purple_bg, foreground=self.c_red)

        # 2. Невыбранные (тёмно-серый приглушённый фон)
        self.tree.tag_configure("unselected", background=self.c_unsel_bg, foreground=self.c_unsel_fg)

        # 3. Скоростные (золотой фон)
        self.tree.tag_configure("gold", background=self.c_gold_bg, foreground=self.c_gold_fg)

        # Скроллбар
        v_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=v_scroll.set)

        self.tree.pack(side="left", fill="both", expand=True)
        v_scroll.pack(side="right", fill="y")

        # Переменная для перетаскивания строк (Drag-and-Drop)
        self._dragged_item = None

        # Привязка событий к таблице
        self.tree.bind("<ButtonPress-1>", self._on_tree_press)
        self.tree.bind("<B1-Motion>", self._on_tree_drag)
        self.tree.bind("<ButtonRelease-1>", self._on_tree_release)
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

        # Подсказка по цветам
        hint_lbl = tk.Label(
            bottom_frame,
            text="💡 1 клик = переключить выбор (фиолетовый). Двойной клик = золотой ⚡ скоростной.",
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

    # ----------------- Обработчики событий таблицы и Drag-and-Drop -----------------

    def _on_tree_press(self, event):
        """Обработка нажатия мыши: перетаскивание (⠿) или выбор строки."""
        item_id = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if col == "#1" and item_id:
            # Нажата колонка ⠿ — начинаем перетаскивание строки
            self._dragged_item = item_id
            return "break"
        else:
            self._dragged_item = None
            self._on_tree_click(event)

    def _on_tree_drag(self, event):
        """Перемещение зажатой строки и авто-прокрутка списка у границ окна."""
        if not self._dragged_item:
            return
        # Автопрокрутка вверх / вниз
        if event.y < 35:
            self.tree.yview_scroll(-1, "units")
        elif event.y > self.tree.winfo_height() - 35:
            self.tree.yview_scroll(1, "units")

        target = self.tree.identify_row(event.y)
        if target and target != self._dragged_item:
            target_idx = self.tree.index(target)
            self.tree.move(self._dragged_item, "", target_idx)

    def _on_tree_release(self, event):
        """Завершение перетаскивания: сохраняем новый порядок серверов в памяти."""
        if self._dragged_item:
            self._sync_servers_order_from_tree()
            self._dragged_item = None

    def _sync_servers_order_from_tree(self):
        """Синхронизирует массив self.servers с текущим порядком строк в Treeview."""
        new_order_ids = []
        for child in self.tree.get_children():
            try:
                sid = int(str(child))
                new_order_ids.append(sid)
            except Exception:
                pass

        server_map = {s.source_id: s for s in self.servers}
        reordered = [server_map[i] for i in new_order_ids if i in server_map]
        remaining = [s for s in self.servers if s.source_id not in new_order_ids]
        self.servers = reordered + remaining
        self.set_status("Порядок серверов изменён (⠿ перетаскивание).")

    def action_move_row_up(self):
        """Переместить выбранный сервер на одну позицию выше."""
        sel = self.tree.selection()
        if not sel:
            return
        item = sel[0]
        idx = self.tree.index(item)
        if idx > 0:
            self.tree.move(item, "", idx - 1)
            self._sync_servers_order_from_tree()
            self.tree.see(item)

    def action_move_row_down(self):
        """Переместить выбранный сервер на одну позицию ниже."""
        sel = self.tree.selection()
        if not sel:
            return
        item = sel[0]
        idx = self.tree.index(item)
        total = len(self.tree.get_children())
        if idx < total - 1:
            self.tree.move(item, "", idx + 1)
            self._sync_servers_order_from_tree()
            self.tree.see(item)

    def action_apply_ping_filters(self):
        """Автоматически помечает быстрые (⚡) и отсекает медленные сервера по ползункам."""
        if not self.scale_fast or not self.scale_slow:
            return
        max_fast = self.scale_fast.get()
        max_allowed = self.scale_slow.get()
        fast_count = 0
        selected_count = 0
        for s in self.servers:
            if s.ping_ms is not None:
                s.is_fast = (s.ping_ms <= max_fast)
                s.selected = (s.ping_ms <= max_allowed)
            else:
                s.is_fast = False
                s.selected = False
            if s.is_fast:
                fast_count += 1
            if s.selected:
                selected_count += 1
        self.populate_table()
        self.update_selected_count()
        self.set_status(f"Фильтры применены: выбрано {selected_count} раб. (до {max_allowed} ms), из них {fast_count} скоростных ⚡ (до {max_fast} ms).")

    def _on_tree_click(self, event):
        """
        Одиночный клик по строке:
        Переключает выбор сервера и делает фон фиолетовым / тёмным.
        """
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return

        if self._single_click_timer:
            self.root.after_cancel(self._single_click_timer)
            self._single_click_timer = None

        self._single_click_timer = self.root.after(220, lambda: self._handle_single_click(item_id))

    def _handle_single_click(self, item_id: str):
        self._single_click_timer = None
        srv = self._find_server_by_item_id(item_id)
        if srv:
            srv.selected = not srv.selected
            self._refresh_tree_row(item_id, srv)
            self.update_selected_count()

    def _on_tree_space(self, event):
        """Нажатие Пробела переключает выбор выделенных строк."""
        selected_items = self.tree.selection()
        if not selected_items:
            return
        for item_id in selected_items:
            srv = self._find_server_by_item_id(item_id)
            if srv:
                srv.selected = not srv.selected
                self._refresh_tree_row(item_id, srv)
        self.update_selected_count()
        return "break"

    def _on_tree_double_click(self, event):
        """
        Двойной клик переключает признак 'скоростной' (⚡)
        и выделяет строку золотым цветом.
        """
        if self._single_click_timer:
            self.root.after_cancel(self._single_click_timer)
            self._single_click_timer = None

        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return

        srv = self._find_server_by_item_id(item_id)
        if not srv:
            return

        srv.is_fast = not srv.is_fast
        self._refresh_tree_row(item_id, srv)
        return "break"

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
        sel_text = "  🟣 Выбран [✓]" if srv.selected else "  ⚪ Снят [ ]"
        fast_text = "⚡ Да" if srv.is_fast else "-"
        country_disp = "Обход" if srv.is_bypass else (srv.country_code or "??")
        
        ping_disp = srv.ping_status
        if srv.ping_ms is not None:
            ping_disp = f"⚡ {srv.ping_ms} ms"

        self.tree.item(
            item_id,
            values=(
                "⠿",
                f"#{srv.source_id}",
                sel_text,
                srv.get_display_name(),
                country_disp,
                ping_disp,
                fast_text
            )
        )

        # Выбираем визуальный тег
        if srv.is_fast:
            tag = "gold"
        elif srv.selected:
            if srv.ping_ms is not None:
                tag = "selected_online"
            elif srv.ping_status not in ("не проверен", ""):
                tag = "selected_dead"
            else:
                tag = "selected"
        else:
            tag = "unselected"

        self.tree.item(item_id, tags=(tag,))

    def populate_table(self):
        """Перерисовывает строки таблицы с актуальными фиолетовыми/темными/золотыми цветами."""
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
            sel_text = "  🟣 Выбран [✓]" if srv.selected else "  ⚪ Снят [ ]"
            fast_text = "⚡ Да" if srv.is_fast else "-"
            country_disp = "Обход" if srv.is_bypass else (srv.country_code or "??")
            
            ping_disp = srv.ping_status
            if srv.ping_ms is not None:
                ping_disp = f"⚡ {srv.ping_ms} ms"

            if srv.is_fast:
                tag = "gold"
            elif srv.selected:
                if srv.ping_ms is not None:
                    tag = "selected_online"
                elif srv.ping_status not in ("не проверен", ""):
                    tag = "selected_dead"
                else:
                    tag = "selected"
            else:
                tag = "unselected"

            self.tree.insert(
                "",
                "end",
                iid=item_id,
                values=(
                    "⠿",
                    f"#{srv.source_id}",
                    sel_text,
                    srv.get_display_name(),
                    country_disp,
                    ping_disp,
                    fast_text
                ),
                tags=(tag,)
            )

        self.update_selected_count()

    # ----------------- Кнопки и действия -----------------

    def action_fetch_servers(self):
        """Загрузка свежих серверов из источника (ТОЛЬКО VLESS)."""
        self.set_status("Загрузка VLESS конфигов из источника...")
        self.btn_fetch.configure(state="disabled")

        def worker():
            try:
                lines = core_engine.fetch_source_configs()
                meta = core_engine.parse_source_metadata(lines)
                servers = core_engine.parse_all_servers(lines)

                def on_done():
                    self.servers = servers
                    self.card_total.configure(text=str(len(servers)))
                    self.card_updated.configure(text=meta.get("source_update_time", "Недавно"))
                    self.populate_table()
                    self.set_status(f"Успешно загружено {len(servers)} VLESS серверов (все выбраны фиолетовым).")
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
                self.set_status(f"Проверка пинга (5 сервисов x2): {completed} из {total}...")
                for srv in self.servers:
                    iid = str(srv.source_id)
                    if self.tree.exists(iid):
                        self._refresh_tree_row(iid, srv)
            self.root.after(0, ui_update)

        def worker():
            try:
                core_engine.ensure_xray_binary(on_status=self.set_status)
                core_engine.test_servers_ping_xray(
                    self.servers,
                    on_progress=on_prog,
                    on_status=self.set_status,
                    timeout=8,
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
                    
                    # Применяем авто-фильтры по ползункам
                    self.action_apply_ping_filters()
                    selected_cnt = sum(1 for s in self.servers if s.selected)
                    self.set_status(f"Проверка завершена! Онлайн: {online_count}. Согласно ползункам отобрано {selected_cnt} серв.")

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
        """Выбирает только сервера с успешным пингом (фиолетовый фон)."""
        for s in self.servers:
            s.selected = (s.ping_ms is not None)
        self.populate_table()
        cnt = sum(1 for s in self.servers if s.selected)
        self.set_status(f"Выбрано {cnt} рабочих серверов (подсвечены фиолетовым).")

    def action_select_all(self):
        for s in self.servers:
            s.selected = True
        self.populate_table()
        self.set_status(f"Выбраны все сервера ({len(self.servers)} шт., фиолетовый фон).")

    def action_deselect_all(self):
        for s in self.servers:
            s.selected = False
        self.populate_table()
        self.set_status("Выбор снят со всех серверов.")

    def action_apply_numbers(self):
        """
        Выбирает сервера по номерам через запятую (напр: 1, 2, 5, 10-15).
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

        matched = 0
        for s in self.servers:
            if s.source_id in target_ids:
                s.selected = True
                matched += 1
            else:
                s.selected = False

        self.populate_table()
        self.set_status(f"Выбрано {matched} серверов (подсвечены фиолетовым).")

    def action_filter_table(self):
        """Фильтрация строк по поисковому запросу."""
        self.populate_table()

    def action_push_github(self):
        """Сохранение ouvpn.txt и отправка на GitHub."""
        selected = [s for s in self.servers if s.selected]
        if not selected:
            messagebox.showwarning("Ничего не выбрано", "Пожалуйста, выберите хотя бы один сервер (фиолетовый фон).")
            return

        confirm = messagebox.askyesno(
            "Подтверждение публикации",
            f"Будет сохранено и отправлено на GitHub серверов: {len(selected)} шт.\n\n"
            f"Категории в ouvpn.txt с заглушками 🇸🇴:\n"
            f"1. 🇸🇴 ОСНОВНЫЕ СЕРВЕРА (Европа и весь мир)\n"
            f"2. 🇸🇴 ЮТУБ БЕЗ РЕКЛАМЫ (Россия RU)\n"
            f"3. 🇸🇴 ОБХОД ДЛЯ БС (CIDR, LTE, SNI, EU)\n\n"
            f"После публикации все снятые сервера будут скрыты из панели,\n"
            f"останутся только эти {len(selected)} выбранных серверов.\n\n"
            f"Продолжить отправку на GitHub?"
        )
        if not confirm:
            return

        self.btn_push.configure(state="disabled")
        self.set_status("Формирование ouvpn.txt и отправка на GitHub...")
        user_comment = self.comment_entry.get().strip() if self.comment_entry else ""

        def worker():
            ok, msg = core_engine.save_and_push_servers(selected, on_status=self.set_status, comment=user_comment, preserve_order=True)

            def on_done():
                self.btn_push.configure(state="normal")
                self.set_status(msg)
                if ok:
                    # Оставляем в панели только опубликованные сервера
                    self.servers = [s for s in self.servers if s.selected]
                    self.populate_table()
                    self.card_total.configure(text=str(len(self.servers)))
                    messagebox.showinfo(
                        "Успешно!",
                        f"{msg}\n\nСнятые сервера скрыты! В панели оставлены только опубликованные ({len(self.servers)} шт.)."
                    )
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
