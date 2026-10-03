import asyncio
import html
import re
import logging
from pathlib import Path

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
    BufferedInputFile,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonWebApp,
    Message,
    WebAppInfo,
)

import db
from config import (
    ADMIN_IDS,
    is_admin_user,
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


def is_admin(user_id: int, username: str | None = None) -> bool:
    return is_admin_user(user_id, username)


def _num(value: str, signed: bool = False) -> int | None:
    """Число из аргумента команды или None (защита от «--5», «²» и т.п.)."""
    if re.fullmatch(r"-?\d{1,9}" if signed else r"\d{1,9}", value or ""):
        return int(value)
    return None


def _lead_word(n: int) -> str:
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return "лид"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "лида"
    return "лидов"


TRIAL_OVER = (
    "<b>Пробный доступ закончился</b>\n\n"
    "Вы использовали пробный запрос и нашли <b>{found} {word}</b>.\n\n"
    "Чтобы продолжить получать лиды и пользоваться Parser C&amp;C, вступите в команду "
    "<b>C&amp;C Family</b> — подробности можно узнать у @{contact}."
)


def trial_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Вступить в команду", url=JOIN_URL)],
            [InlineKeyboardButton(text="Докупить запросы", url=f"https://t.me/{CONTACT_USERNAME}")],
            [InlineKeyboardButton(text="У меня есть ключ", callback_data="key_help")],
        ]
    )


ASSETS = Path(__file__).with_name("assets")
IMAGES = {"closed": ASSETS / "access_closed.jpg", "open": ASSETS / "access_open.jpg"}
_file_ids: dict[str, str] = {}  # после первой загрузки Telegram отдаёт file_id — шлём его

BANNED_TEXT = f"<b>Вы забанены</b>, свяжитесь с @{CONTACT_USERNAME}\n\nЧтобы узнать причину."
ACCESS_CLOSED_TEXT = (
    "<b>Полный доступ к Parser C&amp;C закрыт</b>\n\n"
    f"Подробности можно узнать у @{CONTACT_USERNAME}."
)


def access_open_text(limit: int | None = None, bonus: int = 0, by_key: bool = False) -> str:
    title = "Ключ активирован" if by_key else "Полный доступ к Parser C&amp;C открыт"
    parts = [f"<b>{title}</b>", "Добро пожаловать в <b>C&amp;C Family</b>!"]
    gained = []
    if limit:
        gained.append(f"<b>{limit} {_lead_word(limit)} в день</b>")
    if bonus:
        gained.append(f"<b>+{bonus}</b> поисковых запросов")
    if gained:
        parts.append("Вам доступно: " + ", ".join(gained) + ".")
    parts.append("Откройте приложение и начинайте искать клиентов 👇" if WEBAPP_URL else "Откройте приложение и начинайте искать клиентов.")
    return "\n\n".join(parts)


# Совместимость со старым кодом
ACCESS_OPEN_TEXT = access_open_text()


async def send_picture(user_id: int, kind: str, text: str, reply_markup=None) -> None:
    """Картинка CLOSE/OPEN вместе с текстом. Если картинки нет — просто текст."""
    path = IMAGES.get(kind)
    if not path or not path.exists():
        await bot.send_message(user_id, text, reply_markup=reply_markup)
        return
    cached = _file_ids.get(kind)
    try:
        sent = await bot.send_photo(user_id, cached or FSInputFile(path), caption=text, reply_markup=reply_markup)
    except TelegramAPIError as exc:
        if "blocked" in str(exc).lower() or "chat not found" in str(exc).lower():
            raise
        log.warning("Photo %s failed (%s), retrying", kind, exc)
        _file_ids.pop(kind, None)
        try:
            # старый file_id мог устареть — отправляем файл заново
            sent = await bot.send_photo(user_id, FSInputFile(path), caption=text, reply_markup=reply_markup)
        except TelegramAPIError:
            # картинка не ушла — текст всё равно должен дойти
            await bot.send_message(user_id, text, reply_markup=reply_markup)
            return
    if getattr(sent, "photo", None):
        _file_ids[kind] = sent.photo[-1].file_id


async def send_trial_over(user_id: int, found: int = TRIAL_LEADS) -> None:
    await send_picture(
        user_id, "closed",
        TRIAL_OVER.format(found=found, word=_lead_word(found), contact=CONTACT_USERNAME),
        reply_markup=trial_keyboard(),
    )


async def send_access_opened(user_id: int, limit: int | None = None, bonus: int = 0, by_key: bool = False) -> None:
    if limit is None:
        row = await db.get_user(user_id)
        limit = row["daily_limit"] if row else None
    await send_picture(
        user_id, "open", access_open_text(limit, bonus, by_key),
        reply_markup=app_keyboard() if WEBAPP_URL else None,
    )


async def send_access_closed(user_id: int) -> None:
    await send_picture(user_id, "closed", ACCESS_CLOSED_TEXT, reply_markup=trial_keyboard())


async def deny_admin(message: Message) -> None:
    """Не‑админ вызвал админ‑команду: объясняем, а не молчим."""
    await message.answer(
        "<b>Эта команда только для администратора</b>\n\n"
        f"Ваш Telegram ID: <code>{message.from_user.id}</code>\n"
        "Если вы владелец — впишите этот ID (или свой @username) в переменную "
        "<code>ADMIN_IDS</code> в Railway и нажмите Redeploy."
    )


async def _active_user(message: Message) -> dict | None:
    """Пользователь бота или None, если он заблокирован (ему уже отправлен ответ)."""
    user = message.from_user
    row = await db.upsert_user(user.id, user.username, user.first_name)
    if row.get("banned") and not is_admin(user.id, user.username):
        await send_picture(user.id, "closed", BANNED_TEXT)
        return None
    return row


def _access_line(row: dict) -> str:
    if db.is_member(row):
        return f"<b>Ваш доступ:</b> полный, {row['daily_limit']} {_lead_word(row['daily_limit'])} в день."
    left = db.trial_left(row, TRIAL_SEARCHES)
    if left > 0:
        return f"<b>Ваш доступ:</b> пробный — {left} запрос, до {TRIAL_LEADS} лидов."
    return "<b>Ваш доступ:</b> пробный доступ закончился."


@dp.message(CommandStart())
async def start(message: Message) -> None:
    row = await _active_user(message)
    if not row:
        return
    user = message.from_user
    await db.mark_bot_started(user.id)
    admin = is_admin(user.id, user.username)
    if admin:
        await _set_admin_menu(user.id)
    await message.answer(
        f"<b>Привет, {html.escape(user.first_name or 'друг')}!</b>\n\n"
        "Parser C&amp;C находит бизнесы, которым может быть нужен сайт или Telegram-бот, "
        "и даёт их контакты.\n\n"
        + ("<b>Вы администратор.</b> Админ-панель — в приложении, вкладка «Админ»." if admin else _access_line(row)) + "\n\n"
        "<b>Команды</b>\n"
        "/app — открыть приложение\n"
        "/export — выгрузить лиды в Excel\n"
        "/stats — ваша статистика\n"
        "/key КОД — активировать ключ доступа",
        reply_markup=app_keyboard() if WEBAPP_URL else None,
    )
    if not db.is_member(row) and db.trial_left(row, TRIAL_SEARCHES) <= 0:
        await send_trial_over(user.id, (await db.stats(user.id)).get("found", 0))


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
        "",
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
    await send_access_opened(
        message.from_user.id, limit=key["daily_limit"] or None, bonus=key["bonus"], by_key=True
    )


@dp.callback_query(F.data == "key_help")
async def key_help(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(
        "<b>Как активировать ключ</b>\n\n"
        "Отправьте его боту так:\n<code>/key CC-XXXX-XXXX-XXXX</code>\n\n"
        "Или введите ключ в приложении на главной странице."
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
    if not is_admin(message.from_user.id, message.from_user.username):
        await deny_admin(message)
        return
    parts = (message.text or "").split()
    if len(parts) not in (2, 3) or (len(parts) == 3 and not (_num(parts[2]) is not None)):
        await message.answer("Формат: <code>/adduser 123456789</code> или <code>/adduser @username 100</code>")
        return
    limit = min(int(parts[2]), 5000) if len(parts) == 3 else None
    if (_num(parts[1]) is not None):
        user_id = int(parts[1])
    else:
        target = await _target(message, parts[1])
        if not target:
            return
        user_id = target["id"]
    await db.grant_member(user_id, limit)
    await message.answer(f"Полный доступ выдан: <code>{user_id}</code>")
    try:
        await send_access_opened(user_id, limit=limit)
    except TelegramAPIError:
        await message.answer(
            "Пользователь ещё не писал боту — бот пока не может отправить ему сообщение."
        )


@dp.message(Command("deluser"))
async def delete_user(message: Message) -> None:
    if not is_admin(message.from_user.id, message.from_user.username):
        await deny_admin(message)
        return
    parts = (message.text or "").split()
    if len(parts) != 2 or not (_num(parts[1]) is not None):
        await message.answer("Формат: <code>/deluser 123456789</code>")
        return
    user_id = int(parts[1])
    if user_id in ADMIN_IDS:
        await message.answer("Владелец не может закрыть сам себе доступ этой командой.")
        return
    await db.set_approved(user_id, 0)
    await message.answer("Полный доступ закрыт (пользователь вернулся на пробный режим).")
    try:
        await send_access_closed(user_id)
    except TelegramAPIError:
        pass


@dp.message(Command("limit"))
async def set_user_limit(message: Message) -> None:
    if not is_admin(message.from_user.id, message.from_user.username):
        await deny_admin(message)
        return
    parts = (message.text or "").split()
    if (
        len(parts) != 3
        or not (_num(parts[1]) is not None)
        or not (_num(parts[2]) is not None)
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
        await bot.send_message(
            user_id, f"<b>Лимит изменён</b>\n\nТеперь вам доступно <b>{limit} {_lead_word(limit)} в день</b>."
        )
    except TelegramAPIError:
        pass


@dp.message(Command("users"))
async def users_command(message: Message) -> None:
    if not is_admin(message.from_user.id, message.from_user.username):
        await deny_admin(message)
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
    if not is_admin(message.from_user.id, message.from_user.username):
        await deny_admin(message)
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
    if not is_admin(message.from_user.id, message.from_user.username):
        await deny_admin(message)
        return
    parts = (message.text or "").split()
    amount = _num(parts[2], signed=True) if len(parts) == 3 else None
    if amount is None or abs(amount) > 1000:
        await message.answer("Формат: <code>/bonus @username 5</code> — добавить 5 поисковых запросов")
        return
    target = await _target(message, parts[1])
    if not target:
        return
    total = await db.add_bonus(target["id"], amount)
    await message.answer(f"Готово. Бонусных запросов всего: {total}.")
    if amount > 0:
        try:
            await bot.send_message(
                target["id"], f"<b>Добавлены запросы</b>\n\nВам добавлено поисковых запросов: <b>{amount}</b>."
            )
        except TelegramAPIError:
            pass


@dp.message(Command("newkey"))
async def newkey_command(message: Message) -> None:
    if not is_admin(message.from_user.id, message.from_user.username):
        await deny_admin(message)
        return
    import secrets

    parts = (message.text or "").split()[1:]
    # /newkey · /newkey 100 · /newkey @username · /newkey @username 100 · /newkey id123456 100
    for_user = ""
    if parts and _num(parts[0]) is None:
        for_user = parts.pop(0)
        if for_user.lower().startswith("id") and _num(for_user[2:]) is not None:
            for_user = for_user[2:]
    limit = _num(parts[0]) if parts else 70
    if limit is None or not 1 <= limit <= 5000:
        await message.answer("Формат: <code>/newkey @username 100</code> — лимит лидов в день от 1 до 5000")
        return
    code = "CC-" + "-".join(secrets.token_hex(2).upper() for _ in range(3))
    await db.create_key(code, for_user, limit, 0, 1)
    await message.answer(
        f"Ключ: <code>{code}</code>\n"
        + (f"Только для: {html.escape(for_user)}\n" if for_user else "Для любого пользователя, 1 активация\n")
        + f"Лимит: {limit} лидов в день.\nПользователь вводит: <code>/key {code}</code>"
    )


@dp.message(Command("broadcast"))
async def broadcast(message: Message) -> None:
    if not is_admin(message.from_user.id, message.from_user.username):
        await deny_admin(message)
        return
    text = (message.text or "").partition(" ")[2].strip()
    if not text:
        await message.answer("Формат: <code>/broadcast текст сообщения</code>")
        return
    sent, total = await broadcast_to_approved(html.escape(text))
    await message.answer(f"Отправлено: {sent}/{total}")


CAPTION_LIMIT = 1024


def _plain_len(text: str) -> int:
    import re

    return len(html.unescape(re.sub(r"<[^>]+>", "", text)))


async def broadcast_to_approved(text: str, image: bytes | None = None) -> tuple[int, int]:
    """Рассылка всем незаблокированным. text — уже безопасный HTML (теги Telegram).
    Картинка уходит с подписью; длинный текст (больше 1024 символов) — отдельным сообщением."""
    ids = await db.approved_ids()
    sent = 0
    text = (text or "").strip()
    photo_id = None
    caption_fits = image is not None and _plain_len(text) <= CAPTION_LIMIT
    for user_id in ids:
        try:
            if image is not None:
                photo = photo_id or BufferedInputFile(image, filename="broadcast.jpg")
                message = await bot.send_photo(
                    user_id, photo, caption=text if caption_fits and text else None
                )
                if message.photo:
                    photo_id = message.photo[-1].file_id
                if text and not caption_fits:
                    await bot.send_message(user_id, text)
            else:
                await bot.send_message(user_id, text)
            sent += 1
        except TelegramAPIError:
            log.info("Broadcast failed for user %s", user_id)
        await asyncio.sleep(0.05)
    return sent, len(ids)


@dp.message(Command("id"))
async def id_command(message: Message) -> None:
    admin = is_admin(message.from_user.id, message.from_user.username)
    await message.answer(
        f"Ваш Telegram ID: <code>{message.from_user.id}</code>\n"
        + ("Вы администратор." if admin else "Вы не администратор.")
    )


@dp.message(F.text)
async def fallback(message: Message) -> None:
    if not await _active_user(message):
        return
    await message.answer(
        "Используйте /app, /export, /stats или /key.",
        reply_markup=app_keyboard() if WEBAPP_URL else None,
    )


PUBLIC_COMMANDS: list = []
ADMIN_COMMANDS: list = []


async def _set_admin_menu(chat_id: int) -> None:
    if not ADMIN_COMMANDS:
        return
    try:
        await bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=chat_id))
    except TelegramAPIError:
        log.info("Could not set admin menu for %s", chat_id)


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
    PUBLIC_COMMANDS[:] = public_commands
    ADMIN_COMMANDS[:] = admin_commands
    try:
        await bot.set_my_commands(public_commands, scope=BotCommandScopeDefault())
        known = set(ADMIN_IDS) | set(await db.admin_ids())
        for admin_id in known:
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
