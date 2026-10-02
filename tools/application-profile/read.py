#!/usr/bin/env python3
"""Read a split, local-only application profile without following text references."""

import argparse
import json
from pathlib import Path
import re
import sys

META = {"status", "evidence_status", "record_id", "reuse_scope", "confirmed_on",
        "refresh_triggers", "source", "review_after", "date_confirmed_on",
        "date_fill_policy", "period_boundary"}
TOKEN = re.compile(r"([A-Za-z_][A-Za-z0-9_-]*)|\[(0|[1-9][0-9]*|\*)\]")


class ProfileError(ValueError):
    """A deliberately value-free diagnostic."""


def tokens(ref):
    if not isinstance(ref, str) or not ref:
        raise ProfileError("Invalid logical reference")
    result, offset = [], 0
    for match in TOKEN.finditer(ref):
        gap = ref[offset:match.start()]
        if gap != ("." if result and match.group(1) else ""):
            raise ProfileError("Invalid logical reference")
        result.append(match.group(1) or ("*" if match.group(2) == "*" else int(match.group(2))))
        offset = match.end()
    if offset != len(ref) or not result or not isinstance(result[0], str) or result[0] == "*":
        raise ProfileError("Invalid logical reference")
    return tuple(result)


def path(parts):
    return "".join((f"[{p}]" if isinstance(p, int) or p == "*" else ("." if i else "") + p)
                   for i, p in enumerate(parts))


def prefix(pattern, actual):
    return len(pattern) <= len(actual) and all(a == b or a == "*" and isinstance(b, int)
                                               for a, b in zip(pattern, actual))


def unambiguous(registry):
    keys = list(registry)
    for i, left in enumerate(keys):
        if any(len(left) == len(right) and all(a == b or a == "*" and isinstance(b, int)
               or b == "*" and isinstance(a, int) for a, b in zip(left, right)) for right in keys[i + 1:]):
            raise ProfileError("Ambiguous entry or alias paths")


def strings(value, depth=0):
    if depth > 32:
        raise ProfileError("Reference nesting limit exceeded")
    if isinstance(value, str):
        yield value
    elif isinstance(value, (dict, list)):
        for item in (value.values() if isinstance(value, dict) else value):
            yield from strings(item, depth + 1)
    else:
        raise ProfileError("Invalid reference collection")


def load_json(filename):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ProfileError("Duplicate JSON key")
            result[key] = value
        return result
    try:
        if any(p.is_symlink() for p in (filename, *filename.parents)):
            raise ProfileError("Symlink paths are forbidden")
        with filename.open(encoding="utf-8") as stream:
            value = json.load(stream, object_pairs_hook=unique,
                              parse_constant=lambda _: (_ for _ in ()).throw(ProfileError("Invalid JSON constant")))
        if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != 2:
            raise ProfileError("Expected schema version 2 object")
        return value
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError):
        raise ProfileError("Cannot read a valid JSON-compatible profile file") from None


class Profile:
    def __init__(self, filename):
        self.filename = Path(filename).absolute()
        self.index = load_json(self.filename)
        self.modules = self.index.get("modules")
        if not isinstance(self.modules, dict) or not self.modules:
            raise ProfileError("Missing module registry")
        self.entries = {}
        for module, relative in self.modules.items():
            if (not isinstance(relative, str) or not relative or Path(relative).is_absolute()
                    or ".." in Path(relative).parts):
                raise ProfileError("Unsafe module path")
            entries = load_json(self.filename.parent / relative).get("entries")
            if not isinstance(entries, dict):
                raise ProfileError("Invalid module entries")
            for ref, value in entries.items():
                key = tokens(ref)
                if key in self.entries:
                    raise ProfileError("Duplicate entry path")
                self.entries[key] = (module, ref, value)
        unambiguous(self.entries)
        aliases = self.index.get("aliases", {})
        if not isinstance(aliases, dict):
            raise ProfileError("Invalid alias registry")
        self.aliases = {tokens(key): tokens(value) for key, value in aliases.items()}
        unambiguous(self.aliases)
        self.fill = self.index.get("current_fill_index")
        if not isinstance(self.fill, dict):
            raise ProfileError("Missing current fill index")
        for key in ("required_refs", "internship_refs"):
            if not isinstance(self.fill.get(key), list):
                raise ProfileError("Missing required reference list")
        languages = self.fill.get("language_modules")
        if (not isinstance(languages, dict) or not {"zh", "en"} <= languages.keys()
                or any(not isinstance(module, str) or module not in self.modules for module in languages.values())):
            raise ProfileError("Invalid language module registry")

    def canonical(self, parts):
        seen = set()
        while True:
            if parts in seen:
                raise ProfileError("Cyclic alias")
            seen.add(parts)
            candidates = [key for key in self.aliases if prefix(key, parts)]
            if not candidates:
                return parts
            key = max(candidates, key=len)
            captured = iter(item for pattern, item in zip(key, parts) if pattern == "*")
            parts = tuple(next(captured, "*") if item == "*" else item for item in self.aliases[key]) + parts[len(key):]
            if len(seen) > len(self.aliases) + 1:
                raise ProfileError("Cyclic or expanding alias")

    def resolve(self, parts):
        candidates = [key for key in self.entries if prefix(key, parts)]
        if not candidates:
            raise ProfileError("Reference not found")
        key = max(candidates, key=len)
        module, entry, value = self.entries[key]
        try:
            for item in parts[len(key):]:
                if isinstance(item, int) and isinstance(value, list) or isinstance(item, str) and isinstance(value, dict):
                    value = value[item]
                else:
                    raise ProfileError("Reference not found")
        except (KeyError, IndexError):
            raise ProfileError("Reference not found") from None
        return {"ref": path(parts), "module": self.modules[module], "entry": entry,
                "suffix": path(parts[len(key):]), "value": value}, module

    def expand(self, ref):
        states = [()]
        for item in self.canonical(tokens(ref)):
            if item != "*":
                states = [parts + (item,) for parts in states]
                continue
            expanded = []
            for parts in states:
                indices = {key[len(parts)] for key in self.entries if len(key) > len(parts)
                           and prefix(parts, key) and isinstance(key[len(parts)], int)}
                try:
                    value = self.resolve(parts)[0]["value"]
                    if isinstance(value, list):
                        indices.update(range(len(value)))
                except ProfileError:
                    pass
                expanded.extend(parts + (i,) for i in sorted(indices))
            states = expanded
        if not states:
            raise ProfileError("Wildcard reference has no matches")
        return states

    def locate(self, ref):
        return {"ref": ref, "matches": [{k: v for k, v in self.resolve(parts)[0].items() if k != "value"}
                                         for parts in self.expand(ref)]}

    def get(self, ref, include_history=False):
        matches = []
        for parts in self.expand(ref):
            record, module = self.resolve(parts)
            if module == "history" and not include_history:
                raise ProfileError("Historical values require --include-history")
            metadata = {}
            for size in range(1, len(parts) + 1):
                try:
                    ancestor, ancestor_module = self.resolve(parts[:size])
                except ProfileError:
                    continue
                if ancestor_module == "history" and not include_history:
                    raise ProfileError("Historical values require --include-history")
                value = ancestor["value"]
                if isinstance(value, dict):
                    metadata.update({key: value[key] for key in META if key in value})
            record["metadata"] = metadata
            matches.append(record)
        return {"ref": ref, "matches": matches}

    def get_many(self, refs, include_history=False, verbose=False):
        results = []
        for index, ref in enumerate(refs):
            try:
                matches = self.get(ref, include_history)["matches"]
            except ProfileError as error:
                results.append({"index": index, "error": str(error)})
                continue
            if not verbose:
                matches = [{key: record[key] for key in ("ref", "value", "metadata")}
                           for record in matches]
            results.append({"index": index, "matches": matches})
        return {"ok": all("error" not in item for item in results), "results": results}

    def families(self):
        registry = self.fill.get("problem_family_refs", {})
        if not isinstance(registry, dict):
            raise ProfileError("Invalid answer-family registry")
        return {"problem_families": sorted(registry)}

    def answers(self, problem_family):
        """Retrieve candidates, never infer applicability or a Yes/No answer."""
        if problem_family not in self.families()["problem_families"]:
            raise ProfileError("Answer family not indexed; inspect families and context lookup_refs")
        refs = list(strings(self.fill["problem_family_refs"][problem_family]))
        if not refs:
            raise ProfileError("Answer family has no references; inspect context lookup_refs")
        matches, seen = [], set()
        for ref in refs:
            for record in self.get(ref)["matches"]:
                if record["ref"] not in seen:
                    matches.append(record)
                    seen.add(record["ref"])
        return {"problem_family": problem_family, "candidate_only": True, "matches": matches}

    def check(self):
        checked, ignored = 0, 0
        for alias in self.aliases:
            self.locate(path(alias))
            checked += 1
        for key, value in self.fill.items():
            if key.endswith("_refs"):
                for ref in strings(value):
                    self.locate(ref)
                    checked += 1
        roots = {key[0] for key in self.entries} | {key[0] for key in self.aliases}
        def scan(value, depth=0):
            nonlocal checked, ignored
            if depth > 64:
                raise ProfileError("Module nesting limit exceeded")
            if isinstance(value, dict):
                for key, child in value.items():
                    if key.endswith(("_ref", "_refs")):
                        refs = list(strings(child))
                        for ref in refs:
                            try:
                                logical = tokens(ref)
                            except ProfileError:
                                ignored += 1
                                continue
                            if logical[0] in roots:
                                self.locate(ref)
                                checked += 1
                            else:
                                ignored += 1
                    else:
                        scan(child, depth + 1)
            elif isinstance(value, list):
                for child in value:
                    scan(child, depth + 1)
        for parts, (_, _, value) in self.entries.items():
            if "*" in parts:
                self.locate(path(parts))
            scan({parts[-1]: value} if isinstance(parts[-1], str) else value)
        return {"ok": True, "modules": len(self.modules), "entries": len(self.entries),
                "validated_refs": checked, "ignored_external_refs": ignored}

    def context(self, kind, language, company=None, problem_family=None):
        if kind not in ("internship", "full_time") or language not in ("zh", "en"):
            raise ProfileError("Invalid context selection")
        refs = self.fill["required_refs"] + (self.fill["internship_refs"] if kind == "internship" else [])
        excluded = set(self.fill["language_modules"].values()) - {self.fill["language_modules"][language]}
        excluded |= {"history"} | ({"internship"} if kind == "full_time" else set())
        records = []
        for ref in refs:
            if any(self.resolve(parts)[1] not in ({"preferences", "internship"} - excluded)
                   for parts in self.expand(ref)):
                raise ProfileError("Context value references must select current policy modules")
            for selected in self.get(ref)["matches"]:
                value = selected["value"]
                records.append({"ref": selected["ref"], "value": value,
                                "metadata": {key: item for key, item in selected["metadata"].items()
                                             if not isinstance(value, dict) or key not in value}})
        def scoped_refs(value, depth=0):
            if depth > 32:
                raise ProfileError("Reference nesting limit exceeded")
            if isinstance(value, str):
                return value if all(self.resolve(parts)[1] not in excluded for parts in self.expand(value)) else None
            if isinstance(value, dict):
                return {key: found for key, child in value.items() if (found := scoped_refs(child, depth + 1))}
            if isinstance(value, list):
                return [found for child in value if (found := scoped_refs(child, depth + 1))]
            raise ProfileError("Invalid reference collection")
        lookup = {key: scoped_refs(value) for key, value in self.fill.items()
                  if key.endswith("_refs") and key not in
                  ("required_refs", "internship_refs", "company_refs", "problem_family_refs")}
        for registry, selected in (("company_refs", company), ("problem_family_refs", problem_family)):
            if selected is not None:
                mapping = self.fill.get(registry, {})
                if not isinstance(mapping, dict) or selected not in mapping:
                    raise ProfileError("Requested context scope not found")
                lookup[registry] = {selected: scoped_refs(mapping[selected])}
        return {"kind": kind, "language": language, "records": records,
                "modules": {key: value for key, value in self.modules.items() if key not in excluded},
                "lookup_refs": lookup}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, help="Explicit local JSON or JSON-compatible YAML index")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check")
    commands.add_parser("families")
    answers = commands.add_parser("answers")
    answers.add_argument("--problem-family", required=True, help="Exact key listed by families")
    for name in ("locate", "get"):
        command = commands.add_parser(name)
        command.add_argument("ref")
        if name == "get":
            command.add_argument("--include-history", action="store_true")
    batch = commands.add_parser("get-many", help="Read selected fields in one batch")
    batch.add_argument("refs", nargs="+", help="Exact logical references, in result order")
    batch.add_argument("--include-history", action="store_true")
    batch.add_argument("--verbose", action="store_true", help="Include module, entry and suffix diagnostics")
    context = commands.add_parser("context")
    context.add_argument("--kind", choices=("internship", "full_time"), required=True)
    context.add_argument("--language", choices=("zh", "en"), required=True)
    context.add_argument("--company", help="Include only this company index key")
    context.add_argument("--problem-family", help="Include only this answer-family index key")
    args = parser.parse_args()
    try:
        profile = Profile(args.profile)
        if args.command == "context":
            result = profile.context(args.kind, args.language, args.company, args.problem_family)
        elif args.command == "get":
            result = profile.get(args.ref, args.include_history)
        elif args.command == "get-many":
            result = profile.get_many(args.refs, args.include_history, args.verbose)
        elif args.command == "answers":
            result = profile.answers(args.problem_family)
        else:
            result = getattr(profile, args.command)(*([args.ref] if args.command == "locate" else []))
        if args.command == "get-many" and not args.verbose:
            print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if args.command == "get-many" and not result["ok"] else 0
    except ProfileError as error:
        print(json.dumps({"error": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
