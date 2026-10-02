import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import db
from api import SearchRequest
from parser import GeoError, build_query, overpass, run_search


def lead(osm_key, *, name="TopGun", phone="+7 926 986 44 44", street="Ленина", house="1",
         email="info@topgun.example", site="https://www.topgunbarbershop.ru/"):
    return {
        "osm_key": osm_key,
        "name": name,
        "country": "RU",
        "city": "Москва",
        "phone": phone,
        "site": "weak",
        "site_url": site,
        "reasons": ["Сайт не открывается"],
        "contacts": {"address": f"{street}, {house}", "email": email},
        "hot": 84,
    }


class SearchLocationTests(unittest.TestCase):
    def test_city_may_be_empty_or_omitted(self):
        self.assertEqual(SearchRequest(country="RU", city="", niche=0, count=15).city, "")
        self.assertEqual(SearchRequest(country="RU", niche=0, count=15).city, "")

    def test_country_query_uses_osm_area_and_is_bounded(self):
        query = build_query(None, 0, "", country="RU", result_limit=220)
        self.assertIn('area["ISO3166-1"="RU"][admin_level=2]', query)
        self.assertIn('nwr["shop"="barber"](area.searchArea)', query)
        self.assertIn('nwr["name"~"барбер|barber', query)
        self.assertTrue(query.endswith("out center tags 220;"))

    def test_country_query_caps_remote_result_limit(self):
        query = build_query(None, 0, "", country="RU", result_limit=10000)
        self.assertTrue(query.endswith("out center tags 1500;"))

    def test_city_query_keeps_its_bounding_box(self):
        query = build_query((55.5, 37.3, 56.0, 38.0), 0, "")
        self.assertIn('(55.5,37.3,56.0,38.0)', query)
        self.assertNotIn("area.searchArea", query)

    def test_city_query_can_be_bounded_before_downloading(self):
        query = build_query((55.5, 37.3, 56.0, 38.0), 0, "", result_limit=500)
        self.assertTrue(query.endswith("out center tags 500;"))

    def test_invalid_country_area_is_rejected(self):
        with self.assertRaises(GeoError):
            build_query(None, 0, "", country="RUS", result_limit=200)


class SearchPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_overpass_uses_backup_after_primary_returns_406(self):
        class Response:
            def __init__(self, status, data=None):
                self.status = status
                self.data = data or {}

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            async def json(self, content_type=None):
                return self.data

        class Session:
            def __init__(self):
                self.calls = []
                self.responses = [Response(406), Response(200, {"elements": [{"id": 7}]})]

            def post(self, endpoint, **_kwargs):
                self.calls.append(endpoint)
                return self.responses.pop(0)

        session = Session()
        with patch("parser.OVERPASS_URL", "https://primary.test/api/interpreter"), patch(
            "parser.OVERPASS_FALLBACK_URLS", ("https://backup.test/api/interpreter",)
        ):
            rows = await overpass(session, "[out:json];out;")
        self.assertEqual(rows, [{"id": 7}])
        self.assertEqual(
            session.calls,
            ["https://primary.test/api/interpreter", "https://backup.test/api/interpreter"],
        )

    async def test_blank_city_skips_geocoder_and_uses_country_search(self):
        overpass = AsyncMock(return_value=[])
        geocode = AsyncMock()
        with patch("parser.overpass", overpass), patch("parser.geocode", geocode):
            result = await run_search("RU", "", 0, "", "both", 15)
        self.assertEqual(result, [])
        geocode.assert_not_awaited()
        query = overpass.await_args.args[1]
        self.assertIn('ISO3166-1"="RU', query)
        self.assertRegex(query, r"out center tags \d+;")

    async def test_duplicate_osm_objects_become_one_result(self):
        elements = [
            {"type": "node", "id": 1, "tags": {"name": "TopGun", "phone": "+7 926 986 44 44", "website": "https://topgunbarbershop.ru", "addr:street": "Ленина", "addr:housenumber": "1"}},
            {"type": "way", "id": 2, "tags": {"name": "TOPGUN", "phone": "8 926 986-44-44", "website": "http://www.topgunbarbershop.ru/", "addr:street": "Ленина", "addr:housenumber": "1"}},
            {"type": "node", "id": 3, "tags": {"name": "TopGun", "phone": "+7 999 111 22 33", "website": "https://topgunbarbershop.ru", "addr:street": "Арбат", "addr:housenumber": "5"}},
        ]
        with patch("parser.geocode", AsyncMock(return_value=(55.5, 37.3, 56.0, 38.0))), patch(
            "parser.overpass", AsyncMock(return_value=elements)
        ), patch(
            "parser.analyze_site",
            AsyncMock(side_effect=lambda _session, url, *_args: {
                "status": "weak", "final_url": url, "reasons": ["нет HTTPS"],
                "contacts": {}, "checks": {"https": False},
            }),
        ) as check_site, patch("parser.analysis.TelegramChecker.exists", AsyncMock(return_value=True)):
            result = await run_search("RU", "Москва", 0, "", "both", 10)
        self.assertEqual(len(result), 2)
        self.assertEqual(check_site.await_count, 2)

    async def test_previous_search_lead_is_excluded_by_identity(self):
        elements = [
            {"type": "node", "id": 10, "tags": {"name": "TopGun", "phone": "+7 926 986 44 44", "website": "https://topgunbarbershop.ru"}},
            {"type": "way", "id": 11, "tags": {"name": "TOPGUN", "phone": "8 926 986-44-44", "website": "http://www.topgunbarbershop.ru/"}},
        ]
        existing = [lead("node/1")]
        with patch("parser.geocode", AsyncMock(return_value=(55.5, 37.3, 56.0, 38.0))), patch(
            "parser.overpass", AsyncMock(return_value=elements)
        ), patch("parser.analyze_site", AsyncMock()) as check_site:
            result = await run_search(
                "RU", "Казань", 0, "", "both", 10,
                exclude_keys=set(), exclude_leads=existing,
            )
        self.assertEqual(result, [])
        check_site.assert_not_awaited()


class DatabaseDedupeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="parsercc-db-test-")
        self.original_db_path = db.DB_PATH
        db.DB_PATH = Path(self.temp.name) / "test.sqlite"
        await db.init()

    async def asyncTearDown(self):
        db.DB_PATH = self.original_db_path
        self.temp.cleanup()

    async def test_save_leads_ignores_same_business_with_different_osm_keys(self):
        saved = await db.save_leads(10, [lead("node/1"), lead("way/2", name="TOPGUN")])
        self.assertEqual(saved, 1)
        self.assertEqual(len(await db.list_leads(10, "all", 100)), 1)

    async def test_different_known_branches_are_both_saved(self):
        saved = await db.save_leads(
            11,
            [
                lead("node/1"),
                lead("node/2", phone="+7 999 111 22 33", street="Арбат", house="5",
                     email="arbat@topgun.example", site="https://arbat-topgun.ru/"),
            ],
        )
        self.assertEqual(saved, 2)

    async def test_startup_migration_merges_existing_duplicates_and_keeps_status(self):
        connection = await db.conn()
        try:
            records = [lead("node/1"), lead("way/2", name="TOPGUN")]
            records[1]["contacts"]["vk"] = "topgun"
            records[1]["status"] = "client"
            for record in records:
                await connection.execute(
                    """INSERT INTO leads(
                        user_id, osm_key, name, country, city, phone, site, site_url,
                        reasons, contacts, hot, status, created_at
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (12, record["osm_key"], record["name"], record["country"],
                     record["city"], record["phone"], record["site"], record["site_url"],
                     json.dumps(record["reasons"]), json.dumps(record["contacts"]),
                     record["hot"], record.get("status", "new"), 100),
                )
            await connection.commit()
        finally:
            await connection.close()

        await db.init()
        rows = await db.list_leads(12, "all", 100)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "client")
        self.assertEqual(rows[0]["c"].get("vk"), "topgun")


if __name__ == "__main__":
    unittest.main()
