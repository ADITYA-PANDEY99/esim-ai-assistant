import unittest
import os
from chatbot.image_handler import safe_process_image, validate_and_clean_vlm_json, MAX_IMAGE_BYTES

class TestImageSecurity(unittest.TestCase):
    def test_file_not_found_handling(self):
        res = safe_process_image("non_existent_file.png")
        self.assertFalse(res["success"])
        self.assertIn("not found", res["error"].lower())

    def test_vlm_json_validation_keys(self):
        raw = '{"vision_summary": "Active low-pass filter", "components": ["R1", "C1", "R1"]}'
        cleaned = validate_and_clean_vlm_json(raw)
        self.assertIn("vision_summary", cleaned)
        self.assertIn("component_counts", cleaned)
        # Check deduplication (Defect 9)
        self.assertEqual(cleaned["components"], ["R1", "C1"])
        # Check fallback count calculation (Defect 10)
        self.assertEqual(cleaned["component_counts"]["R"], 1)
        self.assertEqual(cleaned["component_counts"]["C"], 1)

if __name__ == "__main__":
    unittest.main()
