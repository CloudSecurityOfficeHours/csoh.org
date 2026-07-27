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
    python3 tools/check_edge_headers.py                        # 40 samples of the edge
    python3 tools/check_edge_headers.py --url https://csoh.org/about.html
    python3 tools/check_edge_headers.py --url https://<dist>.cloudfront.net/ --samples 1

`--url` points at any hostname; use an origin's own hostname to check that origin
directly instead of the edge.

`--samples` sets how many cache-busted requests to make (default 40). The apex is
a load balancer over three origins and only Azure depends on the Cloudflare
ruleset, so one request can pass while the edge is broken - see DEFAULT_SAMPLES
below. Use `--samples 1` when pointing at a single origin, where there is nothing
to sample. The run reports which origins it reached, and warns if it never
reached Azure, because such a run did not test what it claims to.

Exits non-zero on any missing or mismatched header.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RULES_TF = REPO_ROOT / "infra" / "terraform" / "cloudflare" / "rules.tf"

DEFAULT_URL = "https://csoh.org/"

# How many cache-busted requests to make by default.
#
# The apex is a Cloudflare load balancer over three origins. AWS and GCP now set
# these headers themselves (aws_cloudfront_response_headers_policy.security and
# nginx-security-headers.conf), so ONLY Azure-served responses actually test the
# Cloudflare ruleset this script exists to guard. A single request - which is
# what this gate did until 2026-07-26 - had roughly a 4-in-5 chance of landing
# on an origin that looks correct even with the ruleset deleted.
#
# Steering is not evenly random per request; it arrives in bursts. Measured
# 2026-07-26: two consecutive 25-sample runs reached Azure zero times, then the
# next reached it 17 times. At 40 samples, five consecutive runs reached Azure
# 15, 15, 12, 7 and 11 times. So 40 is chosen from observed behaviour, not from
# a binomial calculation that assumes independence the balancer does not honour.
#
# BE HONEST ABOUT THE LIMIT: this is sampling, not proof. Nothing here can force
# Cloudflare to route to a specific origin, and the only deterministic check
# would be reading the ruleset back through the Cloudflare API, which needs a
# token the deploy path deliberately does not carry (see CLAUDE.md on the two
# tokens). If a run reports no Azure request, it did not test the thing it
# claims to test, and it says so.
#
# Cost is about 10 seconds.
DEFAULT_SAMPLES = 40

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


def identify_origin(headers: dict[str, str]) -> str:
    """Best-effort: which of the three origins answered this request.

    Only used for coverage reporting, never for pass/fail, so a wrong guess
    costs nothing but a confusing label.
    """
    if "x-ms-request-id" in headers or "x-ms-version" in headers:
        return "azure"
    if "x-amz-cf-id" in headers or "x-amz-request-id" in headers:
        return "aws"
    # No positive marker for the GCP origin: Cloudflare rewrites `Server:` to
    # "cloudflare" on the way out, so nginx leaves no fingerprint. Everything
    # that is neither Azure nor AWS is therefore GCP in practice, but label it
    # honestly rather than asserting something we did not observe.
    return "gcp-or-unlabelled"


def check_once(url: str, expected: dict[str, str]) -> tuple[list[str], str]:
    """Check a single response. Returns (problems, origin-label)."""
    actual = fetch_headers(url)
    problems: list[str] = []

    for name, want in expected.items():
        got = actual.get(name.lower())
        if got is None:
            problems.append(f"{name}: MISSING (expected {want!r})")
        elif normalize(got) != normalize(want):
            problems.append(
                f"{name}: DRIFT\n"
                f"      repo: {normalize(want)}\n"
                f"      edge: {normalize(got)}"
            )
    return problems, identify_origin(actual)


def check(url: str, expected: dict[str, str], samples: int = 1) -> tuple[list[str], dict[str, int]]:
    """Sample the URL `samples` times; return (problems, origin hit counts).

    WHY MORE THAN ONE REQUEST. csoh.org is a Cloudflare load balancer over three
    origins, and two of them now set these headers themselves: the AWS origin via
    aws_cloudfront_response_headers_policy.security, and the GCP origin via
    nginx-security-headers.conf. Only Azure Blob cannot, so Azure-served
    responses are the ones that depend entirely on the Cloudflare ruleset this
    script exists to guard.

    A single request therefore had roughly a 4-in-5 chance of landing on an
    origin that would look correct even if the Cloudflare ruleset had been
    deleted. Measured distribution over 20 requests on 2026-07-26: 10 GCP,
    6 AWS, 4 Azure. The gate reported green while a real edge failure would
    have shipped to about one visitor in five.

    Each request carries a unique cache-busting query string, because a cached
    response does not re-exercise the origin and would just re-confirm whichever
    origin answered first.
    """
    problems: list[str] = []
    seen: dict[str, int] = {}
    sep = "&" if "?" in url else "?"

    for i in range(max(1, samples)):
        probe = f"{url}{sep}__hdrcheck={i}-{os.getpid()}"
        found, origin = check_once(probe, expected)
        seen[origin] = seen.get(origin, 0) + 1
        for p in found:
            tagged = f"[origin={origin}] {p}"
            if tagged not in problems:
                problems.append(tagged)
    return problems, seen


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"URL to check (default: {DEFAULT_URL})",
    )
    ap.add_argument(
        "--samples",
        type=int,
        default=DEFAULT_SAMPLES,
        help=(
            f"how many cache-busted requests to make (default: {DEFAULT_SAMPLES}). "
            "The apex is a load balancer over three origins and only one of them "
            "(Azure) depends on the Cloudflare ruleset, so a single request can "
            "pass while the edge is broken. Use 1 only when pointing --url at a "
            "single origin hostname, where there is nothing to sample."
        ),
    )
    args = ap.parse_args()

    expected = parse_expected_headers()
    print(f"Checking {len(expected)} security headers from "
          f"infra/terraform/cloudflare/rules.tf against {args.url}")
    if args.samples > 1:
        print(f"Sampling {args.samples} cache-busted requests to reach all origins")

    problems, seen = check(args.url, expected, args.samples)

    if seen:
        print("  origins reached: "
              + ", ".join(f"{k}={v}" for k, v in sorted(seen.items())))

    if problems:
        print(f"\nFAIL: {len(problems)} header problem(s) versus what Git declares.\n")
        for p in problems:
            print(f"  - {p}")
        print(
            "\nThe csoh-security-headers ruleset has ignore_changes = [rules], so "
            "`terraform apply`\nwill NOT push a fix. Either update the header in "
            "the Cloudflare dashboard to match\nthis repo, or temporarily drop "
            "ignore_changes for one apply."
        )
        print(
            "\nNote the origin= tag on each problem. A failure seen ONLY on "
            "origin=azure means the\nCloudflare ruleset is the broken part, "
            "because Azure Blob cannot set these headers\nitself and depends "
            "entirely on the edge."
        )
        return 1

    for name in expected:
        print(f"  ok  {name}")
    print(f"\nOK: all {len(expected)} headers match the repo "
          f"across {args.samples} request(s) to {args.url}.")
    if args.samples > 1 and "azure" not in seen:
        print(
            "  ! warning: no request landed on the Azure origin, which is the only\n"
            "    one relying on the Cloudflare ruleset. Consider raising --samples."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
