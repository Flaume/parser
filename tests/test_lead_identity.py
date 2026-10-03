import unittest

from lead_identity import LeadIdentityIndex, same_business


class LeadIdentityTests(unittest.TestCase):
    def test_osm_export_duplicate_is_same_business(self):
        first = {
            "osm_key": "node/17",
            "name": "TopGun",
            "country": "RU",
            "city": "Москва",
            "phone": "+7 926 986 44 44",
            "site_url": "http://topgunbarbershop.ru/",
            "contacts": {},
        }
        duplicate = {
            "osm_key": "way/84",
            "name": "TOPGUN",
            "country": "RU",
            "city": "Москва",
            "phone": "8 (926) 986-44-44",
            "site_url": "https://www.topgunbarbershop.ru/contact",
            "contacts": {},
        }
        self.assertTrue(same_business(first, duplicate))

    def test_known_separate_branches_are_not_merged(self):
        first = {
            "name": "TopGun",
            "country": "RU",
            "phone": "+7 926 986 44 44",
            "site_url": "https://topgunbarbershop.ru",
            "contacts": {"address": "Тверская, 1"},
        }
        branch = {
            "name": "TopGun",
            "country": "RU",
            "phone": "+7 926 986 44 44",
            "site_url": "https://topgunbarbershop.ru",
            "contacts": {"address": "Арбат, 5"},
        }
        self.assertFalse(same_business(first, branch))

    def test_same_name_and_normalized_address_match(self):
        first = {
            "name": "Студия красоты",
            "country": "RU",
            "contacts": {"address": "ул. Ленина, 10"},
            "phone": "+7 900 111-22-33",
        }
        duplicate = {
            "name": "СТУДИЯ-КРАСОТЫ",
            "country": "RU",
            "contacts": {"address": "УЛ ЛЕНИНА 10"},
            "phone": "+7 900 999-88-77",
        }
        self.assertTrue(same_business(first, duplicate))

    def test_common_name_without_shared_contacts_is_not_enough(self):
        first = {"name": "Салон красоты", "country": "RU", "city": "Москва"}
        other = {"name": "Салон красоты", "country": "RU", "city": "Казань"}
        self.assertFalse(same_business(first, other))

    def test_identity_index_finds_duplicates_but_retains_distinct_branch(self):
        first = {
            "name": "TopGun",
            "country": "RU",
            "phone": "+7 926 986 44 44",
            "site_url": "https://topgunbarbershop.ru",
        }
        index = LeadIdentityIndex([first])
        duplicate = {
            "name": "TOPGUN",
            "country": "RU",
            "phone": "8 926 986-44-44",
            "site_url": "http://www.topgunbarbershop.ru/",
        }
        branch = {
            **duplicate,
            "contacts": {"address": "ул. Ленина, 3"},
        }
        first["contacts"] = {"address": "ул. Ленина, 1"}
        index.add(first)
        self.assertIs(index.find_duplicate(duplicate), first)
        self.assertIsNone(index.find_duplicate(branch))


if __name__ == "__main__":
    unittest.main()
