"""scripts/i18n/pc_readiness: every locale file has the same keys as en.json.

    python -I tests/test_pc_readiness_i18n.py
"""
import json
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
I18N = os.path.join(ROOT, "scripts", "i18n", "pc_readiness")


class PcReadinessI18nTest(unittest.TestCase):
    def test_locales_match_english_keys(self) -> None:
        master_path = os.path.join(I18N, "en.json")
        with open(master_path, encoding="utf-8") as f:
            master = json.load(f)
        master_keys = set(master)
        for name in sorted(os.listdir(I18N)):
            if not name.endswith(".json"):
                continue
            path = os.path.join(I18N, name)
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(set(data), master_keys, f"{name} keys differ from en.json")


if __name__ == "__main__":
    unittest.main()