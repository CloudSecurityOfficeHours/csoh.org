#!/usr/bin/env python3
"""Stamp a "From the Friday sessions" block onto topic pages.

A search visitor landing on a topic page sees a reference article and leaves.
The thing CSOH has that no reference article has is 100+ recaps of practitioners
arguing about that same topic on a live call. This tool surfaces the most recent
of those recaps on the matching topic page, turning a static page into evidence
that a community is still working the problem, and giving the reader a reason to
show up on Friday.

Scoring uses the full recap text (from meetings-search-index.json); display copy
comes from the curated cards in meetings.html, so the blurb a reader sees is the
same one the recap index shows.

Idempotent: the block is delimited by SESSION_BLOCK markers and replaced whole on
every run, so re-running after new meetings land just refreshes the list.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MEETINGS_HTML = REPO / "meetings.html"
SEARCH_INDEX = REPO / "meetings-search-index.json"

START = "<!-- SESSION_BLOCK_START -->"
END = "<!-- SESSION_BLOCK_END -->"

# How many recaps to list, and the minimum keyword hits a recap needs before it
# counts as being "about" the topic. Two hits keeps out recaps that mention a
# term once in passing.
MAX_RECAPS = 4
MIN_SCORE = 2

# Topic page -> phrases that mean the session covered that topic. Seeded from
# tools/inject_meeting_topic_links.py (which solves the mirror-image problem:
# linking OUT of a recap INTO a topic page). Deliberately excludes bare tokens
# like "AWS" or "IAM" that match nearly every session.
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "ai-ml-security.html": ["prompt injection", "llm security", "ai agent", "ai agents",
                            "model security", "ai security", "ai/ml security", "ai/llm",
                            "agentic ai", "ai governance", "ai model"],
    "iam.html": ["iam identity center", "okta", "entra id", "azure ad", "identity provider",
                 "mfa fatigue", "identity and access management", "least privilege",
                 "privilege escalation", "credential theft", "access management",
                 "role-based access"],
    "kubernetes.html": ["kubernetes", "eks", "aks", "gke", "kubelet", "k8s cluster"],
    "containers.html": ["container image", "container security", "docker", "container runtime"],
    "detection-engineering.html": ["detection engineering", "sigma rule", "detection rule",
                                   "cloud detection and response", "cloud detection",
                                   "siem correlation"],
    "incident-response.html": ["incident response", "dfir", "tabletop exercise",
                               "ransomware attack", "breach response", "forensic investigation",
                               "cloud forensics"],
    "vulnerability-management.html": ["vulnerability management", "cvss", "patch management",
                                      "zero-day", "vulnerability scanning",
                                      "vulnerability prioritization"],
    "threat-research.html": ["mitre att&ck", "threat actor", "threat intelligence",
                             "threat research", "advanced persistent threat", "apt group",
                             "attribution"],
    "zero-trust.html": ["zero trust", "ztna"],
    "cspm-vs-cnapp.html": ["cnapp", "cspm", "ciem", "cwpp", "dspm", "posture management"],
    "backup-dr.html": ["backup strategy", "disaster recovery", "ransomware recovery",
                       "immutable backup", "backup and recovery", "data backup"],
    "compliance-frameworks.html": ["iso 27001", "soc 2", "pci dss", "hipaa", "fedramp",
                                   "nist csf", "compliance framework", "compliance"],
    "ci-cd.html": ["ci/cd pipeline", "supply chain attack", "build pipeline",
                   "devsecops pipeline", "software supply chain"],
    "github-actions.html": ["github actions"],
    "api-security.html": ["api security", "api gateway", "api abuse"],
    "network-security.html": ["security groups", "vpc peering", "network segmentation",
                              "cloud network", "network security"],
    "data-security.html": ["data security posture", "data classification", "encryption at rest",
                           "data exfiltration", "data loss prevention", "bucket security",
                           "storage security"],
    "saas-security.html": ["saas security", "saas posture", "saas sprawl", "saas"],
    "serverless.html": ["lambda function", "serverless function", "serverless security",
                        "serverless"],
    "landing-zones.html": ["landing zone", "control tower", "aws organizations"],
    "aws-security.html": ["aws security hub", "amazon guardduty", "aws iam", "aws s3",
                          "s3 bucket", "s3 buckets", "ec2 instance", "aws account",
                          "aws billing"],
    "azure-security.html": ["azure sentinel", "defender for cloud", "microsoft defender",
                            "azure tenant", "azure", "entra"],
    "gcp-security.html": ["security command center", "gcp organization", "gcp project",
                          "gcp", "google cloud"],
    "cloud-pentesting.html": ["cloud pentest", "red team", "pacu", "cloudgoat",
                              "offensive security", "penetration test", "pen test"],
    "cloud-soc.html": ["cloud soc", "soc operations", "security operations center"],
    "grc.html": ["governance, risk", "grc program", "audit findings"],
    "threat-modeling.html": ["threat model", "threat modeling", "stride"],
    "service-mesh-security.html": ["service mesh", "istio", "linkerd"],
    "shared-responsibility-model.html": ["shared responsibility"],
    "mcp-security.html": ["mcp server", "model context protocol"],
    "non-human-identity.html": ["non-human identity", "non-human", "service account",
                                "workload identity", "machine identity"],
    "cloud-security-certifications.html": ["certification", "cissp", "ccsp", "cpe credits"],
    "conferences.html": ["black hat", "def con", "defcon", "rsa conference", "bsides"],
}

CARD_RE = re.compile(
    r'<article class="section meeting-card" id="meeting-(?P<date>\d{4}-\d{2}-\d{2})">'
    r'.*?<h2><time datetime="[^"]*">(?P<human>[^<]*)</time>\s*-\s*(?P<headline>[^<]*)</h2>'
    r'.*?<p class="meeting-card-summary">(?P<summary>.*?)</p>',
    re.DOTALL,
)


def load_meetings() -> list[dict]:
    """Display copy from the recap cards, scoring text from the search index."""
    cards = {}
    for m in CARD_RE.finditer(MEETINGS_HTML.read_text(encoding="utf-8")):
        cards[m.group("date")] = {
            "date": m.group("date"),
            "human": m.group("human").strip(),
            "headline": m.group("headline").strip(),
            "summary": m.group("summary").strip(),
        }
    index = json.loads(SEARCH_INDEX.read_text(encoding="utf-8"))
    for rec in index:
        date = rec.get("id", "").replace("meeting-", "")
        if date in cards:
            cards[date]["text"] = rec.get("text", "").lower()
    return sorted(
        (c for c in cards.values() if c.get("text")),
        key=lambda c: c["date"],
        reverse=True,
    )


def pick(meetings: list[dict], keywords: list[str]) -> list[dict]:
    """Recaps that clearly covered this topic, most recent first."""
    hits = []
    for m in meetings:
        score = sum(m["text"].count(kw) for kw in keywords)
        if score >= MIN_SCORE:
            hits.append(m)
        if len(hits) >= MAX_RECAPS:
            break
    return hits


def render(picks: list[dict], total: int) -> str:
    items = []
    for m in picks:
        # Every display field is lifted verbatim out of meetings.html, where it is
        # already HTML-escaped. Escaping again here would render entities as
        # literal text ("CISA&#x27;s"), so these interpolate raw by design.
        items.append(
            f'        <li class="session-echo-item">\n'
            f'          <a class="session-echo-link" href="meetings/{m["date"]}.html">\n'
            f'            <time datetime="{m["date"]}">{m["human"]}</time>\n'
            f'            <span class="session-echo-title">{m["headline"]}</span>\n'
            f'          </a>\n'
            f'          <p class="session-echo-summary">{m["summary"]}</p>\n'
            f'        </li>'
        )
    lines = "\n".join(items)
    return (
        f'{START}\n'
        f'      <section class="section session-echo" id="from-the-sessions">\n'
        f'        <h2>From the Friday sessions</h2>\n'
        f'        <p>This is not a settled topic. Here is where the CSOH community worked '
        f'through it on the live Friday call:</p>\n'
        f'        <ul class="session-echo-list">\n'
        f'{lines}\n'
        f'        </ul>\n'
        f'        <p class="session-echo-cta"><a href="sessions.html">Join the next Friday '
        f'session</a> to argue with us in real time, or <a href="meetings.html">browse all '
        f'{total} recaps</a>.</p>\n'
        f'      </section>\n'
        f'      {END}'
    )


def splice(page: str, block: str) -> str | None:
    """Replace an existing block, else insert before the author card / </main>."""
    if START in page and END in page:
        return re.sub(
            re.escape(START) + r".*?" + re.escape(END), lambda _: block, page, flags=re.DOTALL
        )
    anchor = page.rfind('<aside class="author-card"')
    if anchor == -1:
        anchor = page.rfind("</main>")
        if anchor == -1:
            return None
    return page[:anchor] + block + "\n\n      " + page[anchor:]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    ap.add_argument("--pages", nargs="*", help="limit to these topic pages")
    args = ap.parse_args()

    meetings = load_meetings()
    total = len(meetings)
    print(f"Loaded {total} recaps.")

    targets = TOPIC_KEYWORDS
    if args.pages:
        wanted = {Path(p).name for p in args.pages}
        targets = {k: v for k, v in TOPIC_KEYWORDS.items() if k in wanted}

    changed, skipped = 0, []
    for page_name, keywords in sorted(targets.items()):
        path = REPO / page_name
        if not path.exists():
            skipped.append(f"{page_name} (missing)")
            continue
        picks = pick(meetings, keywords)
        if len(picks) < 2:
            skipped.append(f"{page_name} (only {len(picks)} matching recap(s))")
            continue
        page = path.read_text(encoding="utf-8")
        new_page = splice(page, render(picks, total))
        if new_page is None:
            skipped.append(f"{page_name} (no insertion point)")
            continue
        if new_page != page:
            changed += 1
            print(f"  ✓ {page_name}: {', '.join(p['date'] for p in picks)}")
            if not args.dry_run:
                path.write_text(new_page, encoding="utf-8")

    print(f"\n{'Would update' if args.dry_run else 'Updated'} {changed} page(s).")
    if skipped:
        print(f"Skipped {len(skipped)}:")
        for s in skipped:
            print(f"  - {s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
