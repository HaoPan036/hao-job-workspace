#!/usr/bin/env python3
"""Read-only repository checks. No third-party packages or network access."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
import subprocess
import tempfile


PRIVATE_EXAMPLES: set[str] = set()
IGNORE_PROBES = (
    "private/repo-check-probe.txt", "nested/private/probe.txt",
    "private/README.md", "nested/private/README.md",
    ".obsidian/workspace.json", ".obsidian/workspace-mobile.json",
    ".obsidian/plugins/plugin/data.json", ".obsidian/cache/cache.json",
    "nested/.obsidian/workspace.json", ".env", "nested/.env.local",
    "nested/account-credentials.json", "nested/browser-cookies.json",
    "nested/service-api-key", "nested/service-secret.txt",
)


def git(root: Path, *args: str, data: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "core.quotePath=false", "-C", str(root), *args],
        input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )


class CheckFailure(Exception):
    pass


class Checker:
    def __init__(self, root: Path, staged: bool = False):
        self.root = root
        self.staged = staged
        self.findings: list[tuple[str, str, int, str]] = []
        index = git(root, "ls-files", "--stage", "-z")
        if index.returncode:
            raise CheckFailure("Cannot read Git index")
        self.index: dict[str, tuple[str, str]] = {}
        for entry in index.stdout.split(b"\0"):
            if not entry:
                continue
            metadata, raw_path = entry.split(b"\t", 1)
            mode, oid, stage = metadata.decode("ascii").split()
            path = os.fsdecode(raw_path)
            if stage != "0":
                self.add("error", path, 0, "unmerged-index")
                continue
            self.index[path] = (mode, oid)
        self.paths = set(self.index)
        if not staged:
            others = git(root, "ls-files", "--others", "--exclude-standard", "-z")
            if others.returncode:
                raise CheckFailure("Cannot list working-tree paths")
            self.paths.update(os.fsdecode(p) for p in others.stdout.split(b"\0") if p)
            self.paths = {p for p in self.paths if self.safe_exists(p)}

    def add(self, severity: str, path: str, line: int, category: str) -> None:
        item = (severity, path, line, category)
        if item not in self.findings:
            self.findings.append(item)

    def safe_exists(self, path: str) -> bool:
        candidate = self.root / path
        if any(part == ".." for part in PurePosixPath(path).parts):
            return False
        # Do not follow a symlink, including one in an ancestor directory.
        for parent in (candidate, *candidate.parents):
            if parent == self.root:
                break
            if parent.is_symlink():
                return False
        return candidate.is_file()

    def read(self, path: str) -> bytes | None:
        if "private" in PurePosixPath(path).parts:
            return None
        if self.staged:
            entry = self.index.get(path)
            if not entry:
                return None
            mode, oid = entry
            if mode not in {"100644", "100755"}:
                self.add("warn", path, 0, "non-regular-file-not-read")
                return None
            result = git(self.root, "cat-file", "blob", oid)
            if result.returncode:
                self.add("error", path, 0, "index-blob-unreadable")
                return None
            return result.stdout
        if not self.safe_exists(path):
            return None
        try:
            return (self.root / path).read_bytes()
        except OSError:
            self.add("error", path, 0, "working-file-unreadable")
            return None

    @staticmethod
    def managed(path: str) -> bool:
        return PurePosixPath(path).suffix.lower() in {".md", ".markdown"} and "private" not in PurePosixPath(path).parts

    def metadata(self, path: str, text: str) -> None:
        lines = text.splitlines()
        if not lines or lines[0] != "---":
            self.add("error", path, 1, "skill-frontmatter-missing")
            return
        try:
            end = lines.index("---", 1)
        except ValueError:
            self.add("error", path, 1, "skill-frontmatter-unclosed")
            return
        fields: dict[str, str] = {}
        for number, line in enumerate(lines[1:end], 2):
            match = re.match(r"^(name|description):\s*(.*)$", line)
            if not match:
                continue  # Other metadata is outside this intentionally small checker.
            key, value = match.groups()
            if key in fields:
                self.add("error", path, number, "skill-duplicate-field")
            try:
                if value.startswith('"'):
                    value = json.loads(value)
                elif value.startswith("'"):
                    if not value.endswith("'") or len(value) < 2:
                        raise ValueError
                    value = value[1:-1].replace("''", "'")
                else:
                    value = re.split(r"(?:^|\s+)#", value, maxsplit=1)[0].rstrip()
                    if (not value or value[0] in "|>&*!{[" or ": " in value
                            or re.fullmatch(r"(?i)(?:null|true|false|yes|no|on|off|~|[-+]?\d+(?:\.\d+)?)", value)):
                        raise ValueError
                if not isinstance(value, str) or not value.strip():
                    raise ValueError
            except (ValueError, TypeError):
                self.add("error", path, number, "skill-field-needs-simple-string")
                value = ""
            fields[key] = value
        for key in ("name", "description"):
            if key not in fields:
                self.add("error", path, 1, "skill-" + key + "-missing")
        name = fields.get("name", "")
        if name and (not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name)
                     or len(name) > 64 or name != PurePosixPath(path).parent.name):
            self.add("error", path, 2, "skill-name-invalid-or-directory-mismatch")
        if len(fields.get("description", "")) > 1024:
            self.add("error", path, 3, "skill-description-too-long")

    def links(self, path: str, text: str) -> None:
        from urllib.parse import unquote

        in_fence = False
        for number, original in enumerate(text.splitlines(), 1):
            if re.match(r"^\s*(```|~~~)", original):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            line = re.sub(r"`+[^`]*`+", "", original)
            links = [(m.group(1) or m.group(2), False) for m in re.finditer(
                r"\[[^\]\n]*\]\(\s*(?:<([^>\n]+)>|([^\s)]+))(?:\s+\"[^\"]*\")?\s*\)", line)]
            links += [(m.group(1).split("|", 1)[0].rstrip("\\"), True)
                      for m in re.finditer(r"\[\[([^\]\n]+)\]\]", line)]
            for target, wiki in links:
                target = unquote(target.split("#", 1)[0].split("?", 1)[0])
                if (not target or re.match(r"^[a-zA-Z][\w+.-]*:", target)
                        or target.startswith(("/", "~")) or re.search(r"[<>{}]", target)):
                    continue
                base = "" if wiki and not target.startswith(".") else str(PurePosixPath(path).parent)
                resolved = posixpath.normpath(posixpath.join(base, target))
                if resolved == ".." or resolved.startswith("../"):
                    self.add("error", path, number, "link-outside-package")
                    continue
                if resolved == "private" or resolved.startswith("private/"):
                    continue
                candidates = {resolved}
                if wiki and not PurePosixPath(resolved).suffix:
                    candidates.add(resolved + ".md")
                if self.paths.intersection(candidates) or any(
                    p.startswith(resolved.rstrip("/") + "/") for p in self.paths
                ):
                    continue
                if wiki and "/" not in target:
                    matches = [p for p in self.paths if PurePosixPath(p).stem == target
                               and p.endswith(".md") and not p.startswith("private/")]
                    if len(matches) == 1:
                        continue
                    self.add("warn", path, number, "wiki-basename-unresolved-or-ambiguous")
                else:
                    self.add("error", path, number, "local-link-missing")

    def ignore_rules(self) -> None:
        # Git interprets its own ignore syntax against this view of .gitignore files.
        # An isolated temporary repository excludes local/global Git configuration.
        with tempfile.TemporaryDirectory(prefix="repo-check-ignore-") as directory:
            scratch = Path(directory)
            env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}
            for key in list(env):
                if key.startswith("GIT_") and key not in {"GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_GLOBAL"}:
                    del env[key]
            init = subprocess.run(
                ["git", "-c", "init.templateDir=", "init", "--quiet", str(scratch)],
                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            if init.returncode:
                raise CheckFailure("Cannot create isolated ignore-rule check")
            for path in sorted(p for p in self.paths if PurePosixPath(p).name == ".gitignore"):
                if path.startswith("private/"):
                    continue
                data = self.read(path)
                if data is not None:
                    destination = scratch / path
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(data)
            result = subprocess.run(
                ["git", "-C", str(scratch), "check-ignore", "--no-index", "-z", "--stdin"],
                input=b"\0".join(p.encode() for p in IGNORE_PROBES) + b"\0", env=env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            if result.returncode not in (0, 1):
                raise CheckFailure("Cannot evaluate ignore rules")
            ignored = {os.fsdecode(p) for p in result.stdout.split(b"\0") if p}
            for probe in IGNORE_PROBES:
                if probe not in ignored:
                    self.add("error", ".gitignore", 0, "privacy-ignore-missing:" + probe)

    def privacy(self) -> None:
        for path in sorted(self.paths):
            if "private" in PurePosixPath(path).parts:
                self.add("error", path, 0, "private-path-in-package")
                continue
            example = is_example(path)
            name = PurePosixPath(path).name.lower()
            forbidden = (name.startswith(".env") or name in {"id_rsa", "id_ed25519"}
                         or name.endswith((".pem", ".p12", ".pfx", ".key"))
                         or any(s in name for s in ("credentials", "cookies", "api-key", "secret")))
            if forbidden and not example:
                self.add("error", path, 0, "credential-path-staged")
                continue
            data = self.read(path)
            if data is None:
                continue
            if b"\0" in data:
                self.add("warn", path, 0, "binary-content-not-scanned")
                continue
            try:
                content = data.decode("utf-8")
            except UnicodeDecodeError:
                self.add("warn", path, 0, "non-utf8-content-not-scanned")
                continue
            for number, line in enumerate(content.splitlines(), 1):
                for category in sensitive_categories(line, example):
                    self.add("error", path, number, category)

    def run(self) -> int:
        for path in sorted(p for p in self.paths if self.managed(p)):
            data = self.read(path)
            if data is None:
                continue
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                self.add("error", path, 0, "managed-document-not-utf8")
                continue
            if fnmatch.fnmatchcase(path, ".agents/skills/*/SKILL.md"):
                self.metadata(path, text)
            self.links(path, text)
        self.ignore_rules()
        self.privacy()
        diff_args = ["diff", "--no-ext-diff", "--check"]
        if self.staged:
            diff_args.append("--cached")
        if git(self.root, *diff_args).returncode:
            # git diff --check can include source lines; never print its raw output.
            self.add("error", "<git-diff>", 0, "whitespace-or-conflict-marker")
        for severity, path, line, category in self.findings:
            print(f"{severity.upper()} {json.dumps(path, ensure_ascii=False)}:{line} {category}")
        errors = sum(item[0] == "error" for item in self.findings)
        warnings = sum(item[0] == "warn" for item in self.findings)
        print(f"repo-check: view={'index' if self.staged else 'worktree'} errors={errors} warnings={warnings}")
        return 1 if errors else 0


def is_example(path: str) -> bool:
    parts = PurePosixPath(path).parts
    name = PurePosixPath(path).name.lower()
    return (any(p in {"tests", "test", "fixtures", "examples"} for p in parts)
            or ".example." in name or name.endswith(".example") or name.startswith("example."))


def sensitive_categories(line: str, example: bool) -> set[str]:
    categories: set[str] = set()
    token = (r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"
             r"|\b(?:sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}"
             r"|github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{16,}|AKIA[A-Z0-9]{16})\b")
    if re.search(token, line):
        categories.add("secret-token")
    assignments = re.finditer(
        r"(?i)(?:[\"']?\b(?:[a-z][a-z0-9]*[_-])*(?:api[_-]?key|access[_-]?token|auth[_-]?token|password|passwd|secret|cookie)[\"']?)"
        r"\s*[:=]\s*[\"']?([^\s\"',;]+)", line)
    for assigned in assignments:
        value = assigned.group(1)
        if len(value) >= 6 and not re.fullmatch(
            r"(?i)(?:<[^>]+>|\$\{[^}]+\}|\*+|REDACTED|EXAMPLE|PLACEHOLDER|CHANGEME|YOUR_[A-Z_]+|None|False|True)", value
        ) and not value.startswith(("os.environ", "process.env", "re.compile", "r\"", "r'")):
            categories.add("credential-assignment")
    if re.search(r"(?i)\bBearer\s+[A-Za-z0-9._~-]{16,}", line):
        categories.add("bearer-credential")
    for match in re.finditer(r"(?<![\w.-])[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})(?![\w.-])", line):
        domain = match.group(1).lower()
        reserved = domain in {"example.com", "example.org", "example.net"} or domain.endswith((".invalid", ".test"))
        if not (example and reserved):
            categories.add("email-address")
    for match in re.finditer(r"(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)", line):
        if not (example and match.group(0) == "110101" + "199001010000"):
            categories.add("identity-card-number")
    phone_patterns = (
        r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)",
        r"(?<!\d)\+65[- ]?[689]\d{3}[- ]?\d{4}(?!\d)",
        r"(?i)(?:phone|mobile|telephone|手机号|电话)[\"']?\s*[:=：]\s*[\"']?(\+?[\d ()-]{7,20})",
    )
    for pattern in phone_patterns:
        for match in re.finditer(pattern, line):
            digits = re.sub(r"\D", "", match.group(1) if match.lastindex else match.group(0))
            if len(digits) >= 7 and not (example and (digits == "138" + "00138000" or set(digits) <= {"0"})):
                categories.add("phone-number")
    return categories


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true", help="Check index documents, staged blobs, and staged ignore rules")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    result = git(root, "rev-parse", "--show-toplevel")
    if result.returncode:
        parser.error("Run inside a Git working tree")
    try:
        if Path(os.fsdecode(result.stdout).strip()).resolve() != root:
            raise CheckFailure("Run checks in the standalone package copy, not inside a parent repository")
        return Checker(root, args.staged).run()
    except CheckFailure as exc:
        print("ERROR <repo>:0 " + str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
