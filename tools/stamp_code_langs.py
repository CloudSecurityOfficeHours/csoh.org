#!/usr/bin/env python3
"""Stamp data-lang="<language>" onto every `<div class="code-block"><pre>` block.

Why stamp it into the HTML rather than sniff the language in JavaScript:

  - The label renders from CSS `content: attr(data-lang)`, so a reader with
    JavaScript disabled still sees whether a block is shell or a policy file.
    Runtime detection gives them nothing.
  - It is reviewable in a diff and gateable in CI. A misclassification is a
    line someone can see and fix, not a heuristic firing invisibly in a
    browser.
  - It costs nothing at page load.

Only blocks of the form `<div class="code-block"><pre>` are stamped. The site
also carries an older shape, `<div class="code-block">` holding text broken by
<br>, and that shape is deliberately left alone: some of those are not code at
all (an email template on speakers.html, a resume line on the resume guide, a
bare feed URL on rss.html), so a language label would be a lie. They still get
a copy button at runtime; see initCodeBlocks() in main.js.

Usage:
    python3 tools/stamp_code_langs.py            # stamp in place
    python3 tools/stamp_code_langs.py --check    # exit 1 if anything would change
    python3 tools/stamp_code_langs.py --report   # print the classification table

Idempotent: running it twice changes nothing the second time.
"""

from __future__ import annotations

import html as _html
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# `<div class="code-block...">` immediately followed by `<pre>`. The class is
# matched with [^"]* so `code-block--rounded` is included; the attribute list
# is matched with [^>]* so a block that already carries data-lang re-stamps
# rather than gaining a second copy.
BLOCK_RE = re.compile(
    r'(<div class="code-block[^"]*")([^>]*)(>\s*<pre>)(.*?)(</pre>)', re.S)

DATA_LANG_RE = re.compile(r'\s*data-lang="[^"]*"')

# Languages the highlighter in main.js knows. Anything else is stamped "text",
# which still gets a label and a copy button but no tokenising. Keep this list
# in step with LANGS in main.js.
KNOWN = {'bash', 'json', 'yaml', 'rego', 'hcl', 'sql', 'python',
         'xml', 'cedar', 'yara', 'cel', 'regex', 'text',
         # The SIEM query languages of the howto/ detection guides.
         'spl', 'kql', 'esql', 'eql', 'yara-l', 'sumo logic', 'datadog'}

# Shell verbs that make a block bash even when its first line is a comment.
SHELL_CMDS = (
    'aws', 'az', 'gcloud', 'kubectl', 'kind', 'docker', 'helm', 'terraform',
    'tflocal', 'awslocal', 'localstack', 'git', 'curl', 'brew', 'apt', 'dnf',
    'yum', 'pip', 'pip3', 'python3', 'python', 'npm', 'npx', 'cargo', 'go',
    'jq', 'yq', 'opa', 'conftest', 'regal', 'oscap', 'oscap-podman', 'yr',
    'sigma', 'trivy', 'checkov', 'prowler', 'grep', 'rg', 'sed', 'awk', 'cat',
    'echo', 'printf', 'mkdir', 'cd', 'ls', 'rm', 'cp', 'mv', 'chmod', 'export',
    'for', 'while', 'if', 'set', 'sudo', 'ssh', 'scp', 'openssl', 'xmllint',
    'bunzip2', 'tar', 'unzip', 'wget', 'stratus', 'kubescape', 'kube-bench',
    'lychee', 'html5validator', 'gh', 'make', 'bash', 'sh', 'source', 'test',
    'cedar', 'celpy', 'kind-config', 'terraform-local',
)

# Blocks the heuristics get wrong, keyed by a stable hash of their text.
# Add an entry here rather than weakening a rule: a rule loosened to fix one
# block silently re-labels every block it also matches.
OVERRIDES: dict[str, str] = {
    # Genuine regular-expression samples on the regex guide. No heuristic can
    # separate these from shell without also mislabelling real scripts.
    '404123edfae7': 'regex',   # the three too-broad / too-narrow URL patterns
    'e02184c59e86': 'regex',   # the A/B/C/D catastrophic-backtracking exercise
    # Tool OUTPUT rather than input: labelling these bash invites a reader to
    # paste them into a shell.
    'd22e81180d9a': 'text',    # `yr scan -s` match listing
    '5698e5b22db5': 'text',    # Sigma compiled to Splunk SPL
    'adaf4a9ed8d4': 'text',    # infra/terraform/ directory tree
    # A GCP IAM condition: CEL, but with none of the macros the CEL rule keys on.
    '1f26d44948fb': 'cel',
    # A lone HCL attribute (`name = "..."`, spaces around the =) quoted without
    # its enclosing resource block. Broadening the HCL rule to catch it would
    # also swallow Python assignments, so it is named here instead.
    '85a87e511db4': 'hcl',
    # A security-group rule listing on the interview page. `Ingress:` at the
    # start of a line is a YAML mapping key to the heuristic, but this is a
    # description of a rule set, not a file anyone loads.
    '0904c9ff4b8d': 'text',
    # update_news.py's FEEDS list, quoted on contribute.html so a contributor
    # can see where to add a row. `FEEDS = [` has spaces around the `=`, which
    # the bash NAME=value rule deliberately excludes and the HCL rule needs a
    # `resource "..."` header for, so it reaches the end and lands on text.
    '032aef2d6a34': 'python',
    '5b5f9d81d992': 'python',
}


USED_OVERRIDES: set[str] = set()


def block_key(text: str) -> str:
    """Stable id for a block's content, used by OVERRIDES."""
    import hashlib
    return hashlib.sha1(text.strip().encode('utf-8')).hexdigest()[:12]


def _strip_leading_comments(lines: list[str]) -> list[str]:
    """Drop leading `#` / `//` comment and blank lines.

    45 of the blocks on this site open with a comment, so classifying on the
    first line alone would call almost half of them the same thing.
    """
    out = list(lines)
    # '-- ' with the space is a SQL comment; '--flag' without one is a shell
    # option, and stripping that would hide the command being demonstrated.
    while out and (not out[0].strip()
                   or out[0].lstrip().startswith(('#', '//', '-- '))
                   or out[0].strip() == '---'):
        out.pop(0)
    return out


# The detection query languages on the howto/ SIEM guides are pipelines of
# `|`, which the bash fallback at the bottom of classify() would otherwise
# claim, and several of them share commands (`| where`, `| sort`, `| lookup`),
# so no rule may key on a command two of them write. Each rule below keys on
# something only that language writes. ES|QL and SPL are also case-sensitive
# here on purpose: Elastic documents ES|QL in capitals, and lowercase `| eval`
# is SPL.
ESQL_COMMANDS = (r'WHERE|EVAL|KEEP|DROP|STATS|SORT|LIMIT|RENAME|DISSECT|GROK'
                 r'|ENRICH|MV_EXPAND|LOOKUP JOIN|INLINESTATS|CHANGE_POINT|FORK'
                 r'|SAMPLE|COMPLETION|RERANK')
EQL_CATEGORIES = (r'any|api|authentication|configuration|database|driver|email'
                  r'|file|host|iam|intrusion_detection|library|malware|network'
                  r'|package|process|registry|session|threat|vulnerability|web')
# Operators only KQL has among these languages. `lookup` is also SPL and Sumo
# Logic, and `top` is SPL, so neither is here.
KQL_OPERATORS = (r'summarize|project(?:-away|-keep|-rename|-reorder)?|extend'
                 r'|mv-expand|mv-apply|make-series|take|render|top-nested'
                 r'|join\s+kind\s*=|order\s+by|sort\s+by|as\s+hint')
KQL_COMMANDS = (r'create|create-merge|create-or-alter|alter|drop|ingest|set'
                r'|set-or-append|set-or-replace|append|show|execute')
# Built-in metadata fields that open a Sumo Logic scope, and operators SPL and
# KQL do not have (`| count by` is Sumo; SPL writes `| stats count by`).
SUMO_SCOPE = r'_(?:sourceCategory|source|sourceHost|sourceName|collector|index|view|dataTier)\s*='
SUMO_OPERATORS = r'json\b|timeslice\b|count\s+by\b|count_distinct\s*\(|parse\s+(?:regex\b|")|transpose\b'
# SPL: `dedup`, `transaction`, `fields` and `sort` are Sumo Logic operators
# too, so they are not evidence of SPL on their own.
SPL_START = r'(?:index|sourcetype|source|eventtype|tag)\s*=|\|\s*(?:makeresults|tstats|inputlookup|rest|datamodel|metadata)\b'
SPL_OPERATORS = (r'stats|eventstats|streamstats|timechart|chart|eval|table|rex'
                 r'|spath|bin|mvexpand|fillnull|makeresults|tstats|inputlookup'
                 r'|outputlookup|appendpipe|foreach|xyseries|untable')


def _detection_language(first: str, body_text: str) -> str | None:
    """Classify a SIEM query block, or return None if it is not one."""
    if re.match(r'(FROM|ROW|SHOW|TS)\s', first) and \
       re.search(r'(^|\s)\|\s*(' + ESQL_COMMANDS + r')\b', body_text, re.M):
        return 'esql'
    if re.search(r'^\s*(sequence|sample)\s+(by\s|with\s+maxspan|\[)', body_text, re.M) or \
       re.match(r'(' + EQL_CATEGORIES + r')\s+where\s', first):
        return 'eql'
    if re.search(r'(^|\s)\|\s*(' + KQL_OPERATORS + r')\b', body_text, re.M) or \
       re.match(r'\.(' + KQL_COMMANDS + r')\s', first):
        return 'kql'
    if re.match(SUMO_SCOPE, first) or \
       re.search(r'(^|\s)\|\s*(' + SUMO_OPERATORS + r')', body_text, re.M):
        return 'sumo logic'
    if re.match(SPL_START, first) or \
       re.search(r'(^|\s)\|\s*(' + SPL_OPERATORS + r')\b', body_text, re.M):
        return 'spl'
    # KQL that uses only operators it shares with SPL (`| where`, `| count`)
    # still opens with a bare table name on a line of its own, or a `let`.
    # Tested after SPL, whose searches open with `index=` or a quoted term.
    if (re.fullmatch(r'[A-Za-z_]\w*', first) and
            re.search(r'^\s*\|\s*\w', body_text, re.M)) or \
       re.match(r'let\s+\w+\s*=.*;$', first):
        return 'kql'
    # Datadog log search: `source:cloudtrail @evt.name:StopLogging`. A YAML key
    # is followed by a space, which is what keeps `source: x` out of this.
    if re.match(r'-?(@[\w.]+|source|service|host|status|env):[^\s]', first):
        return 'datadog'
    return None


# Planted blocks for --check, which classifies these before the real pages.
# The SIEM rules are the likeliest to be loosened later, and a loosened rule
# fails quietly: blocks change label and the page still renders. Each language
# has a positive case, and the shell cases are the near misses: a command that
# carries a query must stay bash.
SELF_TEST = [
    ('spl', 'index=cloudtrail eventName=StopLogging\n| table _time, eventName'),
    ('spl', 'index="cloudtrail" errorCode=*\n| stats count by errorCode'),
    ('kql', 'AWSCloudTrail\n| summarize count() by SourceIpAddress'),
    ('kql', 'AWSCloudTrail\n| where EventName == "StopLogging"'),
    ('kql', '.create table RawCloudTrail (Record: dynamic)'),
    ('esql', 'FROM logs-aws.cloudtrail-*\n| STATS n = COUNT(*) BY source.ip'),
    ('eql', 'sequence by user.name\n  with maxspan=10m\n  [iam where true]\n  [iam where true]'),
    ('yara-l', 'rule r {\n  events:\n    $e.metadata.product_event_type = "X"\n  condition:\n    $e\n}'),
    ('yara', 'rule r {\n  strings:\n    $a = "x"\n  condition:\n    $a\n}'),
    ('sumo logic', '_sourceCategory=aws/cloudtrail\n| json "eventName" as event_name'),
    ('datadog', 'source:cloudtrail @evt.name:StopLogging'),
    ('text', ' action | ip\n--------+-----------\n Stop   | 192.0.2.1'),
    ('bash', "curl -s localhost:9200/_query -d '{\"query\":\"FROM x | STATS n = COUNT(*)\"}'"),
    ('bash', "docker exec lab splunk search 'index=x | stats count by y'"),
    ('bash', 'cat events.log | sort | uniq -c'),
    ('sql', 'SELECT eventName, count(*)\nFROM ct\nGROUP BY eventName'),
]


def classify(raw: str) -> str:
    """Infer a language for one code block. First match wins, so order matters."""
    text = _html.unescape(raw).strip()
    if not text:
        return 'text'
    if (key := block_key(text)) in OVERRIDES:
        USED_OVERRIDES.add(key)
        return OVERRIDES[key]

    lines = text.splitlines()
    body = _strip_leading_comments(lines)
    body_text = '\n'.join(body).strip()
    first = body[0].strip() if body else ''
    low = text.lower()

    # --- shell heredocs win outright ---------------------------------------
    # `cat > demo.yar <<'EOF'` is a bash command whose payload happens to be
    # YARA. Classifying on the payload labelled the block yara and hid the
    # fact that the reader is meant to run it.
    if re.search(r'<<-?\s*[\'"]?\w+[\'"]?\s*$', text, re.M) and \
       re.match(r'^\s*(cat|tee|read)\b', text, re.M):
        return 'bash'

    # --- unambiguous structural markers first -----------------------------
    if first.startswith('<?xml') or re.match(r'^<[a-zA-Z!/]', first):
        return 'xml'

    if first[:1] in '{[':
        try:
            json.loads(body_text)
            return 'json'
        except Exception:
            pass  # a JSON-ish fragment, or HCL/Rego using braces

    # A rendered results table is output, not input. The ASCII rule under a
    # header (`-----+-----`) or box-drawing borders give it away, and without
    # this the `|` column separators land it on bash, inviting a reader to
    # paste a query result into a shell.
    if re.search(r'^[ \t]*[-+]*-{3,}\+-{3,}[-+]*[ \t]*$', body_text, re.M) or \
       re.search(r'[─-╿]', body_text):
        return 'text'

    # --- languages with a distinctive keyword ------------------------------
    if re.search(r'^\s*package\s+[\w.]+\s*$', body_text, re.M) or \
       re.search(r'\b(deny|allow|violation)\s+contains\b', body_text) or \
       re.search(r'^\s*(default\s+\w+\s*:=|import\s+rego\.v1)', body_text, re.M):
        return 'rego'

    # YARA-L is shaped like YARA (`rule name {` ... `condition:`) but always
    # has an `events:` section, which YARA never does, so it must be tested
    # first or the YARA rule below claims it.
    if re.search(r'^\s*rule\s+\w+\s*\{', body_text, re.M) and \
       re.search(r'^\s*events:\s*$', body_text, re.M):
        return 'yara-l'

    if re.search(r'^\s*rule\s+\w+', body_text, re.M) and 'condition:' in low:
        return 'yara'

    if re.search(r'^\s*(permit|forbid)\s*\(', body_text, re.M) or \
       re.search(r'^\s*entity\s+\w+\s*[;={in]', body_text, re.M) or \
       re.search(r'^\s*action\s+[\w, ]+appliesTo\b', body_text, re.M):
        return 'cedar'

    # SIEM query languages, before SQL: a wrapped EQL `with maxspan=10m` line
    # starts with WITH, which the SQL rule below would claim. Never for a shell
    # command, though: `curl ... -d search='index=x | stats count'` is a
    # command the reader runs, even though it carries SPL.
    verb = first.split()[0].rstrip(':') if first.split() else ''
    is_shell = verb in SHELL_CMDS or first.startswith(('$ ', './', '#!/'))
    if not is_shell and (lang := _detection_language(first, body_text)):
        return lang

    # SQL needs FROM as well as the leading verb. Without it, `with:` in a
    # GitHub Actions workflow matched the case-insensitive WITH and labelled
    # every workflow YAML block as SQL.
    if re.search(r'^\s*(SELECT|WITH)\b', body_text, re.M | re.I) and \
       re.search(r'\bFROM\b', body_text, re.I):
        return 'sql'
    if re.search(r'^\s*(CREATE\s+(TABLE|DATABASE|EXTERNAL)|INSERT\s+INTO|MSCK'
                 r'|DROP\s+TABLE|ALTER\s+TABLE|SHOW\s+(TABLES|PARTITIONS))\b',
                 body_text, re.M | re.I):
        return 'sql'

    if re.search(r'^\s*(resource|provider|variable|module|output|data)\s+"',
                 body_text, re.M) or re.search(r'^\s*terraform\s*\{', body_text, re.M):
        return 'hcl'

    # --- shell before YAML: `kubectl get pods -o yaml` is a command --------
    if is_shell:
        return 'bash'
    # NAME=value at the start of a line, with no spaces around the `=`.
    # HCL writes `attribute_condition = "..."` with spaces, so it is excluded.
    if re.search(r'^[A-Za-z_][A-Za-z0-9_]*=[\"$\'(]', body_text, re.M):
        return 'bash'

    # --- YAML: a mapping key at the start of a line, no shell verbs --------
    if re.match(r'^[\w.$-]+:(\s|$)', first) or first.startswith('- ') or \
       lines[0].strip() == '---':
        return 'yaml'

    # An HCL fragment: a bare `name {` header whose body is `key = value`.
    # terraform.html quotes `condition { ... }` and `target_url { ... }`
    # without the enclosing resource block.
    if re.search(r'^\s*\w+\s*\{\s*$', body_text, re.M) and \
       re.search(r'^\s+\w+\s+=\s', body_text, re.M):
        return 'hcl'

    if re.search(r'^\s*(import|from|def|class)\s', body_text, re.M) or \
       re.search(r'^\s*(print|re\.\w+)\(', body_text, re.M):
        return 'python'

    # CEL: a single boolean expression using CEL's macros and operators, with
    # no statement structure around it.
    if re.search(r'\.(all|exists|exists_one|filter|map)\(\w+,', body_text) or \
       re.search(r'\bhas\([\w.]+\)', body_text):
        return 'cel'

    # Command substitution, checked only after YAML and HCL. `${...}` alone is
    # not enough: HCL interpolates with it and GitHub Actions writes `${{ }}`,
    # so matching on it alone would label every workflow and every Terraform
    # fragment as bash.
    if '$(' in body_text:
        return 'bash'

    # There is deliberately no heuristic for `regex`. Every rule tried here
    # (short block, contains backslash or ^ or $) also matched shell scripts,
    # scanner output, and a directory tree. Genuine regex blocks are named in
    # OVERRIDES instead, where the choice is visible and reviewable.

    if re.search(r'[|$>]|\s--?\w', body_text):
        return 'bash'
    return 'text'


def target_files() -> list[Path]:
    out = subprocess.run(['git', 'ls-files', '*.html'],
                         capture_output=True, text=True, cwd=REPO).stdout.split()
    return [REPO / f for f in out if not f.startswith('tools/')]


def process(path: Path, apply: bool) -> tuple[int, int, Counter]:
    """Return (blocks seen, blocks whose stamp would change, language tally)."""
    text = path.read_text(encoding='utf-8')
    seen = changed = 0
    tally: Counter = Counter()

    def repl(m: re.Match) -> str:
        nonlocal seen, changed
        seen += 1
        head, attrs, mid, body, close = m.groups()
        lang = classify(body)
        tally[lang] += 1
        cleaned = DATA_LANG_RE.sub('', attrs)
        new_attrs = f'{cleaned} data-lang="{lang}"'
        if new_attrs != attrs:
            changed += 1
        return f'{head}{new_attrs}{mid}{body}{close}'

    new = BLOCK_RE.sub(repl, text)
    if apply and new != text:
        path.write_text(new, encoding='utf-8')
    return seen, changed, tally


def self_test() -> None:
    """Refuse to give a verdict if a planted block is misclassified."""
    wrong = [(want, got, text.splitlines()[0])
             for want, text in SELF_TEST
             if (got := classify(_html.escape(text, quote=False))) != want]
    if wrong:
        for want, got, line in wrong:
            print(f'SELF-TEST FAILED: expected {want}, got {got}: {line}')
        print('A classifier rule changed behaviour; fix it before trusting --check.')
        sys.exit(1)


def main() -> None:
    check = '--check' in sys.argv
    report = '--report' in sys.argv
    if check:
        self_test()
    total = changed_total = 0
    tally: Counter = Counter()
    changed_files: list[str] = []

    for path in sorted(target_files()):
        seen, changed, t = process(path, apply=not check)
        total += seen
        changed_total += changed
        tally.update(t)
        if changed:
            changed_files.append(f'{path.relative_to(REPO).as_posix()} ({changed})')

    # An OVERRIDES key is a hash of the block's text, so editing that block
    # silently detaches its override and the block reverts to a heuristic
    # guess. Make that loud rather than invisible.
    stale = set(OVERRIDES) - USED_OVERRIDES
    unknown = {k for k in tally if k not in KNOWN}
    print(f'{total} code blocks; '
          f'{"would update" if check else "updated"} {changed_total}')
    if report or check:
        for lang, n in tally.most_common():
            flag = '  <-- not in KNOWN' if lang in unknown else ''
            print(f'  {n:4d}  {lang}{flag}')
    if stale:
        print(f'ERROR: OVERRIDES keys matching no block (the block was edited, '
              f'so its override no longer applies): {sorted(stale)}')
        print('Re-run with --report to find the new hash, or drop the entry.')
        sys.exit(1)
    if unknown:
        print(f'ERROR: languages not in KNOWN (main.js cannot render them): '
              f'{sorted(unknown)}')
        sys.exit(1)
    if check and changed_total:
        print('Stale data-lang stamps in: ' + ', '.join(changed_files[:12]))
        print('Run: python3 tools/stamp_code_langs.py')
        sys.exit(1)


if __name__ == '__main__':
    main()
