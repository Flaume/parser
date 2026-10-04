"""Проверки новых требований: глобальная уникальность, пробный доступ, источники,
анализ сайтов, честность данных, скрипты, спрос по нишам, админка и бот."""

import asyncio
import json
import socket
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import aiohttp

import analysis
import api
import db
import geoapify
import niches as niches_mod
import parser as search
import scripts
from lead_identity import claim_tokens
from parser import GeoError, run_search


def make_lead(key, *, name="Barber One", phone="+7 926 111 22 33", tg="", city="Москва", site="none"):
    contacts = {"address": "Ленина, 1"}
    if tg:
        contacts["tg"] = tg
    return {
        "osm_key": key, "name": name, "country": "RU", "city": city, "phone": phone,
        "site": site, "site_url": "", "reasons": ["сайта нет"], "contacts": contacts,
        "need": "site_bot", "explain": "Сайт отсутствует.", "hot": 70, "source": "osm",
        "info": {"niche": "Барбершопы", "lat": 55.75, "lon": 37.61},
        "lat": 55.75, "lon": 37.61,
    }



def setUpModule():
    # Без сети: страницы ВК и Instagram в тестах считаем существующими.
    global _social_patch
    from unittest.mock import AsyncMock as _AM, patch as _patch
    _social_patch = _patch("analysis.SocialChecker.exists", _AM(return_value=True))
    _social_patch.start()
    # Эти тесты проверяют режим с анализом сайтов; быстрый режим проверяется отдельно.
    global _analyze_patch
    _analyze_patch = _patch("parser.ANALYZE_SITES", True)
    _analyze_patch.start()


def tearDownModule():
    _social_patch.stop()
    _analyze_patch.stop()

class TempDB(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="parsercc-v2-")
        self.original = db.DB_PATH
        db.DB_PATH = Path(self.temp.name) / "t.sqlite"
        await db.init()

    async def asyncTearDown(self):
        db.DB_PATH = self.original
        self.temp.cleanup()


def osm(id_, **tags):
    return {"type": "node", "id": id_, "lat": 55.75, "lon": 37.61,
            "tags": {"name": tags.pop("name", f"Барбер {id_}"), **tags}}


def weak_site(_session, url, *_args):
    return {"status": "weak", "final_url": url, "reasons": ["нет HTTPS"], "contacts": {},
            "checks": {"https": False, "booking": ""}}


class SearchPatches:
    def patches(self, elements, geo=None, geo_error=None, osm_error=None):
        overpass = AsyncMock(side_effect=osm_error) if osm_error else AsyncMock(return_value=elements)
        geo_mock = AsyncMock(side_effect=geo_error) if geo_error else AsyncMock(return_value=geo or [])
        return [
            patch("parser.GOOGLE_PLACES_API_KEY", ""),
            patch("parser.GEOAPIFY_API_KEY", "geo-key" if (geo is not None or geo_error) else ""),
            patch("parser.geocode", AsyncMock(return_value=(55.5, 37.3, 56.0, 38.0))),
            patch("parser.overpass", overpass),
            patch("parser.geoapify.search", geo_mock),
            patch("parser.analyze_site", AsyncMock(side_effect=weak_site)),
            patch("parser.analysis.TelegramChecker.exists", AsyncMock(return_value=True)),
        ]

    async def search(self, elements, mode="both", count=10, **kwargs):
        patchers = self.patches(elements, kwargs.pop("geo", None), kwargs.pop("geo_error", None),
                                kwargs.pop("osm_error", None))
        for item in patchers:
            item.start()
        try:
            return await run_search("RU", "Москва", 0, "", mode, count, **kwargs)
        finally:
            for item in reversed(patchers):
                item.stop()


def geo_feature(osm_id, name, phone="", website=""):
    return {"properties": {
        "name": name, "country_code": "ru", "city": "Москва", "lat": 55.7501, "lon": 37.6101,
        "formatted": "Ленина 1", "address_line2": "Ленина 1, Москва", "place_id": f"pid{osm_id}",
        "website": website, "contact": {"phone": phone},
        "datasource": {"sourcename": "openstreetmap", "raw": {"osm_id": osm_id, "osm_type": "n", "phone": phone}},
    }}


class UniqueAssignmentTests(TempDB, SearchPatches):
    async def test_same_business_found_five_times_becomes_one_lead(self):
        elements = [
            osm(1, name="Barber One", phone="+7 926 111 22 33"),
            osm(2, name="BARBER ONE", phone="8 (926) 111-22-33"),
            osm(3, name="Barber One", **{"contact:phone": "+79261112233"}),
            osm(4, name="Barber-One", phone="8 926 111 22 33"),
        ]
        geo = [geo_feature(5, "Barber One", phone="+7 926 111-22-33")]
        result = await self.search(elements, geo=geo)
        self.assertEqual(len(result), 1)

    async def test_lead_given_to_a_is_never_given_to_b(self):
        elements = [osm(1, phone="+7 926 111 22 33"), osm(2, phone="+7 926 222 33 44")]
        first = await self.search(elements, exclude_tokens=db.taken_tokens)
        claimed_a = await db.claim_leads(1001, first)
        self.assertEqual(len(claimed_a), 2)
        again = await self.search(
            [osm(7, name="Совсем другое имя", phone="8 926 111-22-33")], exclude_tokens=db.taken_tokens
        )
        self.assertEqual(again, [])
        self.assertEqual(await db.claim_leads(1002, first), [])
        self.assertEqual(len(await db.list_leads(1002)), 0)

    async def test_repeat_search_never_returns_old_leads(self):
        elements = [osm(i, phone=f"+7 926 111 22 {i:02d}") for i in range(10, 16)]
        first = await self.search(elements, count=3, exclude_tokens=db.taken_tokens)
        await db.claim_leads(1, first)
        second = await self.search(elements, count=3, exclude_tokens=db.taken_tokens)
        await db.claim_leads(1, second)
        self.assertEqual(len(first), 3)
        self.assertEqual(len(second), 3)
        self.assertFalse({lead["osm_key"] for lead in first} & {lead["osm_key"] for lead in second})
        third = await self.search(elements, count=3, exclude_tokens=db.taken_tokens)
        self.assertEqual(third, [])

    async def test_100_concurrent_claims_give_one_owner(self):
        lead = make_lead("node/42")
        results = await asyncio.gather(*(db.claim_leads(uid, [dict(lead)]) for uid in range(1, 101)))
        winners = [uid for uid, claimed in zip(range(1, 101), results) if claimed]
        self.assertEqual(len(winners), 1)
        connection = await db.conn()
        try:
            rows = await (await connection.execute("SELECT COUNT(*) AS n FROM leads")).fetchone()
        finally:
            await connection.close()
        self.assertEqual(rows["n"], 1)

    async def test_100_concurrent_overlapping_searches_have_no_duplicates(self):
        pool = [make_lead(f"node/{i}", name=f"Biz {i}", phone=f"+7 926 300 {i:02d} {i:02d}") for i in range(30)]

        async def user(uid):
            batch = [dict(pool[(uid * 7 + step) % 30]) for step in range(10)]
            return await db.claim_leads(uid, batch)

        await asyncio.gather(*(user(uid) for uid in range(1, 101)))
        connection = await db.conn()
        try:
            rows = await (await connection.execute("SELECT osm_key, phone FROM leads")).fetchall()
        finally:
            await connection.close()
        self.assertEqual(len(rows), 30)
        self.assertEqual(len({row["osm_key"] for row in rows}), 30)
        self.assertEqual(len({row["phone"] for row in rows}), 30)

    async def test_blacklisted_business_is_never_given(self):
        lead = make_lead("node/9", phone="+7 926 999 00 11")
        await db.block_tokens({"phone:79269990011"}, "Не звонить")
        self.assertEqual(await db.claim_leads(5, [lead]), [])
        result = await self.search([osm(9, phone="+7 926 999 00 11")], exclude_tokens=db.taken_tokens)
        self.assertEqual(result, [])
        await db.unblock("Не звонить")
        self.assertEqual(len(await db.claim_leads(5, [lead])), 1)

    async def test_chain_with_shared_tg_is_one_contact(self):
        a = make_lead("node/1", phone="+7 926 000 00 01", tg="@chainbarber")
        b = make_lead("node/2", name="Chain 2", phone="+7 926 000 00 02", tg="@chainbarber")
        self.assertEqual(len(await db.claim_leads(1, [a])), 1)
        self.assertEqual(await db.claim_leads(2, [b]), [])

    def test_social_hosts_are_not_domain_tokens(self):
        tokens = claim_tokens({"name": "X", "site_url": "https://vk.com/x", "contacts": {}})
        self.assertFalse(any(token.startswith("domain:") for token in tokens))
        tokens = claim_tokens({"name": "X", "site_url": "https://barber-x.ru/", "contacts": {}})
        self.assertIn("domain:barber-x.ru", tokens)


class SourceIsolationTests(TempDB, SearchPatches):
    async def test_osm_failure_does_not_break_search_when_geoapify_works(self):
        errors = AsyncMock()
        result = await self.search(
            [], osm_error=GeoError("Overpass HTTP 504"),
            geo=[geo_feature(77, "Fade Barber Studio", phone="+7 926 555 44 33")],
            on_source_error=errors,
        )
        self.assertEqual([lead["name"] for lead in result], ["Fade Barber Studio"])
        self.assertEqual(result[0]["source"], "geoapify")
        self.assertEqual(errors.await_args.args[0], "osm")

    async def test_geoapify_failure_does_not_break_search(self):
        errors = AsyncMock()
        result = await self.search(
            [osm(1, phone="+7 926 111 22 33")],
            geo_error=geoapify.SourceError("Geoapify HTTP 401"), on_source_error=errors,
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(errors.await_args.args[0], "geoapify")

    async def test_all_sources_down_gives_clear_error(self):
        with self.assertRaises(GeoError) as caught:
            await self.search([], osm_error=GeoError("down"), geo_error=geoapify.SourceError("down"))
        self.assertIn("недоступны", str(caught.exception))

    async def test_errors_are_logged_for_admin(self):
        await db.log_source_error("osm", "HTTP 504")
        errors = await db.source_errors()
        self.assertEqual(errors["recent"][0]["provider"], "osm")
        self.assertEqual(errors["day"]["osm"], 1)

    def test_geoapify_candidate_uses_osm_tags_and_link(self):
        candidate = geoapify.to_candidate(geo_feature(12, "Barber", phone="+7 926 1"), "RU", "Москва")
        self.assertEqual(candidate["key"], "node/12")
        self.assertEqual(candidate["source_url"], "https://www.openstreetmap.org/node/12")
        self.assertIsNone(geoapify.to_candidate(geo_feature(13, "Nails"), "RU", "", "барбер|barber"))


class FakeResponse:
    def __init__(self, status=200, body="", url="https://site.example/", headers=None):
        self.status = status
        self._body = body.encode()
        self.url = url
        self.headers = headers or {}
        self.charset = "utf-8"
        self.content = SimpleNamespace(read=AsyncMock(return_value=self._body))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False


class FakeSession:
    def __init__(self, responses):
        self.responses = responses

    def get(self, url, **_kwargs):
        item = self.responses.get(url.split("?")[0], self.responses.get("*"))
        if isinstance(item, BaseException):
            raise item
        return item


GOOD_PAGE = """<html><head><meta name="viewport" content="width=device-width"></head><body>
<h1>Барбершоп Фейд</h1>""" + ("<p>Стрижки, бороды, уход. Мастера с опытом.</p>" * 20) + """
<a href="tel:+79261112233">+7 926 111-22-33</a>
<a href="https://t.me/fade_booking_bot">Записаться в боте</a>
<a href="https://n.yclients.com/company/1">Онлайн-запись</a>
<form><input type="tel" name="phone"><button>Отправить</button></form>
<footer>© 2025 Фейд</footer></body></html>"""


class SiteAnalysisTests(unittest.IsolatedAsyncioTestCase):
    async def run_site(self, responses, url="https://site.example/"):
        with patch("parser._checked_url", AsyncMock(side_effect=lambda u: u)):
            return await search.analyze_site(FakeSession(responses), url, "RU")

    async def test_good_site_detects_booking_form_bot_and_contacts(self):
        result = await self.run_site({"*": FakeResponse(body=GOOD_PAGE)})
        self.assertEqual(result["status"], "ok")
        checks = result["checks"]
        self.assertEqual(checks["booking"], "YCLIENTS")
        self.assertTrue(checks["form"])
        self.assertTrue(checks["mobile"])
        self.assertTrue(checks["https"])
        self.assertEqual(checks["tg_bot"], "@fade_booking_bot")
        self.assertEqual(result["contacts"]["phone"], "+79261112233")
        self.assertEqual(analysis.classify("ok", [], True), "")

    async def test_weak_site_reasons(self):
        page = "<html><body>" + "<p>Мы работаем</p>" * 40 + "© 2017</body></html>"
        result = await self.run_site({"*": FakeResponse(body=page, url="http://old.example/")}, "http://old.example/")
        self.assertEqual(result["status"], "weak")
        joined = " ".join(result["reasons"])
        for reason in ("нет HTTPS", "не адаптирован под телефон", "не обновлялся с 2017", "нет онлайн-записи"):
            self.assertIn(reason, joined)
        self.assertEqual(analysis.classify("weak", result["reasons"], False), "redesign")

    async def test_unavailable_sites_are_handled_honestly(self):
        async def run(error=None, status=None):
            response = FakeResponse(status=status or 200)
            with patch("parser._checked_url", AsyncMock(side_effect=error or (lambda u: u))):
                return await search.analyze_site(FakeSession({"*": response}), "https://x.example/", "RU")

        dns = await run(error=search.DNSFailure("x.example"))
        self.assertEqual(dns["status"], "broken")
        self.assertEqual(dns["final_url"], "")
        timeout = await run(error=asyncio.TimeoutError())
        self.assertEqual(timeout["status"], "unknown")
        blocked = await run(status=403)
        self.assertEqual(blocked["status"], "unknown")
        missing = await run(status=404)
        self.assertEqual(missing["status"], "broken")

    async def test_unverifiable_site_lead_is_skipped(self):
        elements = [osm(1, phone="+7 926 111 22 33", website="https://slow.example")]
        with patch("parser.GOOGLE_PLACES_API_KEY", ""), patch("parser.GEOAPIFY_API_KEY", ""), patch(
            "parser.geocode", AsyncMock(return_value=(55.5, 37.3, 56.0, 38.0))
        ), patch("parser.overpass", AsyncMock(return_value=elements)), patch(
            "parser.analyze_site",
            AsyncMock(return_value={"status": "unknown", "final_url": "https://slow.example/",
                                    "reasons": ["сайт не ответил вовремя — не удалось проверить"],
                                    "contacts": {}, "checks": {}}),
        ):
            result = await run_search("RU", "Москва", 0, "", "all", 5)
        self.assertEqual(result, [])

    async def test_dead_telegram_link_is_not_shown(self):
        elements = [osm(1, phone="+7 926 111 22 33", **{"contact:telegram": "@gone_barber"})]
        with patch("parser.GOOGLE_PLACES_API_KEY", ""), patch("parser.GEOAPIFY_API_KEY", ""), patch(
            "parser.geocode", AsyncMock(return_value=(55.5, 37.3, 56.0, 38.0))
        ), patch("parser.overpass", AsyncMock(return_value=elements)), patch(
            "parser.analysis.TelegramChecker.exists", AsyncMock(return_value=False)
        ):
            result = await run_search("RU", "Москва", 0, "", "none", 5)
        self.assertEqual(len(result), 1)
        self.assertNotIn("tg", result[0]["contacts"])

    async def test_bad_contacts_do_not_break_search(self):
        elements = [
            osm(1, phone="abc; +7", website="javascript:alert(1)", email="x@y",
                **{"contact:vk": "https://", "contact:telegram": "https://", "contact:instagram": "p",
                   "contact:whatsapp": "wa.me/abc"}),
            osm(2, phone="+7 926 111 22 33", website="http://[::1]/", **{"contact:facebook": "sharer.php"}),
            osm(3, phone="0000000"),
        ]
        result = await self.search_plain(elements)
        self.assertEqual([lead["name"] for lead in result], ["Барбер 2"])
        self.assertNotIn("fb", result[0]["contacts"])

    async def search_plain(self, elements):
        with patch("parser.GOOGLE_PLACES_API_KEY", ""), patch("parser.GEOAPIFY_API_KEY", ""), patch(
            "parser.geocode", AsyncMock(return_value=(55.5, 37.3, 56.0, 38.0))
        ), patch("parser.overpass", AsyncMock(return_value=elements)), patch(
            "parser.analysis.TelegramChecker.exists", AsyncMock(return_value=True)
        ):
            return await run_search("RU", "Москва", 0, "", "all", 5)

    async def test_telegram_checker_reads_public_page(self):
        session = FakeSession({
            "https://t.me/real_barber": FakeResponse(body='<div class="tgme_page_title">Real</div>'),
            "https://t.me/missing_barber": FakeResponse(body="<div>If you have Telegram</div>"),
            "https://t.me/slow_barber": asyncio.TimeoutError(),
        })
        checker = analysis.TelegramChecker(session)
        self.assertTrue(await checker.exists("@real_barber"))
        self.assertFalse(await checker.exists("@missing_barber"))
        self.assertIsNone(await checker.exists("@slow_barber"))

    async def test_social_checker_drops_deleted_pages(self):
        from unittest.mock import patch as _p
        session = FakeSession({
            "https://vk.com/live_salon": FakeResponse(body="<html><title>Салон</title></html>"),
            "https://vk.com/gone_salon": FakeResponse(status=404),
            "https://www.instagram.com/old_nails/": FakeResponse(body="<p>Sorry, this page isn't available.</p>"),
            "https://www.instagram.com/new_nails/": FakeResponse(body='<title>Nails (@new_nails)</title>'),
            "https://www.instagram.com/wall/": FakeResponse(body="<title>Login</title>"),
        })
        _social_patch.stop()
        try:
            checker = analysis.SocialChecker(session)
            self.assertTrue(await checker.exists("vk", "live_salon"))
            self.assertFalse(await checker.exists("vk", "gone_salon"))
            self.assertFalse(await checker.exists("ig", "old_nails"))
            self.assertTrue(await checker.exists("ig", "new_nails"))
            self.assertIsNone(await checker.exists("ig", "wall"))
        finally:
            _social_patch.start()

    def test_priority_explanation_matches_spec_example(self):
        lead = {"site": "none", "need": "site_bot", "phone": "+7 926 111-22-33",
                "contacts": {"ig": "barber"}, "info": {}, "reasons": ["сайта нет"]}
        score, text = analysis.priority(lead)
        self.assertTrue(0 <= score <= 100)
        self.assertEqual(text, "Сайт отсутствует, есть телефон и Instagram, Telegram-бот не найден.")
        weak = dict(lead, site="weak", need="weak", reasons=["нет HTTPS"])
        self.assertLess(analysis.priority(weak)[0], score)

    def test_modes_filter_by_need(self):
        self.assertEqual(search.MODE_SITES["bot"], {"ok"})
        self.assertEqual(analysis.classify("none", ["сайта нет"], False), "site_bot")
        self.assertEqual(analysis.classify("broken", ["ошибка 500"], False), "broken")
        self.assertEqual(analysis.classify("ok", [], False), "bot")


class CountryTests(unittest.TestCase):
    def test_every_country_has_cities_and_valid_query(self):
        import countries
        for item in countries.public_list():
            self.assertTrue(item["cities"], item["code"])
            query = search.build_query(None, 0, "", country=item["code"], result_limit=100)
            self.assertIn(item["code"], query)

    def test_name_regex_finds_both_letter_cases(self):
        self.assertEqual(search.first_letter_both_cases("барбер|nail"), "[Бб]арбер|[Nn]ail")
        query = search.build_query((1, 2, 3, 4), 5, "Шиномонтаж!")
        self.assertIn('"[Шш]иномонтаж"', query)

    def test_phones_of_each_country(self):
        import contacts as cn
        samples = {
            "RU": "8 (926) 111-22-33", "UA": "+380 44 123 4567", "BY": "+375 29 123-45-67",
            "KZ": "+7 701 123 4567", "UZ": "+998 90 123 45 67", "KG": "+996 555 123 456",
            "AM": "+374 10 123456", "AZ": "+994 12 345 67 89", "GE": "+995 32 212 3456",
            "MD": "+373 22 123456", "PL": "22 123 45 67", "LT": "+370 5 212 3456",
            "DE": "030 12345678", "AE": "04 331 4567",
        }
        for country, raw in samples.items():
            self.assertTrue(cn.phone(raw, country)[0], (country, raw))

    def test_foreign_scripts_ask_for_local_language(self):
        self.assertIn("польском", scripts.lead_prompt({"name": "X", "country": "PL", "site": "none"}, "first"))
        self.assertIn("по-русски", scripts.lead_prompt({"name": "X", "country": "KZ", "site": "none"}, "first"))


class DemandAndScriptTests(TempDB):
    async def test_demand_needs_enough_data(self):
        for i in range(10):
            await db.record_analyzed(make_lead(f"node/{i}", phone=f"+7 926 400 00 {i:02d}"))
        self.assertEqual(await db.niche_demand(min_sample=30), [])
        for i in range(10, 40):
            lead = make_lead(f"node/{i}", phone=f"+7 926 400 00 {i:02d}", site="weak" if i % 2 else "none")
            await db.record_analyzed(lead)
        items = await db.niche_demand(min_sample=30)
        self.assertEqual(items[0]["niche"], "Барбершопы")
        self.assertEqual(items[0]["total"], 40)
        self.assertEqual(items[0]["no_bot"], 100)
        self.assertEqual(items[0]["no_site"] + items[0]["weak"], 100)

    async def test_every_niche_has_five_scripts(self):
        await db.seed_scripts(scripts.defaults())
        await db.seed_scripts(scripts.defaults())
        rows = await db.list_scripts(1)
        by_niche = {}
        for row in rows:
            by_niche.setdefault(row["niche"], set()).add(row["kind"])
        self.assertEqual(len(by_niche), 35)
        for kinds in by_niche.values():
            self.assertEqual(kinds, set(scripts.KINDS))
        self.assertEqual(len(rows), 175)

    async def test_user_edits_own_copy_and_template_uses_lead_data(self):
        script_id = await db.save_script(7, 0, "first", "Мой", "Текст")
        self.assertTrue(any(row["own"] for row in await db.list_scripts(7, 0)))
        self.assertFalse(any(row["own"] for row in await db.list_scripts(8, 0)))
        self.assertFalse(await db.delete_script(8, script_id))
        lead = db.lead_row  # noqa: F841 (just to make sure attribute exists)
        text = scripts.template_for_lead(
            {"name": "Фейд", "site": "weak", "reasons": ["нет HTTPS"], "info": {"niche": "Барбершопы"}},
            "first",
        )
        self.assertIn("«Фейд»", text)
        self.assertIn("нет HTTPS", text)
        detailed = scripts.template_for_lead({"name": "Фейд", "site": "none", "info": {"niche": "Барбершопы"}}, "detailed")
        self.assertIn("своего сайта нет", detailed)
        self.assertNotIn("[что нашли", detailed)

    async def test_gemini_response_is_parsed(self):
        class Session:
            def post(self, url, **kwargs):
                self.url = url
                self.kwargs = kwargs
                return FakeJson(200, {"candidates": [{"content": {"parts": [{"text": "**Здравствуйте!** Текст скрипта для бизнеса."}]}}]})

        session = Session()
        text = await scripts.gemini("KEY", "gemini-3.5-flash-lite", "prompt", session=session)
        self.assertEqual(text, "Здравствуйте! Текст скрипта для бизнеса.")
        self.assertIn("gemini-3.5-flash-lite:generateContent", session.url)
        self.assertEqual(session.kwargs["headers"]["x-goog-api-key"], "KEY")

    async def test_ai_falls_back_to_template(self):
        with patch("api.AI_ENABLED", False):
            text, note = await api._ai_text(1, "prompt")
        self.assertEqual(text, "")
        self.assertEqual(note, "no_ai")
        with patch("api.AI_ENABLED", True), patch(
            "api.scripts.complete", AsyncMock(side_effect=scripts.AIError("AI HTTP 429: quota"))
        ):
            text, note = await api._ai_text(1, "prompt")
        self.assertEqual(text, "")
        self.assertEqual((await db.source_errors())["recent"][0]["provider"], "ai")

    async def test_openai_compatible_provider_and_order(self):
        class Session:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                return False
            def post(self, url, **kwargs):
                self.url = url
                self.kwargs = kwargs
                return FakeJson(200, {"choices": [{"message": {"content": "<think>x</think>Здравствуйте! Текст для бизнеса."}}]})

        session = Session()
        text = await scripts.openai_compatible("KEY", "https://api.deepseek.com", "deepseek-chat", "prompt", session=session)
        self.assertEqual(text, "Здравствуйте! Текст для бизнеса.")
        self.assertEqual(session.url, "https://api.deepseek.com/chat/completions")
        self.assertEqual(session.kwargs["headers"]["Authorization"], "Bearer KEY")
        # сначала DeepSeek/Groq, при ошибке — Gemini
        with patch("config.AI_API_KEY", "a"), patch("config.GEMINI_API_KEY", "g"), patch(
            "scripts.openai_compatible", AsyncMock(side_effect=scripts.AIError("AI HTTP 402"))
        ), patch("scripts.gemini", AsyncMock(return_value="Текст от запасной нейросети")):
            self.assertEqual(await scripts.complete("p"), "Текст от запасной нейросети")


class FakeJson:
    def __init__(self, status, data):
        self.status = status
        self.data = data

    async def json(self, content_type=None):
        return self.data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False


class AccessTests(TempDB):
    async def test_trial_allows_exactly_one_search(self):
        await db.upsert_user(50, "newbie", "New")
        self.assertTrue(await db.reserve_trial(50, 1))
        self.assertFalse(await db.reserve_trial(50, 1))
        await db.refund_trial(50)
        self.assertTrue(await db.reserve_trial(50, 1))
        await db.add_bonus(50, 2)
        self.assertTrue(await db.reserve_trial(50, 1))
        self.assertTrue(await db.reserve_trial(50, 1))
        self.assertFalse(await db.reserve_trial(50, 1))

    async def test_concurrent_trial_reservations(self):
        await db.upsert_user(51, "fast", "Fast")
        results = await asyncio.gather(*(db.reserve_trial(51, 1) for _ in range(20)))
        self.assertEqual(sum(results), 1)

    async def test_keys_bound_to_user(self):
        await db.upsert_user(60, "alice", "A")
        await db.upsert_user(61, "bob", "B")
        await db.create_key("CC-1", "@Alice", 100, 0, 1)
        self.assertEqual((await db.redeem_key(61, "bob", "CC-1"))[0], "other_user")
        self.assertEqual((await db.redeem_key(60, "alice", "CC-1"))[0], "ok")
        self.assertEqual((await db.redeem_key(60, "alice", "CC-1"))[0], "used")
        user = await db.get_user(60)
        self.assertTrue(db.is_member(user))
        self.assertEqual(user["daily_limit"], 100)
        self.assertEqual((await db.redeem_key(60, "alice", "nope"))[0], "not_found")

    async def test_ban_and_find_by_username(self):
        await db.upsert_user(70, "Spammer", "S")
        found = await db.find_user("@spammer")
        self.assertEqual(found["id"], 70)
        await db.set_banned(70, True)
        await db.create_key("CC-2", "", 50, 0, 1)
        self.assertEqual((await db.redeem_key(70, "spammer", "CC-2"))[0], "banned")


class ApiFlowTests(unittest.TestCase):
    """Полный путь через HTTP API: пробный поиск, лимит 10, сообщение о конце пробы, бан."""

    def setUp(self):
        from fastapi.testclient import TestClient

        self.temp = tempfile.TemporaryDirectory(prefix="parsercc-api-")
        self.original = db.DB_PATH
        db.DB_PATH = Path(self.temp.name) / "api.sqlite"
        self.user = {"id": 900, "username": "tester", "first_name": "Тест"}
        self.leads = [make_lead(f"node/{i}", name=f"Biz {i}", phone=f"+7 926 500 {i:02d} {i:02d}") for i in range(15)]
        self.run_search = AsyncMock(side_effect=lambda *a, **k: self.leads[: a[5]])
        self.notify = AsyncMock()
        self.trial_notify = AsyncMock()
        self.patchers = [
            patch("api.verify_init_data", side_effect=lambda _d: dict(self.user)),
            patch("api.run_search", self.run_search),
            patch("api._notify", self.notify),
            patch("api._notify_trial_over", self.trial_notify),
            patch("api._notify_access", AsyncMock()),
            patch("api._notify_closed", AsyncMock()),
        ]
        for item in self.patchers:
            item.start()
        self.client_cm = TestClient(api.app)
        self.client = self.client_cm.__enter__()

    def tearDown(self):
        self.client_cm.__exit__(None, None, None)
        for item in reversed(self.patchers):
            item.stop()
        db.DB_PATH = self.original
        self.temp.cleanup()

    def wait_job(self, job_id):
        for _ in range(100):
            job = self.client.get(f"/api/jobs/{job_id}", headers={"X-Init-Data": "x"}).json()
            if job["status"] != "running":
                return job
            time.sleep(0.05)
        self.fail("job did not finish")

    def search(self, count=50):
        return self.client.post(
            "/api/search", headers={"X-Init-Data": "x"},
            json={"country": "RU", "city": "Москва", "niche": 0, "flt": "both", "count": count},
        )

    def test_trial_gives_10_leads_then_shows_join_message(self):
        me = self.client.get("/api/me", headers={"X-Init-Data": "x"}).json()
        self.assertEqual(me["access"]["plan"], "trial")
        self.assertEqual(me["access"]["searches_left"], 1)
        self.assertEqual(me["name"], "Тест")
        response = self.search(50)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["count"], 10)
        job = self.wait_job(response.json()["job_id"])
        self.assertEqual(job["found"], 10)
        self.assertEqual(job["trial_over"]["join"], "https://t.me/m/KXcCg7quZGFh")
        self.assertIn("Вы использовали пробный запрос и нашли 10 лидов", job["trial_over"]["message"])
        self.assertEqual(self.run_search.await_args.args[5], 10)
        leads = self.client.get("/api/leads", headers={"X-Init-Data": "x"}).json()["leads"]
        self.assertEqual(len(leads), 10)
        second = self.search(1)
        self.assertEqual(second.status_code, 403)
        detail = second.json()["detail"]
        self.assertEqual(detail["code"], "trial_over")
        self.assertIn("@SUN9ISE", detail["message"])
        self.trial_notify.assert_awaited()

    def test_empty_trial_search_is_not_charged(self):
        self.leads = []
        job = self.wait_job(self.search(10).json()["job_id"])
        self.assertEqual(job["found"], 0)
        me = self.client.get("/api/me", headers={"X-Init-Data": "x"}).json()
        self.assertEqual(me["access"]["searches_left"], 1)

    def test_banned_user_is_blocked(self):
        self.client.get("/api/me", headers={"X-Init-Data": "x"})
        asyncio.run(db.set_banned(900, True))
        response = self.client.get("/api/me", headers={"X-Init-Data": "x"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["code"], "banned")

    def test_admin_tools(self):
        with patch("config.ADMIN_IDS", {900}):
            self.client.get("/api/me", headers={"X-Init-Data": "x"})
            key = self.client.post("/api/admin/keys", headers={"X-Init-Data": "x"},
                                   json={"for_user": "@friend", "limit": 120}).json()
            self.assertTrue(key["code"].startswith("CC-"))
            keys = self.client.get("/api/admin/keys", headers={"X-Init-Data": "x"}).json()["keys"]
            self.assertEqual(keys[0]["for_user"], "friend")
            asyncio.run(db.upsert_user(901, "friend", "Друг"))
            grant = self.client.post("/api/admin/grant", headers={"X-Init-Data": "x"},
                                     json={"query": "@friend", "limit": 150})
            self.assertEqual(grant.status_code, 200, grant.text)
            bonus = self.client.post("/api/admin/users/901/bonus", headers={"X-Init-Data": "x"}, json={"amount": 3})
            self.assertEqual(bonus.json()["bonus"], 3)
            ban = self.client.post("/api/admin/users/901/ban", headers={"X-Init-Data": "x"}, json={"banned": True})
            self.assertEqual(ban.status_code, 200)
            users = self.client.get("/api/admin/users", headers={"X-Init-Data": "x"}).json()["users"]
            friend = next(user for user in users if user["id"] == 901)
            self.assertTrue(friend["banned"])
            self.assertEqual(friend["lim"], 150)
            block = self.client.post("/api/admin/blocked", headers={"X-Init-Data": "x"},
                                     json={"text": "+7 926 777-66-55"})
            self.assertEqual(block.status_code, 200, block.text)
            overview = self.client.get("/api/admin/overview", headers={"X-Init-Data": "x"}).json()
            self.assertIn("niches", overview)
            self.assertIn("errors", overview)
            scripts_list = self.client.get("/api/scripts?niche=0", headers={"X-Init-Data": "x"}).json()
            self.assertEqual(len(scripts_list["scripts"]), 5)
            with patch("api.AI_ENABLED", False):
                demand = self.client.get("/api/demand", headers={"X-Init-Data": "x"}).json()
            self.assertEqual(demand["source"], "base")
            self.assertEqual(len(demand["items"]), 10)
            ai_answer = json.dumps([
                {"niche": spec["title"], "score": 10 - index, "why": "причина", "offer": "сайт"}
                for index, spec in enumerate(niches_mod.NICHES.values())
            ], ensure_ascii=False)
            with patch("api.AI_ENABLED", True), patch("api.scripts.complete", AsyncMock(return_value=ai_answer)):
                demand = self.client.get("/api/demand?country=PL", headers={"X-Init-Data": "x"}).json()
            self.assertEqual(demand["source"], "ai")
            self.assertEqual(demand["items"][0]["niche"], "Барбершопы")

    def test_non_admin_cannot_use_admin_api(self):
        response = self.client.get("/api/admin/users", headers={"X-Init-Data": "x"})
        self.assertEqual(response.status_code, 403)

    def test_lead_script_uses_real_data(self):
        self.user = {"id": 902, "username": "m", "first_name": "M"}
        job = self.wait_job(self.search(3).json()["job_id"])
        self.assertEqual(job["found"], 3)
        lead = self.client.get("/api/leads", headers={"X-Init-Data": "x"}).json()["leads"][0]
        with patch("api.AI_ENABLED", False):
            result = self.client.post(f"/api/leads/{lead['id']}/script", headers={"X-Init-Data": "x"},
                                      json={"kind": "first"}).json()
        self.assertEqual(result["source"], "template")
        self.assertIn(lead["name"], result["text"])
        other = self.client.post("/api/leads/999999/script", headers={"X-Init-Data": "x"}, json={"kind": "first"})
        self.assertEqual(other.status_code, 404)


class BotTests(TempDB):
    def message(self, text, uid=300, username="user300"):
        user = SimpleNamespace(id=uid, username=username, first_name="Иван", full_name="Иван")
        return SimpleNamespace(text=text, from_user=user, answer=AsyncMock())

    async def test_start_gives_everyone_trial_without_admin_spam(self):
        import bot

        with patch("bot.bot.send_message", AsyncMock()) as send:
            message = self.message("/start")
            await bot.start(message)
        text = message.answer.await_args.args[0]
        self.assertIn("Привет, Иван", text)
        self.assertIn("пробный", text)
        send.assert_not_awaited()

    async def test_trial_over_message_and_buttons(self):
        import bot

        with patch("bot.bot.send_photo", AsyncMock(return_value=SimpleNamespace(photo=[]))) as send:
            await bot.send_trial_over(300, 10)
        text = send.await_args.kwargs["caption"]
        self.assertTrue(str(send.await_args.args[1]).endswith("access_closed.jpg") or send.await_args.args[1])
        self.assertIn("<b>Пробный доступ закончился</b>\n\n", text)
        self.assertIn("нашли <b>10 лидов</b>", text)
        self.assertIn("@SUN9ISE", text)
        keyboard = send.await_args.kwargs["reply_markup"].inline_keyboard
        self.assertEqual(keyboard[0][0].text, "Вступить в команду")
        self.assertEqual(keyboard[0][0].url, "https://t.me/m/KXcCg7quZGFh")
        self.assertEqual(keyboard[1][0].url, "https://t.me/SUN9ISE")

    async def test_key_command_and_banned_user(self):
        import bot

        await db.create_key("CC-AAAA", "", 90, 0, 1)
        message = self.message("/key CC-AAAA")
        with patch("bot.bot.send_photo", AsyncMock(return_value=SimpleNamespace(photo=[]))) as photo:
            await bot.key_command(message)
        message.answer.assert_not_awaited()  # всё в одном сообщении с картинкой OPEN
        caption = photo.await_args.kwargs["caption"]
        self.assertIn("<b>Ключ активирован</b>", caption)
        self.assertIn("<b>90 лидов в день</b>", caption)
        self.assertIn("access_open", str(getattr(photo.await_args.args[1], "path", "")))
        await db.set_banned(300, True)
        blocked = self.message("/start")
        with patch("bot.bot.send_photo", AsyncMock(return_value=SimpleNamespace(photo=[]))) as photo:
            await bot.start(blocked)
        blocked.answer.assert_not_awaited()
        self.assertIn("<b>Вы забанены</b>, свяжитесь с @SUN9ISE", photo.await_args.kwargs["caption"])
        self.assertIn("Чтобы узнать причину", photo.await_args.kwargs["caption"])

    async def test_admin_commands(self):
        import bot

        await db.upsert_user(301, "client", "C")
        with patch("config.ADMIN_IDS", {1}), patch("bot.bot.send_message", AsyncMock()), patch(
            "bot.bot.send_photo", AsyncMock(return_value=SimpleNamespace(photo=[]))
        ):
            for text in ("/adduser @client 120", "/bonus @client 2", "/ban @client", "/unban @client", "/newkey @client 80"):
                message = self.message(text, uid=1, username="owner")
                handler = {
                    "adduser": bot.add_user, "bonus": bot.bonus_command, "ban": bot.ban_command,
                    "unban": bot.ban_command, "newkey": bot.newkey_command,
                }[text.split()[0][1:]]
                await handler(message)
                self.assertTrue(message.answer.await_args, text)
        user = await db.get_user(301)
        self.assertEqual(user["approved"], 1)
        self.assertEqual(user["daily_limit"], 120)
        self.assertEqual(user["bonus"], 2)
        self.assertEqual(user["banned"], 0)
        self.assertEqual((await db.list_keys())[0]["for_user"], "client")

    async def test_non_admin_cannot_run_admin_commands(self):
        import bot

        await db.upsert_user(302, "x", "X")
        message = self.message("/adduser 302", uid=302)
        await bot.add_user(message)
        self.assertIn("только для администратора", message.answer.await_args.args[0])
        self.assertIn("302", message.answer.await_args.args[0])
        self.assertEqual((await db.get_user(302))["approved"], 0)


if __name__ == "__main__":
    unittest.main()


class QuickModeTests(unittest.IsolatedAsyncioTestCase):
    """Режим по решению владельца: только бизнесы с телефоном и ссылкой на карточку на карте."""

    async def search(self, elements, count=10):
        with patch("parser.GOOGLE_PLACES_API_KEY", ""), patch("parser.GEOAPIFY_API_KEY", ""), patch(
            "parser.geocode", AsyncMock(return_value=(55.5, 37.3, 56.0, 38.0))
        ), patch("parser.overpass", AsyncMock(return_value=elements)), patch(
            "parser.analyze_site", AsyncMock(side_effect=AssertionError("сайт не должен проверяться"))
        ):
            return await run_search("RU", "Москва", 0, "", "none", count, analyze=False)

    async def test_returns_all_phones_and_business_map_link(self):
        result = await self.search([
            osm(1, name="Море красоты", phone="+7 499 126-00-58; +7 936 105-21-03",
                website="https://more.example", **{"contact:vk": "https://vk.com/more"}),
            osm(2, name="Без телефона", **{"contact:instagram": "nophone"}),
        ])
        self.assertEqual(len(result), 1)
        lead = result[0]
        self.assertEqual(lead["info"]["phones"], ["+7 499 126-00-58", "+7 936 105-21-03"])
        self.assertEqual(lead["phone"], "+7 499 126-00-58")
        self.assertIn("text=", lead["contacts"]["map"])
        self.assertNotIn("vk", lead["contacts"])
        self.assertEqual(lead["site"], "unchecked")

    async def test_second_phone_blocks_duplicate_for_other_user(self):
        tmp = tempfile.TemporaryDirectory()
        original = db.DB_PATH
        db.DB_PATH = Path(tmp.name) / "q.sqlite"
        try:
            await db.init()
            first = await self.search([osm(1, name="A", phone="+7 499 126-00-58; +7 936 105-21-03")])
            self.assertEqual(len(await db.claim_leads(1, first)), 1)
            other = await self.search([osm(2, name="B", phone="+7 936 105-21-03")])
            self.assertEqual(await db.claim_leads(2, other), [])
        finally:
            db.DB_PATH = original
            tmp.cleanup()
