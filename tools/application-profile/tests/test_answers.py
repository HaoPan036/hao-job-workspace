"""Retrieval regression tests and a fabricated profile for behavioral exercises."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "read.py"
SPEC = importlib.util.spec_from_file_location("answer_reader", SCRIPT)
READER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(READER)


def make_fixture(folder):
    """No production values, company names, contacts or real confirmations."""
    def answer(record_id, value, scope):
        return {"record_id": record_id, "status": "CONFIRMED_REUSABLE", "value": value,
                "reuse_scope": scope, "confirmed_on": "2099-01-01",
                "refresh_triggers": ["new relevant event", "user correction"],
                "source": "Explicitly fabricated user confirmation for this exercise"}

    modules = {
        "preferences": {"policy": {"mode": "fixture_only"}},
        "answers": {
            "answers": {"status": "NEEDS_CONFIRMATION"},
            "answers.criminal": answer("fixture-crime", False,
                "Applicant has never been charged, convicted or investigated in any country; all companies."),
            "answers.relatives": answer("fixture-relatives", False,
                "No relatives currently employed at any applicant company; all companies. Not shareholding."),
            "answers.privacy": answer("fixture-privacy", True,
                "Required application data processing across companies; not optional marketing or new signatures."),
            "answers.current_membership": answer("fixture-member", False,
                "Current professional organization membership only; not past membership."),
            "answers.legacy": {"status": "NEEDS_CONFIRMATION", "value": None},
            "answers.discipline": answer("fixture-discipline", False,
                "Never dismissed for disciplinary reasons, across companies."),
            "answers.routing": {"status": "ROUTING_ONLY", "value": None,
                "answer_refs": ["answers.criminal", "answers.relatives"]},
            "answers.unrelated": {"value": "UNSELECTED_PRIVATE_VALUE"},
        },
        "companies": {"company.beta.relatives": answer("fixture-beta-disputed", True,
            "A relative currently works at Beta. No statement supersedes the other record; unresolved conflict.")},
        "zh": {}, "en": {}, "history": {"history.old": answer("fixture-old", True, "Historical only")},
    }
    index = {"schema_version": 2, "modules": {k: k + ".json" for k in modules},
             "aliases": {"criminal_alias": "answers.criminal"}, "current_fill_index": {
                 "required_refs": ["policy"], "internship_refs": [],
                 "language_modules": {"zh": "zh", "en": "en"},
                 "on_demand_refs": {"discipline": "answers.discipline"},
                 "company_refs": {"beta": ["company.beta.relatives"]},
                 "problem_family_refs": {
                     "criminal_history": ["answers.criminal.value", "criminal_alias.value"],
                     "relatives_employment": ["answers.relatives"],
                     "required_application_privacy": ["answers.privacy"],
                     "professional_membership": ["answers.current_membership"],
                 }}}
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for key, entries in modules.items():
        (folder / (key + ".json")).write_text(json.dumps(
            {"schema_version": 2, "entries": entries}, indent=2), encoding="utf-8")
    filename = folder / "index.json"
    filename.write_text(json.dumps(index, indent=2), encoding="utf-8")
    return filename


class AnswerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.filename = make_fixture(Path(self.temp.name).resolve())

    def profile(self):
        return READER.Profile(self.filename)

    def change_families(self, key, value):
        data = json.loads(self.filename.read_text())
        data["current_fill_index"]["problem_family_refs"][key] = value
        self.filename.write_text(json.dumps(data))

    def test_family_candidates_keep_scope_and_override_parent_placeholder(self):
        result = self.profile().answers("criminal_history")
        self.assertTrue(result["candidate_only"])
        self.assertEqual(len(result["matches"]), 1)
        record = result["matches"][0]
        self.assertIs(record["value"], False)
        self.assertEqual(record["metadata"]["status"], "CONFIRMED_REUSABLE")
        self.assertEqual(record["metadata"]["record_id"], "fixture-crime")
        self.assertIn("all companies", record["metadata"]["reuse_scope"])
        self.assertNotIn("UNSELECTED", json.dumps(result))

    def test_sibling_placeholder_does_not_change_confirmed_record(self):
        record = self.profile().answers("relatives_employment")["matches"][0]
        self.assertEqual(record["metadata"]["status"], "CONFIRMED_REUSABLE")
        self.assertNotIn("legacy", json.dumps(record))

    def test_company_conflict_remains_visible_without_automatic_override(self):
        profile = self.profile()
        general = profile.answers("relatives_employment")["matches"][0]
        context = profile.context("full_time", "en", company="beta")
        ref = context["lookup_refs"]["company_refs"]["beta"][0]
        specific = profile.get(ref)["matches"][0]
        self.assertIs(general["value"]["value"], False)
        self.assertIs(specific["value"]["value"], True)
        self.assertNotEqual(general["metadata"]["record_id"], specific["metadata"]["record_id"])

    def test_unindexed_family_is_lookup_error_not_missing_fact(self):
        with self.assertRaisesRegex(READER.ProfileError, "not indexed"):
            self.profile().answers("disciplinary_history")
        context = self.profile().context("full_time", "en")
        ref = context["lookup_refs"]["on_demand_refs"]["discipline"]
        self.assertIs(self.profile().get(ref)["matches"][0]["value"]["value"], False)

    def test_empty_or_invalid_family_does_not_return_success(self):
        for value in ([], None, 1, ["missing.answer"]):
            with self.subTest(value=value):
                self.change_families("invalid", value)
                with self.assertRaises(READER.ProfileError):
                    self.profile().answers("invalid")

    def test_candidates_never_read_history(self):
        self.change_families("old", ["history.old"])
        with self.assertRaisesRegex(READER.ProfileError, "Historical"):
            self.profile().answers("old")

    def test_routing_only_record_is_not_a_confirmation(self):
        self.change_families("routing", ["answers.routing"])
        record = self.profile().answers("routing")["matches"][0]
        self.assertEqual(record["metadata"]["status"], "ROUTING_ONLY")
        self.assertIsNone(record["value"]["value"])
        self.assertNotIn("fixture-crime", json.dumps(record))

    def test_cli_family_list_and_selected_answers(self):
        def run(*args):
            return subprocess.run([sys.executable, str(SCRIPT), "--profile", str(self.filename), *args],
                                  text=True, capture_output=True, check=False)
        listed = run("families")
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertNotIn("fixture-crime", listed.stdout)
        self.assertNotIn("UNSELECTED", listed.stdout)
        selected = run("answers", "--problem-family", "criminal_history")
        self.assertEqual(selected.returncode, 0, selected.stderr)
        self.assertEqual(json.loads(selected.stdout), self.profile().answers("criminal_history"))
        unknown = run("answers", "--problem-family", "USER_PRIVATE_MISTYPED_INPUT")
        self.assertEqual(unknown.returncode, 2)
        self.assertNotIn("USER_PRIVATE", unknown.stdout + unknown.stderr)


if __name__ == "__main__":
    unittest.main()
