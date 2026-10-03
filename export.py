import io

from aiogram.types import BufferedInputFile
from openpyxl import Workbook

import db
from analysis import NEED_LABELS

HEADERS = [
    "Название", "Ниша", "Страна", "Город", "Адрес", "Телефон", "Сайт", "URL",
    "Что нужно", "Причины", "Приоритет", "Почему такой приоритет", "Статус",
    "Telegram", "Telegram-бот", "Онлайн-запись", "WhatsApp", "VK",
    "Instagram", "Facebook", "Email", "Viber", "Часы работы", "Рейтинг", "Отзывов",
    "Карта", "Источник",
]
SITE_NAMES = {"none": "нет", "broken": "не работает", "weak": "слабый", "ok": "нормальный", "unchecked": "не проверялся"}
NOT_FOUND = "не найдено"
STATUS_NAMES = {
    "new": "Новый",
    "written": "Написал",
    "replied": "Ответил",
    "rejected": "Отказ",
    "client": "Клиент",
}


def _safe_spreadsheet_text(value) -> str:
    """Prevent user-provided OSM text from being interpreted as an Excel formula."""
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + text
    return text


def build_xlsx(leads: list[dict]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Leads"
    sheet.append(HEADERS)

    for lead in leads:
        contacts = lead["c"]
        info = lead.get("info") or {}
        sources = ", ".join(item.get("u", "") for item in info.get("sources") or [])
        booking = info.get("booking")
        if lead["site"] in ("none", "broken"):
            booking = booking or "нет"
        values = [
            lead["name"],
            lead.get("niche") or info.get("niche", ""),
            lead["country"],
            lead["city"],
            contacts.get("address") or info.get("address") or NOT_FOUND,
            ", ".join(info.get("phones") or []) or lead["phone"] or NOT_FOUND,
            SITE_NAMES.get(lead["site"], lead["site"]),
            lead["url"],
            NEED_LABELS.get(lead.get("need", ""), ""),
            ", ".join(lead["reasons"]),
            lead["hot"],
            lead.get("explain", ""),
            STATUS_NAMES.get(lead["status"], lead["status"]),
            contacts.get("tg", ""),
            info.get("tg_bot") or "не найден",
            booking or "не найдена",
            contacts.get("wa", ""),
            contacts.get("vk") or contacts.get("vkg", ""),
            contacts.get("ig", ""),
            contacts.get("fb", ""),
            contacts.get("email", ""),
            contacts.get("vb", ""),
            info.get("hours") or NOT_FOUND,
            info.get("rating") or NOT_FOUND,
            info.get("reviews") or NOT_FOUND,
            contacts.get("map", ""),
            sources,
        ]
        sheet.append([_safe_spreadsheet_text(value) for value in values])

    widths = [30, 18, 8, 18, 30, 20, 12, 34, 30, 44, 10, 60, 12, 20, 18, 20, 18, 20, 22, 30, 28, 16, 30, 10, 10, 40, 40]
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[sheet.cell(row=1, column=index).column_letter].width = width
    sheet.freeze_panes = "A2"

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


async def send_export(uid: int) -> None:
    from bot import bot

    leads = await db.list_leads(uid, "all", 100000)
    if not leads:
        await bot.send_message(uid, "Пока нет лидов для экспорта.")
        return
    data = build_xlsx(leads)
    await bot.send_document(
        uid,
        BufferedInputFile(data, filename="parser_cc_leads.xlsx"),
        caption=f"Экспорт: {len(leads)} лидов",
    )
