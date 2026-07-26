#!/usr/bin/env python3
"""
CI gate: the robots.txt served at the edge must match the one in Git.

WHY THIS EXISTS
---------------
`robots.txt` in this repo is a deliberate, argued-for policy document. It does
not just keep crawlers out of a few paths - it explicitly *invites* the AI
crawlers by name (GPTBot, ClaudeBot, PerplexityBot, Google-Extended,
Applebot-Extended, CCBot and friends), because CSOH is a public community
resource and being cited in AI-generated answers is the point. `llms.txt` says
so out loud: "The robots.txt explicitly allows GPTBot, ClaudeBot, PerplexityBot,
Google-Extended, Applebot-Extended, CCBot and friends."

Cloudflare can overwrite that from the outside. The "AI Crawl Control" feature
(dashboard: Security -> Bots -> AI Crawl Control -> managed robots.txt) rewrites
the response for /robots.txt at the edge, PREPENDING a Content-Signal preamble
and a `# BEGIN Cloudflare Managed content` block ahead of the origin's file. The
injected block carries `Disallow: /` for exactly the crawlers the repo Allows.
The origin file is still there, untouched, below the injection - which is what
makes this hard to notice: `git diff` is clean, all three origins serve the
right bytes, and only the edge disagrees.

What a given crawler then does is genuinely undefined. RFC 9309 says records
with the same user-agent token should be merged, in which case an `Allow: /` and
a `Disallow: /` of equal specificity resolve to the least restrictive rule; but
plenty of crawlers simply take the first matching group and stop. Either way the
file the world reads no longer says what this repo says, and the promise in
llms.txt becomes false.

That is the same failure class as the security-header ruleset guarded by
tools/check_edge_headers.py: a control plane outside Terraform quietly overriding
policy that lives in Git, with nothing in the repo, the diff, or the deploy log
to show for it. So, same remedy - assert it from the outside.

Remove this script if Cloudflare's managed robots.txt is retired, or if the site
ever decides it *wants* the edge to own robots.txt (in which case the repo's
file, llms.txt, and privacy.html all need to change too).

USAGE
-----
    python3 tools/check_robots_parity.py                    # checks https://csoh.org/robots.txt
    python3 tools/check_robots_parity.py --url https://csoh.org/
    python3 tools/check_robots_parity.py --url http://127.0.0.1:8000/robots.txt

`--url` is the only flag; point it at an origin's own hostname to check that
origin directly instead of the edge. A URL with no path (or a bare `/`) gets
`robots.txt` appended, so `--url https://csoh.org/` does the obvious thing and
the flag reads the same as it does in check_edge_headers.py.

Exits non-zero if the served file differs from the repo's, or if it cannot be
fetched at all.
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ROBOTS_TXT = REPO_ROOT / "robots.txt"

DEFAULT_URL = "https://csoh.org/robots.txt"

# Cloudflare brackets its injection with these two comments. They are matched
# case-insensitively on purpose: the live block currently opens with
# "# BEGIN Cloudflare Managed content" and closes with
# "# END Cloudflare Managed Content" - Cloudflare's own casing is inconsistent,
# so pinning the exact string would make this detection fragile for no benefit.
CF_BEGIN = re.compile(r"^\s*#\s*BEGIN\s+Cloudflare\s+Managed\s+content", re.IGNORECASE)
CF_END = re.compile(r"^\s*#\s*END\s+Cloudflare\s+Managed\s+content", re.IGNORECASE)

# The Content-Signal preamble Cloudflare prepends above the BEGIN marker. It
# arrives with the managed block and is not bracketed by any marker of its own,
# so it needs its own tell.
CF_SIGNAL = re.compile(r"^\s*Content-Signal\s*:", re.IGNORECASE)

# How many diff lines to print before truncating. A drifted robots.txt is
# usually a small prepend; a wholly different file should not flood the CI log.
MAX_DIFF_LINES = 80

DASHBOARD_PATH = (
    "Cloudflare dashboard -> Security -> Bots -> AI Crawl Control -> managed robots.txt"
)


def normalize(text: str) -> list[str]:
    """Reduce a robots.txt to comparable lines, normalizing TRIVIA ONLY.

    Three things are normalized, all of them things an editor or an origin can
    change without changing what any crawler does:

      * CRLF / lone CR line endings -> LF (S3 and Blob both round-trip bytes
        faithfully, but a Windows checkout or a dashboard paste would not).
      * Trailing whitespace on each line.
      * Runs of blank lines collapsed to one, and leading/trailing blanks dropped.

    Deliberately NOT normalized: case, directive order, comments, indentation,
    duplicate rules. All of those are real content. Comments especially - the
    Cloudflare injection this script exists to catch is more than half comment
    text, and normalizing comments away would blind it to the whole preamble.
    """
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    for raw in lines:
        line = raw.rstrip()
        if not line and (not out or not out[-1]):
            continue  # collapse blank runs, and skip leading blanks
        out.append(line)
    while out and not out[-1]:
        out.pop()
    return out


def fetch_text(url: str, timeout: int = 20) -> str:
    """GET the URL and return its decoded body.

    Unlike check_edge_headers.py, a 4xx/5xx is fatal here rather than something
    to assert against: this script compares the *body*, and an error page's body
    is not a robots.txt. A 404 for /robots.txt is itself a deploy-breaking fact
    worth failing on.
    """
    req = urllib.request.Request(
        url,
        method="GET",
        headers={"User-Agent": "csoh-robots-parity-check/1.0 (+https://csoh.org/)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as e:
        sys.exit(f"error: {url} returned HTTP {e.code} {e.reason}; expected 200 with a robots.txt body")
    except (urllib.error.URLError, TimeoutError) as e:
        sys.exit(f"error: could not fetch {url}: {e}")


def resolve_url(url: str) -> str:
    """Append `robots.txt` when the caller passed a bare origin.

    Lets `--url https://csoh.org/` work, so this flag can be copied verbatim
    from the check_edge_headers.py step in deploy.yml without a silent 200 on
    the homepage being compared against robots.txt.
    """
    parts = urllib.parse.urlsplit(url)
    if parts.path in ("", "/"):
        return urllib.parse.urlunsplit(parts._replace(path="/robots.txt"))
    return url


def parse_groups(lines: list[str]) -> list[tuple[list[str], list[tuple[str, str]]]]:
    """Parse robots.txt into (user-agents, rules) groups.

    A group is one or more consecutive `User-agent:` lines followed by the rules
    that apply to all of them; the next `User-agent:` after a rule line starts a
    new group. This is only used to explain a failure in human terms - the
    pass/fail decision is a plain text comparison, so a parser bug can never
    make a drifted file look clean.
    """
    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    agents: list[str] = []
    rules: list[tuple[str, str]] = []
    for line in lines:
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field = field.strip().lower()
        value = value.strip()
        if field == "user-agent":
            if rules:  # a rule already landed, so this starts a new group
                groups.append((agents, rules))
                agents, rules = [], []
            agents.append(value)
        elif agents:
            rules.append((field, value))
    if agents:
        groups.append((agents, rules))
    return groups


def agents_with(lines: list[str], field: str, value: str) -> set[str]:
    """User-agent tokens (casefolded) whose group carries `field: value`."""
    found: set[str] = set()
    for agents, rules in parse_groups(lines):
        if any(f == field and v == value for f, v in rules):
            found.update(a.casefold() for a in agents)
    return found


def find_injection(edge_lines: list[str]) -> list[str] | None:
    """Return the Cloudflare-injected lines, or None if there is no injection.

    The BEGIN/END markers bracket the rule block, but the Content-Signal
    preamble sits ABOVE the BEGIN marker with no marker of its own. So when the
    markers are present, everything from the top of the file through END is
    treated as injected - which is exactly what the edge currently prepends.
    """
    end = next((i for i, ln in enumerate(edge_lines) if CF_END.search(ln)), None)
    if end is not None:
        return edge_lines[: end + 1]
    # Markers absent or renamed: fall back to the Content-Signal preamble, which
    # only Cloudflare emits here (the repo's file has never carried one).
    if any(CF_SIGNAL.search(ln) for ln in edge_lines):
        last = max(i for i, ln in enumerate(edge_lines) if CF_SIGNAL.search(ln))
        return edge_lines[: last + 1]
    if any(CF_BEGIN.search(ln) for ln in edge_lines):
        return edge_lines  # BEGIN with no END: malformed, report the lot
    return None


def report_injection(injected: list[str], repo_lines: list[str]) -> None:
    """Explain the Cloudflare injection and name the crawlers it contradicts."""
    print(
        f"\nCAUSE: Cloudflare's managed robots.txt is prepending "
        f"{len(injected)} line(s) at the edge."
    )

    blocked = agents_with(injected, "disallow", "/")
    allowed = agents_with(repo_lines, "allow", "/")
    # Map back to the repo's own spelling so the message matches what you would
    # grep for in robots.txt.
    conflicts = sorted(
        {
            a
            for agents, rules in parse_groups(repo_lines)
            for a in agents
            if a.casefold() in blocked
            and a.casefold() in allowed
            and any(f == "allow" and v == "/" for f, v in rules)
        },
        key=str.casefold,
    )

    if conflicts:
        print(
            f"\n  {len(conflicts)} crawler(s) the repo explicitly Allows are "
            f"Disallowed by the injected block:"
        )
        for agent in conflicts:
            print(f"    - {agent}")
        print(
            "\n  robots.txt and llms.txt both promise these crawlers are welcome. "
            "The edge\n  is contradicting that, and RFC 9309 leaves the outcome "
            "of two conflicting\n  groups for the same token up to the crawler."
        )

    other = sorted(a for a in blocked if a not in {c.casefold() for c in conflicts})
    if other:
        print(f"\n  Also Disallowed by the injection (not named in the repo): {', '.join(other)}")

    print(f"\n  Turn it off at: {DASHBOARD_PATH}")
    print(
        "  It is a zone-level toggle, not Terraform-managed - "
        "infra/terraform/cloudflare/\n  does not declare it, so `terraform apply` "
        "will neither report nor fix this."
    )


def check(url: str, repo_text: str) -> int:
    """Compare the served robots.txt against the repo's. Returns an exit code."""
    edge_text = fetch_text(url)
    repo_lines = normalize(repo_text)
    edge_lines = normalize(edge_text)

    if repo_lines == edge_lines:
        print(f"  ok  {len(repo_lines)} lines match, byte-for-byte after whitespace normalization")
        print(f"\nOK: robots.txt at {url} matches the repo.")
        return 0

    print(
        f"\nFAIL: the robots.txt served at {url} is not the one in this repo "
        f"({len(edge_lines)} lines served vs {len(repo_lines)} in Git)."
    )

    diff = list(
        difflib.unified_diff(
            repo_lines,
            edge_lines,
            fromfile="repo robots.txt",
            tofile=url,
            lineterm="",
            n=2,
        )
    )
    print()
    for line in diff[:MAX_DIFF_LINES]:
        print(f"  {line}")
    if len(diff) > MAX_DIFF_LINES:
        print(f"  ... {len(diff) - MAX_DIFF_LINES} more diff line(s) suppressed")

    injected = find_injection(edge_lines)
    if injected is not None:
        report_injection(injected, repo_lines)
    else:
        print(
            "\nCAUSE: not the known Cloudflare injection. Check for a stale edge "
            "cache (a\n`cf-cache-status: HIT` serving old bytes), an origin that "
            "missed the last publish,\nor a hand-edit at one origin - "
            "./tools/stage_site.sh /tmp/dist shows what should ship."
        )
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"URL to check (default: {DEFAULT_URL})",
    )
    args = ap.parse_args()

    if not ROBOTS_TXT.exists():
        sys.exit(f"error: cannot find {ROBOTS_TXT}")
    repo_text = ROBOTS_TXT.read_text(encoding="utf-8")

    url = resolve_url(args.url)
    print(f"Checking robots.txt from {ROBOTS_TXT.relative_to(REPO_ROOT)} against {url}")

    return check(url, repo_text)


if __name__ == "__main__":
    sys.exit(main())
