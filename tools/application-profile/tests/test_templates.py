"""Check the shipped blank template and explicitly fictional example."""

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("template_profile_reader", ROOT / "tools/application-profile/read.py")
READER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(READER)


class TemplateTests(unittest.TestCase):
    def test_blank_and_fictional_profiles_resolve_without_granting_authority(self):
        for directory in ("templates/application-profile", "examples/application/profile"):
            with self.subTest(directory=directory):
                profile = READER.Profile(ROOT / directory / "index.json")
                self.assertTrue(profile.check()["ok"])
                context = profile.context("full_time", "en")
                policy = context["records"][0]["value"]
                self.assertEqual(policy["mode"], "review_then_submit")
                self.assertEqual(policy["status"], "NEEDS_CONFIRMATION")
                self.assertEqual(policy["reuse_scope"], [])
                self.assertIsNone(policy["confirmed_on"])
                self.assertEqual(profile.fill["company_refs"], {})

    def test_blank_facts_stay_empty_and_example_values_stay_fictional(self):
        blank = READER.Profile(ROOT / "templates/application-profile/index.json")
        self.assertEqual(blank.get("education")["matches"][0]["value"], [])
        self.assertEqual(blank.get("employment")["matches"][0]["value"], [])
        self.assertIsNone(blank.answers("self_evaluation")["matches"][0]["value"]["value"])
        example = READER.Profile(ROOT / "examples/application/profile/index.json")
        record = example.get("education.example.name")["matches"][0]
        self.assertIn("fictional", record["value"])
        self.assertEqual(record["metadata"]["status"], "FICTIONAL")
        self.assertTrue(example.answers("self_evaluation")["candidate_only"])


if __name__ == "__main__":
    unittest.main()
