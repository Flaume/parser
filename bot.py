import asyncio
import html
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    BotCommandScopeChat,
    BotCommandScopeDefault,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)

import db
from config import (
    ADMIN_IDS,
    BOT_TOKEN,
    CONTACT_USERNAME,
    JOIN_URL,
    TRIAL_LEADS,
    TRIAL_SEARCHES,
    WEBAPP_URL,
)
from export import send_export

bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
log = logging.getLogger("parser_cc.bot")


def app_keyboard() -> InlineKeyboardMarkup:
    if not WEBAPP_URL:
        raise RuntimeError("Сначала укажите WEBAPP_URL в файле .env.")
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Открыть Parser C&C",
                    web_app=WebAppInfo(url=WEBAPP_URL),
                )
            ]
        ]
    )


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


TRIAL_OVER = (
    "Пробный доступ закончился.\n"
    "Вы использовали пробный запрос и нашли {found} лидов.\n"
    "Чтобы продолжить получать лиды и пользоваться Parser C&C, вступите в команду C&C Family,\n"
    "подробности можно узнать у @{contact}."
)


def trial_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Вступить в команду", url=JOIN_URL)],
            [InlineKeyboardButton(text="Докупить запросы", url=f"https://t.me/{CONTACT_USERNAME}")],
            [InlineKeyboardButton(text="У меня есть ключ", callback_data="key_help")],
        ]
    )


async def send_trial_over(user_id: int, found: int = TRIAL_LEADS) -> None:
    await bot.send_message(
        user_id,
        html.escape(TRIAL_OVER.format(found=found, contact=CONTACT_USERNAME)),
        reply_markup=trial_keyboard(),
    )


async def _active_user(message: Message) -> dict | None:
    """Пользователь бота или None, если он заблокирован (ему уже отправлен ответ)."""
    user = message.from_user
    row = await db.upsert_user(user.id, user.username, user.first_name)
    if row.get("banned") and not is_admin(user.id):
        await message.answer(f"Доступ к Parser C&C закрыт. Если это ошибка, напишите @{CONTACT_USERNAME}.")
        return None
    return row


def _access_line(row: dict) -> str:
    if db.is_member(row):
        return f"Полный доступ: {row['daily_limit']} лидов в день."
    left = db.trial_left(row, TRIAL_SEARCHES)
    if left > 0:
        return f"Пробный доступ: осталось запросов — {left}, до {TRIAL_LEADS} лидов в каждом."
    return "Пробный доступ закончился. Подробности — в кнопках ниже."


@dp.message(CommandStart())
async def start(message: Message) -> None:
    row = await _active_user(message)
    if not row:
        return
    user = message.from_user
    await message.answer(
        f"Привет, {html.escape(user.first_name or 'друг')}!\n"
        "Parser C&C находит бизнесы, которым может быть нужен сайт или Telegram-бот, "
        "и даёт их проверенные контакты.\n\n"
        + _access_line(row) + "\n\n"
        "/app — открыть приложение\n"
        "/export — выгрузить лиды в Excel\n"
        "/stats — статистика\n"
        "/key КОД — активировать ключ доступа",
        reply_markup=app_keyboard() if WEBAPP_URL else None,
    )
    if not db.is_member(row) and db.trial_left(row, TRIAL_SEARCHES) <= 0:
        await send_trial_over(user.id)


@dp.message(Command("app"))
async def app_command(message: Message) -> None:
    if not await _active_user(message):
        return
    if not WEBAPP_URL:
        await message.answer(
            "Mini App ещё не привязан. Заполните WEBAPP_URL в файле .env и перезапустите бота."
        )
        return
    await message.answer("Откройте приложение:", reply_markup=app_keyboard())


@dp.message(Command("export"))
async def export_command(message: Message) -> None:
    if not await _active_user(message):
        return
    await message.answer("Готовлю Excel-файл…")
    try:
        await send_export(message.from_user.id)
    except Exception:
        log.exception("Excel export failed for user %s", message.from_user.id)
        await message.answer("Не удалось подготовить файл. Попробуйте ещё раз позже.")


@dp.message(Command("stats"))
async def stats_command(message: Message) -> None:
    row = await _active_user(message)
    if not row:
        return
    stats = await db.stats(message.from_user.id)
    used = await db.used_today(message.from_user.id)
    conversion = round(stats["clients"] / stats["found"] * 100) if stats["found"] else 0
    lines = [
        "<b>Ваша статистика</b>",
        f"Найдено: {stats['found']}",
        f"Связались: {stats['contacted']}",
        f"Ответили: {stats['replied']}",
        f"Клиенты: {stats['clients']} ({conversion}%)",
    ]
    if db.is_member(row):
        lines.append(f"Сегодня использовано: {used}/{row['daily_limit']}")
    else:
        lines.append(_access_line(row))
    await message.answer("\n".join(lines))


KEY_ERRORS = {
    "not_found": "Ключ не найден. Проверьте, что он введён без ошибок.",
    "used": "Этот ключ уже использован.",
    "other_user": "Этот ключ выдан другому пользователю.",
    "banned": "Доступ закрыт администратором.",
}


@dp.message(Command("key"))
async def key_command(message: Message) -> None:
    if not await _active_user(message):
        return
    parts = (message.text or "").split()
    if len(parts) != 2:
        await message.answer("Отправьте ключ так: <code>/key CC-XXXX-XXXX-XXXX</code>")
        return
    result, key = await db.redeem_key(message.from_user.id, message.from_user.username, parts[1])
    if result != "ok":
        await message.answer(KEY_ERRORS[result])
        return
    gained = []
    if key["daily_limit"] > 0:
        gained.append(f"полный доступ, {key['daily_limit']} лидов в день")
    if key["bonus"] > 0:
        gained.append(f"+{key['bonus']} поисковых запросов")
    await message.answer(
        "Ключ активирован: " + ", ".join(gained) + ".",
        reply_markup=app_keyboard() if WEBAPP_URL else None,
    )


@dp.callback_query(F.data == "key_help")
async def key_help(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(
        "Если администратор выдал вам ключ, отправьте его так:\n<code>/key CC-XXXX-XXXX-XXXX</code>"
    )


async def _target(message: Message, raw: str) -> dict | None:
    target = await db.find_user(raw)
    if not target:
        await message.answer(
            "Пользователь не найден. Он должен хотя бы раз нажать /start, "
            "или используйте числовой Telegram ID."
        )
    return target


@dp.message(Command("adduser"))
async def add_user(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) not in (2, 3) or (len(parts) == 3 and not parts[2].isdigit()):
        await message.answer("Формат: <code>/adduser 123456789</code> или <code>/adduser @username 100</code>")
        return
    limit = int(parts[2]) if len(parts) == 3 else None
    if parts[1].isdigit():
        user_id = int(parts[1])
    else:
        target = await _target(message, parts[1])
        if not target:
            return
        user_id = target["id"]
    await db.grant_member(user_id, limit)
    await message.answer(f"Полный доступ выдан: <code>{user_id}</code>")
    try:
        await bot.send_message(
            user_id,
            "Полный доступ к Parser C&C открыт. Добро пожаловать в C&C Family!",
            reply_markup=app_keyboard() if WEBAPP_URL else None,
        )
    except TelegramAPIError:
        await message.answer(
            "Пользователь ещё не писал боту — бот пока не может отправить ему сообщение."
        )


@dp.message(Command("deluser"))
async def delete_user(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Формат: <code>/deluser 123456789</code>")
        return
    user_id = int(parts[1])
    if user_id in ADMIN_IDS:
        await message.answer("Владелец не может закрыть сам себе доступ этой командой.")
        return
    await db.set_approved(user_id, 0)
    await message.answer("Полный доступ закрыт (пользователь вернулся на пробный режим).")
    try:
        await bot.send_message(user_id, "Полный доступ к Parser C&C закрыт.")
    except TelegramAPIError:
        pass


@dp.message(Command("limit"))
async def set_user_limit(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split()
    if (
        len(parts) != 3
        or not parts[1].isdigit()
        or not parts[2].isdigit()
        or int(parts[2]) > 5000
    ):
        await message.answer("Формат: <code>/limit 123456789 100</code>")
        return
    user_id, limit = int(parts[1]), int(parts[2])
    if not await db.set_limit(user_id, limit):
        await message.answer("Пользователь не найден.")
        return
    await message.answer(f"Лимит <code>{user_id}</code>: {limit}/день")
    try:
        await bot.send_message(user_id, f"Ваш дневной лимит изменён: {limit} запросов.")
    except TelegramAPIError:
        pass


@dp.message(Command("users"))
async def users_command(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    rows = await db.all_users_stats()
    def mark(row):
        if row["banned"]:
            return "🚫"
        return "✅" if row["approved"] or row["is_admin"] else "🆓"

    lines = [
        f"{mark(row)} <code>{row['id']}</code> "
        f"@{html.escape(row['username'] or '—')} · "
        + (
            f"{row['today']}/{row['daily_limit']}"
            if row["approved"] or row["is_admin"]
            else f"проба {row['trial_used']}/{TRIAL_SEARCHES + row['bonus']}"
        )
        + f" · лидов {row['found']} · клиентов {row['clients']}"
        for row in rows[:50]
    ]
    await message.answer("<b>Пользователи</b>\n" + ("\n".join(lines) or "Пока пусто."))


@dp.message(Command("ban", "unban"))
async def ban_command(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split()
    banned = parts[0].lstrip("/").split("@")[0] == "ban"
    if len(parts) != 2:
        await message.answer("Формат: <code>/ban @username</code> или <code>/unban 123456789</code>")
        return
    target = await _target(message, parts[1])
    if not target:
        return
    if target["id"] in ADMIN_IDS:
        await message.answer("Владельца заблокировать нельзя.")
        return
    await db.set_banned(target["id"], banned)
    await message.answer("Заблокирован." if banned else "Разблокирован.")


@dp.message(Command("bonus"))
async def bonus_command(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split()
    if len(parts) != 3 or not parts[2].lstrip("-").isdigit():
        await message.answer("Формат: <code>/bonus @username 5</code> — добавить 5 поисковых запросов")
        return
    target = await _target(message, parts[1])
    if not target:
        return
    total = await db.add_bonus(target["id"], int(parts[2]))
    await message.answer(f"Готово. Бонусных запросов всего: {total}.")
    if int(parts[2]) > 0:
        try:
            await bot.send_message(target["id"], f"Вам добавлено поисковых запросов: {parts[2]}.")
        except TelegramAPIError:
            pass


@dp.message(Command("newkey"))
async def newkey_command(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    import secrets

    parts = (message.text or "").split()[1:]
    # /newkey · /newkey 100 · /newkey @username · /newkey @username 100 · /newkey id123456 100
    for_user = ""
    if parts and not parts[0].isdigit():
        for_user = parts.pop(0)
        if for_user.lower().startswith("id") and for_user[2:].isdigit():
            for_user = for_user[2:]
    if parts and not parts[0].isdigit():
        await message.answer("Формат: <code>/newkey @username 100</code> (лимит лидов в день)")
        return
    limit = int(parts[0]) if parts else 70
    code = "CC-" + "-".join(secrets.token_hex(2).upper() for _ in range(3))
    await db.create_key(code, for_user, min(limit, 5000), 0, 1)
    await message.answer(
        f"Ключ: <code>{code}</code>\n"
        + (f"Только для: {html.escape(for_user)}\n" if for_user else "Для любого пользователя, 1 активация\n")
        + f"Лимит: {limit} лидов в день.\nПользователь вводит: <code>/key {code}</code>"
    )


@dp.message(Command("broadcast"))
async def broadcast(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    text = (message.text or "").partition(" ")[2].strip()
    if not text:
        await message.answer("Формат: <code>/broadcast текст сообщения</code>")
        return
    sent, total = await broadcast_to_approved(text)
    await message.answer(f"Отправлено: {sent}/{total}")


async def broadcast_to_approved(text: str) -> tuple[int, int]:
    ids = await db.approved_ids()
    sent = 0
    safe_text = html.escape(text.strip())
    for user_id in ids:
        try:
            await bot.send_message(user_id, safe_text)
            sent += 1
        except TelegramAPIError:
            log.info("Broadcast failed for user %s", user_id)
        await asyncio.sleep(0.05)
    return sent, len(ids)


@dp.message(Command("id"))
async def id_command(message: Message) -> None:
    await message.answer(f"Ваш Telegram ID: <code>{message.from_user.id}</code>")


@dp.message(F.text)
async def fallback(message: Message) -> None:
    if not await _active_user(message):
        return
    await message.answer(
        "Используйте /app, /export, /stats или /key.",
        reply_markup=app_keyboard() if WEBAPP_URL else None,
    )


async def run_bot() -> None:
    public_commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="app", description="Открыть Mini App"),
        BotCommand(command="stats", description="Моя статистика"),
        BotCommand(command="export", description="Скачать лиды в Excel"),
        BotCommand(command="key", description="Активировать ключ доступа"),
        BotCommand(command="id", description="Показать мой Telegram ID"),
    ]
    admin_commands = public_commands + [
        BotCommand(command="adduser", description="Выдать полный доступ (ID или @username)"),
        BotCommand(command="deluser", description="Закрыть полный доступ"),
        BotCommand(command="limit", description="Изменить дневной лимит"),
        BotCommand(command="bonus", description="Добавить поисковые запросы"),
        BotCommand(command="newkey", description="Создать ключ доступа"),
        BotCommand(command="ban", description="Заблокировать пользователя"),
        BotCommand(command="unban", description="Разблокировать пользователя"),
        BotCommand(command="users", description="Список пользователей"),
        BotCommand(command="broadcast", description="Рассылка пользователям"),
    ]
    try:
        await bot.set_my_commands(public_commands, scope=BotCommandScopeDefault())
        for admin_id in ADMIN_IDS:
            await bot.set_my_commands(
                admin_commands,
                scope=BotCommandScopeChat(chat_id=admin_id),
            )
    except TelegramAPIError:
        log.exception("Could not set bot command menus")

    if WEBAPP_URL:
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Parser C&C", web_app=WebAppInfo(url=WEBAPP_URL)
                )
            )
        except TelegramAPIError:
            log.exception("Could not set the Telegram Web App menu button")
    else:
        log.warning("WEBAPP_URL пустой: кнопка Mini App не будет установлена")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
