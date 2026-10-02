"""All values and identifiers in this suite are fabricated fixtures."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "read.py"
SPEC = importlib.util.spec_from_file_location("application_profile_reader", SCRIPT)
READER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(READER)


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name).resolve()
        self.filename = self.folder / "index.yaml"
        self.data = {
            "preferences": {"fill_policy": {"mode": "fill_only", "status": "confirmed"}},
            "facts": {
                "education": [
                    {"record_id": "fictional-study-a", "status": "verified", "name": "School Alpha"},
                    {"record_id": "fictional-study-b", "status": "draft", "name": "School Beta"},
                ],
                "employment": [{"record_id": "fictional-job-a", "status": "confirmed",
                                "reuse_scope": ["fictional-form-only"], "confirmed_on": "2000-01-01",
                                "refresh_triggers": ["new form"], "source": "fabricated fixture",
                                "evidence_status": "fixture", "private_sibling": "UNSELECTED_PRIVATE_FACT",
                                "_text_refs": {"zh": "employment[0].description.zh"}}],
                "employment[0].description": {"status": "reviewed"},
            },
            "answers": {"answers.specific": {"value": "FABRICATED_SCOPED_ANSWER", "status": "confirmed"}},
            "zh": {"employment[0].description.zh": "SELECTED_CHINESE_TEXT"},
            "en": {"employment[0].description.en": "UNSELECTED_ENGLISH_TEXT"},
            "internship": {"availability.internship": {"status": "confirmed", "rule": "FICTIONAL_INTERNSHIP_RULE"}},
            "companies": {"company.example": {"value": "UNSELECTED_COMPANY_VALUE"}},
            "history": {"history.old": {"value": "UNSELECTED_HISTORICAL_VALUE", "status": "expired"}},
        }
        self.index = {
            "schema_version": 2,
            "modules": {module: f"{module}.json" for module in self.data},
            "aliases": {"education.alpha": "education[0]", "education.beta": "education[1]"},
            "current_fill_index": {
                "required_refs": ["fill_policy"], "internship_refs": ["availability.internship"],
                "language_modules": {"zh": "zh", "en": "en"},
                "common_refs": {"schools": "education[*].name"},
                "on_demand_refs": {"answer": "answers.specific", "old": "history.old"},
                "company_refs": {"example": ["company.example"]},
                "problem_family_refs": {"description": ["employment[0].description.zh"]},
            },
        }
        self.write()

    def write(self):
        self.filename.write_text(json.dumps(self.index), encoding="utf-8")
        for module, entries in self.data.items():
            (self.folder / f"{module}.json").write_text(
                json.dumps({"schema_version": 2, "entries": entries}), encoding="utf-8")

    def profile(self):
        self.write()
        return READER.Profile(self.filename)

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), "--profile", str(self.filename), *args],
                              text=True, capture_output=True, check=False)

    def test_selected_read_preserves_nearest_metadata_without_siblings(self):
        selected = self.profile().get("employment[0].description.zh")
        record = selected["matches"][0]
        self.assertEqual(record["value"], "SELECTED_CHINESE_TEXT")
        self.assertEqual(record["metadata"], {
            "record_id": "fictional-job-a", "status": "reviewed", "reuse_scope": ["fictional-form-only"],
            "confirmed_on": "2000-01-01", "refresh_triggers": ["new form"],
            "source": "fabricated fixture", "evidence_status": "fixture",
        })
        self.assertNotIn("UNSELECTED", json.dumps(selected))

    def test_explicit_parent_does_not_dereference_text_refs(self):
        result = self.profile().get("employment[0]")["matches"][0]["value"]
        self.assertEqual(result["_text_refs"]["zh"], "employment[0].description.zh")
        self.assertNotIn("SELECTED_CHINESE_TEXT", json.dumps(result))

    def test_get_many_preserves_order_values_and_scope_without_diagnostics(self):
        self.data["answers"]["answers.specific"]["value"] = False
        profile = self.profile()
        refs = ["education.beta.name", "employment[0].description.zh",
                "education[*].name", "education.beta.name", "answers.specific.value"]
        result = self.run_cli("get-many", *refs)
        self.assertEqual(result.returncode, 0, result.stderr)
        batch = json.loads(result.stdout)
        self.assertTrue(batch["ok"])
        self.assertEqual([item["index"] for item in batch["results"]], list(range(len(refs))))
        for ref, item in zip(refs, batch["results"]):
            expected = [{key: record[key] for key in ("ref", "value", "metadata")}
                        for record in profile.get(ref)["matches"]]
            self.assertEqual(item["matches"], expected)
        self.assertIs(batch["results"][-1]["matches"][0]["value"], False)
        self.assertEqual(batch["results"][1]["matches"][0]["metadata"]["reuse_scope"],
                         ["fictional-form-only"])
        self.assertNotIn("UNSELECTED", result.stdout)
        self.assertEqual(result.stderr, "")

        verbose = self.run_cli("get-many", *refs, "--verbose")
        self.assertEqual(verbose.returncode, 0, verbose.stderr)
        for ref, item in zip(refs, json.loads(verbose.stdout)["results"]):
            self.assertEqual(item["matches"], profile.get(ref)["matches"])

    def test_get_many_reports_each_error_and_keeps_independent_successes(self):
        result = self.run_cli("get-many", "education.alpha.name", "education[0].absent",
                              "USER_PRIVATE_MISTYPED_INPUT..value", "history.old",
                              "employment[0].description.zh")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, "")
        batch = json.loads(result.stdout)
        self.assertFalse(batch["ok"])
        self.assertEqual([item["index"] for item in batch["results"]], [0, 1, 2, 3, 4])
        self.assertEqual(batch["results"][0]["matches"][0]["value"], "School Alpha")
        self.assertEqual(batch["results"][4]["matches"][0]["value"], "SELECTED_CHINESE_TEXT")
        self.assertEqual(batch["results"][1:4], [
            {"index": 1, "error": "Reference not found"},
            {"index": 2, "error": "Invalid logical reference"},
            {"index": 3, "error": "Historical values require --include-history"},
        ])
        for forbidden in ("USER_PRIVATE", "UNSELECTED", str(self.folder)):
            self.assertNotIn(forbidden, result.stdout + result.stderr)

    def test_get_many_keeps_wildcard_atomic_and_requires_history_opt_in(self):
        self.data["history"]["education[1].name"] = "UNSELECTED_HISTORICAL_SCHOOL"
        self.data["history"]["story"] = {"source": "UNSELECTED_HISTORY_SOURCE"}
        self.data["zh"]["story.text"] = "SELECTED_STORY_TEXT"
        self.write()
        refs = ["education[*].name", "story.text", "answers.specific.value"]
        result = self.run_cli("get-many", *refs)
        self.assertEqual(result.returncode, 2)
        batch = json.loads(result.stdout)
        self.assertFalse(batch["ok"])
        self.assertEqual(batch["results"][:2], [
            {"index": 0, "error": "Historical values require --include-history"},
            {"index": 1, "error": "Historical values require --include-history"},
        ])
        self.assertEqual(batch["results"][2]["matches"][0]["value"], "FABRICATED_SCOPED_ANSWER")
        for forbidden in ("UNSELECTED", "SELECTED_STORY_TEXT", "School Alpha"):
            self.assertNotIn(forbidden, result.stdout)

        allowed = self.run_cli("get-many", *refs, "--include-history")
        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        batch = json.loads(allowed.stdout)
        self.assertTrue(batch["ok"])
        self.assertEqual([item["value"] for item in batch["results"][0]["matches"]],
                         ["School Alpha", "UNSELECTED_HISTORICAL_SCHOOL"])
        self.assertEqual(batch["results"][1]["matches"][0]["metadata"],
                         {"source": "UNSELECTED_HISTORY_SOURCE"})

    def test_get_many_rejects_missing_requests_and_unreadable_profile(self):
        missing = self.run_cli("get-many")
        self.assertEqual(missing.returncode, 2)
        self.assertEqual(missing.stdout, "")
        (self.folder / "facts.json").write_text("UNSELECTED_PRIVATE_FACT invalid json", encoding="utf-8")
        result = self.run_cli("get-many", "fill_policy", "education.alpha.name")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertEqual(json.loads(result.stderr), {
            "error": "Cannot read a valid JSON-compatible profile file"})

    def test_leaf_inherits_review_deadline_and_date_policy(self):
        self.data["internship"]["availability.internship"].update({
            "review_after": "2000-02-01", "date_confirmed_on": "2000-01-01",
            "date_fill_policy": "fixture exact dates only", "period_boundary": "fixture semester"})
        result = self.profile().get("availability.internship.rule")["matches"][0]
        self.assertEqual(result["metadata"]["review_after"], "2000-02-01")
        self.assertEqual(result["metadata"]["date_confirmed_on"], "2000-01-01")
        self.assertEqual(result["metadata"]["date_fill_policy"], "fixture exact dates only")
        self.assertEqual(result["metadata"]["period_boundary"], "fixture semester")

    def test_alias_suffix_and_wildcard(self):
        profile = self.profile()
        self.assertEqual(profile.get("education.alpha.name")["matches"][0]["value"], "School Alpha")
        result = profile.get("education[*].name")["matches"]
        self.assertEqual([m["value"] for m in result], ["School Alpha", "School Beta"])
        self.assertEqual(result[1]["metadata"]["record_id"], "fictional-study-b")
        located = profile.locate("education.beta.name")["matches"][0]
        self.assertEqual(located, {"ref": "education[1].name", "module": "facts.json",
                                   "entry": "education", "suffix": "[1].name"})

    def test_wildcard_from_split_indices_and_pattern_entries(self):
        self.data["facts"]["projects[0].name"] = "Project A"
        self.data["facts"]["projects[1].name"] = "Project B"
        self.data["facts"]["education[*].country"] = "Example Country"
        profile = self.profile()
        self.assertEqual(len(profile.get("projects[*].name")["matches"]), 2)
        self.assertEqual(len(profile.get("education[*].country")["matches"]), 2)

    def test_longest_prefix_child_wins(self):
        self.data["facts"]["education[0].name"] = "Corrected School"
        result = self.profile().get("education[0].name")["matches"][0]
        self.assertEqual(result["value"], "Corrected School")
        self.assertEqual(result["metadata"]["status"], "verified")

    def test_check_and_locate_never_output_private_values(self):
        for command in (("check",), ("locate", "employment[0].description.zh")):
            result = self.run_cli(*command)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("SELECTED_CHINESE_TEXT", result.stdout)
            self.assertNotIn("UNSELECTED", result.stdout)
            self.assertNotIn("fictional-form-only", result.stdout)

    def test_internal_refs_validate_and_external_expressions_are_ignored(self):
        self.data["facts"]["notes"] = {"mixed_refs": {"valid_ref": "education.alpha.name",
            "rule_ref": "notes/rules.md#scope", "jsonpath_ref": "$.education[?(@.name)]",
            "source_ref": "external.registry", "expression_ref": "education[*].name + fallback"}}
        result = self.profile().check()
        self.assertEqual(result["ignored_external_refs"], 4)
        self.data["facts"]["notes"]["mixed_refs"]["broken_refs"] = ["notes/rules.md", "education[0].absent"]
        with self.assertRaisesRegex(READER.ProfileError, "Reference not found"):
            self.profile().check()

    def test_check_rejects_invalid_reference_collections_without_values(self):
        for value in (42, True, None, ["education.alpha.name", 42],
                      {"valid": "education.alpha.name", "nested": [None]},
                      ["answers.missing", 42]):
            with self.subTest(value=value):
                self.data["facts"]["notes.answer_refs"] = value
                self.write()
                result = self.run_cli("check")
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertEqual(json.loads(result.stderr), {"error": "Invalid reference collection"})

    def test_context_limits_values_and_selects_language_and_kind(self):
        profile = self.profile()
        full = profile.context("full_time", "en")
        self.assertNotIn("internship", full["modules"])
        self.assertNotIn("zh", full["modules"])
        self.assertNotIn("history", full["modules"])
        self.assertIn("en", full["modules"])
        self.assertEqual(len(full["records"]), 1)
        rendered = json.dumps(full)
        for forbidden in ("SELECTED_CHINESE_TEXT", "UNSELECTED", "School Alpha", "FICTIONAL_INTERNSHIP_RULE"):
            self.assertNotIn(forbidden, rendered)
        self.assertNotIn("old", full["lookup_refs"]["on_demand_refs"])
        intern = profile.context("internship", "zh")
        self.assertEqual(len(intern["records"]), 2)
        self.assertIn("FICTIONAL_INTERNSHIP_RULE", json.dumps(intern))
        self.assertNotIn("en", intern["modules"])

    def test_compact_context_omits_bulk_indexes_and_duplicate_metadata(self):
        self.index["current_fill_index"]["company_refs"] = {
            f"fictional-company-{i}": ["company.example"] for i in range(100)}
        profile = self.profile()
        result = profile.context("full_time", "en")
        self.assertEqual(result["records"], [
            {"ref": "fill_policy", "value": {"mode": "fill_only", "status": "confirmed"}, "metadata": {}}])
        self.assertEqual(result["lookup_refs"]["common_refs"]["schools"], "education[*].name")
        self.assertNotIn("company_refs", result["lookup_refs"])
        self.assertNotIn("problem_family_refs", result["lookup_refs"])
        self.assertLess(len(json.dumps(result)), 1000)
        selected = profile.context("internship", "zh", "fictional-company-5", "description")
        self.assertEqual(selected["lookup_refs"]["company_refs"], {"fictional-company-5": ["company.example"]})
        self.assertEqual(selected["lookup_refs"]["problem_family_refs"], {"description": ["employment[0].description.zh"]})
        self.assertNotIn("fictional-company-6", json.dumps(selected))
        self.assertNotIn("SELECTED_CHINESE_TEXT", json.dumps(selected))
        cli = self.run_cli("context", "--kind", "internship", "--language", "zh",
                           "--company", "fictional-company-5", "--problem-family", "description")
        self.assertEqual(cli.returncode, 0, cli.stderr)
        self.assertEqual(json.loads(cli.stdout), selected)
        with self.assertRaisesRegex(READER.ProfileError, "scope not found"):
            profile.context("full_time", "en", company="unknown")

    def test_wildcard_alias_preserves_selected_numeric_scope(self):
        self.index["aliases"]["studies[*]"] = "education[*]"
        profile = self.profile()
        result = profile.get("studies[1].name")["matches"]
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["value"], "School Beta")
        self.assertEqual(len(profile.get("studies[*].name")["matches"]), 2)
        self.index["aliases"]["studies[0]"] = "education[0]"
        with self.assertRaisesRegex(READER.ProfileError, "Ambiguous"):
            self.profile()

    def test_context_rejects_fact_or_text_in_required_values(self):
        for ref in ("employment[0]", "employment[0].description.zh"):
            self.index["current_fill_index"]["required_refs"] = [ref]
            with self.assertRaisesRegex(READER.ProfileError, "current policy modules"):
                self.profile().context("internship", "zh")

    def test_history_requires_explicit_flag(self):
        result = self.run_cli("get", "history.old")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("UNSELECTED_HISTORICAL_VALUE", result.stderr + result.stdout)
        result = self.run_cli("get", "history.old", "--include-history")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("UNSELECTED_HISTORICAL_VALUE", result.stdout)

    def test_historical_ancestor_requires_opt_in_across_value_readers(self):
        self.data["history"]["story"] = {
            "status": "expired", "source": "UNSELECTED_HISTORY_SOURCE"}
        self.data["zh"]["story.text"] = {"status": "current", "value": "SELECTED_STORY_TEXT"}
        self.data["preferences"]["story.policy"] = {"mode": "fill_only"}
        self.index["aliases"]["current_story"] = "story.text"
        self.index["current_fill_index"]["required_refs"].append("story.policy")
        self.index["current_fill_index"]["problem_family_refs"]["description"].append("story.text.value")
        profile = self.profile()
        self.assertEqual(profile.locate("story.text.value")["matches"][0]["module"], "zh.json")
        self.assertTrue(profile.check()["ok"])

        for command in (
            ("get", "story.text.value"),
            ("get", "current_story.value"),
            ("answers", "--problem-family", "description"),
            ("context", "--kind", "full_time", "--language", "en"),
        ):
            with self.subTest(command=command):
                result = self.run_cli(*command)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertEqual(json.loads(result.stderr), {
                    "error": "Historical values require --include-history"})

        result = self.run_cli("get", "story.text.value", "--include-history")
        self.assertEqual(result.returncode, 0, result.stderr)
        record = json.loads(result.stdout)["matches"][0]
        self.assertEqual(record["value"], "SELECTED_STORY_TEXT")
        self.assertEqual(record["metadata"], {
            "status": "current", "source": "UNSELECTED_HISTORY_SOURCE"})

    def test_missing_invalid_or_cyclic_refs_fail_without_values(self):
        profile = self.profile()
        for ref in ("missing.name", "education[99]", "education[-1]", "education..name", "history[*].value"):
            with self.subTest(ref=ref), self.assertRaises(READER.ProfileError):
                profile.get(ref)
        self.index["aliases"] = {"education.alpha": "education.beta", "education.beta": "education.alpha"}
        with self.assertRaisesRegex(READER.ProfileError, "Cyclic"):
            self.profile().check()

    def test_duplicate_json_keys_entry_paths_and_ambiguity_fail(self):
        self.filename.write_text('{"schema_version":2,"schema_version":2}', encoding="utf-8")
        with self.assertRaisesRegex(READER.ProfileError, "Duplicate JSON key"):
            READER.Profile(self.filename)
        self.data["en"]["education"] = []
        with self.assertRaisesRegex(READER.ProfileError, "Duplicate entry path"):
            self.profile()
        del self.data["en"]["education"]
        self.data["facts"].update({"education[*].name": "generic", "education[0].name": "specific"})
        with self.assertRaisesRegex(READER.ProfileError, "Ambiguous"):
            self.profile()

    def test_module_missing_escape_and_symlink_fail_safely(self):
        for relative in ("missing.json", "../outside.json", str(self.folder / "facts.json")):
            self.index["modules"]["facts"] = relative
            with self.subTest(relative=relative), self.assertRaises(READER.ProfileError):
                self.profile()
        self.index["modules"]["facts"] = "linked.json"
        (self.folder / "linked.json").symlink_to(self.folder / "facts.json")
        with self.assertRaisesRegex(READER.ProfileError, "Symlink"):
            self.profile()

    def test_cli_error_does_not_echo_bad_file_contents(self):
        (self.folder / "facts.json").write_text("UNSELECTED_PRIVATE_FACT invalid json", encoding="utf-8")
        result = self.run_cli("check")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("UNSELECTED_PRIVATE_FACT", result.stderr + result.stdout)
        self.assertNotIn(str(self.folder), result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
