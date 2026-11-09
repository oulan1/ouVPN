<div align="center">
  <h1>🛡️ ouVPN</h1>
  <p><b>Быстрый, бесплатный и надежный VPN от Telegram-канала <a href="https://t.me/oulanGift">@oulanGift</a></b></p>

  <p>
    <a href="https://t.me/oulanGift">
      <img src="https://img.shields.io/badge/Telegram-Присоединиться-blue?style=for-the-badge&logo=telegram" alt="Telegram Channel">
    </a>
  </p>
  
  <p>
    <a href="https://github.com/oulan1/ouVPN/actions/workflows/update.yml">
      <img src="https://github.com/oulan1/ouVPN/actions/workflows/update.yml/badge.svg" alt="Update Status">
    </a>
    <a href="https://github.com/oulan1/ouVPN/stargazers">
      <img src="https://img.shields.io/github/stars/oulan1/ouVPN?style=flat-square&color=yellow&logo=github" alt="GitHub Stars">
    </a>
    <a href="https://github.com/oulan1/ouVPN/commits/main">
      <img src="https://img.shields.io/github/last-commit/oulan1/ouVPN?style=flat-square&color=green&logo=github" alt="Last Commit">
    </a>
  </p>
</div>

---

## 📖 О проекте

**ouVPN** — это проект, предоставляющий открытый доступ к надежным и быстрым VPN-серверам со всего мира. Серверы автоматически синхронизируются и обновляются **каждый час** через GitHub Actions.

Все новости, анонсы и свежие события публикуются в нашем официальном Telegram-канале **[@oulanGift](https://t.me/oulanGift)**.

## ✨ Ключевые особенности

- ⚡ **Автообновление каждый час** — актуальные рабочие серверы благодаря GitHub Actions.
- 🛡️ **Специальные сервера обхода** — оптимизированные серверы для стабильной связи на всех операторах связи (`🇪🇺 Обход №...`).
- 🌍 **Множество локаций** — серверы Европы, Америки, Азии и стран СНГ с единым удобным наименованием.
- 💸 **Абсолютно бесплатно** — никаких ограничений и платных подписок.
- ⚙️ **Гибкая шапка подписки** — файл `heading.txt` позволяет настроить формат шапки и анонсов под свои задачи.

## 📂 Структура репозитория

* 🌍 [`ouvpn.txt`](./ouvpn.txt) — актуальный файл подписки с рабочими серверами (обновляется каждый час).
* 📝 [`heading.txt`](./heading.txt) — шаблон шапки подписки с поддержкой динамических переменных (`{date}`, `{time}`, `{count}`, `{interval}`).
* 🐍 [`update_configs.py`](./update_configs.py) — скрипт парсинга, фильтрации и автоматического форматирования серверов.
* ⚙️ [`.github/workflows/update.yml`](./.github/workflows/update.yml) — автоматизация GitHub Actions, запускающая обновление ежечасно.
* 🌐 [`index.html`](./index.html) — стартовая страница подключения для пользователей ([сайт](https://oulan1.github.io/ouVPN/)).

---

## 🚀 Как подключиться

Для использования наших серверов рекомендуется приложение **Happ**:

### Способ 1: Автоматическое добавление (в 1 клик)
1. Установите [Happ](https://www.happ.su/main/ru).
2. Перейдите на сайт **[oulan1.github.io/ouVPN](https://oulan1.github.io/ouVPN/)** и нажмите **«Добавить подписку»** (или откройте ссылку: `happ://add/https://raw.githubusercontent.com/oulan1/ouVPN/refs/heads/main/ouvpn.txt`).
3. Подписка загрузится сама и будет обновляться автоматически!

### Способ 2: Вручную через ссылку на подписку
1. Скопируйте ссылку на подписку:
   ```text
   https://raw.githubusercontent.com/oulan1/ouVPN/refs/heads/main/ouvpn.txt
   ```
2. В приложении **Happ** нажмите «+» / «Добавить подписку» и вставьте скопированную ссылку.
3. Выберите нужный сервер (например `NL 🇳🇱 ouVPN V2` или `🇪🇺 Обход №1`) и нажмите подключиться.

---

## 🛠️ Настройка шапки подписки (`heading.txt`)

Вы можете в любой момент изменить текст шапки прямо в файле `heading.txt`. Скрипт поддерживает следующие переменные:
- `{count}` — текущее количество серверов
- `{interval}` — интервал обновления (1 час)
- `{date}` — дата по МСК (ГГГГ-ММ-ДД)
- `{time}` или `{hh:mm}` — время по МСК (ЧЧ:ММ)
- `{announce}` / свой текст в строке `# announce:`

---

## 📢 Наше сообщество

Чтобы быть в курсе всех новостей и первыми получать обновления:

👉 **[Подписаться на @oulanGift](https://t.me/oulanGift)**

---

<div align="center">
  <i>Сделано с ❤️ командой <a href="https://t.me/oulanGift">@oulanGift</a></i>
</div>
