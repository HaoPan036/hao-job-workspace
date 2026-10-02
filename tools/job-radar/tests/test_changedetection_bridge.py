"""Only temporary ignored fixtures and mocked API/collector calls; no service runs."""

import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import changedetection_bridge as bridge

ENV_NAME = "CHANGEDETECTION_API_KEY"

class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / ".gitignore").write_text("**/private/\n")
        self.local = self.root / "private/job-search"
        self.local.mkdir(parents=True)
        templates = bridge.TOOL_DIR.parents[1] / "templates/job-search"
        self.config_path = self.local / "changedetection.json"
        self.profile_path = self.local / "profile.json"
        self.sources_path = self.local / "sources.json"
        self.config_path.write_bytes((templates / "changedetection.example.json").read_bytes())
        self.profile_path.write_bytes((templates / "profile.example.json").read_bytes())
        self.source = {"name": "Fictional Careers", "type": "html", "url": "https://careers.example.com/jobs"}
        self.sources_path.write_text(json.dumps({"sources": [self.source]}))
        self.network = mock.patch.object(bridge.urllib.request, "build_opener", side_effect=AssertionError("Live network forbidden"))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.config = self.load()

    def load(self):
        return bridge.load_config(self.config_path, self.profile_path, self.sources_path)

    def change_config(self, **changes):
        values = json.loads(self.config_path.read_text())
        values.update(changes)
        self.config_path.write_text(json.dumps(values))

    def registered(self, last_changed=None):
        state = bridge.load_state(self.config)
        state["managed_watches"] = {"ours": bridge.radar.normalize_url(self.source["url"])}
        state["last_changed"] = last_changed or {}
        bridge.save_json(self.config["state_path"], state)
        return state

    def watch(self, timestamp=100):
        return {**bridge.desired_watch(self.source, self.config), "last_changed": timestamp}

    def arguments(self, command, *extra):
        return [command, "--config", str(self.config_path), "--profile", str(self.profile_path),
                "--sources", str(self.sources_path), *extra]

    def snapshot(self):
        return {str(path.relative_to(self.root)): path.read_bytes()
                for path in (self.root / "private").rglob("*") if path.is_file()}

    def test_preview_and_every_dry_run_are_offline_and_zero_write(self):
        before = self.snapshot()
        with mock.patch.object(bridge, "api_request") as api, mock.patch.object(bridge, "run_collector") as run, mock.patch.object(bridge, "load_api_key") as key:
            for command in ("preview", "sync", "poll", "baseline", "run"):
                for extra in ((), ("--apply", "--dry-run")):
                    with self.subTest(command=command, extra=extra), contextlib.redirect_stdout(io.StringIO()) as output:
                        self.assertEqual(bridge.main(self.arguments(command, *extra)), 0)
                        report = json.loads(output.getvalue())
                        self.assertFalse(report["network_enabled"])
                        self.assertFalse(report["writes_enabled"])
            api.assert_not_called()
            run.assert_not_called()
            key.assert_not_called()
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.local / "radar").exists())

    def test_relative_paths_follow_selected_config_and_profile(self):
        self.assertEqual(self.config["state_path"], self.local / "radar/changedetection_state.json")
        self.assertEqual(self.config["source_health_path"], self.local / "radar/source_health.json")
        self.assertEqual(self.config["profile_path"], self.profile_path)

    def test_preview_cli_does_not_create_import_caches(self):
        tools = self.root / "tools-copy"
        tools.mkdir()
        for name in ("changedetection_bridge.py", "collect.py", "radar.py"):
            shutil.copyfile(bridge.TOOL_DIR / name, tools / name)
        script = tools / "changedetection_bridge.py"
        before = {str(path.relative_to(self.root)) for path in self.root.rglob("*")}
        env = dict(os.environ)
        env.pop("PYTHONDONTWRITEBYTECODE", None)
        env.pop("PYTHONPYCACHEPREFIX", None)
        # The subprocess runs the real parser with networking disabled, without -B.
        wrapper = "import runpy,sys,urllib.request; urllib.request.build_opener=lambda *a,**k: (_ for _ in ()).throw(AssertionError('network forbidden')); sys.path.insert(0,sys.argv[1]); sys.argv=sys.argv[2:]; runpy.run_path(sys.argv[0],run_name='__main__')"
        result = subprocess.run([sys.executable, "-c", wrapper, str(tools), str(script), *self.arguments("preview")],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)["network_enabled"])
        self.assertEqual(before, {str(path.relative_to(self.root)) for path in self.root.rglob("*")})

    def test_private_paths_reject_tracked_unignored_symlink_and_outside_git(self):
        cases = ("tracked", "unignored", "symlink", "outside")
        for case in cases:
            with self.subTest(case=case):
                if case == "tracked":
                    subprocess.run(["git", "-C", str(self.root), "add", "-f", "--", str(self.config_path)], check=True)
                    with self.assertRaises(bridge.BridgeError):
                        self.load()
                    subprocess.run(["git", "-C", str(self.root), "rm", "--cached", "-q", "--", str(self.config_path)], check=True)
                elif case == "unignored":
                    (self.root / ".gitignore").write_text("")
                    with self.assertRaises(bridge.BridgeError):
                        self.load()
                    (self.root / ".gitignore").write_text("**/private/\n")
                elif case == "symlink":
                    alias = self.local / "alias.json"
                    alias.symlink_to(self.config_path)
                    with self.assertRaises(bridge.BridgeError):
                        bridge.private_path(alias)
                else:
                    with tempfile.TemporaryDirectory() as temp:
                        with self.assertRaises(bridge.BridgeError):
                            bridge.private_path(Path(temp).resolve() / "state.json")

    def test_configuration_rejects_credential_urls_unknown_fields_and_output_collisions(self):
        original = self.config_path.read_bytes()
        cases = ({"base_url": "http://user:password@localhost:5000"},
                 {"base_url": "http://localhost:5000/?token=example"},
                 {"base_url": 42}, {"apiKey": "EXAMPLE"},
                 {"remove_default_sample_watches": True}, {"state_path": "profile.json"},
                 {"state_path": "../recruiting/queue.md"}, {"state_path": "radar/source_health.json"})
        for changes in cases:
            with self.subTest(changes=changes):
                self.config_path.write_bytes(original)
                self.change_config(**changes)
                with self.assertRaises((bridge.BridgeError, ValueError)):
                    self.load()

    def test_remote_requires_explicit_configuration_and_https(self):
        self.change_config(base_url="https://monitor.example.com")
        with self.assertRaisesRegex(bridge.BridgeError, "allow_remote"):
            self.load()
        self.change_config(allow_remote=True)
        self.assertTrue(self.load()["remote"])
        self.change_config(base_url="http://monitor.example.com")
        with self.assertRaisesRegex(bridge.BridgeError, "HTTPS"):
            self.load()

    def test_state_and_health_cannot_overwrite_report_or_other_output_ancestors(self):
        original_config = self.config_path.read_bytes()
        original_profile = self.profile_path.read_bytes()
        for output in ("state_path", "source_health_path"):
            for value in ("radar/reports/2099-01-01_Job_Radar.md", "radar/reports", "radar", "radar/dossiers.json/nested.json"):
                with self.subTest(output=output, value=value):
                    self.config_path.write_bytes(original_config)
                    self.profile_path.write_bytes(original_profile)
                    if output == "state_path":
                        self.change_config(state_path=value)
                    else:
                        profile = json.loads(self.profile_path.read_text())
                        profile["collector"][output] = value
                        self.profile_path.write_text(json.dumps(profile))
                    with self.assertRaisesRegex(bridge.BridgeError, "overlap"):
                        self.load()
        self.assertFalse((self.local / "radar").exists())

    def test_token_file_is_explicit_private_and_environment_can_override(self):
        token_path = self.local / "token.txt"
        token_path.write_text("fictional-file-token\n")
        self.change_config(api_key_path="token.txt")
        config = self.load()
        with mock.patch.dict(os.environ, {"CHANGEDETECTION_API_KEY": ""}):
            self.assertEqual(bridge.load_api_key(config), "fictional-file-token")
        value = "fictional-env-token"
        with mock.patch.dict(os.environ, {ENV_NAME: value}):
            self.assertEqual(bridge.load_api_key(config), value)
        subprocess.run(["git", "-C", str(self.root), "add", "-f", "--", str(token_path)], check=True)
        with self.assertRaises(bridge.BridgeError):
            self.load()

    def test_missing_configured_token_fails_without_network(self):
        with mock.patch.dict(os.environ, {"CHANGEDETECTION_API_KEY": ""}):
            with self.assertRaisesRegex(bridge.BridgeError, "unavailable"):
                bridge.api_request(self.config, "/api/v1/watch")

    def test_api_errors_do_not_echo_token_response_url_or_body(self):
        response = urllib.error.HTTPError("https://example.com/private", 403, "private reason", {}, io.BytesIO(b"fictional-secret-response"))
        fake = mock.Mock()
        fake.open.side_effect = response
        value = "fictional-secret-token"
        with mock.patch.dict(os.environ, {ENV_NAME: value}), mock.patch.object(bridge.urllib.request, "build_opener", return_value=fake):
            with self.assertRaises(bridge.BridgeError) as caught:
                bridge.api_request(self.config, "/api/v1/watch")
        self.assertIn("403", str(caught.exception))
        self.assertNotIn("fictional-secret", str(caught.exception))
        self.assertNotIn("private", str(caught.exception))

    def test_redirect_handler_never_forwards_credentials(self):
        self.assertIsNone(bridge.NoRedirect().redirect_request(None, None, 302, "", {}, "https://other.example.com"))

    def test_monitorable_sources_preserves_filters_and_deduplicates_url(self):
        config = {**self.config, "excluded_source_names": ["Excluded"]}
        sources = [self.source, {**self.source, "name": "Same URL"},
                   {**self.source, "name": "Disabled", "enabled": False},
                   {**self.source, "name": "Excluded", "url": "https://example.com/excluded"},
                   {**self.source, "name": "Manual", "type": "manual"},
                   {**self.source, "name": "Private table", "url": "https://example.feishu.cn/base/example"}]
        self.assertEqual(bridge.monitorable_sources(sources, config), [self.source])

    def test_first_snapshot_is_baseline_and_change_after_zero_triggers(self):
        changed, first = bridge.detect_changed_watches({"ours": self.watch(0)}, {})
        self.assertEqual((changed, first), ([], {"ours": 0}))
        self.assertEqual(bridge.detect_changed_watches({"ours": self.watch(100)}, first), (["ours"], {"ours": 100}))

    def test_sync_reads_owned_details_before_deciding_update(self):
        self.registered()
        expected = bridge.desired_watch(self.source, self.config)
        with mock.patch.object(bridge, "list_watches", return_value={"ours": self.watch()}), mock.patch.object(bridge, "api_request", return_value=expected) as api:
            self.assertEqual(bridge.sync_watches(self.config), (0, 0, 0))
        api.assert_called_once_with(self.config, "/api/v1/watch/ours")

    def test_sync_updates_only_changed_fields_of_registered_watch(self):
        self.registered()
        details = {**self.watch(), "paused": True}
        with mock.patch.object(bridge, "list_watches", return_value={"ours": self.watch()}), mock.patch.object(bridge, "api_request", side_effect=[details, {}]) as api:
            self.assertEqual(bridge.sync_watches(self.config), (0, 1, 0))
        self.assertEqual(api.call_args, mock.call(self.config, "/api/v1/watch/ours", method="PUT", payload={"paused": False}))

    def test_sync_never_adopts_or_deletes_unregistered_watches_even_same_prefix(self):
        foreign = {"foreign": self.watch(), "sample": {"title": None, "url": "https://example.com/sample"}}
        with mock.patch.object(bridge, "list_watches", return_value=foreign), mock.patch.object(bridge, "api_request", return_value="new-uuid") as api:
            self.assertEqual(bridge.sync_watches(self.config), (1, 0, 0))
        self.assertEqual(api.call_args.kwargs["method"], "POST")
        state = bridge.load_state(self.config)
        self.assertEqual(set(state["managed_watches"]), {"new-uuid"})
        self.assertEqual(state["pending_creates"], [])

    def test_sync_deletes_removed_source_only_if_registered(self):
        self.registered({"ours": 10})
        self.config["sources"] = []
        foreign = {"ours": self.watch(), "foreign": self.watch(), "sample": {"title": None, "url": "https://example.com/sample"}}
        with mock.patch.object(bridge, "list_watches", return_value=foreign), mock.patch.object(bridge, "api_request") as api:
            self.assertEqual(bridge.sync_watches(self.config), (0, 0, 1))
        api.assert_called_once_with(self.config, "/api/v1/watch/ours", method="DELETE")
        self.assertEqual(bridge.load_state(self.config)["managed_watches"], {})

    def test_deleted_registered_watch_is_replaced_without_retaining_stale_uuid(self):
        self.registered({"ours": 10})
        with mock.patch.object(bridge, "list_watches", return_value={}), mock.patch.object(bridge, "api_request", return_value="replacement"):
            self.assertEqual(bridge.sync_watches(self.config), (1, 0, 0))
        state = bridge.load_state(self.config)
        self.assertEqual(set(state["managed_watches"]), {"replacement"})
        self.assertNotIn("ours", state["last_changed"])

    def test_uncertain_create_preserves_pending_and_blocks_blind_retry(self):
        with mock.patch.object(bridge, "list_watches", return_value={}), mock.patch.object(bridge, "api_request", side_effect=bridge.BridgeError("API timeout")):
            with self.assertRaises(bridge.BridgeError):
                bridge.sync_watches(self.config)
        self.assertEqual(len(bridge.load_state(self.config)["pending_creates"]), 1)
        with mock.patch.object(bridge, "api_request") as api:
            with self.assertRaisesRegex(bridge.BridgeError, "uncertain"):
                bridge.sync_watches(self.config)
            api.assert_not_called()

    def test_service_change_and_watch_url_change_do_not_modify_foreign_watches(self):
        self.registered()
        changed_config = {**self.config, "base_url": "http://127.0.0.1:5001"}
        with self.assertRaisesRegex(bridge.BridgeError, "incompatible"):
            bridge.load_state(changed_config)
        with mock.patch.object(bridge, "list_watches", return_value={"ours": {**self.watch(), "url": "https://example.com/changed"}}), mock.patch.object(bridge, "api_request") as api:
            with self.assertRaisesRegex(bridge.BridgeError, "URL changed"):
                bridge.sync_watches(self.config)
            api.assert_not_called()

    def test_poll_ignores_foreign_and_does_not_collect_on_first_baseline(self):
        self.registered()
        with mock.patch.object(bridge, "list_watches", return_value={"ours": self.watch(), "foreign": self.watch(1000)}), mock.patch.object(bridge, "run_collector") as run, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(bridge.poll(self.config), 0)
            run.assert_not_called()
        self.assertEqual(bridge.load_state(self.config)["last_changed"], {"ours": 100})

    def test_failed_collector_preserves_change_for_retry_then_success_advances(self):
        self.registered({"ours": 0})
        before = self.config["state_path"].read_bytes()
        with mock.patch.object(bridge, "list_watches", return_value={"ours": self.watch(100)}), mock.patch.object(bridge, "run_collector", side_effect=[subprocess.CompletedProcess([], 2), subprocess.CompletedProcess([], 0)]) as run, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(bridge.poll(self.config), 2)
            self.assertEqual(before, self.config["state_path"].read_bytes())
            self.assertEqual(bridge.poll(self.config), 0)
            self.assertEqual(run.call_count, 2)
        self.assertEqual(bridge.load_state(self.config)["last_changed"], {"ours": 100})

    def test_main_failure_counter_retries_and_does_not_echo_subprocess_output(self):
        failed = subprocess.CompletedProcess([], 2, "fictional-secret-output", "fictional-secret-error")
        with mock.patch.object(bridge, "run_collector", side_effect=[failed, failed, subprocess.CompletedProcess([], 0)]), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(bridge.main(self.arguments("run", "--apply")), 2)
            self.assertEqual(bridge.main(self.arguments("run", "--apply")), 2)
            self.assertEqual(json.loads(self.config["source_health_path"].read_text())["bridge"]["consecutive_failures"], 2)
            self.assertEqual(bridge.main(self.arguments("run", "--apply")), 0)
        self.assertNotIn("fictional-secret", output.getvalue())
        self.assertEqual(json.loads(self.config["source_health_path"].read_text())["bridge"]["consecutive_failures"], 0)

    def test_collector_command_uses_explicit_public_interface_and_no_queue_flag(self):
        with mock.patch.object(bridge.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
            bridge.run_collector(self.config)
        command = run.call_args.args[0]
        self.assertEqual(command, [sys.executable, str(bridge.TOOL_DIR / "collect.py"), "--profile", str(self.profile_path), "--sources", str(self.sources_path)])
        self.assertNotIn("--write-queue", command)


if __name__ == "__main__":
    unittest.main()
