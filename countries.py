"""Страны и крупные города для поиска.

Если город не указан, парсер ищет по крупным городам страны по очереди
(каждый раз начиная с другого города), а не одним огромным запросом
по всей стране — такой запрос к картам часто не успевает выполниться."""

from __future__ import annotations

import random

COUNTRIES: dict[str, dict] = {
    "RU": {"title": "Россия", "cities": [
        "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань", "Нижний Новгород",
        "Челябинск", "Красноярск", "Самара", "Уфа", "Ростов-на-Дону", "Омск", "Краснодар",
        "Воронеж", "Пермь", "Волгоград", "Тюмень", "Саратов", "Тольятти", "Ижевск",
    ]},
    "UA": {"title": "Украина", "cities": [
        "Киев", "Харьков", "Одесса", "Днепр", "Львов", "Запорожье", "Винница", "Полтава",
    ]},
    "BY": {"title": "Беларусь", "cities": ["Минск", "Гомель", "Могилёв", "Витебск", "Гродно", "Брест"]},
    "KZ": {"title": "Казахстан", "cities": [
        "Алматы", "Астана", "Шымкент", "Караганда", "Актобе", "Тараз", "Павлодар", "Усть-Каменогорск",
    ]},
    "UZ": {"title": "Узбекистан", "cities": ["Ташкент", "Самарканд", "Наманган", "Андижан", "Бухара", "Фергана"]},
    "KG": {"title": "Кыргызстан", "cities": ["Бишкек", "Ош", "Джалал-Абад"]},
    "AM": {"title": "Армения", "cities": ["Ереван", "Гюмри", "Ванадзор"]},
    "AZ": {"title": "Азербайджан", "cities": ["Баку", "Гянджа", "Сумгаит"]},
    "GE": {"title": "Грузия", "cities": ["Тбилиси", "Батуми", "Кутаиси", "Рустави"]},
    "MD": {"title": "Молдова", "cities": ["Кишинёв", "Бельцы"]},
    "PL": {"title": "Польша", "cities": [
        "Warszawa", "Kraków", "Wrocław", "Łódź", "Poznań", "Gdańsk", "Szczecin", "Lublin",
    ]},
    "LT": {"title": "Литва", "cities": ["Vilnius", "Kaunas", "Klaipėda", "Šiauliai"]},
    "DE": {"title": "Германия", "cities": [
        "Berlin", "Hamburg", "München", "Köln", "Frankfurt am Main", "Stuttgart", "Düsseldorf", "Leipzig",
    ]},
    "AE": {"title": "ОАЭ", "cities": ["Dubai", "Abu Dhabi", "Sharjah", "Ajman"]},
}

ORDER = ["RU", "UA", "BY", "KZ", "UZ", "KG", "AM", "AZ", "GE", "MD", "PL", "LT", "DE", "AE"]

# Сколько городов максимум обходить за один поиск без указанного города.
MAX_CITIES_PER_SEARCH = 4


def cities(country: str) -> list[str]:
    return list(COUNTRIES.get(country.upper(), {}).get("cities", []))


def search_order(country: str, rng: random.Random | None = None) -> list[str]:
    """Города страны, начиная со случайного: повторные поиски охватывают разные города."""
    items = cities(country)
    if not items:
        return []
    start = (rng or random).randrange(len(items))
    return items[start:] + items[:start]


def public_list() -> list[dict]:
    return [
        {"code": code, "title": COUNTRIES[code]["title"], "cities": COUNTRIES[code]["cities"]}
        for code in ORDER
    ]
