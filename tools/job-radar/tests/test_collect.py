import contextlib
import datetime as dt
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import collect
import radar

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "examples" / "discovery"


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture_dir = self.root / "fixtures"
        shutil.copytree(FIXTURES, self.fixture_dir)
        self.sources = self.fixture_dir / "sources.fixture.json"
        self.profile = self.root / "profile.json"
        self.profile_data = json.loads((ROOT / "templates/job-search/profile.example.json").read_text())
        self.profile_data["application_queue"] = {
            "enabled": True, "path": "queue.md", "application_history_path": "history.md",
        }
        self.save_profile()
        for name in ("queue.md", "history.md"):
            (self.root / name).write_bytes(b"Fictional record; never mutate.\r\n")

    def save_profile(self):
        self.profile.write_text(json.dumps(self.profile_data), encoding="utf-8")

    def run_cli(self, *extra, at=None, fixture=True):
        out, err = io.StringIO(), io.StringIO()
        when = at or dt.datetime(2030, 1, 2, 12, tzinfo=dt.timezone.utc)
        args = ["--profile", str(self.profile), "--fixtures" if fixture else "--sources", str(self.sources), *extra]
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                mock.patch.object(collect, "utc_now", return_value=when), \
                mock.patch("socket.create_connection", side_effect=AssertionError("No real network in tests")):
            code = collect.main(args)
        return code, out.getvalue(), err.getvalue()

    def rows(self):
        payload = json.loads(self.sources.read_text())
        config, sources = collect.validate_inputs(self.profile_data, payload, True)
        with mock.patch.object(collect, "fetch_text", side_effect=AssertionError("Fixtures cannot fetch")):
            return collect.collect_all(sources, self.profile_data, config,
                                       "2030-01-02T12:00:00Z", self.fixture_dir)

    def test_all_migrated_parsers_feed_the_existing_pending_dossier(self):
        rows, errors, counts = self.rows()
        self.assertEqual(errors, [])
        self.assertEqual(len(rows), 11)
        self.assertEqual(sum(counts.values()), 11)
        self.assertEqual({row.item.source_type for row in rows}, {
            "html", "rss", "ashby", "greenhouse", "lever", "mycareersfuture",
            "baidu_campus", "wechat_search", "portal",
        })
        for row in rows:
            self.assertIsInstance(row.dossier, radar.JobDossier)
            self.assertEqual(row.dossier.verification.status, "PENDING")
            self.assertEqual(row.dossier.feasibility.status, "UNKNOWN")
            self.assertEqual(row.dossier.capability_match.level, "UNKNOWN")
            self.assertEqual(row.dossier.strategic_priority.level, "UNKNOWN")
            self.assertEqual(row.dossier.recommendation.action, "MANUAL_REVIEW")
            self.assertFalse(radar.is_auto_queue_eligible(row.dossier))
        self.assertEqual(len([row for row in rows if row.item.source_type == "ashby"]), 2)
        html_row = next(row for row in rows if row.item.source_type == "html")
        self.assertIn("Python", html_row.detail.requirements)
        mcf = next(row.item for row in rows if row.item.source_type == "mycareersfuture")
        self.assertEqual(mcf.employment_type, "Internship")
        self.assertEqual(mcf.minimum_years_experience, 0)

    def test_careers_hostname_does_not_turn_about_link_into_job(self):
        items = collect.parse_html_items({"name": "Fictional", "url": "https://careers.example.test"},
            '<a href="/jobs/101">Engineer</a><a href="/about">About us</a>')
        self.assertEqual([item.title for item in items], ["Engineer"])

    def test_source_filters_and_preferred_experience_remain_distinct(self):
        source = {"name": "Fictional", "type": "ashby", "url": "https://example.test",
                  "require_location_any": ["Toronto"], "require_title_any": ["Backend"]}
        text = (self.fixture_dir / "ashby.json").read_text()
        self.assertEqual(len(collect.parse_payload(source, text)), 2)
        source["require_location_any"] = ["Vancouver"]
        self.assertEqual(collect.parse_payload(source, text), [])
        self.assertEqual(collect.extract_minimum_years_experience("Required: 5 years of relevant experience."), 5)
        self.assertIsNone(collect.extract_minimum_years_experience("Preferred: 5 years of relevant experience."))
        evidence = collect.classify_requirement_evidence(
            "Required: Python. Preferred: SQL. Nice to have: Rust.")
        self.assertEqual(len(evidence.required), 1)
        self.assertEqual(len(evidence.preferred), 1)
        self.assertEqual(len(evidence.nice_to_have), 1)

    def test_empty_profile_does_not_impose_region_graduation_or_role_preference(self):
        item = collect.JobItem("2099届 Data Analyst Intern", "https://example.test/jobs/1", "Source",
                               company="Fictional", location="Singapore", employment_type="Internship")
        self.assertEqual(collect.configured_exclusion_reasons(item, self.profile_data), ())
        self.assertEqual(collect.score_item(item, {}, self.profile_data), (0, ()))
        profile = {"allowed_graduation_years": ["2028"], "internship_keywords": ["intern"],
                   "internship_excluded_locations": ["Singapore"]}
        self.assertEqual(len(collect.configured_exclusion_reasons(item, profile)), 2)
        self.assertFalse(collect.matching_terms("internal platform", ["intern"]))

    def test_source_name_is_not_retrieval_evidence(self):
        item = collect.JobItem("Analyst", "https://example.test/jobs/1", "AI Agent Graduate Singapore")
        score, _ = collect.score_item(item, {}, {"target_roles": ["Agent"], "locations": ["Singapore"],
                                                "fresh_grad_keywords": ["Graduate"]})
        self.assertEqual(score, 0)

    def test_detail_extraction_uses_same_parser_with_mock_http(self):
        item = collect.JobItem("Backend Engineer", "https://careers.example.test/jobs/HTML-101", "Fictional")
        with mock.patch.object(collect, "fetch_text", return_value=(self.fixture_dir / "detail.html").read_text()) as fetch:
            detail = collect.fetch_job_detail(item, 3, self.profile_data)
        fetch.assert_called_once_with(item.url, 3)
        self.assertIn("Python", detail.requirements)
        self.assertTrue(detail.title_matches)
        self.assertTrue(detail.apply_url.endswith("/apply"))

    def test_http_transport_rejects_file_urls_and_decodes_declared_charset(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = "Café".encode("latin-1")
        response.headers = {"content-type": "text/html; charset=latin-1"}
        with mock.patch.object(collect.urllib.request, "urlopen", return_value=response) as urlopen:
            self.assertEqual(collect.fetch_text("https://example.test/jobs", 4), "Café")
            with self.assertRaises(ValueError):
                collect.fetch_text("file:///etc/passwd", 4)
            self.assertEqual(urlopen.call_count, 1)
            self.assertEqual(urlopen.call_args.kwargs["timeout"], 4)

    def test_dry_run_leaves_all_input_and_runtime_bytes_unchanged(self):
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with mock.patch.object(collect, "fetch_text", side_effect=AssertionError("No fixture network")):
            code, out, err = self.run_cli("--dry-run")
        self.assertEqual((code, err), (0, ""))
        self.assertIn('"writes_enabled": false', out)
        after = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse((self.root / "radar").exists())

    def test_cli_dry_run_does_not_create_import_cache_without_environment_override(self):
        tools = self.root / "tool-copy"
        tools.mkdir()
        for name in ("collect.py", "radar.py"):
            shutil.copyfile(ROOT / "tools/job-radar" / name, tools / name)
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        environment = dict(os.environ)
        environment.pop("PYTHONDONTWRITEBYTECODE", None)
        result = subprocess.run([sys.executable, str(tools / "collect.py"), "--profile", str(self.profile),
                                 "--fixtures", str(self.sources), "--dry-run"],
                                env=environment, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((tools / "__pycache__").exists())
        after = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_explicit_sources_can_fetch_in_dry_run_without_writing(self):
        self.sources.write_text(json.dumps({"sources": [{"name": "Fictional HTTP", "type": "ashby",
            "url": "https://example.test/jobs"}]}))
        with mock.patch.object(collect, "fetch_text", return_value=(self.fixture_dir / "ashby.json").read_text()) as fetch:
            code, _, err = self.run_cli("--dry-run", fixture=False)
        self.assertEqual((code, err), (0, ""))
        fetch.assert_called_once()
        self.assertFalse((self.root / "radar").exists())

    def test_persistence_same_day_next_day_and_include_seen_do_not_touch_queue(self):
        ledger_before = {name: (self.root / name).read_bytes() for name in ("queue.md", "history.md")}
        with mock.patch.object(collect, "fetch_text", side_effect=AssertionError("No fixture network")):
            for hour in (10, 15):
                code, out, err = self.run_cli(at=dt.datetime(2030, 1, 2, hour, tzinfo=dt.timezone.utc))
                self.assertEqual((code, err), (0, ""))
                self.assertEqual(json.loads(out)["visible_count"], 11)
            code, out, _ = self.run_cli(at=dt.datetime(2030, 1, 3, 12, tzinfo=dt.timezone.utc))
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out)["visible_count"], 0)
            code, out, _ = self.run_cli("--include-seen", at=dt.datetime(2030, 1, 3, 13, tzinfo=dt.timezone.utc))
            self.assertEqual(json.loads(out)["visible_count"], 11)
        dossiers = radar.load_dossiers(self.root / "radar/dossiers.json")
        self.assertEqual(len(dossiers), 11)
        self.assertFalse(any(map(radar.is_auto_queue_eligible, dossiers)))
        self.assertTrue((self.root / "radar/source_health.json").exists())
        self.assertTrue(any((self.root / "radar/reports").glob("*_Job_Radar.md")))
        for name, before in ledger_before.items():
            self.assertEqual((self.root / name).read_bytes(), before)

    def test_seen_database_migrates_url_key_without_reappearing(self):
        item = collect.JobItem("Engineer", "https://example.test/jobs/1", "Fictional",
                               company="Fictional", location="Toronto", job_id="1")
        row = collect.ScoredItem(item, 20, (), collect.item_key(item))
        with contextlib.closing(collect.init_db(self.root / "seen.sqlite3")) as conn:
            conn.execute("INSERT INTO seen_jobs VALUES (?, ?, ?, ?, ?, ?, ?)",
                         ("legacy-url-key", item.title, item.url, item.source,
                          "2030-01-01T12:00:00Z", "2030-01-01T12:00:00Z", 10))
            result = collect.mark_seen(conn, row, "2030-01-02T12:00:00Z")
            self.assertFalse(result.is_new)
            self.assertEqual(collect.read_seen_retrieval_score(conn, row.key), 20)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM seen_jobs").fetchone()[0], 1)

    def test_database_closes_when_schema_initialization_fails(self):
        connection = mock.Mock()
        connection.execute.side_effect = sqlite3.OperationalError("fixture failure")
        with mock.patch.object(collect.sqlite3, "connect", return_value=connection):
            with self.assertRaises(sqlite3.OperationalError):
                collect.init_db(self.root / "failed.sqlite3")
        connection.close.assert_called_once()

    def test_health_counts_failure_days_and_resets_after_success(self):
        path = self.root / "health.json"
        sources = [{"name": "Fictional", "type": "html"}]
        for day, expected in ((1, 1), (1, 1), (2, 2)):
            state = collect.update_source_health(path, sources, ["Fictional: timeout"],
                now=dt.datetime(2030, 1, day, 12, tzinfo=dt.timezone.utc))
            self.assertEqual(state["sources"]["Fictional"]["consecutive_failures"], expected)
        state = collect.update_source_health(path, sources, [],
            now=dt.datetime(2030, 1, 3, 12, tzinfo=dt.timezone.utc))
        self.assertEqual(state["sources"]["Fictional"]["consecutive_failures"], 0)
        self.assertIn("2030-01-03", state["sources"]["Fictional"]["last_success_at"])

    def test_source_failure_keeps_other_leads_and_reports_partial_failure(self):
        payload = json.loads(self.sources.read_text())
        payload["sources"][0]["fixture_path"] = "missing.html"
        self.sources.write_text(json.dumps(payload))
        code, out, err = self.run_cli()
        self.assertEqual(code, 2)
        self.assertEqual(err, "")
        self.assertEqual(json.loads(out)["collected_count"], 10)
        report = next((self.root / "radar/reports").glob("*.md")).read_text()
        self.assertIn("Collection errors", report)
        self.assertIn("Fictional HTML Careers", report)

    def test_unignored_nonexistent_output_directory_is_rejected_before_collection(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.profile_data["collector"]["reports_dir"] = "unignored/new/reports"
        self.save_profile()
        with mock.patch.object(collect, "collect_all") as run:
            code, _, err = self.run_cli()
        self.assertEqual(code, 2)
        self.assertIn("ignored and untracked", err)
        run.assert_not_called()
        self.assertFalse((self.root / "unignored").exists())

    def test_output_cannot_overwrite_profile_or_queue(self):
        for filename in ("profile.json", "queue.md", "history.md"):
            self.profile_data["collector"]["dossiers_path"] = filename
            self.save_profile()
            before = (self.root / filename).read_bytes()
            with mock.patch.object(collect, "collect_all") as run:
                code, _, err = self.run_cli()
            self.assertEqual(code, 2)
            self.assertIn("distinct", err)
            run.assert_not_called()
            self.assertEqual((self.root / filename).read_bytes(), before)

    def test_output_symlink_and_parent_alias_are_rejected_without_overwriting_target(self):
        victim = self.root / "unrelated.json"
        victim.write_text("UNRELATED_SENTINEL")
        alias = self.root / "dossiers-link.json"
        alias.symlink_to(victim)
        self.profile_data["collector"]["dossiers_path"] = alias.name
        self.save_profile()
        with mock.patch.object(collect, "collect_all") as run:
            code, _, err = self.run_cli()
        self.assertEqual(code, 2)
        self.assertIn("symbolic links", err)
        run.assert_not_called()
        self.assertEqual(victim.read_text(), "UNRELATED_SENTINEL")
        directory = self.root / "actual"
        directory.mkdir()
        linked_directory = self.root / "linked"
        linked_directory.symlink_to(directory, target_is_directory=True)
        self.profile_data["collector"]["dossiers_path"] = "linked/dossiers.json"
        self.save_profile()
        code, _, err = self.run_cli()
        self.assertEqual(code, 2)
        self.assertFalse((directory / "dossiers.json").exists())

    def test_fixed_temporary_symlink_is_never_opened(self):
        victim = self.root / "unrelated.txt"
        victim.write_text("UNRELATED_SENTINEL")
        health = self.root / "health.json"
        legacy_tmp = self.root / "health.json.tmp"
        legacy_tmp.symlink_to(victim)
        collect.save_source_health(health, {"sources": {}, "updated_at": None})
        self.assertEqual(victim.read_text(), "UNRELATED_SENTINEL")
        self.assertTrue(legacy_tmp.is_symlink())
        self.assertFalse(health.is_symlink())
        self.assertEqual(json.loads(health.read_text())["sources"], {})
        self.assertEqual(list(self.root.glob(".health.json.*")), [])

    def test_fixture_input_and_database_sidecar_are_protected(self):
        self.profile_data["collector"]["dossiers_path"] = "fixtures/ashby.json"
        self.save_profile()
        before = (self.fixture_dir / "ashby.json").read_bytes()
        code, _, _ = self.run_cli()
        self.assertEqual(code, 2)
        self.assertEqual((self.fixture_dir / "ashby.json").read_bytes(), before)
        victim = self.root / "victim"
        victim.write_text("UNRELATED_SENTINEL")
        (self.root / "seen.sqlite3-journal").symlink_to(victim)
        with self.assertRaises(ValueError):
            collect.init_db(self.root / "seen.sqlite3")
        self.assertEqual(victim.read_text(), "UNRELATED_SENTINEL")
        self.assertFalse((self.root / "seen.sqlite3").exists())

    def test_empty_source_template_has_no_network_and_invalid_input_fails_closed(self):
        payload = json.loads((ROOT / "templates/job-search/sources.example.json").read_text())
        self.assertEqual(payload, {"sources": []})
        with self.assertRaises(ValueError):
            collect.validate_inputs(self.profile_data, {"sources": [{"name": "Broken", "type": "unknown"}]}, False)
        with self.assertRaises(ValueError):
            collect.validate_inputs(self.profile_data, {"sources": [{"name": "Local", "url": "file:///tmp/data"}]}, False)

    def test_invalid_container_and_flag_types_fail_before_collection(self):
        for value in (["not an object"], {"jd_headings": "Requirements"}):
            self.profile_data["detail_sections"] = value
            self.save_profile()
            with mock.patch.object(collect, "collect_all") as run:
                code, _, err = self.run_cli("--dry-run")
            self.assertEqual(code, 2)
            self.assertIn("detail_sections", err)
            run.assert_not_called()
        self.profile_data["detail_sections"] = {}
        for extra in ({"enabled": "false"}, {"detail_fixtures": []}, {"type": "wechat_search", "query": ""}):
            with self.assertRaises(ValueError):
                collect.validate_inputs(self.profile_data, {"sources": [{"name": "Fictional", "url": "https://example.test", **extra}]}, False)


if __name__ == "__main__":
    unittest.main()
