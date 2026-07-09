#!/usr/bin/env python3
"""Inject contextual topic-page links into meeting recap bodies.

For each meetings/YYYY-MM-DD.html, scans the recap prose (the <article
class="section meeting-page"> region) for cloud-security topic keywords
and wraps the first occurrence of each in a link to the matching topic
page (e.g. "Kubernetes" → ../kubernetes.html). Caps at 3 inserts per meeting to avoid
over-linking.

Skips matches that are already inside an <a>...</a> tag, so existing
glossary-links are preserved.

Usage:
    python3 tools/inject_meeting_topic_links.py
    python3 tools/inject_meeting_topic_links.py --pages meetings/2026-05-08.html
    python3 tools/inject_meeting_topic_links.py --dry-run
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MEETINGS_DIR = REPO_ROOT / "meetings"

# (topic-page, [keywords ordered by specificity, most specific first]).
# Keywords are matched as whole words, case-insensitive.
# Order matters - earlier rows get priority when multiple topics match.
TOPIC_KEYWORDS: list[tuple[str, list[str]]] = [
    ("../ai-ml-security.html",        ["prompt injection", "LLM security", "AI agent", "AI agents", "Claude code", "model security", "AI security", "AI/ML security", "AI/LLM"]),
    ("../iam.html",                   ["IAM Identity Center", "Okta", "Entra ID", "Azure AD", "identity provider", "MFA fatigue", "Identity and Access Management", "least privilege", "privilege escalation", "credential theft", "access management", "role-based access"]),
    ("../kubernetes.html",            ["Kubernetes", "EKS", "AKS", "GKE", "kubelet", "K8s cluster"]),
    ("../containers.html",            ["container image", "container security", "Docker", "container runtime"]),
    ("../detection-engineering.html", ["detection engineering", "Sigma rule", "detection rule", "Cloud Detection and Response", "cloud detection", "SIEM correlation"]),
    ("../incident-response.html",     ["incident response", "DFIR", "tabletop exercise", "ransomware attack", "breach response", "forensic investigation", "cloud forensics", "automated forensics"]),
    ("../vulnerability-management.html", ["vulnerability management", "CVSS score", "patch management", "zero-day vulnerability", "vulnerability scanning"]),
    ("../threat-research.html",       ["MITRE ATT&CK", "threat actor", "threat intelligence", "threat research", "advanced persistent threat", "APT group"]),
    ("../zero-trust.html",            ["Zero Trust", "ZTNA"]),
    ("../cspm-vs-cnapp.html",         ["CNAPP", "CSPM", "CIEM", "CWPP", "DSPM"]),
    ("../backup-dr.html",             ["backup strategy", "disaster recovery", "ransomware recovery", "immutable backup", "backup and recovery", "data backup"]),
    ("../compliance-frameworks.html", ["ISO 27001", "SOC 2", "PCI DSS", "HIPAA", "FedRAMP", "NIST CSF", "compliance framework"]),
    ("../ci-cd.html",                 ["CI/CD pipeline", "supply chain attack", "build pipeline", "DevSecOps pipeline"]),
    ("../github-actions.html",        ["GitHub Actions"]),
    ("../api-security.html",          ["API security", "API gateway", "API abuse"]),
    ("../network-security.html",      ["security groups", "VPC peering", "network segmentation", "cloud network"]),
    ("../data-security.html",         ["data security posture", "data classification", "encryption at rest", "data exfiltration", "data loss prevention", "bucket security", "storage security"]),
    ("../saas-security.html",         ["SaaS security", "SaaS posture", "SaaS sprawl"]),
    ("../serverless.html",            ["Lambda function", "serverless function", "serverless security"]),
    ("../landing-zones.html",         ["landing zone", "Control Tower", "AWS Organizations"]),
    ("../aws-security.html",          ["AWS Security Hub", "Amazon GuardDuty", "AWS IAM", "AWS S3", "S3 bucket", "S3 buckets", "EC2 instance", "AWS account"]),
    ("../azure-security.html",        ["Azure Sentinel", "Defender for Cloud", "Microsoft Defender", "Azure tenant"]),
    ("../gcp-security.html",          ["Security Command Center", "GCP Organization", "GCP project"]),
    ("../cloud-pentesting.html",      ["cloud pentest", "red team", "Pacu", "CloudGoat", "offensive security"]),
    ("../cloud-soc.html",             ["cloud SOC", "SOC operations", "security operations center"]),
    ("../grc.html",                   ["governance, risk", "GRC program", "audit findings"]),
    ("../threat-modeling.html",       ["threat model", "threat modeling", "STRIDE"]),
    ("../service-mesh-security.html", ["service mesh", "Istio", "Linkerd"]),
    ("../shared-responsibility-model.html", ["shared responsibility model", "shared responsibility"]),
    ("../breach-timeline.html",       ["Capital One breach", "SolarWinds breach", "MGM breach", "Uber breach", "LastPass breach", "Snowflake breach", "Storm-0558"]),
]

# Words that are too generic to safely wrap - never link these.
DENYLIST = {"AI", "ML", "AWS", "Azure", "GCP", "S3", "EC2", "IAM"}

MAX_LINKS_PER_MEETING = 3

ARTICLE_RE = re.compile(
    r'(<article class="section meeting-page">)(.*?)(</article>)',
    re.DOTALL,
)


def is_inside_anchor(text_before_match: str) -> bool:
    """True if the count of open <a> tags exceeds closing </a> tags so far,
    meaning the match position is inside an existing anchor."""
    opens = len(re.findall(r"<a\b", text_before_match))
    closes = text_before_match.count("</a>")
    return opens > closes


def find_first_replaceable(body: str, keyword: str) -> int | None:
    """Return the index of the first whole-word, case-insensitive match of
    `keyword` in `body` that is NOT inside an existing anchor tag and not
    inside any HTML tag. Returns None if no safe match exists."""
    # Whole-word boundary; tolerant of trailing s/punctuation isn't useful
    # for our short keyword list, keep it strict.
    pattern = re.compile(r"(?<!\w)" + re.escape(keyword) + r"(?!\w)", re.IGNORECASE)
    for m in pattern.finditer(body):
        start = m.start()
        before = body[:start]
        if is_inside_anchor(before):
            continue
        # Skip if we're inside an HTML tag (between < and >)
        last_lt = before.rfind("<")
        last_gt = before.rfind(">")
        if last_lt > last_gt:
            continue
        return start
    return None


def inject_links(body: str) -> tuple[str, list[tuple[str, str]]]:
    """Inject at most MAX_LINKS_PER_MEETING topic-page links. Returns the
    new body and the list of (topic_page, matched_phrase) inserted."""
    inserts: list[tuple[str, str]] = []
    seen_topics: set[str] = set()
    seen_phrases: set[str] = set()

    for topic_href, keywords in TOPIC_KEYWORDS:
        if len(inserts) >= MAX_LINKS_PER_MEETING:
            break
        if topic_href in seen_topics:
            continue
        for kw in keywords:
            if kw in DENYLIST or kw.lower() in seen_phrases:
                continue
            pos = find_first_replaceable(body, kw)
            if pos is None:
                continue
            # Find exact matched span so we preserve original capitalization
            end = pos + len(kw)
            actual = body[pos:end]
            replacement = f'<a href="{topic_href}">{actual}</a>'
            body = body[:pos] + replacement + body[end:]
            inserts.append((topic_href, actual))
            seen_topics.add(topic_href)
            seen_phrases.add(kw.lower())
            break
    return body, inserts


def process_file(path: Path, dry_run: bool) -> tuple[bool, list[tuple[str, str]]]:
    s = path.read_text(encoding="utf-8")
    m = ARTICLE_RE.search(s)
    if not m:
        return False, []
    prefix, body, suffix = m.group(1), m.group(2), m.group(3)
    new_body, inserts = inject_links(body)
    if not inserts:
        return False, []
    new_s = s[:m.start()] + prefix + new_body + suffix + s[m.end():]
    if not dry_run:
        path.write_text(new_s, encoding="utf-8")
    return True, inserts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", nargs="*",
                        help="Subset of meeting files (default: all meetings/*.html)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would change without writing")
    args = parser.parse_args()

    if args.pages:
        targets = [Path(p) for p in args.pages]
        targets = [p if p.is_absolute() else (REPO_ROOT / p) for p in targets]
        targets = [p for p in targets if p.exists()]
    else:
        targets = sorted(MEETINGS_DIR.glob("*.html"))

    updated = 0
    total_inserts = 0
    for p in targets:
        changed, inserts = process_file(p, args.dry_run)
        if changed:
            updated += 1
            total_inserts += len(inserts)
            insert_summary = ", ".join(f"{phrase}→{href.replace('../', '').replace('.html', '')}"
                                       for href, phrase in inserts)
            print(f"  ✓ {p.relative_to(REPO_ROOT)}: {insert_summary}")
        else:
            # Skip silent - too verbose to print every no-op meeting
            pass

    print(f"\nUpdated {updated}/{len(targets)} meetings; inserted {total_inserts} contextual links.")
    if args.dry_run:
        print("(dry-run - no files written)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
