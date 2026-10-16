import unittest
from src.core.updater import parse_version_tuple


class TestUpdater(unittest.TestCase):
    def test_parse_version_tuple(self):
        self.assertEqual(parse_version_tuple("0.1.0"), (0, 1, 0))
        self.assertEqual(parse_version_tuple("v0.2.0"), (0, 2, 0))
        self.assertEqual(parse_version_tuple("v1.0.0-dev.1"), (1, 0, 0))
        self.assertTrue(parse_version_tuple("v0.2.1") > parse_version_tuple("0.2.0"))
        self.assertTrue(parse_version_tuple("0.2.1A") > parse_version_tuple("0.2.0"))
        self.assertTrue(parse_version_tuple("0.2.1B") > parse_version_tuple("0.2.1A"))
        self.assertTrue(parse_version_tuple("0.3.0") > parse_version_tuple("0.2.9"))
        self.assertFalse(parse_version_tuple("0.2.0") > parse_version_tuple("0.2.0"))


if __name__ == "__main__":
    unittest.main()
