import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
_admin_values = [value.strip() for value in os.getenv("ADMIN_IDS", "").split(",") if value.strip()]
ADMIN_IDS_INVALID = [
    value for value in _admin_values
    if not value.isdigit() or int(value) <= 0
]
ADMIN_IDS = {
    int(value)
    for value in _admin_values
    if value.isdigit() and int(value) > 0
}
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()
API_HOST = os.getenv("API_HOST", "0.0.0.0").strip()
API_PORT = int(os.getenv("PORT") or os.getenv("API_PORT", "8080"))

_db_path = Path(os.getenv("DB_PATH", "./parser.db")).expanduser()
DB_PATH = _db_path if _db_path.is_absolute() else ROOT_DIR / _db_path

DEFAULT_LIMIT = int(os.getenv("DEFAULT_LIMIT", "70"))
OVERPASS_URL = os.getenv(
    "OVERPASS_URL", "https://maps.mail.ru/osm/tools/overpass/api/interpreter"
).strip()
NOMINATIM_URL = os.getenv(
    "NOMINATIM_URL", "https://nominatim.openstreetmap.org/search"
).strip()
CONTACT_EMAIL = os.getenv("CONTACT_EMAIL", "you@example.com").strip()
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
GOOGLE_MAX_PAGES = max(1, min(3, int(os.getenv("GOOGLE_MAX_PAGES", "3"))))
GOOGLE_MONTHLY_LIMIT = max(0, int(os.getenv("GOOGLE_MONTHLY_LIMIT", "1000")))
def _int(name: str, default: int, low: int, high: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        value = default
    return max(low, min(high, value))


# Geoapify Places: бесплатный тариф 3000 кредитов в день, карта не нужна.
GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY", "").strip()
GEOAPIFY_DAILY_CREDITS = _int("GEOAPIFY_DAILY_CREDITS", 2500, 0, 100000)

# Нейросеть для скриптов: Google Gemini API (бесплатный уровень, ключ без карты).
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
AI_DAILY_LIMIT = _int("AI_DAILY_LIMIT", 900, 0, 100000)
AI_USER_DAILY_LIMIT = _int("AI_USER_DAILY_LIMIT", 30, 0, 1000)

# Пробный доступ: у каждого нового пользователя TRIAL_SEARCHES поисков по TRIAL_LEADS лидов.
TRIAL_SEARCHES = _int("TRIAL_SEARCHES", 1, 0, 100)
TRIAL_LEADS = _int("TRIAL_LEADS", 10, 1, 200)
JOIN_URL = os.getenv("JOIN_URL", "https://t.me/m/KXcCg7quZGFh").strip()
CONTACT_USERNAME = os.getenv("CONTACT_USERNAME", "SUN9ISE").strip().lstrip("@")

USER_AGENT = f"ParserCC/2.0 (Telegram Mini App; contact: {CONTACT_EMAIL})"


def validate_config() -> None:
    if (
        not BOT_TOKEN
        or ":" not in BOT_TOKEN
        or "your_bot_token" in BOT_TOKEN.lower()
        or "..." in BOT_TOKEN
    ):
        raise RuntimeError(
            "Не задан BOT_TOKEN. Создайте файл .env по образцу .env.example "
            "и вставьте токен от BotFather."
        )
    if WEBAPP_URL:
        try:
            parsed_url = urlsplit(WEBAPP_URL)
            valid_webapp_url = (
                parsed_url.scheme == "https"
                and bool(parsed_url.hostname)
                and not parsed_url.username
                and not parsed_url.password
            )
        except ValueError:
            valid_webapp_url = False
        if not valid_webapp_url:
            raise RuntimeError(
                "WEBAPP_URL должен быть публичным HTTPS-адресом Mini App. "
                "Оставьте поле пустым на первом запуске и следуйте README.md."
            )
    if ADMIN_IDS_INVALID:
        raise RuntimeError(
            "ADMIN_IDS содержит нечисловой Telegram ID: "
            + ", ".join(ADMIN_IDS_INVALID)
        )
    if len(ADMIN_IDS) > 1:
        raise RuntimeError(
            "В ADMIN_IDS можно указать только один Telegram ID владельца. "
            "Это единственный аккаунт с админ-панелью."
        )
    if not 1 <= API_PORT <= 65535:
        raise RuntimeError("API_PORT должен быть числом от 1 до 65535.")
    if not 0 <= DEFAULT_LIMIT <= 5000:
        raise RuntimeError("DEFAULT_LIMIT должен быть числом от 0 до 5000.")
