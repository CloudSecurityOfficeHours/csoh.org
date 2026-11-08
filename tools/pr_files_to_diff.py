#!/usr/bin/env python3
"""
Rebuild a unified diff from the pull request "files" API.

WHY THIS EXISTS
---------------
`.github/workflows/security-impact-review.yml` reads a pull request as data: a
.diff fetched through the API and parsed by `tools/pr_security_triage.py`.
GitHub serves that whole-PR diff (`Accept: application/vnd.github.v3.diff`)
only for pull requests touching 300 files or fewer. Past that it answers HTTP
406 and points at the paginated "List pull request files" endpoint, which has
a 3000-file ceiling but returns JSON: one object per file, the hunks in a
`patch` field, and no file modes.

This script turns that JSON back into the shape the triage script parses: a
`diff --git` header per file, mode lines, rename lines, the `---`/`+++` pair
and the hunks. File modes come from the git trees API (one recursive listing
of the head tree, and one of the base tree for the files that existed before),
because the triage script's symlink and executable-bit checks read modes from
the headers and the files endpoint does not carry them.

WHAT IT DOES NOT DO
-------------------
It never fetches anything and never touches the filesystem beyond the paths
it is given. The workflow fetches; this script only reshapes, so the untrusted
content still enters as data and is still read by a checked-in script.

It also cannot recover a patch GitHub withheld. The files endpoint omits
`patch` for binary files and for a change too large to render. Both come out
as a `Binary files ... differ` line, which the triage script reports as content
that could not be read in review. That is the honest outcome for an unread
file, whichever of the two reasons applies.

A truncated tree listing is an error, not a warning. A mode the script cannot
see defaults to a plain file, and a symlink check that defaults to "plain
file" is a check that reports nothing while broken.

USAGE
-----
    gh api --paginate "repos/O/R/pulls/N/files?per_page=100" > pr-files.json
    gh api "repos/O/R/git/trees/<head sha>?recursive=1" > head-tree.json
    gh api "repos/O/R/git/trees/<base sha>?recursive=1" > base-tree.json
    python3 tools/pr_files_to_diff.py --files pr-files.json \\
        --head-tree head-tree.json --base-tree base-tree.json > pr.diff
    python3 tools/pr_files_to_diff.py --self-test

`--files` accepts whatever `gh api --paginate` wrote: one JSON array per page
back to back, the arrays nested by `--slurp`, or one object per line from
`--jq '.[]'`. Exit status is 0 on success, 1 on any input it cannot use.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PLAIN_MODE = "100644"


# -----------------------------------------------------------------------------
# Input
# -----------------------------------------------------------------------------

def read_json_values(text: str) -> list:
    """Parse every JSON value in `text`, however the values were concatenated."""
    decoder = json.JSONDecoder()
    values = []
    pos = 0
    length = len(text)
    while True:
        while pos < length and text[pos].isspace():
            pos += 1
        if pos >= length:
            break
        value, pos = decoder.raw_decode(text, pos)
        values.append(value)
    return values


def flatten_files(values: list) -> list[dict]:
    """Collapse pages, slurped pages and bare objects into one list of files."""
    files: list[dict] = []
    for value in values:
        if isinstance(value, dict):
            files.append(value)
        elif isinstance(value, list):
            files.extend(flatten_files(value))
        else:
            raise ValueError(f"unexpected JSON value in files input: {type(value).__name__}")
    for f in files:
        if "filename" not in f or "status" not in f:
            raise ValueError("a files entry lacks `filename` or `status`; this is not the pull request files endpoint")
    return files


def tree_modes(tree: dict, label: str) -> dict[str, str]:
    """Map path -> mode for every non-directory entry of a recursive tree listing."""
    if tree.get("truncated"):
        raise ValueError(
            f"the {label} tree listing is truncated, so file modes are incomplete; "
            "refusing to default the missing ones to plain files"
        )
    entries = tree.get("tree")
    if not isinstance(entries, list):
        raise ValueError(f"the {label} tree listing has no `tree` array; this is not the git trees endpoint")
    return {e["path"]: e["mode"] for e in entries if e.get("type") != "tree"}


# -----------------------------------------------------------------------------
# Output
# -----------------------------------------------------------------------------

def render_file(f: dict, head: dict[str, str], base: dict[str, str]) -> list[str]:
    new_path = f["filename"]
    old_path = f.get("previous_filename") or new_path
    status = f["status"]
    patch = f.get("patch")
    changes = int(f.get("changes") or 0)

    new_mode = head.get(new_path, PLAIN_MODE)
    old_mode = base.get(old_path, PLAIN_MODE)

    lines = [f"diff --git a/{old_path} b/{new_path}"]

    if status == "added":
        lines.append(f"new file mode {new_mode}")
    elif status == "removed":
        lines.append(f"deleted file mode {old_mode}")
    else:
        if old_mode != new_mode:
            lines.append(f"old mode {old_mode}")
            lines.append(f"new mode {new_mode}")
        if status in ("renamed", "copied") and old_path != new_path:
            verb = "rename" if status == "renamed" else "copy"
            lines.append(f"{verb} from {old_path}")
            lines.append(f"{verb} to {new_path}")

    a_side = "/dev/null" if status == "added" else f"a/{old_path}"
    b_side = "/dev/null" if status == "removed" else f"b/{new_path}"

    if patch:
        lines.append(f"--- {a_side}")
        lines.append(f"+++ {b_side}")
        lines.append(patch)
    elif changes > 0 or status in ("added", "removed", "modified"):
        # No hunks to show. A rename, copy or mode change with zero changes is
        # legitimately empty; anything else here is content GitHub would not
        # render, binary or oversized, and the reviewer has to be told so.
        lines.append(f"Binary files {a_side} and {b_side} differ")
    return lines


def build_diff(files: list[dict], head: dict[str, str], base: dict[str, str]) -> str:
    out: list[str] = []
    for f in files:
        out.extend(render_file(f, head, base))
    return "\n".join(out) + ("\n" if out else "")


# -----------------------------------------------------------------------------
# Self-test
# -----------------------------------------------------------------------------
# Runs the output through the consumer's own parser. Asserting on the text
# would only prove the script agrees with itself; what matters is that
# pr_security_triage.py reads back the file states this script meant to write.

def _self_test() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import pr_security_triage as triage  # noqa: E402  (the consumer, imported for its parser)

    page1 = [
        {"filename": "docs/new.md", "status": "added", "additions": 2, "deletions": 0, "changes": 2,
         "patch": "@@ -0,0 +1,2 @@\n+hello\n+world"},
        {"filename": "tools/run.sh", "status": "modified", "additions": 1, "deletions": 0, "changes": 1,
         "patch": "@@ -1,2 +1,3 @@\n #!/bin/sh\n+echo hi\n exit 0"},
        {"filename": "old.txt", "status": "removed", "additions": 0, "deletions": 1, "changes": 1,
         "patch": "@@ -1 +0,0 @@\n-gone"},
    ]
    page2 = [
        {"filename": "moved/b.txt", "previous_filename": "a.txt", "status": "renamed",
         "additions": 0, "deletions": 0, "changes": 0},
        {"filename": "img/pic.png", "status": "added", "additions": 0, "deletions": 0, "changes": 0},
        {"filename": "link", "status": "added", "additions": 1, "deletions": 0, "changes": 1,
         "patch": "@@ -0,0 +1 @@\n+/etc/passwd\n\\ No newline at end of file"},
        {"filename": "big.txt", "status": "modified", "additions": 50000, "deletions": 0, "changes": 50000},
    ]
    head = {"tree": [
        {"path": "docs", "type": "tree", "mode": "040000"},
        {"path": "docs/new.md", "type": "blob", "mode": "100644"},
        {"path": "tools/run.sh", "type": "blob", "mode": "100755"},
        {"path": "moved/b.txt", "type": "blob", "mode": "100644"},
        {"path": "img/pic.png", "type": "blob", "mode": "100644"},
        {"path": "link", "type": "blob", "mode": "120000"},
        {"path": "big.txt", "type": "blob", "mode": "100644"},
    ]}
    base = {"tree": [
        {"path": "tools/run.sh", "type": "blob", "mode": "100644"},
        {"path": "old.txt", "type": "blob", "mode": "100644"},
        {"path": "a.txt", "type": "blob", "mode": "100644"},
        {"path": "big.txt", "type": "blob", "mode": "100644"},
    ]}

    # Three spellings of the same input must give the same files.
    concatenated = json.dumps(page1) + json.dumps(page2)
    slurped = json.dumps([page1, page2])
    per_object = "\n".join(json.dumps(o) for o in page1 + page2)
    want = page1 + page2
    for label, text in (("concatenated", concatenated), ("slurped", slurped), ("per-object", per_object)):
        got = flatten_files(read_json_values(text))
        assert got == want, f"{label} input parsed differently"

    diff = build_diff(want, tree_modes(head, "head"), tree_modes(base, "base"))
    parsed = {fd.path: fd for fd in triage.parse_diff(diff)}

    assert set(parsed) == {f["filename"] for f in want}, sorted(parsed)
    assert parsed["docs/new.md"].is_new and parsed["docs/new.md"].added == [(1, "hello"), (2, "world")]
    assert parsed["tools/run.sh"].became_executable, "100644 -> 100755 must read as a new executable"
    assert parsed["tools/run.sh"].added == [(2, "echo hi")]
    assert parsed["old.txt"].is_deleted and not parsed["old.txt"].added
    assert not parsed["moved/b.txt"].is_binary, "a pure rename must not be reported as binary"
    assert parsed["img/pic.png"].is_binary and parsed["img/pic.png"].is_new
    assert parsed["link"].is_symlink and parsed["link"].is_new
    assert parsed["big.txt"].is_binary, "a withheld patch must surface as unreadable content"

    # Controls: the parser must see what the script wrote, so a diff written
    # without the trees must lose exactly the mode-based states.
    blind = {fd.path: fd for fd in triage.parse_diff(build_diff(want, {}, {}))}
    assert not blind["link"].is_symlink and not blind["tools/run.sh"].became_executable

    for bad in ({"truncated": True, "tree": []}, {"sha": "x"}):
        try:
            tree_modes(bad, "head")
        except ValueError:
            pass
        else:
            raise AssertionError(f"tree listing {bad} must be rejected")
    try:
        flatten_files(read_json_values('{"message": "Not Found"}'))
    except ValueError:
        pass
    else:
        raise AssertionError("an API error body must be rejected as files input")

    print("self-test: ok")
    return 0


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description="Rebuild a unified diff from the pull request files API.")
    ap.add_argument("--files", help="output of `gh api --paginate .../pulls/N/files`")
    ap.add_argument("--head-tree", help="output of `gh api .../git/trees/<head sha>?recursive=1`")
    ap.add_argument("--base-tree", help="output of `gh api .../git/trees/<base sha>?recursive=1`")
    ap.add_argument("--self-test", action="store_true", help="exercise the writer against the triage parser")
    args = ap.parse_args()

    if args.self_test:
        return _self_test()
    if not (args.files and args.head_tree and args.base_tree):
        ap.error("--files, --head-tree and --base-tree are all required")

    try:
        files = flatten_files(read_json_values(Path(args.files).read_text(encoding="utf-8")))
        head = tree_modes(json.loads(Path(args.head_tree).read_text(encoding="utf-8")), "head")
        base = tree_modes(json.loads(Path(args.base_tree).read_text(encoding="utf-8")), "base")
    except (OSError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not files:
        print("error: the files input holds no files, so there is no diff to build", file=sys.stderr)
        return 1

    sys.stdout.write(build_diff(files, head, base))
    print(f"{len(files)} file(s) rebuilt from the files endpoint", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
