"""Удаление лида, источник 2ГИС и склейка одинаковых бизнесов из разных баз."""
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import api
import db
import dgis
import parser as search


def dgis_item(i, phone, lat=55.75, lon=37.6):
    return {
        "id": f"7000000{i}_abc", "name": f"Барбершоп {i}", "address_name": f"Тверская, {i}",
        "point": {"lat": lat, "lon": lon},
        "contact_groups": [{"contacts": [
            {"type": "phone", "value": phone, "text": phone},
            {"type": "website", "value": "http://link.2gis.ru/xyz", "text": f"barber{i}.ru", "url": f"https://barber{i}.ru"},
        ]}],
        "reviews": {"general_rating": 4.8, "general_review_count": 120},
        "schedule": {"Mon": {"working_hours": [{"from": "10:00", "to": "21:00"}]}},
        "adm_div": [{"type": "city", "name": "Москва"}],
    }


class DgisAdapterTests(unittest.IsolatedAsyncioTestCase):
    def test_candidate_fields(self):
        item = dgis_item(1, "+79263000101")
        candidate = dgis.to_candidate(item, "RU")
        self.assertEqual(candidate["key"], "d:70000001")
        self.assertEqual(candidate["phone_raw"], "+79263000101")
        self.assertEqual(candidate["url_raw"], "https://barber1.ru")  # не ссылка-редирект 2ГИС
        self.assertEqual(candidate["map"], "https://2gis.ru/firm/70000001")
        self.assertEqual((candidate["rating"], candidate["reviews"]), (4.8, 120))
        self.assertIn("Пн 10:00–21:00", candidate["hours"])
        self.assertEqual(candidate["city"], "Москва")

    def test_area_radius_is_limited(self):
        point, radius = dgis.area((55.5, 37.3, 56.0, 38.0))
        self.assertTrue(point.startswith("37.65"))
        self.assertLessEqual(radius, 50_000)
        self.assertGreater(radius, 20_000)

    async def test_errors_and_not_found(self):
        class Resp:
            def __init__(self, data):
                self.data = data
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def json(self, content_type=None):
                return self.data

        class Session:
            def __init__(self, data):
                self.data = data
            def get(self, *a, **kw):
                return Resp(self.data)

        empty = await dgis.search(Session({"meta": {"code": 404}}), "k", "барбершоп", (55.5, 37.3, 56.0, 38.0))
        self.assertEqual(empty, [])
        with self.assertRaises(dgis.DgisError):
            await dgis.search(Session({"meta": {"code": 403, "error": {"message": "Invalid key"}}}),
                              "k", "барбершоп", (55.5, 37.3, 56.0, 38.0))


class MultiSourceTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_business_from_three_bases_becomes_one_rich_lead(self):
        # Один и тот же барбершоп в Google, 2ГИС и OSM + ещё 11 разных из 2ГИС.
        google_place = {
            "id": "G1", "displayName": {"text": "Барбершоп 1"}, "businessStatus": "OPERATIONAL",
            "internationalPhoneNumber": "+7 926 300-01-01", "googleMapsUri": "https://maps.google.com/?cid=1",
            "location": {"latitude": 55.75, "longitude": 37.6},
        }
        items = [dgis_item(1, "+79263000101", 55.7501, 37.6001)] + [
            dgis_item(i, f"+7926300{i:02d}{i:02d}", 55.75 + i / 100, 37.6) for i in range(2, 13)
        ]
        osm = [{"type": "node", "id": 5, "lat": 55.7502, "lon": 37.6002,
                "tags": {"name": "Барбершоп 1", "phone": "+7 926 300 01 01", "opening_hours": "Mo-Su 10:00-21:00"}}]

        async def text_search(*_a, **_kw):
            return [google_place]

        async def dgis_search(*_a, **_kw):
            return items

        with patch("parser.GOOGLE_PLACES_API_KEY", "g"), patch("parser.DGIS_API_KEY", "d"), \
                patch("google_places.text_search", text_search), patch("dgis.search", dgis_search), \
                patch("parser.overpass", AsyncMock(return_value=osm)), patch("parser.GEOAPIFY_API_KEY", ""), \
                patch("parser.ANALYZE_SITES", False):
            result = await search.run_search("RU", "Москва", 0, "", "all", 10)
        self.assertEqual(len(result), 10)
        phones = [lead["phone_e164"] for lead in result]
        self.assertEqual(len(phones), len(set(phones)))  # без дублей
        first = next(lead for lead in result if lead["phone_e164"] == "+79263000101")
        titles = {item["t"] for item in first["info"]["sources"]}
        self.assertTrue({"2ГИС", "Google Maps"} <= titles)
        self.assertEqual(first["info"]["rating"], 4.8)  # рейтинг из 2ГИС дополнил карточку

    async def test_dgis_failure_does_not_break_search(self):
        osm = [{"type": "node", "id": i, "lat": 55.75, "lon": 37.6 + i / 100,
                "tags": {"name": f"Салон {i}", "phone": f"+7 926 400 {i:02d} {i:02d}"}} for i in range(1, 8)]

        async def broken(*_a, **_kw):
            raise dgis.DgisError("2ГИС 403: Invalid key")

        errors = []

        async def on_error(source, message):
            errors.append(source)

        with patch("parser.DGIS_API_KEY", "d"), patch("dgis.search", broken), \
                patch("parser.GOOGLE_PLACES_API_KEY", ""), patch("parser.GEOAPIFY_API_KEY", ""), \
                patch("parser.overpass", AsyncMock(return_value=osm)), patch("parser.ANALYZE_SITES", False):
            result = await search.run_search("RU", "Москва", 0, "", "all", 5, on_source_error=on_error)
        self.assertEqual(len(result), 5)
        self.assertIn("dgis", errors)


class TakenByOthersTests(unittest.IsolatedAsyncioTestCase):
    async def test_osm_is_awaited_when_google_results_are_taken(self):
        places = [{
            "id": f"P{i}", "displayName": {"text": f"Барбер {i}"}, "businessStatus": "OPERATIONAL",
            "internationalPhoneNumber": f"+7 926 300-{i:02d}-{i:02d}", "googleMapsUri": f"https://maps.google.com/?cid={i}",
            "location": {"latitude": 55.75, "longitude": 37.6 + i / 1000},
        } for i in range(1, 40)]
        osm = [{"type": "node", "id": i, "lat": 55.7, "lon": 37.5 + i / 100,
                "tags": {"name": f"Салон {i}", "phone": f"+7 916 500 {i:02d} {i:02d}"}} for i in range(1, 30)]

        async def text_search(*_a, **_kw):
            return places

        async def slowish_overpass(*_a, **_kw):
            await asyncio.sleep(0.5)
            return osm

        async def taken(tokens):  # все бизнесы из Google уже выданы другим участникам
            return {t for t in tokens if t.startswith("phone:7926300")}

        with patch("parser.GOOGLE_PLACES_API_KEY", "g"), patch("google_places.text_search", text_search), \
                patch("parser.overpass", slowish_overpass), patch("parser.GEOAPIFY_API_KEY", ""), \
                patch("parser.DGIS_API_KEY", ""), patch("parser.ANALYZE_SITES", False), patch("parser.OSM_GRACE", 0.1):
            result = await search.run_search("RU", "Москва", 0, "", "all", 10, exclude_tokens=taken)
        self.assertEqual(len(result), 10)
        self.assertTrue(all(lead["source"] == "osm" for lead in result))

    async def test_results_never_share_a_phone(self):
        # Филиал с общим «центральным» номером не должен давать два лида с одним телефоном.
        async def text_search(*_a, **_kw):
            return [{"id": "A", "displayName": {"text": "Салон Альфа"}, "businessStatus": "OPERATIONAL",
                     "internationalPhoneNumber": "+7 495 111-11-11", "googleMapsUri": "https://maps.google.com/?cid=A",
                     "location": {"latitude": 55.70, "longitude": 37.50}}]

        async def dgis_search(*_a, **_kw):
            item = dgis_item(2, "+74952222222", 55.80, 37.70)
            item["contact_groups"][0]["contacts"].append({"type": "phone", "value": "+74951111111"})
            return [item]

        with patch("parser.GOOGLE_PLACES_API_KEY", "g"), patch("parser.DGIS_API_KEY", "d"), \
                patch("google_places.text_search", text_search), patch("dgis.search", dgis_search), \
                patch("parser.overpass", AsyncMock(return_value=[])), patch("parser.GEOAPIFY_API_KEY", ""), \
                patch("parser.ANALYZE_SITES", False):
            result = await search.run_search("RU", "Москва", 0, "", "all", 5)
        from lead_identity import claim_tokens
        seen = set()
        for lead in result:
            tokens = claim_tokens(lead)
            self.assertFalse(tokens & seen)
            seen |= tokens


class DeleteLeadTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        self.temp = tempfile.TemporaryDirectory(prefix="parsercc-v4-")
        self.original = db.DB_PATH
        db.DB_PATH = Path(self.temp.name) / "t.sqlite"
        self.user = {"id": 7, "username": "u", "first_name": "U"}
        self.patcher = patch("api.verify_init_data", side_effect=lambda _d: dict(self.user))
        self.patcher.start()
        self.cm = TestClient(api.app)
        self.client = self.cm.__enter__()
        asyncio.run(db.upsert_user(7, "u", "U"))
        asyncio.run(db.upsert_user(8, "v", "V"))
        lead = {"osm_key": "node/1", "name": "Автотрейд", "country": "RU", "city": "Краснодар",
                "phone": "+7 800 555-54-15", "phone_e164": "+78005555415", "site": "unchecked",
                "contacts": {}, "info": {"phones_e164": ["+78005555415"]}}
        self.lead_id = asyncio.run(db.claim_leads(7, [lead]))[0]["id"]
        self.lead = lead

    def tearDown(self):
        self.cm.__exit__(None, None, None)
        self.patcher.stop()
        db.DB_PATH = self.original
        self.temp.cleanup()

    def test_delete_own_lead_and_it_never_comes_back(self):
        h = {"X-Init-Data": "x"}
        self.user = {"id": 8, "username": "v", "first_name": "V"}
        self.assertEqual(self.client.delete(f"/api/leads/{self.lead_id}", headers=h).status_code, 404)  # чужой
        self.user = {"id": 7, "username": "u", "first_name": "U"}
        self.assertEqual(self.client.delete(f"/api/leads/{self.lead_id}", headers=h).status_code, 200)
        self.assertEqual(self.client.get("/api/leads", headers=h).json()["leads"], [])
        self.assertEqual(self.client.get("/api/stats", headers=h).json()["found"], 0)
        # тот же бизнес больше не выдаётся ни ему, ни другим
        self.assertEqual(asyncio.run(db.claim_leads(7, [dict(self.lead, osm_key="node/2")])), [])
        self.assertEqual(asyncio.run(db.claim_leads(8, [dict(self.lead, osm_key="node/3")])), [])


if __name__ == "__main__":
    unittest.main()


class DefaultLimitTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="parsercc-def-")
        self.original = db.DB_PATH
        db.DB_PATH = Path(self.temp.name) / "t.sqlite"
        await db.init()

    async def asyncTearDown(self):
        db.DB_PATH = self.original
        self.temp.cleanup()
        await asyncio.sleep(0)
        db._DEFAULTS["limit"] = db.DEFAULT_LIMIT

    async def test_scopes_and_persistence(self):
        start = db.default_limit()
        await db.grant_member(10)            # стандартный лимит
        await db.grant_member(11, 200)       # ручной лимит
        self.assertEqual(await db.set_default_limit(50, "standard"), 1)
        self.assertEqual((await db.get_user(10))["daily_limit"], 50)
        self.assertEqual((await db.get_user(11))["daily_limit"], 200)
        await db.grant_member(12)
        self.assertEqual((await db.get_user(12))["daily_limit"], 50)
        await db.set_default_limit(20, "new")
        self.assertEqual((await db.get_user(10))["daily_limit"], 50)
        await db.set_default_limit(25, "all")
        self.assertEqual({(await db.get_user(u))["daily_limit"] for u in (10, 11, 12)}, {25})
        # после перезапуска значение берётся из базы, а не из переменной окружения
        db._DEFAULTS["limit"] = start
        await db.init()
        self.assertEqual(db.default_limit(), 25)
        await db.create_key("CC-T", "", None, 0, 1)
        self.assertEqual([k for k in await db.list_keys() if k["code"] == "CC-T"][0]["daily_limit"], 25)
