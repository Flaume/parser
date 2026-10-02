"""Ниши поиска: какие объекты искать в каждом источнике.

Номера 0–5 совпадают с прежней версией (5 — своя ниша), новые ниши идут дальше.
Для каждой ниши несколько запросов: теги OpenStreetMap, поиск по названию,
категории Geoapify и текстовые запросы Google (если он подключён)."""

from __future__ import annotations

CUSTOM = 5

# Ключи OSM, у которых бывают организации. Поиск по названию ограничен ими,
# чтобы не попадали улицы, остановки и прочие объекты с похожим названием.
BUSINESS_KEYS = "shop|amenity|craft|office|leisure|healthcare|tourism|club"

NICHES: dict[int, dict] = {
    0: {
        "title": "Барбершопы",
        "short": "Барбершоп",
        "osm": [
            '["shop"="barber"]',
            '["shop"="hairdresser"]["hairdresser"~"barber|men",i]',
            '["shop"="hairdresser"]["male"="yes"]',
        ],
        "name": "барбер|barber|мужская парикмахерская",
        "geoapify": ["service.beauty.hairdresser"],
        "name_filter": r"барбер|barber|мужск|men|gentle|бород|beard",
        "google_ru": ["барбершоп", "мужская парикмахерская"],
        "google_en": ["barber shop", "barbershop"],
    },
    1: {
        "title": "Салоны красоты",
        "short": "Салон красоты",
        "osm": ['["shop"="beauty"]', '["shop"="hairdresser"]'],
        "name": "салон красоты|beauty salon|студия красоты",
        "geoapify": ["service.beauty"],
        "google_ru": ["салон красоты", "парикмахерская"],
        "google_en": ["beauty salon", "hair salon"],
    },
    2: {
        "title": "Автосервисы",
        "short": "Автосервис",
        "osm": ['["shop"="car_repair"]', '["shop"="tyres"]', '["craft"="car_repair"]'],
        "name": "автосервис|шиномонтаж|автотехцентр|кузовн|car service|auto service",
        "geoapify": ["service.vehicle.repair", "commercial.vehicle"],
        "google_ru": ["автосервис", "шиномонтаж"],
        "google_en": ["car repair", "auto service"],
    },
    3: {
        "title": "Стоматологии",
        "short": "Стоматология",
        "osm": ['["amenity"="dentist"]', '["healthcare"="dentist"]'],
        "name": "стоматолог|dental|dentist|дентал",
        "geoapify": ["healthcare.dentist"],
        "google_ru": ["стоматология", "стоматологическая клиника"],
        "google_en": ["dentist", "dental clinic"],
    },
    4: {
        "title": "Фитнес и спортзалы",
        "short": "Фитнес",
        "osm": [
            '["leisure"="fitness_centre"]',
            '["leisure"="sports_centre"]["sport"~"fitness|yoga|crossfit|boxing|martial",i]',
            '["sport"="yoga"]["leisure"]',
        ],
        "name": "фитнес|fitness|тренажерн|тренажёрн|gym|йога|yoga|кроссфит|crossfit",
        "geoapify": ["sport.fitness", "activity.sport_club"],
        "google_ru": ["фитнес клуб", "тренажёрный зал"],
        "google_en": ["fitness club", "gym"],
    },
    6: {
        "title": "Маникюр и ногти",
        "short": "Маникюр",
        "osm": ['["shop"="beauty"]["beauty"~"nails",i]', '["shop"="nails"]'],
        "name": "маникюр|ногт|nail|нейл",
        "geoapify": ["service.beauty"],
        "name_filter": r"маникюр|ногт|nail|нейл|педикюр",
        "google_ru": ["студия маникюра", "ногтевая студия"],
        "google_en": ["nail salon", "manicure"],
    },
    7: {
        "title": "Кофейни и кафе",
        "short": "Кафе",
        "osm": ['["amenity"="cafe"]'],
        "name": "кофейн|coffee|кафе",
        "geoapify": ["catering.cafe"],
        "google_ru": ["кофейня", "кафе"],
        "google_en": ["coffee shop", "cafe"],
    },
    8: {
        "title": "Рестораны",
        "short": "Ресторан",
        "osm": ['["amenity"="restaurant"]'],
        "name": "ресторан|restaurant|бистро|bistro|траттория|trattoria",
        "geoapify": ["catering.restaurant"],
        "google_ru": ["ресторан"],
        "google_en": ["restaurant"],
    },
    9: {
        "title": "Ветклиники",
        "short": "Ветклиника",
        "osm": ['["amenity"="veterinary"]', '["healthcare"="veterinary"]'],
        "name": "ветеринар|ветклиник|vet|зоовет",
        "geoapify": ["pet.veterinary"],
        "google_ru": ["ветеринарная клиника"],
        "google_en": ["veterinary clinic"],
    },
    10: {
        "title": "Языковые и детские школы",
        "short": "Школа",
        "osm": [
            '["amenity"="language_school"]',
            '["amenity"="prep_school"]',
            '["amenity"="music_school"]',
            '["amenity"="dancing_school"]',
        ],
        "name": "английск|языков|english|школа танц|детский центр|развивающ|лингв",
        "geoapify": ["education.language_school", "education.music_school", "education.dancing_school"],
        "google_ru": ["школа английского языка", "детский развивающий центр"],
        "google_en": ["language school", "kids learning center"],
    },
}

ORDER = [0, 1, 6, 2, 3, 4, 7, 8, 9, 10]


def get(niche: int) -> dict:
    return NICHES.get(niche, NICHES[0])


def title(niche: int, custom: str = "") -> str:
    if niche == CUSTOM:
        return (custom or "Своя ниша").strip()[:80]
    return get(niche)["title"]


def valid(niche: int) -> bool:
    return niche == CUSTOM or niche in NICHES


def public_list() -> list[dict]:
    items = [{"id": key, "title": NICHES[key]["title"], "short": NICHES[key]["short"]} for key in ORDER]
    items.append({"id": CUSTOM, "title": "Своя ниша", "short": "Своя"})
    return items
