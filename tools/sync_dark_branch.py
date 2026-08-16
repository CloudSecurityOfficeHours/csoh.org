#!/usr/bin/env python3
"""Keep the two dark-mode branches in style.css in step.

The site has two ways of being dark, and they are *not* the same selector:

  [data-theme="dark"] X        - the toggle branch. main.js stamps the
                                 attribute, so this governs once JS has run.
  :root:not([data-theme]) X    - the system branch, inside
    @media (prefers-color-scheme: dark)

main.js loads at the bottom of <body>, so a visitor on a dark OS renders the
*entire* page through the system branch before the attribute ever lands.
JS-off visitors stay there permanently. Both branches therefore have to carry
the same overrides - but only the toggle branch was ever maintained, and the
system branch drifted to 36 rules against its 196. The gap showed up as
light-mode text colours on dark surfaces: .next-session__note at 2.04:1,
.hamburger at 1.08:1, and a .btn-primary whose text matched its own
background exactly (contrast 1.00, invisible).

This script regenerates the system branch from the toggle branch, so the two
cannot disagree. It writes a single marked block; everything between the
BEGIN/END markers is owned by this script and rewritten wholesale.

Hand-written rules already present in the @media block are left alone and are
*not* duplicated - that is the escape hatch for cases where the two branches
genuinely need to differ (the hero's !important overrides, for one).

  python3 tools/sync_dark_branch.py            # rewrite the generated block
  python3 tools/sync_dark_branch.py --check    # CI gate: fail on drift

Re-run update_sri.py afterwards or browsers refuse the stylesheet.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STYLE = REPO_ROOT / "style.css"

DARK_ATTR = '[data-theme="dark"]'
SYS_PREFIX = ":root:not([data-theme])"
MEDIA_DARK = "@media (prefers-color-scheme: dark)"

BEGIN = "/* ==== BEGIN generated: system-dark branch (tools/sync_dark_branch.py) ===="
END = "/* ==== END generated: system-dark branch ==== */"


class Rule:
    __slots__ = ("context", "selector", "body")

    def __init__(self, context: tuple[str, ...], selector: str, body: str):
        self.context = context
        self.selector = selector
        self.body = body


def parse_rules(css: str) -> list[Rule]:
    """Brace-aware walk that records each style rule with its @-rule context.

    Not a real CSS parser - it only needs to be right about brace nesting and
    about which @media a rule sits inside, which is all the generation below
    depends on.
    """
    rules: list[Rule] = []
    stack: list[str] = []
    i = 0
    n = len(css)
    start = 0
    while i < n:
        ch = css[i]
        if ch == "{":
            prelude = re.sub(r"/\*.*?\*/", "", css[start:i], flags=re.S).strip()
            if prelude.startswith("@"):
                stack.append(prelude)
                i += 1
                start = i
                continue
            depth = 1
            j = i + 1
            while depth and j < n:
                if css[j] == "{":
                    depth += 1
                elif css[j] == "}":
                    depth -= 1
                j += 1
            body = css[i + 1 : j - 1]
            rules.append(Rule(tuple(stack), " ".join(prelude.split()), body))
            i = j
            start = i
            continue
        if ch == "}":
            if stack:
                stack.pop()
            i += 1
            start = i
            continue
        i += 1
    return rules


def strip_generated(css: str) -> str:
    """Remove a previously generated block so regeneration is idempotent."""
    b = css.find(BEGIN)
    if b == -1:
        return css
    e = css.find(END, b)
    if e == -1:
        raise SystemExit("style.css has a BEGIN marker with no END marker")
    return css[:b].rstrip("\n") + "\n" + css[e + len(END) :].lstrip("\n")


def twin_selector(selector: str) -> str | None:
    """Rewrite a toggle-branch selector into its system-branch equivalent.

    Comma parts that never mention the attribute are dropped: they already
    apply unconditionally, so re-emitting them under the system branch would
    change what they match rather than mirror it.
    """
    parts = [p.strip() for p in selector.split(",")]
    keep = [p.replace(DARK_ATTR, SYS_PREFIX) for p in parts if DARK_ATTR in p]
    return ",\n".join(keep) if keep else None


def normalise(selector: str) -> str:
    """Collapse a selector to a branch-independent key, for dedupe."""
    s = selector.replace(DARK_ATTR, "").replace(SYS_PREFIX, "")
    return " ".join(s.split())


def build(css: str) -> str:
    rules = parse_rules(css)

    # What the @media block already says by hand - never duplicate these.
    handwritten = {
        normalise(part)
        for r in rules
        if r.context and r.context[0] == MEDIA_DARK
        for part in r.selector.split(",")
    }

    top: list[Rule] = []
    nested: dict[str, list[Rule]] = {}
    for r in rules:
        if DARK_ATTR not in r.selector:
            continue
        if r.context and r.context[0] == MEDIA_DARK:
            continue  # already in the system branch
        if not r.context:
            top.append(r)
        else:
            # e.g. @media (max-width: 1023px) -> needs a combined condition
            nested.setdefault(r.context[0], []).append(r)

    def emit(rs: list[Rule], indent: str) -> list[str]:
        out: list[str] = []
        for r in rs:
            sel = twin_selector(r.selector)
            if sel is None:
                continue
            if all(normalise(p) in handwritten for p in sel.split(",")):
                continue
            decls = " ".join(r.body.split())
            if not decls:
                continue
            sel_txt = ("\n" + indent).join(sel.split("\n"))
            out.append(f"{indent}{sel_txt} {{ {decls} }}")
        return out

    lines: list[str] = [
        BEGIN,
        "   Mirrors every [data-theme=\"dark\"] rule onto :root:not([data-theme]) so a",
        "   dark-OS visitor gets the same colours at first paint that the toggle gives",
        "   them after main.js runs. Do not hand-edit - run tools/sync_dark_branch.py.",
        "   To make the two branches differ on purpose, add the rule to the @media",
        "   block above by hand; anything already there is skipped here. ==== */",
        "",
        f"{MEDIA_DARK} {{",
    ]
    lines += emit(top, "    ")
    lines.append("}")

    for cond, rs in nested.items():
        inner = cond[len("@media ") :].strip()
        body = emit(rs, "    ")
        if not body:
            continue
        lines.append("")
        lines.append(f"@media (prefers-color-scheme: dark) and {inner} {{")
        lines += body
        lines.append("}")

    lines.append("")
    lines.append(END)
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the generated block is missing or stale")
    args = ap.parse_args()

    original = STYLE.read_text(encoding="utf-8")
    base = strip_generated(original)
    block = build(base)
    updated = base.rstrip("\n") + "\n\n" + block + "\n"

    count = block.count("{") - block.count(f"{MEDIA_DARK}") - block.count("and (")

    if args.check:
        if updated != original:
            print("✗ style.css system-dark branch is out of date.", file=sys.stderr)
            print("  Run: python3 tools/sync_dark_branch.py && python3 update_sri.py",
                  file=sys.stderr)
            return 1
        print(f"✓ system-dark branch in step ({count} mirrored rules)")
        return 0

    if updated == original:
        print(f"✓ already in step ({count} mirrored rules) - nothing to do")
        return 0

    STYLE.write_text(updated, encoding="utf-8")
    print(f"✓ regenerated the system-dark branch ({count} mirrored rules)")
    print("  Now run: python3 update_sri.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
