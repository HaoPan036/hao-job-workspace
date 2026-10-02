#!/usr/bin/env python3
"""Explicit changedetection.io synchronization and foreground collector triggers."""

from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.dont_write_bytecode = True
import collect
import radar


TOOL_DIR = Path(__file__).resolve().parent
MAX_BYTES = 8 * 1024 * 1024
DEFAULTS = {
    "base_url": "http://127.0.0.1:5000", "allow_remote": False,
    "api_key_env": "CHANGEDETECTION_API_KEY", "api_key_path": "",
    "state_path": "radar/changedetection_state.json",
    "watch_title_prefix": "Job Workspace | ", "check_interval_hours": 2,
    "request_timeout_seconds": 30, "collector_timeout_seconds": 900,
    "source_types": ["html", "rss", "ashby", "greenhouse", "lever", "mycareersfuture", "baidu_campus"],
    "excluded_source_names": [],
}


class BridgeError(ValueError):
    """Errors intentionally omit response bodies, credentials and private values."""


def fail(message: str) -> None:
    raise BridgeError(message)


def private_path(value: Path, *, must_exist: bool = False) -> Path:
    try:
        collect.reject_symlinks(value)
        path = value.resolve()
        ancestor = path.parent
        while not ancestor.exists() and ancestor != ancestor.parent:
            ancestor = ancestor.parent
        repo = subprocess.run(["git", "-C", str(ancestor), "rev-parse", "--show-toplevel"],
                              capture_output=True, text=True, check=False)
        if repo.returncode:
            fail("bridge paths must belong to a Git repository and be ignored and untracked")
        root = Path(repo.stdout.strip()).resolve()
        relative = path.relative_to(root).as_posix()
        ignored = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", "--", relative],
                                 capture_output=True, check=False)
        tracked = subprocess.run(["git", "-C", str(root), "ls-files", "--", relative],
                                 capture_output=True, check=False)
        if ignored.returncode or tracked.returncode or tracked.stdout:
            fail("bridge paths must be ignored and untracked")
        if path.exists() and not path.is_file():
            fail("bridge file path must be a regular file")
        if must_exist and not path.is_file():
            fail("required bridge input file is missing")
        return path
    except (OSError, ValueError) as error:
        if isinstance(error, BridgeError):
            raise
        fail("bridge path is invalid or uses a symbolic link")


def relative_path(base: Path, value: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        fail("configured path must be a non-empty string")
    candidate = Path(value).expanduser()
    return candidate if candidate.is_absolute() else base.parent / candidate


def read_json(path: Path) -> dict:
    path = private_path(path, must_exist=True)
    if path.stat().st_size > MAX_BYTES:
        fail("bridge input exceeds size limit")
    try:
        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    fail("bridge JSON has duplicate keys")
                result[key] = value
            return result
        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)
    except (OSError, UnicodeError, ValueError):
        fail("bridge input is not valid JSON")
    if not isinstance(data, dict):
        fail("bridge JSON must be an object")
    return data


def load_config(path: Path, profile_path: Path, sources_path: Path) -> dict:
    path = private_path(path, must_exist=True)
    values = read_json(path)
    if set(values) - set(DEFAULTS):
        fail("unsupported bridge configuration field")
    config = {**DEFAULTS, **values}
    if not isinstance(config["base_url"], str):
        fail("service URL must be a string")
    parts = urllib.parse.urlsplit(config["base_url"])
    if (parts.scheme not in {"http", "https"} or not parts.hostname or parts.username
            or parts.password or parts.query or parts.fragment or parts.path not in {"", "/"}):
        fail("service URL must be an HTTP(S) origin without credentials or query parameters")
    try:
        local = parts.hostname.lower() == "localhost" or ipaddress.ip_address(parts.hostname).is_loopback
    except ValueError:
        local = False
    if type(config["allow_remote"]) is not bool or (not local and not config["allow_remote"]):
        fail("remote service requires explicit allow_remote configuration")
    if not local and parts.scheme != "https":
        fail("remote service requires HTTPS")
    config["base_url"] = config["base_url"].rstrip("/")
    for key in ("check_interval_hours", "request_timeout_seconds", "collector_timeout_seconds"):
        if type(config[key]) is not int or config[key] < 1:
            fail("bridge intervals and timeouts must be positive integers")
    for key in ("source_types", "excluded_source_names"):
        if not isinstance(config[key], list) or any(not isinstance(v, str) or not v for v in config[key]):
            fail("bridge source filters must be string lists")
    if set(config["source_types"]) - collect.SOURCE_TYPES:
        fail("bridge source type is unsupported")
    if not isinstance(config["watch_title_prefix"], str) or not config["watch_title_prefix"].strip():
        fail("watch title prefix must be non-empty")
    if not isinstance(config["api_key_env"], str) or (config["api_key_env"] and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", config["api_key_env"])):
        fail("API key environment variable name is invalid")
    if not isinstance(config["api_key_path"], str):
        fail("API key path must be a string")
    config["state_path"] = private_path(relative_path(path, config["state_path"]))
    config["profile_path"] = private_path(profile_path, must_exist=True)
    config["sources_path"] = private_path(sources_path, must_exist=True)
    profile = read_json(config["profile_path"])
    payload = read_json(config["sources_path"])
    try:
        collector, sources = collect.validate_inputs(profile, payload, fixtures=False)
    except (ValueError, KeyError, TypeError):
        fail("collector profile or source configuration is invalid")
    config["sources"] = sources
    # Use the collector's existing health file; never create a second health ledger.
    config["source_health_path"] = private_path(relative_path(config["profile_path"], collector["source_health_path"]))
    protected = {path, config["profile_path"], config["sources_path"]}
    queue = profile.get("application_queue", {})
    if isinstance(queue, dict):
        for key in ("path", "application_history_path"):
            if queue.get(key):
                protected.add(private_path(relative_path(config["profile_path"], queue[key])))
    for key in ("database_path", "dossiers_path"):
        protected.add(private_path(relative_path(config["profile_path"], collector[key])))
    if config["api_key_path"]:
        config["api_key_path"] = private_path(relative_path(path, config["api_key_path"]), must_exist=True)
        protected.add(config["api_key_path"])
    reports_dir = relative_path(config["profile_path"], collector["reports_dir"])
    # Check privacy and symlinks without treating an existing directory as a file.
    private_path(reports_dir / ".bridge-path-check")
    reports_dir = reports_dir.resolve()
    outputs = (config["state_path"], config["source_health_path"])
    def overlaps(left, right):
        return left == right or left in right.parents or right in left.parents
    if (overlaps(*outputs)
            or any(overlaps(output, target) for output in outputs for target in protected)
            or any(overlaps(output, reports_dir) for output in outputs)):
        fail("bridge outputs must not overlap inputs, records, collector outputs or the reports directory")
    config["remote"] = not local
    return config


def load_api_key(config: dict) -> str:
    env_name = config["api_key_env"]
    key = os.environ.get(env_name, "").strip() if env_name else ""
    if not key and config["api_key_path"]:
        path = private_path(Path(config["api_key_path"]), must_exist=True)
        if path.stat().st_size > 65536:
            fail("API key file exceeds size limit")
        key = path.read_text(encoding="utf-8").strip()
    if not key and (env_name or config["api_key_path"]):
        fail("configured API key is unavailable")
    if any(ord(char) < 32 for char in key):
        fail("API key has invalid control characters")
    return key


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def api_request(config: dict, path: str, method: str = "GET", payload: dict | None = None) -> object:
    headers = {"Accept": "application/json"}
    key = load_api_key(config)
    if key:
        headers["x-api-key"] = key
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(config["base_url"] + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=config["request_timeout_seconds"]) as response:
            raw = response.read(MAX_BYTES + 1)
            content_type = response.headers.get("content-type", "")
        if len(raw) > MAX_BYTES:
            fail("service response exceeds size limit")
        body = raw.decode("utf-8")
        return json.loads(body) if body and "json" in content_type else body.strip()
    except urllib.error.HTTPError as error:
        fail(f"changedetection API returned HTTP {error.code}; response details suppressed")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, UnicodeError):
        fail("changedetection API request failed; response details suppressed")


def monitorable_sources(sources: list[dict], config: dict) -> list[dict]:
    result, seen = [], set()
    for source in sources:
        if (not source.get("enabled", True) or source.get("type", "html") not in config["source_types"]
                or source.get("type") in {"manual", "portal", "wechat_search"}
                or source["name"] in config["excluded_source_names"]):
            continue
        url = collect.source_url(source)
        if not url or "feishu.cn/base/" in url:
            continue
        normalized = radar.normalize_url(url)
        if normalized not in seen:
            result.append(source)
            seen.add(normalized)
    return result


def desired_watch(source: dict, config: dict) -> dict:
    return {"url": collect.source_url(source), "title": config["watch_title_prefix"] + source["name"],
            "fetch_backend": "html_requests", "processor": "text_json_diff", "paused": False,
            "notification_muted": True, "time_between_check_use_default": False,
            "time_between_check": {"hours": config["check_interval_hours"]}}


def watch_id(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        fail("watch identifier is invalid")
    return value


def load_state(config: dict) -> dict:
    path = private_path(config["state_path"])
    if not path.exists():
        return {"service_url": config["base_url"], "managed_watches": {}, "last_changed": {}, "pending_creates": []}
    state = read_json(path)
    if (state.get("service_url") != config["base_url"] or not isinstance(state.get("managed_watches"), dict)
            or not isinstance(state.get("last_changed"), dict) or not isinstance(state.get("pending_creates"), list)):
        fail("bridge state is incompatible with the configured service; preserve it for review")
    for uuid, url in state["managed_watches"].items():
        watch_id(uuid)
        if not isinstance(url, str) or not url:
            fail("managed watch URL is invalid")
    for uuid, timestamp in state["last_changed"].items():
        watch_id(uuid)
        if type(timestamp) is not int or timestamp < 0:
            fail("watch change timestamp is invalid")
    if any(not isinstance(url, str) or not url for url in state["pending_creates"]):
        fail("pending watch registration is invalid")
    return state


def save_json(path: Path, value: dict) -> None:
    path = private_path(path)
    collect.atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def list_watches(config: dict) -> dict[str, dict]:
    payload = api_request(config, "/api/v1/watch")
    if not isinstance(payload, dict) or any(not isinstance(watch, dict) for watch in payload.values()):
        fail("service returned an invalid watch list")
    return {watch_id(uuid): watch for uuid, watch in payload.items()}


def owned_watches(watches: dict, state: dict) -> dict:
    result = {}
    for uuid, registered_url in state["managed_watches"].items():
        if uuid in watches:
            watch = watches[uuid]
            if radar.normalize_url(watch.get("url", "")) != registered_url:
                fail("registered watch URL changed outside the bridge; reconcile before continuing")
            result[uuid] = watch
    return result


def sync_watches(config: dict) -> tuple[int, int, int]:
    state = load_state(config)
    if state["pending_creates"]:
        fail("a previous watch creation has an uncertain outcome; reconcile the service before retrying")
    watches = list_watches(config)
    owned = owned_watches(watches, state)
    for uuid in set(state["managed_watches"]) - set(watches):
        state["managed_watches"].pop(uuid)
        state["last_changed"].pop(uuid, None)
    save_json(config["state_path"], state)
    existing = {state["managed_watches"][uuid]: uuid for uuid in owned}
    desired = {radar.normalize_url(collect.source_url(source)): desired_watch(source, config)
               for source in monitorable_sources(config["sources"], config)}
    created = updated = deleted = 0
    for url, payload in desired.items():
        uuid = existing.get(url)
        if uuid is None:
            # A timeout after POST must not silently create duplicate watches on retry.
            state["pending_creates"].append(url)
            save_json(config["state_path"], state)
            response = api_request(config, "/api/v1/watch", method="POST", payload=payload)
            uuid = watch_id(response.get("uuid") if isinstance(response, dict) else response)
            if uuid in watches or uuid in state["managed_watches"]:
                fail("service returned an already known identifier; reconcile the pending creation")
            state["managed_watches"][uuid] = url
            state["pending_creates"].remove(url)
            save_json(config["state_path"], state)
            created += 1
        else:
            details = api_request(config, "/api/v1/watch/" + uuid)
            if not isinstance(details, dict) or radar.normalize_url(details.get("url", "")) != url:
                fail("service returned invalid registered watch details")
            fields = {key: value for key, value in payload.items() if details.get(key) != value}
            if fields:
                api_request(config, "/api/v1/watch/" + uuid, method="PUT", payload=fields)
                updated += 1
    for uuid, url in list(state["managed_watches"].items()):
        if url not in desired:
            if uuid in owned:
                api_request(config, "/api/v1/watch/" + uuid, method="DELETE")
                deleted += 1
            state["managed_watches"].pop(uuid)
            state["last_changed"].pop(uuid, None)
            save_json(config["state_path"], state)
    return created, updated, deleted


def detect_changed_watches(watches: dict, previous: dict) -> tuple[list[str], dict]:
    changed, current = [], {}
    for uuid, watch in watches.items():
        value = watch.get("last_changed") or 0
        if type(value) is not int or value < 0:
            fail("service returned an invalid change timestamp")
        current[uuid] = value
        if uuid in previous and value > previous[uuid]:
            changed.append(uuid)
    return changed, current


def run_collector(config: dict) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOL_DIR / "collect.py"),
                           "--profile", str(config["profile_path"]), "--sources", str(config["sources_path"])],
                          cwd=TOOL_DIR, capture_output=True, text=True, check=False,
                          timeout=config["collector_timeout_seconds"])


def poll(config: dict, baseline_only: bool = False) -> int:
    state = load_state(config)
    if state["pending_creates"]:
        fail("pending watch creation must be reconciled before polling")
    owned = owned_watches(list_watches(config), state)
    changed, current = detect_changed_watches(owned, state["last_changed"])
    if changed and not baseline_only:
        result = run_collector(config)
        if result.returncode:
            print("Collector failed; change timestamps kept for retry. Its outputs may be partial.", file=sys.stderr)
            return result.returncode
    state["last_changed"] = current
    save_json(config["state_path"], state)
    print(f"BRIDGE_BASELINE watches={len(current)}" if baseline_only else f"BRIDGE_POLL changed={len(changed)}")
    return 0


def record_bridge_result(config: dict, succeeded: bool) -> None:
    path = private_path(config["source_health_path"])
    health = collect.load_source_health(path)
    previous = health.get("bridge", {})
    failures = previous.get("consecutive_failures", 0)
    if type(failures) is not int or failures < 0:
        fail("bridge health failure count is invalid")
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    health["bridge"] = {**previous, "consecutive_failures": 0 if succeeded else failures + 1,
                        "last_run_at": now, "last_result": "success" if succeeded else "failed"}
    health["updated_at"] = now
    save_json(path, health)


def preview(config: dict, command: str) -> dict:
    state = load_state(config)
    return {"command": command, "preview_only": True, "network_enabled": False, "writes_enabled": False,
            "remote_service": config["remote"], "registered_watches": len(state["managed_watches"]),
            "pending_creates": len(state["pending_creates"]),
            "desired_watches": [desired_watch(source, config) for source in monitorable_sources(config["sources"], config)]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preview", "sync", "poll", "baseline", "run"))
    for name in ("config", "profile", "sources"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="Explicitly allow this command's network and local writes")
    parser.add_argument("--dry-run", action="store_true", help="Offline preview; no API calls, collector or file writes")
    args = parser.parse_args(argv)
    config = None
    active = args.command != "preview" and args.apply and not args.dry_run
    try:
        config = load_config(args.config, args.profile, args.sources)
        if not active:
            print(json.dumps(preview(config, args.command), ensure_ascii=False, indent=2))
            return 0
        if args.command == "sync":
            created, updated, deleted = sync_watches(config)
            print(f"BRIDGE_SYNC created={created} updated={updated} deleted={deleted}")
            result = 0
        elif args.command in {"poll", "baseline"}:
            result = poll(config, baseline_only=args.command == "baseline")
        else:
            result = run_collector(config).returncode
            print(f"BRIDGE_COLLECTOR exit={result}")
        record_bridge_result(config, result == 0)
        return result
    except (BridgeError, OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as error:
        # Never print API bodies, token values, subprocess output or raw config errors.
        message = str(error) if isinstance(error, BridgeError) else "operation failed; inspect configured paths and service without sharing secrets"
        print("bridge: " + message, file=sys.stderr)
        if active and config is not None:
            try:
                record_bridge_result(config, False)
            except (BridgeError, OSError, ValueError, TypeError, KeyError):
                pass
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
