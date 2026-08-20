import unittest
from chatbot.Appconfig import _deep_merge, _DEFAULT_CONFIG

class TestConfig(unittest.TestCase):
    def test_deep_merge_preserves_defaults(self):
        custom = {"num_ctx": 8192, "new_field": "test"}
        merged = _deep_merge(_DEFAULT_CONFIG, custom)
        self.assertEqual(merged["num_ctx"], 8192)
        self.assertEqual(merged["repeat_penalty"], 1.15)
        self.assertEqual(merged["new_field"], "test")

if __name__ == "__main__":
    unittest.main()
