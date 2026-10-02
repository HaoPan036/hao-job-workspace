#!/usr/bin/env python3
"""Initialize missing local templates, or check their structure without reading resumes."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True


PACKAGE = Path(__file__).resolve().parents[2]
FILES = {
    "templates/material-index.md": "private/material-index.md",
    **{f"templates/application-profile/{name}.json": f"private/application-profile/{name}.json"
       for name in ("index", "preferences", "facts", "answers", "internship", "zh", "en", "history")},
    "templates/recruiting/config.example.json": "private/recruiting/config.json",
    "templates/recruiting/history.md": "private/recruiting/history.md",
    "templates/recruiting/queue.md": "private/recruiting/queue.md",
    "templates/job-search/profile.example.json": "private/job-search/profile.json",
    "templates/job-search/sources.example.json": "private/job-search/sources.json",
    **{f"templates/job-search/{name}.md": f"private/job-search/{name}.md"
       for name in ("company-coverage", "current-actions", "dashboard")},
}


def load_tool(name, relative):
    spec = importlib.util.spec_from_file_location(name, PACKAGE / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sync = load_tool("workspace_sync", "tools/recruiting-sync/sync.py")
profile_tool = load_tool("workspace_profile", "tools/application-profile/read.py")
load_tool("radar", "tools/job-radar/radar.py")
collector = load_tool("workspace_collector", "tools/job-radar/collect.py")


def root_path(root):
    root = Path(root).absolute()
    if any(part.is_symlink() for part in (root, *root.parents)):
        sync.fail("root: symlink forbidden")
    return sync.repository(root)


def local_file(root, relative):
    path = sync.safe_path(root, relative, private=True)
    if path.exists() and not path.is_file():
        sync.fail("setup: expected a regular file")
    for parent in path.parents:
        if parent == root:
            break
        if parent.exists() and not parent.is_dir():
            sync.fail("setup: file blocks a parent directory")
    return path


def profile_path(root, profile, value):
    if not isinstance(value, str) or not value:
        sync.fail("search: file path required")
    raw = Path(value) if Path(value).is_absolute() else profile.parent / value
    if any(part.is_symlink() for part in (raw, *raw.parents)):
        sync.fail("search: symlink forbidden")
    return local_file(root, raw.resolve())


def destinations(root):
    result = dict(FILES)
    config_path = local_file(root, "private/recruiting/config.json")
    if config_path.is_file():
        config = sync.load_config(root)
        result["templates/recruiting/history.md"] = config.history
        result["templates/recruiting/queue.md"] = config.queue
    search_path = local_file(root, "private/job-search/profile.json")
    if search_path.is_file():
        search = sync.decode(sync.read_bytes(search_path))
        if not isinstance(search, dict):
            sync.fail("search: configuration object required")
        for key, name in (("company_coverage", "company-coverage"),
                          ("current_actions", "current-actions"), ("dashboard", "dashboard")):
            path = profile_path(root, search_path, search.get(key))
            result[f"templates/job-search/{name}.md"] = path.relative_to(root).as_posix()
    if len(set(result.values())) != len(result):
        sync.fail("setup: template destinations must be distinct")
    return result


def initialize(root, dry_run=False):
    root = root_path(root)
    pending, kept = [], []
    # Validate every destination and source before creating the first directory.
    for source, relative in destinations(root).items():
        destination = local_file(root, relative)
        if destination.exists():
            kept.append(relative)
        else:
            pending.append((destination, sync.read_bytes(PACKAGE / source)))
    if not dry_run:
        for destination, data in pending:
            local_file(root, destination)
            destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            # Exclusive creation also protects a file added after the preflight.
            fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
    return {"created" if not dry_run else "would_create":
            [path.relative_to(root).as_posix() for path, _ in pending], "kept": kept}


def check(root):
    root = root_path(root)
    missing = [relative for relative in destinations(root).values() if not local_file(root, relative).is_file()]
    if missing:
        return {"ok": False, "missing": missing, "issues": ["setup: run init to create missing templates"]}
    index = root / "private/application-profile/index.json"
    index_data = sync.decode(sync.read_bytes(index))
    if not isinstance(index_data, dict) or not isinstance(index_data.get("modules"), dict):
        sync.fail("profile: module registry required")
    for value in index_data["modules"].values():
        if not isinstance(value, str) or Path(value).is_absolute():
            sync.fail("profile: relative module path required")
        local_file(root, index.parent / value)
    profile_result = profile_tool.Profile(index).check()
    records = sync.audit(root)
    config = sync.load_config(root)
    search_path = root / "private/job-search/profile.json"
    search = sync.decode(sync.read_bytes(search_path))
    if not isinstance(search, dict) or not isinstance(search.get("application_queue"), dict):
        sync.fail("search: application_queue configuration required")
    issues = list(records["issues"])
    for key, target in (("path", config.queue), ("application_history_path", config.history)):
        value = search["application_queue"].get(key)
        resolved = profile_path(root, search_path, value)
        if resolved != root / target:
            issues.append(f"search: {key} does not match recruiting configuration")
    for key in ("company_coverage", "current_actions", "dashboard"):
        value = search.get(key)
        path = profile_path(root, search_path, value)
        if not path.is_file():
            issues.append(f"search: {key} file missing")
    sources = sync.decode(sync.read_bytes(root / "private/job-search/sources.json"))
    collector.validate_inputs(search, sources, fixtures=False)
    return {"ok": not issues, "profile_structure": profile_result["ok"],
            "history_rows": records["history_rows"], "issues": issues,
            "scope": "Structure only; facts, completeness and job authorization are not verified."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "check"):
        command = commands.add_parser(name)
        command.add_argument("--root", default=PACKAGE)
        if name == "init":
            command.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            result = initialize(args.root, args.dry_run)
            key = "would_create" if args.dry_run else "created"
            print(f"{'INIT_PREVIEW' if args.dry_run else 'INIT_DONE'} {key}={len(result[key])} kept={len(result['kept'])}")
            for path in result[key]:
                print(path)
            print("Edit the blank profile and example region configuration before using real data.")
            return 0
        result = check(args.root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("SETUP_CHECK_PASS" if result["ok"] else "SETUP_CHECK_REVISE")
        return 0 if result["ok"] else 1
    except (sync.SyncError, profile_tool.ProfileError) as error:
        print(str(error), file=sys.stderr)
        return 1
    except (OSError, ValueError, TypeError):
        print("setup: local file or configuration error; no source files were overwritten", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
