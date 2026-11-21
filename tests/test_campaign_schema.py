"""Схема campaign.json и человекочитаемые ошибки валидатора."""

import copy
import json
import os
import tempfile
import unittest

from svenmap.campaign import load_campaign
from svenmap.campaign_schema import (
    CampaignValidationError, validate_data,
)


def _good_data():
    return {
        "name": "test_campaign",
        "chapters": [
            {
                "name": "map_one", "seed": 1, "rooms": 6,
                "branches": 1, "theme": "industrial",
                "puzzles": ["collect", "enemies"],
            },
            {
                "name": "map_two", "seed": 2, "rooms": 8,
                "branches": 2, "theme": "industrial",
                "puzzles": ["buttons"], "final": True,
            },
        ],
    }


class TestCampaignSchema(unittest.TestCase):
    def test_valid_data_has_no_errors(self):
        self.assertEqual(validate_data(_good_data()), [])

    def test_real_campaign_is_valid(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "campaign.json",
        )
        with open(path, encoding="utf-8") as f:
            self.assertEqual(validate_data(json.load(f)), [])

    def test_error_has_path_and_hint(self):
        data = _good_data()
        data["chapters"][0]["seed"] = 2
        issues = validate_data(data)
        # Дубликат сообщается у второго вхождения — его и нужно исправить.
        self.assertTrue(any(i.path == "chapters[1].seed" for i in issues))
        self.assertIn("уже используется", str(issues[0]))

    def test_unknown_theme_and_puzzle(self):
        data = _good_data()
        data["chapters"][0]["theme"] = "lab"
        data["chapters"][0]["puzzles"] = ["teleport"]
        paths = {i.path for i in validate_data(data)}
        self.assertIn("chapters[0].theme", paths)
        self.assertIn("chapters[0].puzzles[0]", paths)

    def test_conflicting_objectives(self):
        data = _good_data()
        data["chapters"][0]["puzzles"] = ["collect", "buttons"]
        self.assertTrue(any(
            "collect" in i.message and "buttons" in i.message
            for i in validate_data(data)
        ))

    def test_final_must_be_last(self):
        data = _good_data()
        data["chapters"][0]["final"] = True
        data["chapters"][1].pop("final")
        self.assertTrue(any(i.path.endswith(".final") for i in validate_data(data)))

    def test_load_campaign_raises_readable_error(self):
        data = _good_data()
        data["chapters"][0]["name"] = "map_two"
        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            with self.assertRaises(CampaignValidationError) as ctx:
                load_campaign(path)
            self.assertIn("chapters[1].name", str(ctx.exception))
            self.assertIn("уже использовано", str(ctx.exception))
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
