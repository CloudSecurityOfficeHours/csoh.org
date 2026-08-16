#!/usr/bin/env python3
"""Keep every count on the site in sync with reality.

The site repeats the same counts in many places (JSON-LD `numberOfItems`,
Open Graph card subtitles, ...), so they drift as content is added. This
script recomputes the counts from the single source of truth - the actual
cards and files on disk - and rewrites them. Run it weekly (see
.github/workflows/update-counts.yml) or locally before a release.

What it manages
---------------
1. resources.html: regenerates BOTH structured-data ItemLists from the page's
   own resource cards - the standalone ItemList enumerates every UNIQUE
   resource (deduped by URL, in page order) and the CollectionPage.mainEntity
   list enumerates the category sections. numberOfItems follows automatically.
2. Every other ItemList on the site: enforces the invariant
   numberOfItems == number of enumerated ListItems, so no count can lie.
3. generate_og_images.py: updates the count-bearing OG-card subtitles
   (meetings = exact; resources / glossary terms = a "N+" floor rounded down
   to the nearest ten). The weekly workflow then regenerates those images.

Usage
-----
    python3 tools/sync_counts.py            # apply fixes, print what changed
    python3 tools/sync_counts.py --check    # exit 1 if anything is out of sync
                                            # (no writes) - for CI
"""
from __future__ import annotations

import argparse
import html as html_lib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Category sections on resources.html, in the order they appear on the page.
# name + description feed the CollectionPage.mainEntity table-of-contents.
CATEGORY_META = {
    "ctf-challenges": ("CTF Challenges & Vulnerable Environments",
                       "Hands-on vulnerable environments and CTF labs for AWS, Azure, GCP, and Kubernetes"),
    "labs-training": ("Hands-On Labs & Training Platforms",
                      "Interactive labs and training providers for cloud security skill building"),
    "security-tools": ("Security Tools & Platforms",
                       "CNAPP, CSPM, KSPM, SIEM, and other cloud security tools"),
    "certifications": ("Certifications & Professional Development",
                       "Certification paths and professional development resources"),
    "ai-security": ("AI Security & LLM Protection",
                    "Securing AI/ML systems and LLM applications, prompt-injection defenses, and AI governance"),
    "job-search": ("Job Search & Career Development",
                   "Job boards, hiring platforms, and career resources for cloud security roles"),
}

CARD_RE = re.compile(
    r'<a\s+[^>]*?href="([^"]+)"[^>]*>\s*<div class="resource-card"[^>]*>.*?<h3>(.*?)</h3>',
    re.DOTALL,
)
LDJSON_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL)


# ---------------------------------------------------------------- source of truth
def floor10(n: int) -> int:
    return (n // 10) * 10


def unique_resources(html: str) -> list[tuple[str, str]]:
    """Ordered (url, name) for every resource card, deduped by URL (first wins)."""
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for url, raw in CARD_RE.findall(html):
        name = html_lib.unescape(re.sub(r"<[^>]+>", "", raw).strip())
        if url not in seen:
            seen.add(url)
            out.append((url, name))
    return out


def present_categories(html: str) -> list[str]:
    """Category-section ids that actually exist on the page, in page order."""
    positions = []
    for cid in CATEGORY_META:
        m = re.search(r'id="%s"' % re.escape(cid), html)
        if m:
            positions.append((m.start(), cid))
    return [cid for _, cid in sorted(positions)]


# ------------------------------------------------------------- resources.html gen
def _resource_itemlist_block(resources: list[tuple[str, str]]) -> str:
    items = ",\n".join(
        "    {\n"
        '      "@type": "ListItem",\n'
        f'      "position": {i},\n'
        f"      \"url\": {json.dumps(u, ensure_ascii=False)},\n"
        f"      \"name\": {json.dumps(n, ensure_ascii=False)}\n"
        "    }"
        for i, (u, n) in enumerate(resources, start=1)
    )
    return (
        '<script type="application/ld+json">\n'
        "{\n"
        '  "@context": "https://schema.org",\n'
        '  "@type": "ItemList",\n'
        '  "name": "Cloud Security Resources",\n'
        '  "description": "Curated cloud security resources - CTFs, labs, tools, '
        'certifications, and AI security materials.",\n'
        f'  "numberOfItems": {len(resources)},\n'
        '  "itemListElement": [\n'
        f"{items}\n"
        "  ]\n"
        "}\n"
        "    </script>"
    )


def _collectionpage_block(categories: list[str], floor: int) -> str:
    cats = ",\n".join(
        "          {\n"
        '            "@type": "ListItem",\n'
        f'            "position": {i},\n'
        '            "item": {\n'
        '              "@type": "WebPage",\n'
        f"              \"name\": {json.dumps(CATEGORY_META[cid][0], ensure_ascii=False)},\n"
        f"              \"description\": {json.dumps(CATEGORY_META[cid][1], ensure_ascii=False)},\n"
        f'              "url": "https://csoh.org/resources.html#{cid}"\n'
        "            }\n"
        "          }"
        for i, cid in enumerate(categories, start=1)
    )
    return (
        '<script type="application/ld+json">\n'
        "    {\n"
        '      "@context": "https://schema.org",\n'
        '      "@type": "CollectionPage",\n'
        '      "name": "Cloud Security Resources",\n'
        f'      "description": "Comprehensive collection of {floor}+ curated cloud '
        'security resources including CTF challenges, labs, tools, and certifications",\n'
        '      "url": "https://csoh.org/resources.html",\n'
        '      "about": {\n'
        '        "@type": "Thing",\n'
        '        "name": "Cloud Security",\n'
        '        "description": "Cloud security resources for AWS, Azure, GCP, and Kubernetes"\n'
        "      },\n"
        '      "mainEntity": {\n'
        '        "@type": "ItemList",\n'
        '        "name": "Cloud Security Resources",\n'
        '        "description": "Curated collection of cloud security resources",\n'
        f'        "numberOfItems": {len(categories)},\n'
        '        "itemListElement": [\n'
        f"{cats}\n"
        "        ]\n"
        "      }\n"
        "    }\n"
        "    </script>"
    )


def rebuild_resources(html: str) -> str:
    """Replace the CollectionPage block and the standalone ItemList block."""
    resources = unique_resources(html)
    categories = present_categories(html)
    floor = floor10(len(resources))
    for m in LDJSON_RE.finditer(html):
        try:
            obj = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        if obj.get("@type") == "CollectionPage":
            html = html.replace(m.group(0), _collectionpage_block(categories, floor), 1)
        elif obj.get("@type") == "ItemList":
            html = html.replace(m.group(0), _resource_itemlist_block(resources), 1)
    return html


# --------------------------------------------------- generic numberOfItems invariant
def enforce_itemlist_invariant(html: str) -> tuple[str, list[str]]:
    """For every ld+json block, set each ItemList numberOfItems to its real
    enumerated length. Returns (new_html, notes)."""
    notes: list[str] = []

    def fix_block(block: str) -> str:
        try:
            obj = json.loads(block)
        except json.JSONDecodeError:
            return block

        # Only single-ItemList blocks are handled surgically here; the multi-list
        # resources.html page is regenerated separately.
        def count_for(o):
            if isinstance(o, dict):
                if o.get("@type") == "ItemList":
                    return len(o.get("itemListElement", []))
                for v in o.values():
                    r = count_for(v)
                    if r is not None:
                        return r
            elif isinstance(o, list):
                for v in o:
                    r = count_for(v)
                    if r is not None:
                        return r
            return None

        real = count_for(obj)
        if real is None:
            return block
        m = re.search(r'"numberOfItems":\s*(\d+)', block)
        if m and int(m.group(1)) != real:
            notes.append(f'numberOfItems {m.group(1)} -> {real}')
            return re.sub(r'"numberOfItems":\s*\d+', f'"numberOfItems": {real}', block, count=1)
        return block

    def repl(mo):
        return '<script type="application/ld+json">' + fix_block(mo.group(1)) + '</script>'

    return LDJSON_RE.sub(repl, html), notes


# ------------------------------------------------------------------- OG subtitles
def og_rules(counts: dict) -> list[tuple[str, str]]:
    """(regex, replacement) pairs for count-bearing OG-card strings."""
    meetings = counts["meetings"]
    res_floor = floor10(counts["resources"])
    # Note: glossary "N+ terms" is deliberately NOT managed here - the glossary
    # has more <dt> ids (aliases) than visible terms, so an auto floor would
    # overclaim. The safe "300+" is left as authored.
    return [
        (r'(\d+)\+ resources', f'{res_floor}+ resources'),
        (r'"(\d+)\+ Cloud Security Resources"', f'"{res_floor}+ Cloud Security Resources"'),
        (r'(\d+) Weekly Cloud Security Recaps', f'{meetings} Weekly Cloud Security Recaps'),
        (r'(\d+) meetings searchable', f'{meetings} meetings searchable'),
    ]


def sync_og(counts: dict, apply: bool) -> tuple[bool, list[str]]:
    path = REPO / "tools" / "generate_og_images.py"
    text = path.read_text(encoding="utf-8")
    changed = []
    for pat, rep in og_rules(counts):
        new = re.sub(pat, rep, text)
        if new != text:
            changed.append(rep)
            text = new
    if changed and apply:
        path.write_text(text, encoding="utf-8")
    return bool(changed), changed


# ---------------------------------------------------- cloud-security-reading-list
READING_ITEM_RE = re.compile(r'<div class="resource-card">\s*<h3>\s*<a\s+[^>]*?href="([^"]+)"[^>]*>(.*?)</a>',
                             re.DOTALL)


def reading_list_items(html: str) -> list[tuple[str, str]]:
    """Ordered (url, name) for every reading-list card, deduped by URL."""
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for url, raw in READING_ITEM_RE.findall(html):
        name = html_lib.unescape(re.sub(r"<[^>]+>", "", raw).strip())
        if url not in seen:
            seen.add(url)
            out.append((url, name))
    return out


def rebuild_reading_list(html: str) -> str:
    """Regenerate the reading-list ItemList so it enumerates every item card
    (was a hand-kept '6 ways' category stub)."""
    items = reading_list_items(html)
    entries = ",\n".join(
        f'        {{ "@type": "ListItem", "position": {i}, '
        f"\"name\": {json.dumps(n, ensure_ascii=False)}, "
        f"\"url\": {json.dumps(u, ensure_ascii=False)} }}"
        for i, (u, n) in enumerate(items, start=1)
    )
    block = (
        '<script type="application/ld+json">\n'
        "    {\n"
        '      "@context": "https://schema.org",\n'
        '      "@type": "ItemList",\n'
        '      "name": "Cloud Security Reading List",\n'
        '      "description": "Books, newsletters, blogs, podcasts, and people to follow that CSOH members read.",\n'
        '      "itemListOrder": "https://schema.org/ItemListOrderAscending",\n'
        f'      "numberOfItems": {len(items)},\n'
        '      "itemListElement": [\n'
        f"{entries}\n"
        "      ]\n"
        "    }\n"
        "    </script>"
    )
    for m in LDJSON_RE.finditer(html):
        try:
            obj = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("@type") == "ItemList":
            return html.replace(m.group(0), block, 1)
    return html


# ------------------------------------------------------- prose counts via markers
# Prose counts are wrapped in HTML-comment sentinels so the tool can rewrite the
# number without touching surrounding text, e.g.
#     <!--count:resources_floor-->380+<!--/count--> curated resources
# The comment is invisible in rendered HTML and on GitHub-rendered Markdown.
MARKER_RE = re.compile(r"<!--count:([a-z_]+)-->(.*?)<!--/count-->", re.DOTALL)


def display_values(counts: dict) -> dict:
    return {
        "resources_floor": f"{floor10(counts['resources'])}+",
        "resources": str(counts["resources"]),
        "meetings": str(counts["meetings"]),
        "meetings_floor": f"{floor10(counts['meetings'])}+",
        "breaches": str(counts["breaches"]),
        "feeds": str(counts["feeds"]),
        "ctfs": str(counts["ctfs"]),
        "ctfs_floor": f"{floor10(counts['ctfs'])}+",
        "conferences": str(counts["conferences"]),
        "glossary_terms": str(counts["glossary_terms"]),
        "glossary_terms_floor": f"{floor10(counts['glossary_terms'])}+",
        "long_form_floor": f"{floor10(counts['long_form'])}+",
    }


def sync_markers(text: str, disp: dict) -> str:
    def repl(m):
        key = m.group(1)
        if key not in disp:
            return m.group(0)
        return f"<!--count:{key}-->{disp[key]}<!--/count-->"
    return MARKER_RE.sub(repl, text)


# Count phrases that live where a marker comment cannot: inside `content="..."`
# attributes (meta / Open Graph) and inside JSON-LD, where an HTML comment would
# render as literal text or break the JSON. Same idea as the llms.txt rules, but
# applied to HTML. Patterns are deliberately narrow so they only ever rewrite a
# resource count that is already spelled out as "<number>+ <phrase>".
HTML_PROSE_RULES = [
    (r"\d+\+ vendor-neutral resources", "{resources_floor} vendor-neutral resources"),
    (r"\d+\+ curated cloud security resources", "{resources_floor} curated cloud security resources"),
    (r"\d+\+ curated resources", "{resources_floor} curated resources"),
    (r"\d+\+ entry Resources Directory", "{resources_floor} entry Resources Directory"),
    (r"broad catalog \(\d+\+\)", "broad catalog ({resources_floor})"),
    (r"\d+\+ links, vendor-neutral", "{resources_floor} links, vendor-neutral"),
]


def sync_html_prose(text: str, disp: dict) -> str:
    for pat, rep in HTML_PROSE_RULES:
        text = re.sub(pat, rep.format(**disp), text)
    return text


def sync_llms(disp: dict, apply: bool) -> tuple[bool, list[str]]:
    """llms.txt is plain text (HTML comments would show), so update its known
    count phrases with targeted regexes instead of markers."""
    path = REPO / "llms.txt"
    text = path.read_text(encoding="utf-8")
    rules = [
        (r"\d+\+ curated resources", f"{disp['resources_floor']} curated resources"),
        (r"\d+\+ curated tools", f"{disp['resources_floor']} curated tools"),
        (r"\d+\+ weekly sessions", f"{disp['meetings_floor']} weekly sessions"),
        (r"\d+ vendor-neutral sources", f"{disp['feeds']} vendor-neutral sources"),
    ]
    changed = []
    for pat, rep in rules:
        new = re.sub(pat, rep, text)
        if new != text:
            changed.append(rep)
            text = new
    if changed and apply:
        path.write_text(text, encoding="utf-8")
    return bool(changed), changed


# ------------------------------------------------------------------------- counts
def feeds_count() -> int:
    """Number of FEEDS entries in update_news.py (the news source list)."""
    text = (REPO / "update_news.py").read_text(encoding="utf-8")
    m = re.search(r"FEEDS\s*=\s*\[(.*?)\n\]", text, re.DOTALL)
    if not m:
        return 0
    return len(re.findall(r'"url"\s*:', m.group(1)))


def card_count(page: str) -> int:
    """Number of entry cards on a directory page.

    ctfs.html and conferences.html are flat lists of `.resource-card` articles,
    and each page's JSON-LD numberOfItems already tracks that same figure, so
    counting the cards keeps the prose and the structured data on one source.
    """
    text = (REPO / page).read_text(encoding="utf-8")
    return len(re.findall(r'class="resource-card"', text))


def long_form_count() -> int:
    """Root-level guide pages substantial enough to call long-form.

    "Long-form" is defined here rather than asserted in prose: a root page that
    is not a utility page and carries at least 1,500 words of body copy. Nav,
    footer, script, and style blocks are stripped first so chrome does not
    inflate the count.
    """
    utility = {
        "403.html", "404.html", "search.html", "rss.html", "present.html",
        "google66d489593949bd4c.html",
    }
    total = 0
    for path in REPO.glob("*.html"):
        if path.name in utility:
            continue
        text = path.read_text(encoding="utf-8")
        body = re.sub(r"(?s)<(script|style|head|nav|footer).*?</\1>", "", text)
        if len(re.sub(r"<[^>]+>", " ", body).split()) >= 1500:
            total += 1
    return total


def canonical_counts() -> dict:
    res_html = (REPO / "resources.html").read_text(encoding="utf-8")
    gloss = (REPO / "glossary.html").read_text(encoding="utf-8")
    return {
        "resources": len(unique_resources(res_html)),
        "meetings": len(list((REPO / "meetings").glob("*.html"))),
        "breaches": len(list((REPO / "breaches").glob("*.html"))),
        "feeds": feeds_count(),
        "glossary_terms": len(re.findall(r'id="term-[a-z0-9-]+"', gloss)),
        "ctfs": card_count("ctfs.html"),
        "conferences": card_count("conferences.html"),
        "long_form": long_form_count(),
    }


def html_files() -> list[Path]:
    out = list(REPO.glob("*.html"))
    for sub in ("breaches", "meetings", "portfolio", "homelab"):
        out += (REPO / sub).glob("*.html")
    return sorted(out)


def md_files() -> list[Path]:
    return sorted(list(REPO.glob("*.md")) + list((REPO / "tools").glob("*.md")))


# Pages whose ItemList structured data is regenerated wholesale from the cards.
MANAGED = {
    "resources.html": rebuild_resources,
    "cloud-security-reading-list.html": rebuild_reading_list,
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Keep site counts in sync with reality.")
    ap.add_argument("--check", action="store_true",
                    help="report drift and exit 1 without writing (for CI)")
    args = ap.parse_args()
    apply = not args.check

    counts = canonical_counts()
    disp = display_values(counts)
    print("Canonical counts:", ", ".join(f"{k}={v}" for k, v in counts.items()))

    drift = []

    # 1. HTML pages: regenerate managed ItemLists (or enforce the count
    #    invariant elsewhere), then refresh any <!--count:...--> prose markers.
    for f in html_files():
        txt = f.read_text(encoding="utf-8")
        new_txt = MANAGED[f.name](txt) if f.name in MANAGED else enforce_itemlist_invariant(txt)[0]
        new_txt = sync_markers(new_txt, disp)
        new_txt = sync_html_prose(new_txt, disp)
        if new_txt != txt:
            drift.append(str(f.relative_to(REPO)))
            if apply:
                f.write_text(new_txt, encoding="utf-8")

    # 2. Markdown docs: prose markers only.
    for f in md_files():
        txt = f.read_text(encoding="utf-8")
        new_txt = sync_markers(txt, disp)
        if new_txt != txt:
            drift.append(str(f.relative_to(REPO)))
            if apply:
                f.write_text(new_txt, encoding="utf-8")

    # 3. llms.txt (plain text: regex, not markers).
    llms_changed, _ = sync_llms(disp, apply)
    if llms_changed:
        drift.append("llms.txt")

    # 4. OG-card subtitles.
    og_changed, og_notes = sync_og(counts, apply)
    if og_changed:
        drift.append("generate_og_images.py OG subtitles: " + "; ".join(og_notes))

    if not drift:
        print("All counts already in sync.")
        return 0

    verb = "Would update" if args.check else "Updated"
    print(f"\n{verb} {len(drift)} location(s):")
    for d in drift:
        print(f"  - {d}")
    if args.check:
        print("\nRun `python3 tools/sync_counts.py` to fix.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
