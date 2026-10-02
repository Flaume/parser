import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import contacts as cn
import db
import google_places
from parser import extract_site_contacts, osm_candidate, run_search


class ContactNormalizationTests(unittest.TestCase):
    def test_vk_full_links_keep_the_page_not_https(self):
        for raw, expected in [
            ("https://vk.com/club123456", "club123456"),
            ("http://m.vk.com/barber_spb?w=wall", "barber_spb"),
            ("vk.com/public777", "public777"),
            ("https://vk.ru/topgun.msk", "topgun.msk"),
            ("@salon_lux", "salon_lux"),
            ("salon_lux", "salon_lux"),
        ]:
            self.assertEqual(cn.vk(raw), expected, raw)
        for raw in ("https", "https://", "https://vk.com/", "https://vk.com/share.php?url=x", "https://example.com/vk", "12345"):
            self.assertEqual(cn.vk(raw), "", raw)

    def test_telegram_links(self):
        for raw, expected in [
            ("https://t.me/barber_club", "@barber_club"),
            ("t.me/s/barber_club", "@barber_club"),
            ("@BarberClub", "@BarberClub"),
            ("telegram.me/barberclub/12", "@barberclub"),
        ]:
            self.assertEqual(cn.telegram(raw), expected, raw)
        for raw in ("https://t.me/", "https", "https://t.me/+AbCdEf", "@abc", "https://t.me/joinchat/xyz", "+7 999 123 45 67"):
            self.assertEqual(cn.telegram(raw), "", raw)

    def test_instagram_and_facebook(self):
        self.assertEqual(cn.instagram("https://www.instagram.com/barber.spb/?hl=ru"), "barber.spb")
        self.assertEqual(cn.instagram("@barber_spb"), "barber_spb")
        self.assertEqual(cn.instagram("https://instagram.com/p/Cx12/"), "")
        self.assertEqual(cn.instagram("https"), "")
        self.assertEqual(cn.facebook("https://m.facebook.com/barberwaw/"), "https://www.facebook.com/barberwaw")
        self.assertEqual(cn.facebook("https://www.facebook.com/profile.php?id=10001"), "https://www.facebook.com/profile.php?id=10001")
        self.assertEqual(cn.facebook("https://facebook.com/sharer.php?u=x"), "")

    def test_phones_are_real_numbers_in_international_format(self):
        self.assertEqual(cn.phone("8 (926) 986-44-44", "RU"), ("+79269864444", "+7 926 986-44-44"))
        self.assertEqual(cn.phone("+48 22 628 00 00; +48 600 000 000", "PL")[0], "+48226280000")
        self.assertEqual(cn.phone("+7 985 7635041+7 903 7635041", "RU")[0], "+79857635041")
        self.assertEqual(cn.phone("123-45", "RU"), ("", ""))
        self.assertEqual(cn.phone("+7 000 000 00 00", "RU"), ("", ""))

    def test_whatsapp_and_viber(self):
        self.assertEqual(cn.whatsapp("https://wa.me/79269864444", "RU"), "79269864444")
        self.assertEqual(cn.whatsapp("https://api.whatsapp.com/send?phone=79269864444&text=hi", "RU"), "79269864444")
        self.assertEqual(cn.whatsapp("8 926 986 44 44", "RU"), "79269864444")
        self.assertEqual(cn.whatsapp("https://wa.me/123", "RU"), "")
        self.assertEqual(cn.viber("viber://chat?number=%2B79269864444", "RU"), "79269864444")

    def test_email_filters_image_names_and_placeholders(self):
        self.assertEqual(cn.email("Пишите: Info@Barber.ru."), "info@barber.ru")
        self.assertEqual(cn.email("logo@2x.png"), "")
        self.assertEqual(cn.email("you@example.com"), "")

    def test_map_links(self):
        self.assertTrue(cn.map_link(55.75, 37.61, "X", "RU").startswith("https://yandex.ru/maps/?pt=37.610000,55.750000"))
        self.assertTrue(cn.map_link(52.23, 21.01, "X", "PL").startswith("https://www.google.com/maps/search/?api=1&query=52.230000%2C21.010000"))
        self.assertEqual(cn.map_link(None, None), "")

    def test_clean_contacts_repairs_old_broken_values(self):
        cleaned = cn.clean_contacts({"vk": "https", "tg": "@https", "ig": "barber", "wa": "8926", "address": "Ленина 1"}, "RU")
        self.assertEqual(cleaned, {"ig": "barber", "address": "Ленина 1"})


class SiteContactTests(unittest.TestCase):
    def test_site_links_are_normalized(self):
        body = """<html><body>
          <a href="https://vk.com/club42">ВК</a>
          <a href="https://www.instagram.com/barber.top/">Insta</a>
          <a href="https://t.me/barber_top">TG</a>
          <a href="https://wa.me/79269864444">WA</a>
          <a href="tel:+7 (926) 986-44-44">Позвонить</a>
          <a href="https://vk.com/share.php?url=x">Поделиться</a>
          <img src="logo@2x.png"> info@barber.top
        </body></html>"""
        found = extract_site_contacts(body, "https://barber.top/", "RU")
        self.assertEqual(found["vkg"], "club42")
        self.assertEqual(found["ig"], "barber.top")
        self.assertEqual(found["tg"], "@barber_top")
        self.assertEqual(found["wa"], "79269864444")
        self.assertEqual(found["phone"], "+7 (926) 986-44-44")
        self.assertEqual(found["email"], "info@barber.top")


def osm(id_, **tags):
    return {"type": "node", "id": id_, "lat": 55.75, "lon": 37.61, "tags": {"name": f"Барбер {id_}", **tags}}


class OsmPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def run_osm(self, elements, mode="none", count=10, **kwargs):
        with patch("parser.GOOGLE_PLACES_API_KEY", ""), patch(
            "parser.geocode", AsyncMock(return_value=(55.5, 37.3, 56.0, 38.0))
        ), patch("parser.overpass", AsyncMock(return_value=elements)), patch(
            "parser.analyze_site", AsyncMock(side_effect=lambda _s, url, *_a: {
                "status": "weak", "final_url": url, "reasons": ["нет HTTPS"], "contacts": {}, "checks": {},
            })
        ), patch("parser.analysis.TelegramChecker.exists", AsyncMock(return_value=True)):
            return await run_search("RU", "Москва", 0, "", mode, count, **kwargs)

    async def test_full_vk_link_from_osm_becomes_working_link(self):
        result = await self.run_osm([osm(1, **{"contact:vk": "https://vk.com/barber_one", "phone": "8 926 986 44 44"})])
        self.assertEqual(result[0]["contacts"]["vk"], "barber_one")
        self.assertEqual(result[0]["phone"], "+7 926 986-44-44")
        self.assertTrue(result[0]["contacts"]["map"].startswith("https://yandex.ru/maps/"))

    async def test_leads_without_any_contact_are_skipped(self):
        result = await self.run_osm([
            osm(1),
            osm(2, phone="123"),
            osm(3, **{"contact:vk": "https"}),
            osm(4, **{"contact:telegram": "https://t.me/barber_four"}),
        ])
        self.assertEqual([lead["name"] for lead in result], ["Барбер 4"])

    async def test_closed_businesses_are_skipped(self):
        result = await self.run_osm([
            osm(1, phone="+7 926 111 22 33", **{"disused:shop": "hairdresser"}),
            osm(2, phone="+7 926 111 22 44", opening_hours="closed"),
            osm(3, phone="+7 926 111 22 55"),
        ])
        self.assertEqual([lead["name"] for lead in result], ["Барбер 3"])

    async def test_site_without_contacts_on_page_and_on_map_is_skipped(self):
        result = await self.run_osm([osm(1, website="https://barber.example")], mode="weak")
        self.assertEqual(result, [])

    async def test_same_business_is_not_returned_twice_to_same_user(self):
        first = await self.run_osm([osm(1, phone="+7 926 111 22 33")])
        again = await self.run_osm(
            [osm(9, phone="8 926 111-22-33", name="Барбер 1")],
            exclude_keys={first[0]["osm_key"]}, exclude_leads=first,
        )
        self.assertEqual(again, [])


def gplace(pid, name, phone="+48 600 100 200", site="", status="OPERATIONAL"):
    place = {
        "id": pid, "displayName": {"text": name}, "businessStatus": status,
        "formattedAddress": "ul. Marszałkowska 1, 00-001 Warszawa, Polska",
        "shortFormattedAddress": "Marszałkowska 1",
        "addressComponents": [{"longText": "Warszawa", "types": ["locality", "political"]}],
        "googleMapsUri": f"https://maps.google.com/?cid={pid}",
        "location": {"latitude": 52.23, "longitude": 21.01},
    }
    if phone:
        place["internationalPhoneNumber"] = phone
    if site:
        place["websiteUri"] = site
    return place


class GoogleSourceTests(unittest.IsolatedAsyncioTestCase):
    async def test_google_results_have_phone_map_and_skip_closed(self):
        places = [
            gplace("A1", "Fade Lab", phone="+48 600 100 200"),
            gplace("A2", "Old Barber", status="CLOSED_PERMANENTLY"),
            gplace("A3", "No Contacts", phone=""),
        ]
        with patch("parser.GOOGLE_PLACES_API_KEY", "key"), patch(
            "parser.google_places.text_search", AsyncMock(return_value=places)
        ) as search, patch("parser.overpass", AsyncMock(return_value=[])), patch(
            "parser.geocode", AsyncMock(return_value=(52.0, 20.8, 52.4, 21.3))
        ):
            result = await run_search("PL", "Warszawa", 0, "", "both", 5)
        self.assertEqual([lead["name"] for lead in result], ["Fade Lab"])
        lead = result[0]
        self.assertEqual(lead["osm_key"], "g:A1")
        self.assertEqual(lead["phone"], "+48 600 100 200")
        self.assertEqual(lead["contacts"]["map"], "https://maps.google.com/?cid=A1")
        self.assertEqual(lead["city"], "Warszawa")
        self.assertIn("barber shop Warszawa", search.await_args_list[0].args[2])

    async def test_google_error_falls_back_to_osm(self):
        with patch("parser.GOOGLE_PLACES_API_KEY", "key"), patch(
            "parser.google_places.text_search",
            AsyncMock(side_effect=google_places.GoogleError("HTTP 403")),
        ), patch("parser.geocode", AsyncMock(return_value=(55.5, 37.3, 56.0, 38.0))), patch(
            "parser.overpass", AsyncMock(return_value=[osm(1, phone="+7 926 111 22 33")])
        ):
            result = await run_search("RU", "Москва", 0, "", "none", 5)
        self.assertEqual(len(result), 1)

    async def test_text_search_stops_when_budget_is_spent(self):
        class Session:
            calls = 0
            def post(self, *_a, **_k):
                Session.calls += 1
                raise AssertionError("must not be called")
        budget = AsyncMock(return_value=False)
        places = await google_places.text_search(Session(), "key", "barber", "PL", on_request=budget)
        self.assertEqual(places, [])
        self.assertEqual(Session.calls, 0)

    def test_queries_follow_country_language(self):
        self.assertEqual(google_places.queries_for("RU", 2, "")[0], "автосервис")
        self.assertEqual(google_places.queries_for("DE", 3, "")[0], "dentist")
        self.assertEqual(google_places.queries_for("PL", 5, "kebab"), ["kebab"])


class DatabaseRepairTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="parsercc-db-test-")
        self.original = db.DB_PATH
        db.DB_PATH = Path(self.temp.name) / "t.sqlite"
        await db.init()

    async def asyncTearDown(self):
        db.DB_PATH = self.original
        self.temp.cleanup()

    async def test_old_broken_links_are_repaired_on_start(self):
        connection = await db.conn()
        try:
            await connection.execute(
                """INSERT INTO leads(user_id, osm_key, name, country, city, phone, site, site_url,
                reasons, contacts, hot, status, created_at) VALUES(1,'node/1','X','RU','M','', 'none','',
                '[]', ?, 50, 'new', 1)""",
                (json.dumps({"vk": "https", "tg": "@https", "ig": "ok_name"}),),
            )
            await connection.commit()
        finally:
            await connection.close()
        await db.init()
        rows = await db.list_leads(1, "all", 10)
        self.assertEqual(rows[0]["c"], {"ig": "ok_name"})

    async def test_monthly_google_limit(self):
        self.assertTrue(await db.reserve_api_call("google", 2))
        self.assertTrue(await db.reserve_api_call("google", 2))
        self.assertFalse(await db.reserve_api_call("google", 2))
        self.assertEqual(await db.api_calls_this_month("google"), 2)


if __name__ == "__main__":
    unittest.main()
