# Запуск на Railway + Vercel

## Что уже настроено

В аккаунте Railway созданы проект и сервис:

- Проект: `parser-cc`
- Сервис: `parser-cc-bot`
- Адрес сервера: `https://parser-cc-bot-production.up.railway.app`
- Постоянное хранилище (volume): `/data`

Токен бота храните только в Railway: не вставляйте его в файлы проекта, в Vercel и в переписку.

## Как всё устроено

- Railway запускает Telegram-бота, API и базу SQLite (папка проекта).
- База `parser.db` лежит на постоянном хранилище `/data` и не пропадает при обновлениях.
- Папка `vercel` — это сам Mini App. Файл `vercel/vercel.json` перенаправляет запросы `/api/*` на сервер Railway.

## Переменные в Railway

Откройте [проект в Railway](https://railway.com/project/1ed78ca8-84a5-41ea-804f-48387b8021d0) → сервис `parser-cc-bot` → вкладка **Variables**.

Обязательные:

- `BOT_TOKEN` — токен от BotFather.
- `CONTACT_EMAIL` — ваша почта для связи (передаётся сервису карт OpenStreetMap, так требуют его правила).
- `DB_PATH` — уже стоит `/data/parser.db`.
- `DEFAULT_LIMIT` — уже стоит `70` (дневной лимит участника).
- `WEBAPP_URL` — уже стоит `https://parser-cc-miniapp.vercel.app`.
- `ADMIN_IDS` — ваш числовой Telegram ID (см. ниже).

Бесплатные ключи (рекомендуется, карта не нужна):

- `GEOAPIFY_API_KEY` — запасной источник, когда основной сервер карт перегружен. Ключ: [myprojects.geoapify.com](https://myprojects.geoapify.com).
- `GEMINI_API_KEY` — нейросеть для скриптов. Ключ: [aistudio.google.com/apikey](https://aistudio.google.com/apikey) → **Create API key**. Без ключа скрипты собираются из шаблонов.

Пробный доступ уже настроен значениями по умолчанию, менять не обязательно: `TRIAL_SEARCHES=1`, `TRIAL_LEADS=10`, `JOIN_URL=https://t.me/m/KXcCg7quZGFh`, `CONTACT_USERNAME=SUN9ISE`.

Переменную `PORT` Railway задаёт сам.

## Загрузка сервера (Railway)

В PowerShell:

```powershell
cd C:\Users\MakeMyCry\Desktop\parser_cc
railway up
```

Сервис должен работать в **одном** экземпляре (replica = 1): бот может быть запущен только один, а хранилище Railway не работает с несколькими копиями.

## Загрузка Mini App (Vercel)

В PowerShell:

```powershell
cd C:\Users\MakeMyCry\Desktop\parser_cc\vercel
vercel --prod
```

Адрес Mini App: `https://parser-cc-miniapp.vercel.app` — он уже записан в `WEBAPP_URL`. Если поменяете домен, обновите эту переменную в Railway и перезапустите сервис.

## Настройка владельца

1. Когда сервер запустился, отправьте боту `/id` и скопируйте числовой ID.
2. В Railway впишите его в `ADMIN_IDS` (только один ID) и нажмите Redeploy.
3. Отправьте боту `/start` и откройте Mini App — появится вкладка «Админ».
4. Проверка: `https://parser-cc-bot-production.up.railway.app/healthz` должен показать `{"status":"ok"}`.

## Обновления

- Изменили сервер → `railway up` в папке `parser_cc`.
- Изменили Mini App → `vercel --prod` в папке `parser_cc\vercel`.

Не удаляйте хранилище `/data` — в нём пользователи, лиды, лимиты и ключи. При обновлении все данные переносятся автоматически.
