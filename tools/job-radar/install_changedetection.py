#!/usr/bin/env python3
"""Plan optional macOS LaunchAgents; only install --apply writes or starts them.

No dependency installation, shell commands, token extraction, watch changes,
replacement of existing agents, or removal of service data is performed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import re
import stat
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

import collect
import radar


TOOL_DIR = Path(__file__).resolve().parent
COMPONENTS = {"server", "bridge"}


def configured_path(config_path: Path, value: object) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("configured paths must be non-empty strings")
    return collect.configured_path(config_path, value)


def read_config(path: Path) -> dict:
    collect.reject_symlinks(path)
    result = radar.load_json(path)
    if not isinstance(result, dict):
        raise ValueError("installer configuration must be an object")
    return result


def loopback_port(base_url: object) -> int:
    from urllib.parse import urlsplit

    if not isinstance(base_url, str):
        raise ValueError("base_url must be a loopback HTTP URL")
    parsed = urlsplit(base_url)
    if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1"
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        raise ValueError("local installation requires http://127.0.0.1:<port>")
    port = parsed.port
    if port is None or not 1 <= port <= 65535:
        raise ValueError("base_url must include a valid port")
    return port


def build_plan(config_path: Path) -> dict:
    """Read only named configuration files; do not read credentials or services."""
    config = read_config(config_path)
    selected = config.get("components", ["server", "bridge"])
    if (not isinstance(selected, list) or not selected
            or any(item not in COMPONENTS for item in selected)
            or len(set(selected)) != len(selected)):
        raise ValueError("components must select server, bridge, or both once")
    prefix = config.get("label_prefix", "local.job-workspace.changedetection")
    if not isinstance(prefix, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.-]{0,110}", prefix):
        raise ValueError("label_prefix must contain only letters, digits, dots and hyphens")
    interval = config.get("poll_interval_seconds", 300)
    if isinstance(interval, bool) or not isinstance(interval, int) or interval < 1:
        raise ValueError("poll_interval_seconds must be a positive integer")
    runtime = configured_path(config_path, config.get("runtime_dir", "background"))
    agents = configured_path(config_path, config.get(
        "launch_agents_dir", str(Path.home() / "Library" / "LaunchAgents")))
    port = loopback_port(config.get("base_url", "http://127.0.0.1:5000"))
    environment = {"DISABLE_VERSION_CHECK": "true", "LLM_FEATURES_DISABLED": "true"}
    timezone = config.get("timezone")
    if timezone is not None:
        if not isinstance(timezone, str) or not timezone.strip() or "\n" in timezone:
            raise ValueError("timezone must be a non-empty single-line string")
        environment["TZ"] = timezone
    inputs = [str(config_path.resolve())]
    token_path = None
    bridge_args: list[str] = []
    if "bridge" in selected:
        bridge_config = configured_path(config_path, config.get("bridge_config"))
        profile = configured_path(config_path, config.get("profile"))
        sources = configured_path(config_path, config.get("sources"))
        bridge = read_config(bridge_config)
        if loopback_port(bridge.get("base_url", "http://127.0.0.1:5000")) != port:
            raise ValueError("installer and bridge base_url ports must match")
        token_path = str(configured_path(bridge_config, bridge.get("api_key_path")))
        python = Path(config.get("python_executable", sys.executable)).expanduser().resolve()
        bridge_args = [str(python), str(TOOL_DIR / "changedetection_bridge.py"), "poll",
                       "--config", str(bridge_config), "--profile", str(profile),
                       "--sources", str(sources), "--apply"]
        inputs.extend(map(str, [bridge_config, profile, sources]))
    outputs = []
    for component in selected:
        label = prefix + "." + component
        arguments = bridge_args
        if component == "server":
            executable = config.get("server_executable")
            if not isinstance(executable, str) or not executable or not Path(executable).is_absolute():
                raise ValueError("server_executable must name an explicitly selected absolute executable path")
            arguments = [str(Path(executable).expanduser().resolve()), "-h", "127.0.0.1",
                         "-d", str(runtime / "data"), "-p", str(port)]
        payload = {
            "Label": label, "ProgramArguments": arguments,
            "WorkingDirectory": str(TOOL_DIR), "EnvironmentVariables": environment,
            "RunAtLoad": True, "ProcessType": "Background",
            "StandardOutPath": str(runtime / "logs" / (component + ".stdout.log")),
            "StandardErrorPath": str(runtime / "logs" / (component + ".stderr.log")),
        }
        if component == "server":
            payload["KeepAlive"] = True
        else:
            payload["StartInterval"] = interval
        outputs.append({"component": component, "label": label,
                        "plist_path": str(agents / (label + ".plist")),
                        "manifest_path": str(runtime / "manifests" / (label + ".json")),
                        "plist": payload})
    protected = set(inputs + ([token_path] if token_path else []))
    generated = [path for output in outputs for path in (
        output["plist_path"], output["manifest_path"], output["plist"]["StandardOutPath"],
        output["plist"]["StandardErrorPath"])]
    if len(set(generated)) != len(generated) or set(generated) & protected:
        raise ValueError("installation outputs must not overlap configuration or credential inputs")
    return {"schema_version": 1, "action": "plan", "writes_enabled": False,
            "runtime_dir": str(runtime), "inputs": inputs, "api_key_path": token_path,
            "agents": outputs,
            "notes": ["Existing plist, manifest, log targets or loaded labels block installation.",
                      "No dependency download, token extraction, sync or baseline is performed.",
                      "Successful bootstrap does not prove service readiness or authentication."]}


def exclusive_write(path: Path, content: bytes) -> None:
    collect.reject_symlinks(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    collect.reject_symlinks(path)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)


def launchctl(*arguments: str) -> str:
    result = subprocess.run(["/bin/launchctl", *arguments], capture_output=True,
                            text=True, check=False, shell=False)
    if result.returncode:
        # Service output may contain user-specific paths or configuration.
        raise RuntimeError("launchctl operation failed: " + arguments[0])
    return result.stdout


def require_ignored_path(path: Path) -> None:
    collect.require_runtime_path(path)
    ancestor = path.parent
    while not ancestor.exists() and ancestor != ancestor.parent:
        ancestor = ancestor.parent
    result = subprocess.run(["git", "-C", str(ancestor), "rev-parse", "--show-toplevel"],
                            capture_output=True, text=True, check=False, shell=False)
    if result.returncode:
        raise ValueError("installer runtime and inputs must be inside Git, ignored and untracked")


def preflight(plan: dict) -> None:
    if sys.platform != "darwin":
        raise ValueError("installation is supported only on macOS; use plan on other systems")
    runtime = Path(plan["runtime_dir"])
    require_ignored_path(runtime)
    for value in plan["inputs"]:
        path = Path(value)
        require_ignored_path(path)
        if not path.is_file():
            raise ValueError("a required local configuration file is missing")
    if plan["api_key_path"]:
        token = Path(plan["api_key_path"])
        require_ignored_path(token)
        if not token.is_file() or stat.S_IMODE(token.stat().st_mode) != 0o600:
            raise ValueError("api_key_path must be a local file with permissions 0600")
        if token.stat().st_size == 0:
            raise ValueError("api_key_path must not be empty")
        # Share the bridge's configuration and runtime-path validation without
        # contacting its service or reading the token value.
        import changedetection_bridge
        changedetection_bridge.load_config(
            Path(plan["inputs"][1]), Path(plan["inputs"][2]), Path(plan["inputs"][3]))
    for output in plan["agents"]:
        payload = output["plist"]
        executable = Path(payload["ProgramArguments"][0])
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise ValueError("a configured executable is missing or not executable")
        if output["component"] == "bridge" and not Path(payload["ProgramArguments"][1]).is_file():
            raise ValueError("changedetection_bridge.py is missing")
        if output["component"] == "server" and (runtime / "data").exists():
            raise ValueError("server data directory already exists; choose an unused runtime directory")
        for value in (output["plist_path"], output["manifest_path"],
                      payload["StandardOutPath"], payload["StandardErrorPath"]):
            path = Path(value)
            collect.require_runtime_path(path)
            if path.exists():
                raise ValueError("installation target already exists; existing files are never replaced")
    # A task can already be loaded even when its plist has been moved away.
    loaded = {line.split()[-1] for line in launchctl("list").splitlines() if line.split()}
    if any(output["label"] in loaded for output in plan["agents"]):
        raise ValueError("a selected LaunchAgent label is already loaded")


def install(plan: dict) -> dict:
    preflight(plan)
    runtime = Path(plan["runtime_dir"])
    runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
    if any(output["component"] == "server" for output in plan["agents"]):
        (runtime / "data").mkdir(mode=0o700)
    (runtime / "logs").mkdir(parents=True, exist_ok=True, mode=0o700)
    created = []
    for output in plan["agents"]:
        payload = plistlib.dumps(output["plist"], sort_keys=False)
        exclusive_write(Path(output["plist_path"]), payload)
        created.append(output["plist_path"])
        manifest = {"schema_version": 1, "label": output["label"],
                    "plist_path": output["plist_path"],
                    "plist_sha256": hashlib.sha256(payload).hexdigest(),
                    "meaning": "installer-created file; not proof of a running or ready service"}
        exclusive_write(Path(output["manifest_path"]),
                        (json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
        created.append(output["manifest_path"])
    bootstrapped = []
    try:
        for output in plan["agents"]:
            launchctl("bootstrap", f"gui/{os.getuid()}", output["plist_path"])
            bootstrapped.append(output["label"])
    except RuntimeError as error:
        raise RuntimeError("installation partially completed; preserve generated files and inspect macOS service state; no rollback or deletion was attempted") from error
    return {"action": "install", "writes_enabled": True, "created_files": created,
            "bootstrapped_labels": bootstrapped, "service_readiness": "NOT_CHECKED"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "install"), nargs="?", default="plan")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="Enable an explicitly selected install action")
    parser.add_argument("--dry-run", action="store_true", help="Always print a plan without writing or invoking services")
    args = parser.parse_args(argv)
    try:
        if args.apply and args.command != "install":
            raise ValueError("--apply requires the install command")
        plan = build_plan(args.config)
        result = install(plan) if args.command == "install" and args.apply and not args.dry_run else plan
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
