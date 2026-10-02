"""Скрипты продаж: готовые шаблоны по нишам и генерация под конкретный лид.

Генерация идёт через Google Gemini API (бесплатный уровень). Если ключа нет,
лимит исчерпан или сервис не ответил, скрипт собирается из шаблона по реальным
данным лида — пользователь всегда получает результат."""

from __future__ import annotations

import asyncio
import re

import aiohttp

import analysis
import niches

KINDS = {
    "first": "Первое сообщение",
    "short": "Короткое сообщение",
    "detailed": "Подробное сообщение",
    "call": "Скрипт звонка",
    "followup": "Повторное сообщение",
}

_NICHE_TEXT = {
    0: dict(
        plural="барбершопов", acc="ваш барбершоп", clients="клиенты", come="записываются",
        pain="клиенты пишут в директ, ждут ответа и часть уходит к соседям",
        pain_detail="записаться можно только через звонок или сообщения, а ночью и в выходные заявки теряются",
        site_offer="сайт с услугами, ценами, работами мастеров и онлайн-записью к конкретному барберу",
        site_offer_short="сайты с онлайн-записью и Telegram-ботов",
        bot_offer="Telegram-бот: сам записывает к мастеру, напоминает о визите и зовёт вернуться через месяц",
        result="больше записей без звонков и меньше пустых окон", busy="барбершопе",
        call_hook="записаться к вам онлайн нельзя",
        followup_value="бот сам напоминает клиентам о стрижке через 3–4 недели — это возвращает тех, кто забывает записаться",
    ),
    1: dict(
        plural="салонов красоты", acc="ваш салон", clients="клиентки", come="записываются",
        pain="администратор не успевает отвечать всем, и заявки теряются в переписках",
        pain_detail="у клиенток нет одного места, где видно все услуги, цены и свободное время мастеров",
        site_offer="сайт с услугами, ценами, портфолио мастеров и онлайн-записью",
        site_offer_short="сайты с онлайн-записью и Telegram-ботов",
        bot_offer="Telegram-бот: запись к мастеру в пару касаний, напоминания и акции для постоянных клиенток",
        result="больше записей и меньше нагрузки на администратора", busy="салоне",
        call_hook="у салона нет своего сайта с онлайн-записью",
        followup_value="запись через сайт и бота работает круглосуточно — клиентки записываются даже ночью",
    ),
    2: dict(
        plural="автосервисов", acc="ваш автосервис", clients="клиенты", come="записываются на ремонт",
        pain="люди ищут сервис в интернете и выбирают тех, у кого видны цены и запись",
        pain_detail="нет страницы с услугами и примерными ценами, поэтому клиенты звонят и уходят сравнивать",
        site_offer="сайт с услугами, примерными ценами, отзывами и онлайн-записью на ремонт или ТО",
        site_offer_short="сайты и Telegram-ботов для записи на ремонт",
        bot_offer="Telegram-бот: запись на удобное время, статус ремонта и напоминание о следующем ТО",
        result="больше заявок и постоянных клиентов", busy="сервисе",
        call_hook="у сервиса нет сайта с онлайн-записью",
        followup_value="бот напоминает клиентам о сезонной смене шин и ТО — это повторные заказы без рекламы",
    ),
    3: dict(
        plural="стоматологий", acc="вашу клинику", clients="пациенты", come="записываются на приём",
        pain="пациенты выбирают клинику по сайту и уходят туда, где можно записаться сразу",
        pain_detail="нет удобной онлайн-записи и информации о врачах и ценах",
        site_offer="сайт клиники с врачами, услугами, ценами и онлайн-записью на приём",
        site_offer_short="сайты для клиник с онлайн-записью и Telegram-ботов",
        bot_offer="Telegram-бот: запись к врачу, напоминание о приёме и о профилактическом осмотре",
        result="больше первичных пациентов и меньше неявок", busy="клинике",
        call_hook="записаться в клинику онлайн нельзя",
        followup_value="напоминания в Telegram заметно снижают число пациентов, которые забыли о приёме",
    ),
    4: dict(
        plural="фитнес-клубов и студий", acc="ваш клуб", clients="клиенты", come="записываются на тренировки",
        pain="расписание и цены разбросаны по соцсетям, и новые клиенты не доходят до пробной тренировки",
        pain_detail="нет страницы с расписанием, абонементами и записью на пробное занятие",
        site_offer="сайт с расписанием, тренерами, абонементами и записью на пробную тренировку",
        site_offer_short="сайты с расписанием и Telegram-ботов для записи",
        bot_offer="Telegram-бот: расписание, запись на занятия, напоминания и продление абонемента",
        result="больше пробных тренировок и продлений", busy="клубе",
        call_hook="записаться на пробную тренировку онлайн нельзя",
        followup_value="бот сам напоминает об окончании абонемента — продления не теряются",
    ),
    6: dict(
        plural="студий маникюра", acc="вашу студию", clients="клиентки", come="записываются",
        pain="запись идёт через переписку, и мастер отвлекается от работы, чтобы ответить",
        pain_detail="клиентки не видят свободные окна и цены, поэтому пишут и ждут ответа",
        site_offer="сайт с ценами, работами мастеров и онлайн-записью на свободные окна",
        site_offer_short="сайты с онлайн-записью и Telegram-ботов",
        bot_offer="Telegram-бот: запись на свободное окно, напоминание о коррекции через 3 недели",
        result="заполненное расписание без постоянных переписок", busy="студии",
        call_hook="у студии нет онлайн-записи",
        followup_value="бот напоминает о коррекции — клиентки возвращаются вовремя",
    ),
    7: dict(
        plural="кофеен и кафе", acc="ваше заведение", clients="гости", come="узнают о вас",
        pain="гости ищут меню и часы работы в интернете и не находят",
        pain_detail="нет страницы с меню, ценами и предзаказом",
        site_offer="сайт с меню, ценами, часами работы и предзаказом",
        site_offer_short="сайты с меню и Telegram-ботов для предзаказа",
        bot_offer="Telegram-бот: меню, предзаказ к определённому времени и карта лояльности",
        result="больше постоянных гостей и заказов навынос", busy="кафе",
        call_hook="меню и предзаказа нет онлайн",
        followup_value="предзаказ через бота: гость заказывает кофе по дороге и забирает без очереди",
    ),
    8: dict(
        plural="ресторанов", acc="ваш ресторан", clients="гости", come="бронируют столы",
        pain="гости хотят забронировать стол онлайн, а приходится звонить",
        pain_detail="нет онлайн-бронирования и актуального меню на сайте",
        site_offer="сайт с меню, фото зала и онлайн-бронированием столов",
        site_offer_short="сайты с бронированием и Telegram-ботов",
        bot_offer="Telegram-бот: бронь стола, меню, напоминание о брони и приглашения на события",
        result="больше броней и меньше пропущенных звонков", busy="ресторане",
        call_hook="забронировать стол онлайн нельзя",
        followup_value="онлайн-бронь работает и ночью — гости бронируют, когда планируют вечер",
    ),
    9: dict(
        plural="ветклиник", acc="вашу клинику", clients="владельцы питомцев", come="записываются на приём",
        pain="владельцы питомцев ищут клинику срочно и выбирают ту, где сразу видно врачей и запись",
        pain_detail="нет онлайн-записи и информации об услугах и врачах",
        site_offer="сайт клиники с услугами, врачами, ценами и онлайн-записью",
        site_offer_short="сайты для ветклиник и Telegram-ботов",
        bot_offer="Telegram-бот: запись к врачу, напоминания о прививках и обработках",
        result="больше записей и повторных визитов", busy="клинике",
        call_hook="записаться в клинику онлайн нельзя",
        followup_value="бот сам напоминает о прививках и обработках — это повторные визиты без рекламы",
    ),
    10: dict(
        plural="школ и учебных центров", acc="вашу школу", clients="родители и ученики",
        come="записываются на занятия",
        pain="родители сравнивают школы в интернете и выбирают тех, где понятны программы и цены",
        pain_detail="нет страницы с программами, расписанием и записью на пробный урок",
        site_offer="сайт с программами, преподавателями, ценами и записью на пробный урок",
        site_offer_short="сайты для школ и Telegram-ботов для записи",
        bot_offer="Telegram-бот: запись на пробный урок, расписание и напоминания об оплате",
        result="больше записей на пробные уроки", busy="школе",
        call_hook="записаться на пробный урок онлайн нельзя",
        followup_value="бот сам напоминает о занятиях и оплате — меньше пропусков",
    ),
}

_TEMPLATES = {
    "first": (
        "Здравствуйте! Меня зовут [Ваше имя], я делаю сайты и Telegram-ботов для {plural}.\n"
        "Нашёл {acc} «[Название]» на карте и не увидел своего сайта. Часто без сайта {pain}.\n"
        "Могу сделать {site_offer}.\n"
        "Если интересно, пришлю пример и примерную стоимость — это займёт пару минут."
    ),
    "short": (
        "Здравствуйте! Делаю {site_offer_short} для {plural}. "
        "Для «[Название]» могу показать готовый пример. Прислать?"
    ),
    "detailed": (
        "Здравствуйте!\n"
        "Я [Ваше имя], занимаюсь сайтами и Telegram-ботами для {plural}.\n"
        "Посмотрел, как «[Название]» представлен в интернете:\n"
        "— [что нашли: нет сайта / сайт не открывается / нет онлайн-записи];\n"
        "— {pain_detail}.\n\n"
        "Что предлагаю:\n"
        "1. {site_offer_cap}.\n"
        "2. {bot_offer}.\n"
        "3. Ссылки на карты и соцсети, чтобы {clients} находили вас сразу.\n\n"
        "Цель — {result}. Сроки и стоимость обсудим под ваши задачи.\n"
        "Удобно, если я пришлю пару примеров работ?"
    ),
    "call": (
        "— Здравствуйте! Это [Ваше имя]. Подскажите, могу поговорить с владельцем или управляющим «[Название]»?\n"
        "— Я делаю сайты и Telegram-ботов для {plural}. Звоню, потому что увидел: {call_hook}.\n"
        "— Скажите, как к вам сейчас чаще всего {come}: по телефону или через соцсети?\n"
        "(Слушаем ответ, не перебиваем.)\n"
        "— Понял. Часто бывает так, что {pain}. Это решается так: {bot_offer_low}.\n"
        "— Могу прислать пример и примерную цену в Telegram или WhatsApp, посмотрите в удобное время. Куда удобнее?\n\n"
        "Если «не интересно»: — Понимаю. Можно пришлю один пример? Если не подойдёт, больше не побеспокою."
    ),
    "followup": (
        "Здравствуйте! Писал вам недавно про сайт и бота для «[Название]». "
        "Понимаю, что в {busy} много дел.\n"
        "Коротко: {followup_value}.\n"
        "Если сейчас не актуально — ответьте «не сейчас», и я не буду отвлекать. "
        "Если интересно — пришлю пример за минуту."
    ),
}


def _vars(niche: int) -> dict:
    data = dict(_NICHE_TEXT.get(niche, _NICHE_TEXT[1]))
    data["site_offer_cap"] = data["site_offer"][:1].upper() + data["site_offer"][1:]
    data["bot_offer_low"] = data["bot_offer"][:1].lower() + data["bot_offer"][1:]
    return data


def defaults() -> list[dict]:
    items = []
    for niche in niches.ORDER:
        values = _vars(niche)
        for kind, template in _TEMPLATES.items():
            items.append(
                {
                    "niche": niche,
                    "kind": kind,
                    "title": KINDS[kind],
                    "body": template.format(**values),
                }
            )
    return items


def _niche_id(title: str) -> int:
    for key, spec in niches.NICHES.items():
        if spec["title"] == title:
            return key
    return 1


def _findings(lead: dict) -> list[str]:
    info = lead.get("info") or {}
    site = lead.get("site")
    found = []
    if site == "none":
        found.append("своего сайта нет")
    elif site == "broken":
        found.append("сайт не открывается" + (f" ({lead['reasons'][0]})" if lead.get("reasons") else ""))
    elif site == "weak":
        found.extend((lead.get("reasons") or [])[:3])
    if not info.get("tg_bot"):
        found.append("Telegram-бота нет")
    if site in ("weak", "ok") and not info.get("booking"):
        found.append("онлайн-записи нет")
    return found


def template_for_lead(lead: dict, kind: str = "first") -> str:
    """Скрипт без нейросети: шаблон ниши + реальные данные лида."""
    niche = _niche_id((lead.get("info") or {}).get("niche") or lead.get("niche") or "")
    values = _vars(niche)
    findings = _findings(lead)
    name = lead.get("name") or "[Название]"
    if kind == "first":
        site = lead.get("site")
        hook = {
            "none": "и не увидел своего сайта",
            "broken": "и заметил, что ваш сайт сейчас не открывается",
            "weak": "и посмотрел ваш сайт: " + ", ".join((lead.get("reasons") or [])[:2]),
            "ok": "— сайт у вас есть, но записаться через Telegram нельзя",
        }.get(site, "")
        offer = values["bot_offer"] if site == "ok" else values["site_offer"]
        text = (
            f"Здравствуйте! Меня зовут [Ваше имя], я делаю сайты и Telegram-ботов для {values['plural']}.\n"
            f"Нашёл «{name}» на карте {hook}.\n"
            f"Могу сделать: {offer}.\n"
            "Если интересно, пришлю пример и примерную стоимость — это займёт пару минут."
        )
        return text
    text = _TEMPLATES.get(kind, _TEMPLATES["first"]).format(**values).replace("[Название]", name)
    if findings:
        text = text.replace(
            "[что нашли: нет сайта / сайт не открывается / нет онлайн-записи]", "; ".join(findings)
        )
    return text


def lead_prompt(lead: dict, kind: str) -> str:
    info = lead.get("info") or {}
    contacts = lead.get("c") or lead.get("contacts") or {}
    channels = [analysis.CONTACT_WORDS.get(key, key) for key in ("tg", "wa", "vb", "ig", "vk", "email") if contacts.get(key)]
    if lead.get("phone"):
        channels.insert(0, "телефон")
    facts = [
        f"Название: {lead.get('name')}",
        f"Ниша: {info.get('niche') or lead.get('niche') or 'не указана'}",
        f"Город: {lead.get('city')}",
        "Сайт: " + {
            "none": "нет", "broken": "есть, но не открывается", "weak": "есть, слабый",
            "ok": "есть, нормальный",
        }.get(lead.get("site"), "не удалось проверить"),
        "Что найдено: " + ("; ".join(_findings(lead)) or "нет данных"),
        "Каналы связи: " + (", ".join(channels) or "нет данных"),
    ]
    if info.get("rating") and info.get("reviews"):
        facts.append(f"Рейтинг на картах: {info['rating']} ({info['reviews']} отзывов)")
    return (
        f"Напиши {KINDS.get(kind, KINDS['first']).lower()} для продажи услуг: разработка сайта "
        "и/или Telegram-бота для этого бизнеса.\n" + "\n".join(facts) + "\n\n"
        "Требования: по-русски, вежливо и по-человечески, без канцелярита и без эмодзи; "
        "используй только факты выше и ничего не придумывай (никаких цифр, отзывов, имён, "
        "обещаний результата); вместо имени отправителя пиши [Ваше имя]; "
        + ("формат — реплики для телефонного разговора с вариантом ответа на отказ; " if kind == "call" else "")
        + ("не длиннее 3 предложений; " if kind == "short" else "не длиннее 900 символов; ")
        + "в конце — один простой вопрос, на который легко ответить."
    )


def niche_prompt(niche: int, kind: str, custom: str = "") -> str:
    title = niches.title(niche, custom)
    return (
        f"Напиши новый вариант: {KINDS.get(kind, KINDS['first']).lower()} для продажи услуг "
        f"разработки сайта и Telegram-бота бизнесу из ниши «{title}». Название бизнеса заменяй на "
        "[Название], имя отправителя — на [Ваше имя]. По-русски, без эмодзи, ничего не выдумывай "
        "(никаких цифр и гарантий), в конце — один простой вопрос."
        + (" Формат — реплики телефонного разговора." if kind == "call" else "")
    )


SYSTEM = (
    "Ты помогаешь фрилансерам, которые делают сайты и Telegram-ботов, писать первые сообщения "
    "и скрипты звонков малому бизнесу. Пиши кратко, честно и уважительно. Возвращай только "
    "готовый текст скрипта без пояснений и без markdown."
)


class AIError(Exception):
    pass


async def gemini(api_key: str, model: str, prompt: str, *, session: aiohttp.ClientSession | None = None) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.8, "maxOutputTokens": 800},
    }
    owns = session is None
    session = session or aiohttp.ClientSession()
    try:
        async with session.post(
            url, json=body, headers={"x-goog-api-key": api_key},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as response:
            data = await response.json(content_type=None)
            if response.status != 200:
                message = ""
                if isinstance(data, dict):
                    message = str((data.get("error") or {}).get("message") or "")
                raise AIError(f"Gemini HTTP {response.status}: {message}"[:300])
    except asyncio.TimeoutError as exc:
        raise AIError("Gemini не ответил вовремя.") from exc
    except aiohttp.ClientError as exc:
        raise AIError("Не удалось связаться с Gemini.") from exc
    except ValueError as exc:
        raise AIError("Gemini вернул некорректный ответ.") from exc
    finally:
        if owns:
            await session.close()
    try:
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(part.get("text", "") for part in parts).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise AIError("Gemini не вернул текст (возможно, сработал фильтр).") from exc
    text = re.sub(r"[*_#`]+", "", text).strip()
    if len(text) < 20:
        raise AIError("Gemini вернул слишком короткий ответ.")
    return text[:2500]
