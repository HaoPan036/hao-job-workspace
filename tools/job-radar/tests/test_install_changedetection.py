import contextlib
import io
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import install_changedetection as installer


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fictional-installer-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        subprocess.run(["git", "init", "--quiet", str(self.root)], check=True)
        (self.root / ".gitignore").write_text("private/\nagents/\n", encoding="utf-8")
        self.local = self.root / "private"
        self.local.mkdir()
        self.config_path = self.local / "installer.json"
        self.bridge_path = self.local / "bridge.json"
        self.profile_path = self.local / "profile.json"
        self.source_path = self.local / "sources.json"
        self.token_path = self.local / "token"
        self.token_path.write_text("fictional-local-token\n", encoding="utf-8")
        self.token_path.chmod(0o600)
        self.bridge_path.write_text(json.dumps({
            "base_url": "http://127.0.0.1:5123", "api_key_env": "",
            "api_key_path": "token", "state_path": "state.json"}), encoding="utf-8")
        self.profile_path.write_text("{}", encoding="utf-8")
        self.source_path.write_text('{"sources": []}', encoding="utf-8")
        self.config = {
            "components": ["server", "bridge"], "label_prefix": "local.fictional.radar",
            "runtime_dir": "background", "launch_agents_dir": "../agents",
            "base_url": "http://127.0.0.1:5123", "poll_interval_seconds": 420,
            # Stand-in path only; every service invocation is mocked below.
            "server_executable": str(Path(sys.executable).resolve()),
            "python_executable": str(Path(sys.executable).resolve()),
            "bridge_config": "bridge.json", "profile": "profile.json", "sources": "sources.json",
        }
        self.save()
        self.launch = mock.patch.object(installer, "launchctl", return_value="PID\tStatus\tLabel\n")
        self.mock_launch = self.launch.start()
        self.addCleanup(self.launch.stop)
        self.network = mock.patch("socket.create_connection", side_effect=AssertionError("No network"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def save(self):
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes()
                for p in self.root.rglob("*") if p.is_file() and ".git" not in p.parts}

    def run_cli(self, *arguments, platform="darwin"):
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error), \
                mock.patch.object(installer.sys, "platform", platform):
            code = installer.main([*arguments, "--config", str(self.config_path)])
        return code, output.getvalue(), error.getvalue()

    def test_default_and_unapplied_install_are_read_only(self):
        before = self.snapshot()
        for args in [(), ("plan",), ("install",), ("install", "--apply", "--dry-run")]:
            code, output, error = self.run_cli(*args)
            self.assertEqual(code, 0, error)
            self.assertEqual(json.loads(output)["action"], "plan")
            self.assertNotIn("fictional-local-token", output)
        self.assertEqual(self.snapshot(), before)
        self.mock_launch.assert_not_called()

    def test_fresh_cli_plan_does_not_create_bytecode_or_runtime_files(self):
        scripts = self.root / "scripts"
        scripts.mkdir()
        for name in ("install_changedetection.py", "collect.py", "radar.py"):
            shutil.copyfile(installer.TOOL_DIR / name, scripts / name)
        self.config["components"] = ["server"]
        self.save()
        before = self.snapshot()
        environment = os.environ.copy()
        environment.pop("PYTHONDONTWRITEBYTECODE", None)
        result = subprocess.run([
            sys.executable, str(scripts / "install_changedetection.py"),
            "plan", "--config", str(self.config_path)], env=environment,
            capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(list(self.root.rglob("__pycache__")))
        self.mock_launch.assert_not_called()

    def test_plan_keeps_local_server_and_explicit_bridge_interface(self):
        plan = installer.build_plan(self.config_path)
        server, bridge = [row["plist"] for row in plan["agents"]]
        self.assertEqual(server["ProgramArguments"][1:3], ["-h", "127.0.0.1"])
        self.assertEqual(server["ProgramArguments"][-2:], ["-p", "5123"])
        self.assertEqual(server["EnvironmentVariables"]["LLM_FEATURES_DISABLED"], "true")
        self.assertNotIn("TZ", server["EnvironmentVariables"])
        self.assertEqual(bridge["StartInterval"], 420)
        self.assertEqual(bridge["ProgramArguments"][2:], [
            "poll", "--config", str(self.bridge_path), "--profile", str(self.profile_path),
            "--sources", str(self.source_path), "--apply"])
        self.assertNotIn("fictional-local-token", json.dumps(plan))

    def test_mocked_install_creates_private_files_then_bootstraps_without_reload(self):
        code, output, error = self.run_cli("install", "--apply")
        self.assertEqual(code, 0, error)
        result = json.loads(output)
        self.assertEqual(result["service_readiness"], "NOT_CHECKED")
        for value in result["created_files"]:
            path = Path(value)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("fictional-local-token", path.read_text())
            if path.suffix == ".plist":
                self.assertIn("ProgramArguments", plistlib.loads(path.read_bytes()))
        commands = [call.args[0] for call in self.mock_launch.call_args_list]
        self.assertEqual(commands, ["list", "bootstrap", "bootstrap"])
        self.assertEqual(self.token_path.read_text(), "fictional-local-token\n")

    def test_existing_plist_manifest_log_or_data_is_never_replaced(self):
        plan = installer.build_plan(self.config_path)
        for target in [Path(plan["agents"][0]["plist_path"]),
                       Path(plan["agents"][0]["manifest_path"]),
                       Path(plan["agents"][0]["plist"]["StandardOutPath"])]:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("pre-existing user file")
            before = self.snapshot()
            code, _, _ = self.run_cli("install", "--apply")
            self.assertEqual(code, 2)
            self.assertEqual(self.snapshot(), before)
            target.unlink()
        data = Path(plan["runtime_dir"]) / "data"
        data.mkdir(parents=True)
        (data / "user-record").write_text("keep")
        before = self.snapshot()
        self.assertEqual(self.run_cli("install", "--apply")[0], 2)
        self.assertEqual(self.snapshot(), before)
        self.mock_launch.assert_not_called()

    def test_loaded_label_conflict_is_rejected_before_writes(self):
        self.mock_launch.return_value = "PID Status Label\n- 0 local.fictional.radar.server\n"
        before = self.snapshot()
        self.assertEqual(self.run_cli("install", "--apply")[0], 2)
        self.assertEqual(self.snapshot(), before)
        self.mock_launch.assert_called_once_with("list")

    def test_tracked_or_unignored_inputs_and_runtime_are_rejected(self):
        subprocess.run(["git", "-C", str(self.root), "add", "-f", str(self.config_path)], check=True)
        self.assertEqual(self.run_cli("install", "--apply")[0], 2)
        subprocess.run(["git", "-C", str(self.root), "rm", "--cached", "--quiet", str(self.config_path)], check=True)
        self.config["runtime_dir"] = "../unignored"
        self.save()
        self.assertEqual(self.run_cli("install", "--apply")[0], 2)
        self.assertFalse((self.root / "unignored").exists())
        self.mock_launch.assert_not_called()

    def test_symbolic_runtime_or_token_path_is_rejected(self):
        destination = self.local / "elsewhere"
        destination.mkdir()
        (self.local / "background").symlink_to(destination, target_is_directory=True)
        self.assertEqual(self.run_cli("install", "--apply")[0], 2)
        (self.local / "background").unlink()
        self.token_path.unlink()
        real = self.local / "real-token"
        real.write_text("fictional")
        real.chmod(0o600)
        self.token_path.symlink_to(real)
        self.assertEqual(self.run_cli("install", "--apply")[0], 2)
        self.assertEqual(real.read_text(), "fictional")
        self.mock_launch.assert_not_called()

    def test_token_requires_0600_without_reading_or_printing_it(self):
        self.token_path.chmod(0o644)
        code, output, error = self.run_cli("install", "--apply")
        self.assertEqual(code, 2)
        self.assertIn("0600", error)
        self.assertNotIn("fictional-local-token", output + error)
        self.mock_launch.assert_not_called()

    def test_remote_service_mismatched_port_and_unsafe_label_rejected(self):
        for change in [{"base_url": "http://0.0.0.0:5123"},
                       {"base_url": "http://127.0.0.1:5999"},
                       {"label_prefix": "../../other"}]:
            original = self.config.copy()
            self.config.update(change)
            self.save()
            self.assertEqual(self.run_cli("plan")[0], 2)
            self.config = original
        self.mock_launch.assert_not_called()

    def test_server_only_needs_no_token_and_bridge_can_be_installed_later(self):
        self.config["components"] = ["server"]
        self.save()
        self.token_path.unlink()
        self.assertEqual(self.run_cli("install", "--apply")[0], 0)
        self.config["components"] = ["bridge"]
        self.save()
        self.token_path.write_text("fictional-later-token")
        self.token_path.chmod(0o600)
        self.assertEqual(self.run_cli("install", "--apply")[0], 0)

    def test_non_macos_apply_is_blocked_and_plan_still_works(self):
        before = self.snapshot()
        self.assertEqual(self.run_cli("install", "--apply", platform="linux")[0], 2)
        self.assertEqual(self.run_cli("plan", platform="linux")[0], 0)
        self.assertEqual(self.snapshot(), before)
        self.mock_launch.assert_not_called()

    def test_bootstrap_failure_keeps_files_and_does_not_bootout_other_agents(self):
        self.mock_launch.side_effect = ["PID Status Label\n", RuntimeError("simulated bootstrap failure")]
        code, _, error = self.run_cli("install", "--apply")
        self.assertEqual(code, 2)
        self.assertIn("partially completed", error)
        self.assertTrue(list((self.root / "agents").glob("*.plist")))
        self.assertEqual([c.args[0] for c in self.mock_launch.call_args_list], ["list", "bootstrap"])
        self.assertTrue(self.token_path.exists())


if __name__ == "__main__":
    unittest.main()
