#!/usr/bin/env python3
"""
CI gate: the security headers served at the edge must match the ones in Git.

WHY THIS EXISTS
---------------
`infra/terraform/cloudflare/rules.tf` declares the csoh-security-headers
ruleset - HSTS, CSP, X-Frame-Options and the rest. It is the ONLY source of
those headers for the Azure origin, because Azure Blob static websites cannot
emit custom response headers at all. The GCP/nginx origin sets them itself via
nginx-security-headers.conf, and the S3/CloudFront origin does too via
`aws_cloudfront_response_headers_policy.security` in aws/cloudfront.tf - though
that policy only takes effect once `terraform -chdir=infra/terraform/aws apply`
has run.

That ruleset also carries `lifecycle { ignore_changes = [rules] }`, a
deliberate workaround for a cloudflare v4 provider bug that returns the
multi-header block in a non-deterministic order. The cost of the workaround is
that `rules` is the only meaningful attribute of a `cloudflare_ruleset`, so
ignoring it makes the resource inert after creation: you can tighten the CSP in
this repo, run `terraform apply`, get a clean plan, and ship nothing. The edge
keeps the old policy while the repo, the diff, and any reviewer believe it was
changed.

So this script closes the loop from the other end. It parses the header
name/value pairs out of rules.tf and asserts them against what the live site
actually returns. Drift - whether from a forgotten apply, a dashboard edit, or
someone with the Cloudflare API token weakening a header - fails the build
instead of going unnoticed.

Remove this script when the cloudflare v5 provider upgrade lands and the
`ignore_changes` workaround can be deleted, at which point Terraform manages
the ruleset for real again.

USAGE
-----
    python3 tools/check_edge_headers.py                 # checks https://csoh.org/
    python3 tools/check_edge_headers.py --url https://csoh.org/about.html

`--url` is the only flag; point it at an origin's own hostname to check that
origin directly instead of the edge.

Exits non-zero on any missing or mismatched header.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RULES_TF = REPO_ROOT / "infra" / "terraform" / "cloudflare" / "rules.tf"

DEFAULT_URL = "https://csoh.org/"

# The rule we care about inside rules.tf. Anchoring on the ref keeps us from
# picking up headers from some future second rule in the same file.
RULE_REF = "set_security_headers"

# One `headers { name = "..." operation = "set" value = "..." }` block.
# `re.DOTALL` is deliberately NOT used: every field sits on its own line.
HEADER_BLOCK = re.compile(
    r"headers\s*\{"
    r"\s*name\s*=\s*\"(?P<name>[^\"]+)\""
    r"\s*operation\s*=\s*\"(?P<op>[^\"]+)\""
    r"\s*value\s*=\s*\"(?P<value>[^\"]*)\""
    r"\s*\}"
)


def parse_expected_headers(path: Path = RULES_TF) -> dict[str, str]:
    """Pull the expected header name -> value map out of the Terraform source."""
    if not path.exists():
        sys.exit(f"error: cannot find {path}")
    text = path.read_text(encoding="utf-8")

    # Narrow to the security-headers rule so we never read a different rule's
    # headers. The rule starts at its `ref` and ends at the `action_parameters`
    # closing brace; taking everything from the ref to the `lifecycle` block (or
    # end of resource) is enough and is robust to comment churn.
    start = text.find(f'ref         = "{RULE_REF}"')
    if start == -1:
        start = text.find(RULE_REF)
    if start == -1:
        sys.exit(f"error: could not find the '{RULE_REF}' rule in {path.name}")
    # Bound the section at the `lifecycle {` block that follows. Match it as an
    # actual block opener, not the bare word: the CSP comment above mentions
    # "the lifecycle block below", and a plain substring search stops there and
    # silently drops the last three headers (CSP, COOP, CORP) - exactly the
    # ones this check exists to protect.
    end_match = re.search(r"^\s*lifecycle\s*\{", text[start:], re.MULTILINE)
    section = text[start:start + end_match.start()] if end_match else text[start:]

    expected: dict[str, str] = {}
    for m in HEADER_BLOCK.finditer(section):
        if m.group("op") != "set":
            continue
        expected[m.group("name")] = m.group("value")

    if not expected:
        sys.exit(
            f"error: parsed zero headers out of {path.name}. The file's shape "
            f"probably changed - update HEADER_BLOCK in this script."
        )
    return expected


def fetch_headers(url: str, timeout: int = 20) -> dict[str, str]:
    """GET the URL and return its response headers, lowercased by name."""
    req = urllib.request.Request(
        url,
        method="GET",
        headers={"User-Agent": "csoh-edge-header-check/1.0 (+https://csoh.org/)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as e:
        # A 4xx/5xx still carries headers, and the nginx config sets them with
        # `always`, so an error page is still a valid thing to assert against.
        return {k.lower(): v for k, v in e.headers.items()}
    except (urllib.error.URLError, TimeoutError) as e:
        sys.exit(f"error: could not fetch {url}: {e}")


def normalize(value: str) -> str:
    """Collapse whitespace so trivial formatting differences don't fail CI."""
    return re.sub(r"\s+", " ", value).strip()


def check(url: str, expected: dict[str, str]) -> list[str]:
    """Return a list of human-readable problems; empty means the edge matches."""
    actual = fetch_headers(url)
    problems: list[str] = []

    for name, want in expected.items():
        got = actual.get(name.lower())
        if got is None:
            problems.append(f"{name}: MISSING at the edge (expected {want!r})")
        elif normalize(got) != normalize(want):
            problems.append(
                f"{name}: DRIFT\n"
                f"      repo: {normalize(want)}\n"
                f"      edge: {normalize(got)}"
            )
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"URL to check (default: {DEFAULT_URL})",
    )
    args = ap.parse_args()

    expected = parse_expected_headers()
    print(f"Checking {len(expected)} security headers from "
          f"infra/terraform/cloudflare/rules.tf against {args.url}")

    problems = check(args.url, expected)

    if problems:
        print(f"\nFAIL: {len(problems)} header(s) do not match what Git declares.\n")
        for p in problems:
            print(f"  - {p}")
        print(
            "\nThe csoh-security-headers ruleset has ignore_changes = [rules], so "
            "`terraform apply`\nwill NOT push a fix. Either update the header in "
            "the Cloudflare dashboard to match\nthis repo, or temporarily drop "
            "ignore_changes for one apply."
        )
        return 1

    for name in expected:
        print(f"  ok  {name}")
    print(f"\nOK: all {len(expected)} headers at {args.url} match the repo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
