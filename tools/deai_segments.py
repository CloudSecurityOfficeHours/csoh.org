#!/usr/bin/env python3
"""Extract, check and apply style-only rewrites of prose segments (EDITORIAL_STANDARDS section 9).

WHY THIS EXISTS
---------------
A de-AI pass rewrites sentences that carry a section-9 pattern (dash asides,
reversals, reveal labels, empty intensifiers, question strings) and must not
change anything a sentence claims. Two things make that safe at scale:

- The rewriter never touches the page. It sees one innermost prose block at a
  time (a "segment": the inner HTML of a <p>, <li>, <dd>, <td>, <th> or
  <figcaption> inside <main>) and returns a replacement for it. This tool
  applies the replacement only if a mechanical check passes.
- The mechanical check is the floor, not the ceiling. It rejects anything it
  can prove changed: markup, link targets and the text they wrap, code,
  numbers, hedge and quantifier counts, quoted passages, vendor mentions,
  dashes. It cannot see meaning. Every accepted rewrite still needs an
  adversarial meaning review by a reader who sees both versions (section 9,
  "Checking a pass").

WHAT IS NEVER A SEGMENT
-----------------------
Headings, <head>, code and <pre>, SVG, scripts, the generated SESSION_BLOCK and
QUOTES blocks, byline/TOC/author-card/breadcrumb/share/card chrome, and any
block that quotes the page's own pull quote (the pull quote repeats that
sentence, so the two would drift). Blocks shorter than six words are skipped.

USAGE
-----
  extract  PAGES.txt OUT.json [--skip-intensifier-only]
                       flagged segments, with byte offsets into each page
  batch    SEGMENTS.json OUTDIR N
                       N batch files of roughly equal size, each page kept whole
  check    BATCH.json REWRITES.json
                       print every rewrite the apply step would reject; exit 1 if any
  apply    SEGMENTS.json REWRITES.json REPORT.json [--dry-run]
                       write accepted rewrites into the pages, last offset first
  verify   [--ref REF]
                       whole-file check of every page modified since REF (default HEAD)
  self-test            planted cases the check must accept or reject

REWRITES.json is a list of {"id": ..., "after": ...}. A segment id is
"<page>#<n>", numbered in page order at extraction time; offsets are only
valid against the file as it was then, and apply refuses a segment whose
bytes have since changed.

Paths are relative to the repository root (or to CSOH_ROOT when set).
"""
from __future__ import annotations

import argparse
import collections
import html
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get('CSOH_ROOT', Path(__file__).resolve().parent.parent))

BLOCK = {'p', 'li', 'dd', 'td', 'th', 'figcaption'}
CONTAINER = BLOCK | {'ul', 'ol', 'dl', 'dt', 'div', 'section', 'article', 'aside', 'table', 'tr', 'thead', 'tbody',
                     'pre', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'figure', 'details', 'summary', 'nav', 'header',
                     'footer', 'form', 'main', 'svg', 'script', 'style', 'iframe', 'picture', 'video', 'blockquote'}
VOID = {'br', 'img', 'wbr', 'input', 'source', 'hr', 'meta', 'link', 'col', 'area', 'embed', 'track', 'path',
        'circle', 'rect', 'line', 'polyline', 'polygon', 'ellipse', 'stop', 'use'}
PROTECTED = [r'<!--\s*SESSION_BLOCK_START.*?SESSION_BLOCK_END\s*-->', r'<!--\s*QUOTES_START.*?QUOTES_END\s*-->',
             r'<script\b.*?</script>', r'<pre\b.*?</pre>', r'<svg\b.*?</svg>', r'<style\b.*?</style>',
             r'<blockquote\b.*?</blockquote>']
SKIP_CLASS = re.compile(r'class="[^"]*\b(?:page-meta|pull-quote|author-card|breadcrumb|toc|share-|card-meta|'
                        r'resource-card|session-block)')
TELLS = {
    'dash aside': re.compile(r'\w - \w'),
    'reversal': re.compile(r"\b(?:is|are|was) not\b[^.]{1,60}\.\s+(?:It|They|That) (?:is|are|was)\b|"
                           r"\bisn't\b[^.]{1,50}\.\s+It's\b|\bnot just\b"),
    'reveal label': re.compile(r"\bThe (?:catch|point|result|fix|lesson|upshot|bottom line|short version|good news|"
                               r"bad news):|\bHere's (?:why|how|the)\b|\b(?:This|That) is (?:where|why)\b|"
                               r"\bThe (?:honest|real|uncomfortable|transferable) (?:lesson|answer|question|point)\b"),
    'intensifier': re.compile(r'(?i)\b(?:actually|genuinely|truly|single most|highest-leverage)\b'),
    'question string': re.compile(r'\?\s+[A-Z][^.?]{3,60}\?\s+[A-Z][^.?]{3,60}\?'),
}
# Label separators are not asides for detection: a bold term or a link followed by " - ", and the bold term itself.
LABEL = re.compile(r'^\s*<(?:strong|b)>.*?</(?:strong|b)>|</a>\s+-\s|<(?:strong|b)>[^<]{1,80}</(?:strong|b)>')
TAG = re.compile(r'<!--.*?-->|<(/?)([a-zA-Z][\w-]*)\b([^>]*?)(/?)>', re.S)
NUM = re.compile(r'\$?\d[\d,.]*(?:k|%|\+)?')
QUANT = re.compile(r'(?i)\b(?:all|every|almost|most|mostly|many|some|few|often|usually|typically|always|never|'
                   r'rarely|only|primarily|increasingly|any|each|none|nearly|roughly|approximately|'
                   r'at least|more than|less than|fewer than)\b')
DASH = re.compile('[–—]|&[mn]dash;|&#821[12];|&#x201[34];', re.I)


def text_of(h: str) -> str:
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', h))).strip()


def tells_in(inner: str) -> list[str]:
    t = text_of(LABEL.sub(' ', inner))
    return sorted(k for k, r in TELLS.items() if r.search(t))


def asides(h: str) -> int:
    return len(TELLS['dash aside'].findall(text_of(LABEL.sub(' ', h))))


def quoted(t: str) -> list[str]:
    """Quoted passages in reading order. Unbalanced straight quotes pin the whole text."""
    spans = re.findall('“([^”]*)”', t)
    parts = t.split('"')
    if len(parts) % 2:
        spans += parts[1::2]
    else:
        spans.append('UNBALANCED:' + t)
    return spans


def vendor_names() -> list[str]:
    """Vendor names as listed on vendor-landscape.html (<li><strong>Name</strong>, no trailing period)."""
    p = ROOT / 'vendor-landscape.html'
    if not p.exists():
        return []
    names = {html.unescape(n).strip() for n in re.findall(r'<li>\s*<strong>([^<]{2,60})</strong>', p.read_text())}
    return sorted(n for n in names if not n.endswith(('.', ':')) and n[:1].isupper())


VENDORS: list[str] | None = None


def vendor_counts(t: str) -> collections.Counter:
    global VENDORS
    if VENDORS is None:
        VENDORS = vendor_names()
    c = collections.Counter()
    for v in VENDORS:
        n = len(re.findall(r'(?<![\w-])' + re.escape(v) + r'(?![\w-])', t))
        if n:
            c[v] = n
    return c


def markup(h: str) -> tuple[list[str], list[str]]:
    """Every tag with its attributes, every comment, and the text inside a/code/kbd/abbr/time, in order."""
    toks = [m.group(0) if m.group(0).startswith('<!--') else re.sub(r'\s+', ' ', m.group(0)) for m in TAG.finditer(h)]
    pinned = [text_of(x) for x in re.findall(r'<(?:a|code|kbd|abbr|time)\b[^>]*>(.*?)</(?:a|code|kbd|abbr|time)>',
                                             h, re.S)]
    return toks, pinned


def check(before: str, after: str) -> list[str]:
    """Reasons the apply step would reject this rewrite; empty means accepted."""
    problems = []
    tb, ta = text_of(before), text_of(after)
    if not after.strip():
        return ['empty']
    if markup(before) != markup(after):
        problems.append('markup, comments, or text inside a link/code changed')
    if sorted(NUM.findall(tb)) != sorted(NUM.findall(ta)):
        problems.append('numbers changed')
    if DASH.search(after):
        problems.append('em or en dash')
    qb = collections.Counter(w.lower() for w in QUANT.findall(tb))
    qa = collections.Counter(w.lower() for w in QUANT.findall(ta))
    if qb != qa:
        problems.append(f'quantifiers changed: -{dict(qb - qa)} +{dict(qa - qb)}')
    if asides(after) > asides(before):
        problems.append('adds a spaced-hyphen aside')
    if quoted(tb) != quoted(ta):
        problems.append('a quoted passage changed')
    vb, va = vendor_counts(tb), vendor_counts(ta)
    if vb != va:
        problems.append(f'vendor mentions changed: -{dict(vb - va)} +{dict(va - vb)}')
    return problems


# ---- extract --------------------------------------------------------------------------------------------------

def elements(s: str, lo: int, hi: int):
    """Yield (tag, open_start, open_end, close_start, close_end, open_tag_text) for elements in s[lo:hi]."""
    stack = []
    for m in TAG.finditer(s, lo, hi):
        if m.group(0).startswith('<!--'):
            continue
        closing, name, selfclose = m.group(1), m.group(2).lower(), m.group(4)
        if name in VOID or selfclose:
            continue
        if not closing:
            stack.append((name, m.start(), m.end(), m.group(0)))
            continue
        for i in range(len(stack) - 1, -1, -1):
            if stack[i][0] == name:
                tag, os_, oe, ot = stack[i]
                del stack[i:]
                yield tag, os_, oe, m.start(), m.end(), ot
                break


def extract(pages: list[str], out: str, skip_intensifier_only: bool) -> None:
    segs, skipped = [], 0
    for f in pages:
        s = (ROOT / f).read_text(encoding='utf-8')
        m = re.search(r'<main\b.*?</main>', s, re.S)
        if not m:
            continue
        prot = [(x.start(), x.end()) for p in PROTECTED for x in re.finditer(p, s, re.S | re.I)]
        prot += [(os_, ce) for _, os_, _, _, ce, ot in elements(s, m.start(), m.end()) if SKIP_CLASS.search(ot)]
        quotes = [text_of(re.sub(r'<cite\b.*?</cite>', '', q, flags=re.S))
                  for q in re.findall(r'<blockquote class="pull-quote"[^>]*>(.*?)</blockquote>', s, re.S)]
        n = 0
        for tag, os_, oe, cs, ce, ot in elements(s, m.start(), m.end()):
            inner = s[oe:cs]
            if tag not in BLOCK or re.search(r'<(?:%s)\b' % '|'.join(CONTAINER), inner, re.I):
                continue
            if any(a <= os_ < b for a, b in prot) or any(q and q in text_of(inner) for q in quotes):
                continue
            found = tells_in(inner)
            if not found or len(text_of(inner).split()) < 6:
                continue
            if skip_intensifier_only and found == ['intensifier']:
                skipped += 1
                continue
            n += 1
            segs.append(dict(id=f'{f}#{n}', file=f, start=oe, end=cs, tag=tag, before=inner,
                             text=text_of(inner), tells=found))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(segs, indent=1, ensure_ascii=False))
    pages_hit = len({x['file'] for x in segs})
    print(f'{len(segs)} segments, {sum(len(x["text"].split()) for x in segs):,} words, from {pages_hit} pages'
          + (f'; {skipped} intensifier-only skipped' if skip_intensifier_only else ''))
    print(collections.Counter(t for x in segs for t in x['tells']).most_common())


def batch(segs_path: str, outdir: str, n: int) -> None:
    segs = json.loads(Path(segs_path).read_text())
    pages = collections.OrderedDict()
    for s in segs:
        pages.setdefault(s['file'], []).append(s)
    bins = [[] for _ in range(n)]
    for f in sorted(pages, key=lambda f: -len(pages[f])):
        min(bins, key=lambda b: sum(len(pages[p]) for p in b)).append(f)
    Path(outdir).mkdir(parents=True, exist_ok=True)
    manifest = []
    for i, b in enumerate(bins, 1):
        items = [dict(id=s['id'], tells=s['tells'], html=s['before']) for f in sorted(b) for s in pages[f]]
        name = f'batch-{i:02d}'
        (Path(outdir) / f'{name}.json').write_text(json.dumps(items, indent=1, ensure_ascii=False))
        manifest.append(dict(name=name, pages=sorted(b), segments=len(items)))
        print(f'{name}: {len(b):3} pages, {len(items):4} segments')
    (Path(outdir) / 'manifest.json').write_text(json.dumps(manifest, indent=1))


# ---- check / apply ----------------------------------------------------------------------------------------------

def check_file(batch_path: str, rw_path: str) -> int:
    before = {x['id']: x['html'] for x in json.loads(Path(batch_path).read_text())}
    bad = 0
    for r in json.loads(Path(rw_path).read_text()):
        if r['id'] not in before:
            print(json.dumps({'id': r['id'], 'problems': ['unknown id']}))
            bad += 1
            continue
        if r.get('after') is None or r['after'] == before[r['id']]:
            continue
        probs = check(before[r['id']], r['after'])
        if probs:
            print(json.dumps({'id': r['id'], 'problems': probs}))
            bad += 1
    print(f'{bad} rejected')
    return 1 if bad else 0


def apply(segs_path: str, rw_path: str, report_path: str, dry: bool) -> int:
    segs = {x['id']: x for x in json.loads(Path(segs_path).read_text())}
    by_file = collections.defaultdict(list)
    report = {'applied': [], 'rejected': [], 'stale': []}
    for r in json.loads(Path(rw_path).read_text()):
        sg = segs.get(r['id'])
        if not sg or r.get('after') in (None, sg['before']):
            continue
        probs = check(sg['before'], r['after'])
        if probs:
            report['rejected'].append({'id': r['id'], 'problems': probs})
        else:
            by_file[sg['file']].append((sg, r['after']))
    for f, items in by_file.items():
        s = (ROOT / f).read_text(encoding='utf-8')
        for sg, after in sorted(items, key=lambda x: -x[0]['start']):
            if s[sg['start']:sg['end']] != sg['before']:
                report['stale'].append(sg['id'])
                continue
            s = s[:sg['start']] + after + s[sg['end']:]
            report['applied'].append(sg['id'])
        if not dry:
            (ROOT / f).write_text(s, encoding='utf-8')
    Path(report_path).write_text(json.dumps(report, indent=1))
    print({k: len(v) for k, v in report.items()}, '(dry run)' if dry else '')
    return 0


# ---- verify -----------------------------------------------------------------------------------------------------

def _head_sans_structured_text(s: str) -> str:
    h = s[:s.find('</head>')]
    return re.sub(r'<script type="application/ld\+json">\s*\{[^<]*?"@type":\s*"(?:FAQPage|DefinedTermSet)".*?</script>',
                  '', h, flags=re.S)


def _main_of(s: str) -> str:
    m = re.search(r'<main\b.*?</main>', s, re.S)
    return m.group(0) if m else s


def verify(ref: str) -> int:
    """Only prose text may differ from REF: tags, attributes, comments, links, numbers and <head> stay put."""
    files = subprocess.run(['git', 'diff', '--name-only', ref, '--', '*.html'], cwd=ROOT,
                           capture_output=True, text=True).stdout.split()
    bad = collections.defaultdict(list)

    def tokens(s: str) -> list[str]:
        return [re.sub(r'\s+', ' ', m.group(0)) for m in TAG.finditer(s)]

    def links(s: str) -> list[tuple[str, str]]:
        # Every target is pinned. Wrapped text is pinned for inline links only: a link that wraps a whole card
        # (a <p>, <div> or heading inside it) carries prose the pass may rewrite.
        return [(h, '<card>' if re.search(r'<(?:p|div|h[1-6]|li|ul|ol|section|article)\b', x) else text_of(x))
                for h, x in re.findall(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', s, re.S)]

    for f in files:
        old = subprocess.run(['git', 'show', f'{ref}:{f}'], cwd=ROOT, capture_output=True, text=True).stdout
        new = (ROOT / f).read_text(encoding='utf-8')
        if tokens(old) != tokens(new):
            bad[f].append('tag/attribute/comment sequence differs')
        if _head_sans_structured_text(old) != _head_sans_structured_text(new):
            bad[f].append('<head> changed outside FAQPage/DefinedTerm JSON-LD')
        if links(old) != links(new):
            bad[f].append('a link target or wrapped term changed')
        if sorted(NUM.findall(text_of(_main_of(old)))) != sorted(NUM.findall(text_of(_main_of(new)))):
            bad[f].append('numbers in <main> changed')
        if len(DASH.findall(new)) > len(DASH.findall(old)):
            bad[f].append('em/en dash added')
    print(f'{len(files)} modified pages checked against {ref}; {len(bad)} with problems')
    for f, p in bad.items():
        print(' ', f, p)
    return 1 if bad else 0


# ---- self-test --------------------------------------------------------------------------------------------------

def self_test() -> int:
    base = ('Most teams pay <a href="x.html">CSPM</a> vendors like Wiz $130k - and the bill "keeps growing fast" '
            'every year.')
    good = ('Most teams pay <a href="x.html">CSPM</a> vendors like Wiz $130k, and the bill "keeps growing fast" '
            'every year.')
    cases = {
        'faithful rewrite': (good, []),
        'link target changed': (good.replace('x.html', 'y.html'), ['markup']),
        'linked term changed': (good.replace('>CSPM<', '>CNAPP<'), ['markup']),
        'number changed': (good.replace('$130k', '$140k'), ['numbers']),
        'hedge changed': (good.replace('Most', 'All'), ['quantifiers']),
        'em dash added': (good.replace(', and', ' — and'), ['em or en dash']),
        'aside added': (good.replace('every year', 'every year - really - now'), ['aside']),
        'quote edited': (good.replace('keeps growing fast', 'keeps growing'), ['quoted']),
        'vendor dropped': (good.replace('like Wiz ', ''), ['vendor']),
    }
    global VENDORS
    VENDORS = ['Wiz']
    failures = 0
    for name, (after, expect) in cases.items():
        got = check(base, after)
        ok = (not expect and not got) or (expect and all(any(e in p for p in got) for e in expect))
        failures += not ok
        print(f'{"ok  " if ok else "FAIL"} {name}: {got or "accepted"}')
    VENDORS = None
    if failures:
        print(f'{failures} self-test case(s) failed')
        return 1
    print('self-test passed')
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    e = sub.add_parser('extract')
    e.add_argument('pages')
    e.add_argument('out')
    e.add_argument('--skip-intensifier-only', action='store_true')
    b = sub.add_parser('batch')
    b.add_argument('segments')
    b.add_argument('outdir')
    b.add_argument('n', type=int)
    c = sub.add_parser('check')
    c.add_argument('batch')
    c.add_argument('rewrites')
    a = sub.add_parser('apply')
    a.add_argument('segments')
    a.add_argument('rewrites')
    a.add_argument('report')
    a.add_argument('--dry-run', action='store_true')
    v = sub.add_parser('verify')
    v.add_argument('--ref', default='HEAD')
    sub.add_parser('self-test')
    args = ap.parse_args()
    if args.cmd == 'extract':
        pages = [line.strip() for line in Path(args.pages).read_text().splitlines() if line.strip()]
        extract(pages, args.out, args.skip_intensifier_only)
        return 0
    if args.cmd == 'batch':
        batch(args.segments, args.outdir, args.n)
        return 0
    if args.cmd == 'check':
        return check_file(args.batch, args.rewrites)
    if args.cmd == 'apply':
        return apply(args.segments, args.rewrites, args.report, args.dry_run)
    if args.cmd == 'verify':
        return verify(args.ref)
    return self_test()


if __name__ == '__main__':
    sys.exit(main())
