#!/usr/bin/env python3
"""
Inventory, audit and roll every long-lived credential the workflows depend on.

WHY THIS EXISTS
---------------
Almost everything in the deploy path is already credential-free: all three
clouds mint ~1-hour tokens per run via OIDC, and `csoh-ci` hands out ~1-hour
installation tokens. What is left is a short tail of secrets that genuinely
cannot federate, and that tail is the part nobody remembers to rotate because
there is no forcing function - nothing breaks, nothing warns, the tokens just
get older.

Two failure modes this script is built around, both of which have already
happened in this repo:

1. **The inventory drifts away from reality, silently.** SECURITY.md carried a
   row for `SSH_PRIVATE_KEY` marked "live but unreferenced - flagged for
   removal, still present", re-confirmed by hand on 2026-07-26. It is not
   present; it had already been deleted. A hand-maintained list of secrets is
   exactly as trustworthy as the last time somebody diffed it against the API,
   so this script does that diff on every run and *fails* rather than prints.
   (See "A silent count is a failure mode" in CLAUDE.md.)

2. **A rotation half-lands and nobody notices until CI breaks.** Writing a new
   value into an Actions secret gives no feedback whatsoever: `gh secret set`
   succeeds against a typo, a truncated paste, or a token created with the
   wrong permissions, and you find out on the next scheduled run - or worse, on
   the next deploy. So no value is ever written here until it has been proven
   against the live API it will be used on, and no old credential is revoked
   until the new one is in place.

VERIFY BEFORE WRITE, REVOKE AFTER
---------------------------------
Every roll runs in the same order, and stops at the first failure:

    mint new  ->  verify new  ->  write secret  ->  confirm write  ->  revoke old

The window where both credentials are valid is deliberate. Reversing any two of
those steps is how you end up with CI holding a credential nobody has tested.

EVERY VERIFY CARRIES A CONTROL
------------------------------
CLAUDE.md's DNS section states the general rule this file leans on hardest: *an
instrument that reports "nothing is there" is indistinguishable from a broken
instrument until you point it at something you know is there.* A check that a
token works is worthless if the probe would have passed anyway - if `claude`
silently fell back to your local session auth, if an unauthenticated request to
that Google API returns 200 regardless, if the call you made needs no
permission at all.

So each credential is probed three ways:

  * **positive**  - do the exact thing CI does with it, and succeed.
  * **negative**  - do it again with the value corrupted, and *fail*. If a
                    deliberately broken credential passes, the probe is
                    measuring nothing and the roll is aborted.
  * **scope**     - do something the credential is supposed to be too narrow
                    for, and get denied. This catches the over-scoped token,
                    which is the failure that never announces itself.

A credential that passes positive but fails scope is a *worse* outcome than a
broken one, and is treated as a hard failure.

USAGE
-----
    python3 tools/rotate_secrets.py                  # audit: inventory + drift + ages
    python3 tools/rotate_secrets.py audit --check    # same, exit 1 on drift/overdue (CI gate)
    python3 tools/rotate_secrets.py list             # the registry and how each one rolls
    python3 tools/rotate_secrets.py verify           # probe what is held locally, roll nothing
    python3 tools/rotate_secrets.py verify ZOOM_CLIENT_SECRET
    python3 tools/rotate_secrets.py roll PSI_API_KEY
    python3 tools/rotate_secrets.py roll --due       # everything past its cadence
    python3 tools/rotate_secrets.py roll --all
    python3 tools/rotate_secrets.py roll CLOUDFLARE_API_TOKEN --dry-run

WHAT IT CAN AND CANNOT AUTOMATE
-------------------------------
Not every provider will let a script create a credential, and pretending
otherwise produces a tool that lies about what it did. Each credential declares
its own honest level:

  AUTO    end to end, no browser: mint, verify, write, revoke.
  GUIDED  the provider has no create API (GitHub App keys, fine-grained PATs,
          Zoom S2S secrets, Cloudflare tokens without a meta-token). The script
          prints the exact URL and the exact settings, takes the value without
          echoing it, and then does the verify/write/revoke half itself - which
          is the half that actually goes wrong.

`roll` never opens a browser for you and never submits a form on your behalf.

ORG-LEVEL SECRETS NEED A SCOPE YOU PROBABLY DO NOT HAVE
-------------------------------------------------------
`CSOH_CI_*`, `CSOH_PAT` and `ZOOM_*` live at the org, not on the repo. The
default `gh` token here carries `gist, read:org, repo, workflow`, so it can
neither read nor write them - org reads 403 and the audit reports their age as
unknown rather than guessing. To let this script write them:

    gh auth refresh -h github.com -s admin:org

That broadens a token sitting on your laptop, which is a real tradeoff, so the
script will tell you the command and will not run it. Without it, `roll` still
mints, verifies and revokes; it just hands you the value to paste into
Settings -> Secrets, and prints the URL.

SEE ALSO
--------
SECURITY.md "Repository secrets" and "Rotation guidance" - the prose version of
the registry below. If you change a cadence or add a credential, change it in
both; `audit` will tell you when the registry and the workflows disagree, but it
cannot read English.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import getpass
import json
import os
import re
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
ENV_FILE = REPO_ROOT / ".env"

OWNER = "CloudSecurityOfficeHours"
REPO_NAME = "csoh.org"
NWO = f"{OWNER}/{REPO_NAME}"
APP_SLUG = "csoh-ci"

# `${{ secrets.GITHUB_TOKEN }}` is minted per run by Actions itself - there is
# nothing to rotate and nothing to store. Anything else appearing in a workflow
# is expected to be in the registry below.
AUTO_PROVIDED = {"GITHUB_TOKEN"}

TODAY = dt.date.today()

# --------------------------------------------------------------------------
# Local environment quirks
# --------------------------------------------------------------------------

# Python on this machine ships without a usable CA bundle, so every https call
# in tools/ dies with CERTIFICATE_VERIFY_FAILED and looks like "the whole
# provider is down". Point it at the system bundle if the caller has not.
if not os.environ.get("SSL_CERT_FILE") and Path("/etc/ssl/cert.pem").exists():
    os.environ["SSL_CERT_FILE"] = "/etc/ssl/cert.pem"

SSL_CTX = ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE") or None)


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

_TTY = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _TTY else text


def bold(t: str) -> str:
    return _c("1", t)


def green(t: str) -> str:
    return _c("32", t)


def red(t: str) -> str:
    return _c("31", t)


def yellow(t: str) -> str:
    return _c("33", t)


def dim(t: str) -> str:
    return _c("2", t)


def heading(t: str) -> None:
    print(f"\n{bold(t)}\n{'-' * len(t)}")


def redact(value: str | None) -> str:
    """Never print a credential. Show enough to tell two values apart, no more."""
    if not value:
        return "(empty)"
    v = value.strip()
    if len(v) <= 12:
        return f"<{len(v)} chars>"
    return f"{v[:4]}…{v[-4:]} <{len(v)} chars>"


class RollAborted(Exception):
    """Raised to stop a rotation without touching anything downstream."""


# --------------------------------------------------------------------------
# Shell / HTTP plumbing
# --------------------------------------------------------------------------


def run(
    cmd: Sequence[str],
    *,
    stdin_text: str | None = None,
    check: bool = False,
    capture: bool = True,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(cmd),
        input=stdin_text,
        text=True,
        capture_output=capture,
        check=check,
    )


@dataclass
class Response:
    status: int
    body: str

    def json(self) -> dict:
        try:
            return json.loads(self.body) if self.body.strip() else {}
        except json.JSONDecodeError:
            return {}


def http(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict | None = None,
    timeout: int = 30,
) -> Response:
    """A request that returns the error status instead of raising on it.

    Every check in this file cares about 401 and 403 as *results*, not as
    exceptions - a scope control is only meaningful if a denial comes back as
    data we can assert on.
    """
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {"User-Agent": "csoh-rotate-secrets", "Accept": "application/json"}
    if data is not None:
        hdrs["Content-Type"] = "application/json"
    hdrs.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as r:
            return Response(r.status, r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return Response(e.code, e.read().decode("utf-8", "replace"))
    except urllib.error.URLError as e:
        return Response(0, f"network error: {e.reason}")


def corrupt(secret: str) -> str:
    """Produce a value that is the right shape but definitely invalid.

    Used for every negative control. Flipping characters in the middle keeps
    any prefix the provider validates on (`Iv23.`, `github_pat_`, …) so the
    request reaches real authentication rather than bouncing off a format check
    - a 400 "malformed" would not prove the probe can detect a *wrong* secret.
    """
    if len(secret) < 10:
        return secret + "xxxxxxxx"
    mid = len(secret) // 2
    swap = "z" if secret[mid] != "z" else "q"
    return secret[:mid] + swap * 6 + secret[mid + 6 :]


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

POSITIVE = "positive"
NEGATIVE = "negative"
SCOPE = "scope"


@dataclass
class Check:
    kind: str
    name: str
    ok: bool
    detail: str = ""

    def render(self) -> str:
        mark = green("PASS") if self.ok else red("FAIL")
        return f"  [{mark}] {self.kind:<8} {self.name}" + (
            f"\n           {dim(self.detail)}" if self.detail else ""
        )


def report(checks: list[Check]) -> bool:
    for c in checks:
        print(c.render())
    return all(c.ok for c in checks)


# --------------------------------------------------------------------------
# .env
# --------------------------------------------------------------------------


def read_env_file() -> dict[str, str]:
    if not ENV_FILE.exists():
        return {}
    out: dict[str, str] = {}
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def write_env_key(key: str, value: str) -> None:
    """Replace one key in .env, preserving order, comments and file mode.

    .env holds the broad Terraform Cloudflare token; clobbering it while
    updating an unrelated key would cost an afternoon, so this rewrites a
    single line and keeps a .bak.
    """
    if not ENV_FILE.exists():
        raise RollAborted(f"{ENV_FILE} does not exist; cannot mirror {key}")
    original = ENV_FILE.read_text()
    mode = ENV_FILE.stat().st_mode & 0o777

    backup = ENV_FILE.with_suffix(".env.bak")
    backup.write_text(original)
    os.chmod(backup, 0o600)

    lines = original.splitlines(keepends=True)
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    replaced = False
    for i, line in enumerate(lines):
        if pattern.match(line):
            lines[i] = f"{key}={value}\n"
            replaced = True
            break
    if not replaced:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(f"{key}={value}\n")

    ENV_FILE.write_text("".join(lines))
    os.chmod(ENV_FILE, mode)
    print(f"  {green('updated')} .env {key}  (backup: {backup.name})")


# --------------------------------------------------------------------------
# GitHub secret plumbing
# --------------------------------------------------------------------------

REPO_SCOPE = "repo"
ORG_SCOPE = "org"


def gh_scopes() -> set[str]:
    p = run(["gh", "auth", "status"])
    m = re.search(r"Token scopes:\s*(.+)", (p.stdout or "") + (p.stderr or ""))
    if not m:
        return set()
    return {s.strip().strip("'\"") for s in m.group(1).split(",")}


def list_repo_secrets() -> dict[str, dt.datetime] | None:
    p = run(["gh", "api", f"repos/{NWO}/actions/secrets", "--paginate"])
    if p.returncode != 0:
        return None
    try:
        data = json.loads(p.stdout)
    except json.JSONDecodeError:
        return None
    return {
        s["name"]: dt.datetime.fromisoformat(s["updated_at"].replace("Z", "+00:00"))
        for s in data.get("secrets", [])
    }


def list_org_secrets() -> dict[str, dt.datetime] | None:
    """Returns None when the local gh token lacks admin:org - which is normal.

    Reporting "no org secrets" would be a lie of exactly the shape CLAUDE.md
    warns about, so the caller renders this as *unknown* instead.
    """
    p = run(["gh", "api", f"orgs/{OWNER}/actions/secrets", "--paginate"])
    if p.returncode != 0:
        return None
    try:
        data = json.loads(p.stdout)
    except json.JSONDecodeError:
        return None
    return {
        s["name"]: dt.datetime.fromisoformat(s["updated_at"].replace("Z", "+00:00"))
        for s in data.get("secrets", [])
    }


def actual_scope(cred: "Credential", repo_secrets: dict | None = None) -> str:
    """Where the secret really lives, which is not always where the registry says.

    A repo-level secret shadows an org-level one of the same name. So if the
    registry claims org and the value is actually set on the repo, writing to
    the org updates something nothing reads: `gh secret set` succeeds, the
    audit looks clean, and CI keeps using the old value. That is the same
    silent-no-op shape as the inert Cloudflare ruleset in CLAUDE.md.

    This is not hypothetical. `ZOOM_*` were declared org-level here on the
    strength of SECURITY.md's description of the org secrets, and are in fact
    repo-level. The write target follows what the API reports, and `audit`
    reports the disagreement rather than quietly papering over it.
    """
    if repo_secrets is None:
        repo_secrets = list_repo_secrets()
    if repo_secrets is not None and cred.name in repo_secrets:
        return REPO_SCOPE
    return cred.scope


def set_repo_secret(name: str, value: str, dry_run: bool) -> None:
    if dry_run:
        print(f"  {yellow('dry-run')} would set repo secret {name} = {redact(value)}")
        return
    p = run(["gh", "secret", "set", name, "--repo", NWO], stdin_text=value)
    if p.returncode != 0:
        raise RollAborted(f"gh secret set {name} failed: {p.stderr.strip()}")
    print(f"  {green('wrote')} repo secret {name}")


def set_org_secret(name: str, value: str, dry_run: bool) -> None:
    """Write an org secret, or hand the value back if the scope is missing.

    Deliberately pins `--visibility selected --repos csoh.org`. That matches
    how these are configured today (the App is installed on this one repo), but
    it is a *write* of visibility as well as value - so it prints what it is
    about to do rather than doing it quietly.
    """
    if "admin:org" not in gh_scopes():
        print(f"  {yellow('manual step')} - local gh token cannot write org secrets.")
        print(f"    Paste into: https://github.com/organizations/{OWNER}/settings/secrets/actions")
        print(f"    Secret name: {bold(name)}   (value: {redact(value)})")
        print("    Or grant the scope once:  gh auth refresh -h github.com -s admin:org")
        if not confirm(f"Have you saved {name} at the org?"):
            raise RollAborted(f"{name} not saved; old credential left in place")
        return
    if dry_run:
        print(
            f"  {yellow('dry-run')} would set org secret {name} "
            f"(visibility=selected, repos={REPO_NAME}) = {redact(value)}"
        )
        return
    print(f"  about to set org secret {bold(name)} visibility=selected repos={REPO_NAME}")
    if not confirm("Proceed?"):
        raise RollAborted("cancelled at org secret write")
    p = run(
        [
            "gh", "secret", "set", name,
            "--org", OWNER,
            "--visibility", "selected",
            "--repos", REPO_NAME,
        ],
        stdin_text=value,
    )
    if p.returncode != 0:
        raise RollAborted(f"gh secret set --org {name} failed: {p.stderr.strip()}")
    print(f"  {green('wrote')} org secret {name}")


def confirm_write_landed(
    cred: "Credential", scope: str, before: dt.datetime | None, dry_run: bool
) -> Check:
    """Assert the write moved `updated_at`.

    This does not prove the value is good - that was the verify step, before
    the write. It proves the write happened at all, which `gh secret set`'s
    exit code alone does not distinguish from a no-op against the wrong scope.
    """
    if dry_run:
        return Check(POSITIVE, "secret write confirmed", True, "skipped in dry-run")
    if scope == ORG_SCOPE and "admin:org" not in gh_scopes():
        return Check(
            POSITIVE, "secret write confirmed", True,
            "org scope not readable from here; confirmed interactively instead",
        )
    listing = list_repo_secrets() if scope == REPO_SCOPE else list_org_secrets()
    if listing is None or cred.name not in listing:
        return Check(POSITIVE, "secret write confirmed", False, "secret not present after write")
    after = listing[cred.name]
    if before is not None and after <= before:
        return Check(
            POSITIVE, "secret write confirmed", False,
            f"updated_at did not move (still {after.isoformat()})",
        )
    return Check(POSITIVE, "secret write confirmed", True, f"updated_at now {after.isoformat()}")


# --------------------------------------------------------------------------
# Prompts
# --------------------------------------------------------------------------


def confirm(prompt: str) -> bool:
    if not sys.stdin.isatty():
        raise RollAborted(f"needs an answer to {prompt!r} but stdin is not a terminal")
    return input(f"{prompt} [y/N] ").strip().lower() in {"y", "yes"}


def prompt_secret(label: str) -> str:
    """Read a credential without echoing it and without leaving it in history."""
    if not sys.stdin.isatty():
        raise RollAborted(
            f"{label!r} needs a terminal - this provider has no create API, so "
            "the value has to be pasted by hand"
        )
    value = getpass.getpass(f"{label} (input hidden): ").strip()
    if not value:
        raise RollAborted("empty value")
    return value


def open_url_note(url: str, steps: Iterable[str]) -> None:
    print(f"\n  {bold('Open:')} {url}")
    for s in steps:
        print(f"    - {s}")
    print()


# --------------------------------------------------------------------------
# Drivers
#
# A driver is the per-provider half: how to produce a new credential, how to
# prove it works before anything depends on it, and how to retire the old one.
# The mint/verify/write/revoke *ordering* is enforced by roll(), not here.
# --------------------------------------------------------------------------


@dataclass
class Driver:
    automation: str  # "AUTO" | "GUIDED"
    mint: Callable[["Ctx"], str]
    verify: Callable[["Ctx", str], list[Check]]
    revoke: Callable[["Ctx", str], None] | None = None
    # Where the previous credential's identity lives, so revoke can find it.
    snapshot: Callable[["Ctx"], object] | None = None


# ---- Google Cloud API key (PSI_API_KEY) ----------------------------------


def _gcloud_project(ctx: "Ctx") -> str:
    p = run(["gcloud", "config", "get-value", "project"])
    proj = (p.stdout or "").strip()
    if not proj or proj == "(unset)":
        raise RollAborted("no gcloud project configured (gcloud config set project ...)")
    return proj


PSI_SERVICE = "pagespeedonline.googleapis.com"


def psi_snapshot(ctx: "Ctx") -> list[str]:
    """Resource names of the existing PSI-restricted keys, so we can delete them after."""
    p = run([
        "gcloud", "services", "api-keys", "list",
        "--project", _gcloud_project(ctx), "--format", "json",
    ])
    if p.returncode != 0:
        return []
    keys = json.loads(p.stdout or "[]")
    out = []
    for k in keys:
        targets = (k.get("restrictions") or {}).get("apiTargets") or []
        if any(t.get("service") == PSI_SERVICE for t in targets):
            out.append(k["name"])
    return out


def psi_mint(ctx: "Ctx") -> str:
    project = _gcloud_project(ctx)
    display = f"GitHub Actions PSI (rotated {TODAY.isoformat()})"
    print(f"  creating API key in {project}, restricted to {PSI_SERVICE}")
    if ctx.dry_run:
        raise RollAborted("dry-run: not creating a real Google API key")
    p = run([
        "gcloud", "services", "api-keys", "create",
        "--project", project,
        "--display-name", display,
        f"--api-target=service={PSI_SERVICE}",
        "--format", "json",
    ])
    if p.returncode != 0:
        raise RollAborted(f"api-keys create failed: {p.stderr.strip()}")
    created = json.loads(p.stdout or "{}")
    # gcloud returns the long-running-operation envelope; the key is in .response
    key_res = created.get("response", created).get("name") or created.get("name")
    if not key_res:
        raise RollAborted("could not find key resource name in gcloud output")
    ctx.scratch["psi_new_resource"] = key_res
    p2 = run([
        "gcloud", "services", "api-keys", "get-key-string", key_res,
        "--format", "value(keyString)",
    ])
    if p2.returncode != 0:
        raise RollAborted(f"get-key-string failed: {p2.stderr.strip()}")
    return p2.stdout.strip()


def psi_verify(ctx: "Ctx", key: str) -> list[Check]:
    base = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    target = urllib.parse.quote("https://csoh.org/", safe="")

    # A brand-new key takes up to a couple of minutes to propagate. Retrying
    # only the positive check is deliberate: a *negative* control that needed
    # retries would be indistinguishable from propagation lag.
    positive = None
    for attempt in range(6):
        r = http("GET", f"{base}?url={target}&key={urllib.parse.quote(key)}&strategy=mobile", timeout=90)
        if r.status == 200:
            positive = Check(POSITIVE, "PSI v5 runPagespeed with new key", True, "HTTP 200")
            break
        positive = Check(
            POSITIVE, "PSI v5 runPagespeed with new key", False,
            f"HTTP {r.status}: {r.body[:180]}",
        )
        if attempt < 5:
            print(f"    {dim(f'key not live yet (HTTP {r.status}); retrying in 20s')}")
            time.sleep(20)
    checks = [positive]

    bad = http("GET", f"{base}?url={target}&key={urllib.parse.quote(corrupt(key))}&strategy=mobile", timeout=60)
    checks.append(Check(
        NEGATIVE, "corrupted key is rejected", bad.status in (400, 403),
        f"HTTP {bad.status} (a 200 here would mean the probe proves nothing)",
    ))

    # The restriction is the whole reason this key is low-sensitivity. If the
    # new key can reach a second Google API, it was created unrestricted.
    other = http(
        "GET",
        "https://www.googleapis.com/customsearch/v1?q=x&cx=x&key=" + urllib.parse.quote(key),
        timeout=30,
    )
    blocked = other.status in (403, 400) and (
        "API_KEY_SERVICE_BLOCKED" in other.body or "blocked" in other.body.lower()
        or other.status == 403
    )
    checks.append(Check(
        SCOPE, "key is restricted to PageSpeed Insights only", blocked,
        f"customsearch returned HTTP {other.status}",
    ))
    return checks


def psi_revoke(ctx: "Ctx", _value: str) -> None:
    old = [k for k in (ctx.scratch.get("psi_old") or []) if k != ctx.scratch.get("psi_new_resource")]
    if not old:
        print("  no previous PSI key found to revoke")
        return
    for res in old:
        print(f"  deleting old key {res.rsplit('/', 1)[-1]}")
        if ctx.dry_run:
            continue
        p = run(["gcloud", "services", "api-keys", "delete", res, "--quiet"])
        if p.returncode != 0:
            print(f"  {yellow('warn')} delete failed: {p.stderr.strip()}")
        else:
            print(f"  {green('revoked')} {res.rsplit('/', 1)[-1]}")


# ---- Cloudflare cache-purge token ----------------------------------------

CF_API = "https://api.cloudflare.com/client/v4"
CF_PURGE_PROBE = "https://csoh.org/robots.txt"


def _cf_zone(ctx: "Ctx") -> str:
    zone = ctx.env.get("TF_VAR_zone_id")
    if not zone:
        p = run(["gh", "variable", "get", "CLOUDFLARE_ZONE_ID", "--repo", NWO])
        zone = (p.stdout or "").strip()
    if not zone:
        raise RollAborted("no zone id (set TF_VAR_zone_id in .env)")
    return zone


def cf_snapshot(ctx: "Ctx") -> list[dict]:
    """List existing user tokens - only possible with a meta-token.

    The purge token itself deliberately cannot do this: its single permission
    is Zone -> Cache Purge. Managing tokens needs User -> API Tokens -> Edit,
    which the Terraform token in .env does not carry either (verified: 9109).
    """
    meta = ctx.env.get("CLOUDFLARE_TOKENS_API_TOKEN")
    if not meta:
        return []
    r = http("GET", f"{CF_API}/user/tokens", headers={"Authorization": f"Bearer {meta}"})
    if r.status != 200:
        return []
    return r.json().get("result") or []


def cf_mint(ctx: "Ctx") -> str:
    meta = ctx.env.get("CLOUDFLARE_TOKENS_API_TOKEN")
    zone = _cf_zone(ctx)

    if meta:
        r = http("GET", f"{CF_API}/user/tokens/permission_groups",
                 headers={"Authorization": f"Bearer {meta}"})
        groups = r.json().get("result") or []
        purge = next((g for g in groups if g.get("name") == "Cache Purge"), None)
        if purge and not ctx.dry_run:
            body = {
                "name": f"csoh-org cache purge (rotated {TODAY.isoformat()})",
                "policies": [{
                    "effect": "allow",
                    "permission_groups": [{"id": purge["id"], "name": "Cache Purge"}],
                    "resources": {f"com.cloudflare.api.account.zone.{zone}": "*"},
                }],
            }
            cr = http("POST", f"{CF_API}/user/tokens",
                      headers={"Authorization": f"Bearer {meta}"}, body=body)
            if cr.status == 200 and cr.json().get("success"):
                result = cr.json()["result"]
                ctx.scratch["cf_new_id"] = result["id"]
                return result["value"]
            print(f"  {yellow('warn')} automated create failed "
                  f"(HTTP {cr.status}); falling back to guided")

    open_url_note(
        "https://dash.cloudflare.com/profile/api-tokens",
        [
            "Create Token -> Custom token",
            "Permissions: exactly one row - Zone / Cache Purge / Purge",
            f"Zone Resources: Include / Specific zone / {REPO_NAME}",
            "Create a NEW token. Do NOT use 'Roll' on the existing one - rolling",
            "  invalidates the value CI holds before the new one is verified,",
            "  and Actions secrets are write-only so you cannot read it back.",
        ],
    )
    return prompt_secret("Paste the new Cloudflare token")


def cf_verify(ctx: "Ctx", token: str) -> list[Check]:
    zone = _cf_zone(ctx)
    auth = {"Authorization": f"Bearer {token}"}
    checks: list[Check] = []

    # /user/tokens/verify reports "active" regardless of scope - CLAUDE.md
    # records this specifically. So the positive check is the real operation:
    # purge one harmless file, which is exactly what deploy.yml does.
    r = http("POST", f"{CF_API}/zones/{zone}/purge_cache",
             headers=auth, body={"files": [CF_PURGE_PROBE]})
    ok = r.status == 200 and r.json().get("success") is True
    checks.append(Check(
        POSITIVE, "purge_cache on csoh.org succeeds", ok,
        f"HTTP {r.status} purging {CF_PURGE_PROBE}"
        + ("" if ok else f": {r.body[:180]}"),
    ))

    bad = http("POST", f"{CF_API}/zones/{zone}/purge_cache",
               headers={"Authorization": f"Bearer {corrupt(token)}"},
               body={"files": [CF_PURGE_PROBE]})
    checks.append(Check(
        NEGATIVE, "corrupted token cannot purge", bad.status in (400, 401, 403),
        f"HTTP {bad.status}",
    ))

    # The narrowness is the point. A token that can also read DNS is not the
    # token SECURITY.md describes, and shipping it silently widens the deploy
    # path's blast radius from "cold the cache" to "read the zone".
    dns = http("GET", f"{CF_API}/zones/{zone}/dns_records?per_page=1", headers=auth)
    checks.append(Check(
        SCOPE, "token cannot read DNS (Cache Purge only)", dns.status in (401, 403),
        f"HTTP {dns.status}" + ("" if dns.status in (401, 403) else " - TOKEN IS OVER-SCOPED"),
    ))
    return checks


def cf_revoke(ctx: "Ctx", _value: str) -> None:
    meta = ctx.env.get("CLOUDFLARE_TOKENS_API_TOKEN")
    old = [t for t in (ctx.scratch.get("cf_old") or [])
           if t.get("id") != ctx.scratch.get("cf_new_id")
           and "purge" in (t.get("name") or "").lower()]
    if meta and old:
        for t in old:
            print(f"  deleting old token {t['name']!r}")
            if ctx.dry_run:
                continue
            r = http("DELETE", f"{CF_API}/user/tokens/{t['id']}",
                     headers={"Authorization": f"Bearer {meta}"})
            print(f"  {green('revoked') if r.status == 200 else yellow('warn')} HTTP {r.status}")
        return
    print(f"  {yellow('manual step')} delete the OLD purge token now that the new one is live:")
    print("    https://dash.cloudflare.com/profile/api-tokens -> the previous "
          "'cache purge' token -> Delete")


# ---- Claude Code OAuth token ---------------------------------------------


def claude_mint(ctx: "Ctx") -> str:
    print("  `claude setup-token` opens a browser and prints a token at the end.")
    if confirm("  Run it now?"):
        subprocess.run(["claude", "setup-token"], check=False)
    else:
        print("  Run `claude setup-token` in another terminal, then paste below.")
    return prompt_secret("Paste the new CLAUDE_CODE_OAUTH_TOKEN")


def claude_verify(ctx: "Ctx", token: str) -> list[Check]:
    """Prove the token buys model access - and that the probe isn't cheating.

    The negative control matters more here than anywhere else in this file. If
    `claude` falls through to the logged-in local session when the supplied
    token is bad, then the positive check passes for *any* string and this
    whole verification is theatre. So a corrupted token must fail; if it does
    not, the result is discarded.
    """
    def ask(value: str) -> tuple[bool, str]:
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        env["CLAUDE_CODE_OAUTH_TOKEN"] = value
        try:
            p = subprocess.run(
                ["claude", "-p", "Reply with exactly: ROTATION_OK"],
                text=True, capture_output=True, env=env, timeout=120,
            )
        except subprocess.TimeoutExpired:
            return False, "timed out after 120s"
        out = (p.stdout or "") + (p.stderr or "")
        return ("ROTATION_OK" in out and p.returncode == 0), out.strip()[:180]

    good_ok, good_detail = ask(token)
    bad_ok, bad_detail = ask(corrupt(token))
    return [
        Check(POSITIVE, "new token completes a model request", good_ok, good_detail),
        Check(
            NEGATIVE, "corrupted token is rejected", not bad_ok,
            "corrupted token also succeeded - `claude` is falling back to local "
            "session auth, so the positive check proves nothing"
            if bad_ok else f"rejected: {bad_detail}",
        ),
    ]


def claude_revoke(ctx: "Ctx", _v: str) -> None:
    print(f"  {yellow('manual step')} revoke the previous token at "
          "https://claude.ai/settings (it is not exposed by an API).")


# ---- GitHub App private key ----------------------------------------------


def app_jwt(pem_path: Path, client_id: str) -> str:
    """RS256 JWT signed with openssl, so this file needs no crypto dependency."""
    def b64(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    now = int(time.time())
    header = b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    payload = b64(json.dumps({"iat": now - 60, "exp": now + 540, "iss": client_id}).encode())
    signing_input = f"{header}.{payload}".encode()

    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(signing_input)
        tmp = tf.name
    try:
        p = subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", str(pem_path), tmp],
            capture_output=True, check=False,
        )
        if p.returncode != 0:
            raise RollAborted(f"openssl could not sign with that key: "
                              f"{p.stderr.decode(errors='replace').strip()}")
        return f"{header}.{payload}.{b64(p.stdout)}"
    finally:
        os.unlink(tmp)


def appkey_mint(ctx: "Ctx") -> str:
    open_url_note(
        f"https://github.com/organizations/{OWNER}/settings/apps/{APP_SLUG}",
        [
            "Scroll to 'Private keys' -> 'Generate a private key'",
            "GitHub downloads a .pem - it is the only time you can get it",
            "Do NOT delete the old key yet; this script revokes after verifying",
        ],
    )
    if not sys.stdin.isatty():
        raise RollAborted("needs a terminal to accept the .pem path")
    raw = input("  Path to the downloaded .pem: ").strip().strip("'\"")
    path = Path(raw).expanduser()
    if not path.is_file():
        raise RollAborted(f"no such file: {path}")
    pem = path.read_text()
    if "PRIVATE KEY" not in pem:
        raise RollAborted(f"{path} does not look like a PEM private key")
    ctx.scratch["app_pem_path"] = path
    return pem


def appkey_verify(ctx: "Ctx", pem: str) -> list[Check]:
    """Do exactly what every workflow's mint step does, and assert the result.

    `actions/create-github-app-token` is opaque when it fails; a wrong key
    surfaces as a red X in a scheduled run days later. This walks the same
    path - sign a JWT, identify the App, find the installation, mint an
    installation token - and checks the permissions that CI actually relies on.
    """
    client_id = ctx.env.get("CSOH_CI_CLIENT_ID") or ctx.scratch.get("client_id")
    if not client_id:
        client_id = input("  CSOH_CI_CLIENT_ID (the Iv23.* value, not secret): ").strip()
        ctx.scratch["client_id"] = client_id

    with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False) as tf:
        tf.write(pem)
        pem_tmp = Path(tf.name)
    os.chmod(pem_tmp, 0o600)

    checks: list[Check] = []
    try:
        jwt = app_jwt(pem_tmp, client_id)
        gh_hdr = {"Accept": "application/vnd.github+json",
                  "X-GitHub-Api-Version": "2022-11-28"}

        r = http("GET", "https://api.github.com/app",
                 headers={**gh_hdr, "Authorization": f"Bearer {jwt}"})
        app = r.json()
        checks.append(Check(
            POSITIVE, f"key authenticates as the {APP_SLUG} App",
            r.status == 200 and app.get("slug") == APP_SLUG,
            f"HTTP {r.status}, slug={app.get('slug')!r}",
        ))

        bad_jwt = jwt[:-8] + "AAAAAAAA"
        rb = http("GET", "https://api.github.com/app",
                  headers={**gh_hdr, "Authorization": f"Bearer {bad_jwt}"})
        checks.append(Check(
            NEGATIVE, "tampered signature is rejected", rb.status == 401,
            f"HTTP {rb.status}",
        ))

        if r.status == 200:
            ri = http("GET", "https://api.github.com/app/installations",
                      headers={**gh_hdr, "Authorization": f"Bearer {jwt}"})
            installs = ri.json() if isinstance(ri.json(), list) else []
            inst = next(
                (i for i in installs if (i.get("account") or {}).get("login") == OWNER),
                None,
            )
            if not inst:
                checks.append(Check(POSITIVE, "installation on " + OWNER, False,
                                    f"HTTP {ri.status}, no matching installation"))
            else:
                rt = http("POST",
                          f"https://api.github.com/app/installations/{inst['id']}/access_tokens",
                          headers={**gh_hdr, "Authorization": f"Bearer {jwt}"})
                perms = (rt.json() or {}).get("permissions") or {}
                checks.append(Check(
                    POSITIVE, "mints an installation token", rt.status == 201,
                    f"HTTP {rt.status}",
                ))
                needed = {"contents": "write", "pull_requests": "write"}
                got = {k: perms.get(k) for k in needed}
                checks.append(Check(
                    SCOPE, "installation grants contents+pull_requests write",
                    got == needed, f"permissions: {got}",
                ))
    finally:
        os.unlink(pem_tmp)
    return checks


def appkey_revoke(ctx: "Ctx", _v: str) -> None:
    print(f"  {yellow('manual step')} the new key is live; now delete the OLD one:")
    print(f"    https://github.com/organizations/{OWNER}/settings/apps/{APP_SLUG}"
          " -> Private keys -> Delete (the one you did NOT just create)")
    pem = ctx.scratch.get("app_pem_path")
    if pem:
        print(f"  {yellow('also')} shred the downloaded file: {pem}")


# ---- CSOH_PAT ------------------------------------------------------------


def pat_mint(ctx: "Ctx") -> str:
    open_url_note(
        "https://github.com/settings/personal-access-tokens/new",
        [
            f"Resource owner: {OWNER}",
            f"Repository access: Only select repositories -> {REPO_NAME}",
            "Repository permissions: Pull requests -> Read and write. Nothing else.",
            "Expiration: 6 months (or less)",
            "This token exists only to approve PRs the App opened, because",
            "  GitHub's auto-merge scheduler ignores ruleset bypass.",
        ],
    )
    return prompt_secret("Paste the new CSOH_PAT")


def pat_verify(ctx: "Ctx", token: str) -> list[Check]:
    hdr = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}",
           "X-GitHub-Api-Version": "2022-11-28"}
    checks: list[Check] = []

    r = http("GET", "https://api.github.com/user", headers=hdr)
    checks.append(Check(POSITIVE, "token authenticates", r.status == 200,
                        f"HTTP {r.status}, login={r.json().get('login')!r}"))

    rp = http("GET", f"https://api.github.com/repos/{NWO}/pulls?per_page=1", headers=hdr)
    checks.append(Check(POSITIVE, "can read pull requests", rp.status == 200,
                        f"HTTP {rp.status}"))

    rb = http("GET", "https://api.github.com/user",
              headers={**hdr, "Authorization": f"Bearer {corrupt(token)}"})
    checks.append(Check(NEGATIVE, "corrupted token is rejected", rb.status == 401,
                        f"HTTP {rb.status}"))

    # SECURITY.md's claim for this PAT is "even if it leaks, all an attacker can
    # do is approve PRs". Reading Actions secrets requires admin, so a 200 here
    # would mean the fine-grained scoping was not applied and the claim is false.
    rs = http("GET", f"https://api.github.com/repos/{NWO}/actions/secrets", headers=hdr)
    checks.append(Check(
        SCOPE, "cannot read Actions secrets (PR-only scope)", rs.status in (401, 403, 404),
        f"HTTP {rs.status}" + ("" if rs.status in (401, 403, 404) else " - PAT IS OVER-SCOPED"),
    ))
    return checks


def pat_revoke(ctx: "Ctx", _v: str) -> None:
    print(f"  {yellow('manual step')} delete the previous CSOH_PAT at "
          "https://github.com/settings/personal-access-tokens")


# ---- Zoom Server-to-Server OAuth ----------------------------------------


def zoom_mint(ctx: "Ctx") -> str:
    open_url_note(
        "https://marketplace.zoom.us/user/build",
        [
            "Open the Server-to-Server OAuth app used by publish-recaps.yml",
            "App Credentials -> Regenerate (Client Secret)",
            f"{bold('Note:')} Zoom invalidates the old secret immediately, so CI is",
            "  broken from this moment until the new value is written. That is",
            "  a Zoom constraint, not a choice - keep the window short.",
            "Account ID and Client ID do not change.",
        ],
    )
    return prompt_secret("Paste the new ZOOM_CLIENT_SECRET")


def zoom_verify(ctx: "Ctx", secret: str) -> list[Check]:
    account = ctx.env.get("ZOOM_ACCOUNT_ID")
    client = ctx.env.get("ZOOM_CLIENT_ID")
    if not (account and client):
        return [Check(POSITIVE, "zoom identifiers present", False,
                      "ZOOM_ACCOUNT_ID / ZOOM_CLIENT_ID missing from .env")]

    def grant(sec: str) -> Response:
        basic = base64.b64encode(f"{client}:{sec}".encode()).decode()
        return http(
            "POST",
            "https://zoom.us/oauth/token?grant_type=account_credentials"
            f"&account_id={urllib.parse.quote(account)}",
            headers={"Authorization": f"Basic {basic}"},
        )

    checks: list[Check] = []
    g = grant(secret)
    token = g.json().get("access_token")
    checks.append(Check(POSITIVE, "S2S grant returns an access token",
                        g.status == 200 and bool(token), f"HTTP {g.status}"))

    gb = grant(corrupt(secret))
    checks.append(Check(NEGATIVE, "corrupted secret is rejected",
                        gb.status in (400, 401), f"HTTP {gb.status}"))

    if token:
        # The grant alone only proves the credential exists. Call the exact
        # endpoint tools/fetch_zoom_transcript.py uses - /users/{id}/recordings
        # - because the S2S app is scoped per-endpoint and a token can grant
        # cleanly while being useless to the pipeline. (/users/me is NOT a
        # valid probe here: this app has no user:read scope, so it 400s even
        # with a perfectly good secret.)
        u = http("GET", "https://api.zoom.us/v2/users/me/recordings?page_size=1",
                 headers={"Authorization": f"Bearer {token}"})
        scopes = g.json().get("scope", "")
        has_rec = "cloud_recording:read" in scopes and "meeting:read" in scopes
        checks.append(Check(
            POSITIVE, "can list recordings (what fetch_zoom_transcript.py calls)",
            u.status == 200, f"HTTP {u.status}"
            + ("" if u.status == 200 else f": {u.json().get('message', u.body[:120])}"),
        ))
        checks.append(Check(
            SCOPE, "grant carries the recording/meeting read scopes", has_rec,
            "publish-recaps.yml needs cloud_recording:read + meeting:read",
        ))
    return checks


# --------------------------------------------------------------------------
# Registry
# --------------------------------------------------------------------------


@dataclass
class Credential:
    name: str
    scope: str
    sensitivity: str
    cadence_days: int | None  # None = no scheduled rotation
    purpose: str
    driver: Driver | None = None
    env_keys: list[str] = field(default_factory=list)
    note: str = ""

    @property
    def rotatable(self) -> bool:
        return self.driver is not None


REGISTRY: list[Credential] = [
    Credential(
        name="CSOH_CI_PRIVATE_KEY",
        scope=ORG_SCOPE,
        sensitivity="high",
        cadence_days=365,
        purpose="GitHub App RSA key; every workflow mints ~1h installation tokens from it",
        driver=Driver("GUIDED", appkey_mint, appkey_verify, appkey_revoke),
        note="csoh-ci is on the Main ruleset bypass list, so a leak is a direct push to main",
    ),
    Credential(
        name="CSOH_PAT",
        scope=ORG_SCOPE,
        sensitivity="medium",
        cadence_days=270,
        purpose="Approves App-opened PRs so auto-merge can fire (bypass does not cover it)",
        driver=Driver("GUIDED", pat_mint, pat_verify, pat_revoke),
    ),
    Credential(
        name="CLOUDFLARE_API_TOKEN",
        scope=REPO_SCOPE,
        sensitivity="medium",
        cadence_days=270,
        purpose="deploy.yml purge-cloudflare; the only long-lived credential in the deploy path",
        driver=Driver("AUTO", cf_mint, cf_verify, cf_revoke, snapshot=cf_snapshot),
        note="Cloudflare has no OIDC. Set CLOUDFLARE_TOKENS_API_TOKEN in .env "
             "(User -> API Tokens -> Edit) to make this fully automatic.",
    ),
    Credential(
        name="ZOOM_CLIENT_SECRET",
        scope=REPO_SCOPE,
        sensitivity="medium",
        cadence_days=270,
        purpose="publish-recaps.yml pulls meeting summaries via Server-to-Server OAuth",
        driver=Driver("GUIDED", zoom_mint, zoom_verify),
        env_keys=["ZOOM_CLIENT_SECRET"],
        note="Regenerating invalidates the old secret instantly - CI is down until written",
    ),
    Credential(
        name="CLAUDE_CODE_OAUTH_TOKEN",
        scope=REPO_SCOPE,
        sensitivity="medium",
        cadence_days=365,
        purpose="update-resources.yml model auth (subscription quota, no repo access)",
        driver=Driver("GUIDED", claude_mint, claude_verify, claude_revoke),
    ),
    Credential(
        name="PSI_API_KEY",
        scope=REPO_SCOPE,
        sensitivity="low",
        cadence_days=365,
        purpose="check-pagespeed.yml; restricted to the PageSpeed Insights API alone",
        driver=Driver("AUTO", psi_mint, psi_verify, psi_revoke, snapshot=psi_snapshot),
    ),
    # Identifiers, listed so the audit does not flag them as unknown. None of
    # these is a credential; rotating them means reconfiguring the provider.
    Credential("CSOH_CI_CLIENT_ID", ORG_SCOPE, "identifier", None,
               "GitHub App Client ID (Iv23.*) - changes only if the App is replaced"),
    Credential("ZOOM_ACCOUNT_ID", REPO_SCOPE, "identifier", None,
               "Zoom account id - fixed for the account", env_keys=["ZOOM_ACCOUNT_ID"]),
    Credential("ZOOM_CLIENT_ID", REPO_SCOPE, "identifier", None,
               "Zoom S2S app client id - changes only if the app is recreated",
               env_keys=["ZOOM_CLIENT_ID"]),
]

BY_NAME = {c.name: c for c in REGISTRY}


# --------------------------------------------------------------------------
# Context
# --------------------------------------------------------------------------


@dataclass
class Ctx:
    env: dict[str, str]
    dry_run: bool = False
    scratch: dict = field(default_factory=dict)


# --------------------------------------------------------------------------
# Workflow scanning
# --------------------------------------------------------------------------


def referenced_secrets() -> dict[str, set[str]]:
    """Map secret name -> workflow files that consume it.

    Derived, never hand-listed. SECURITY.md's inventory drifted precisely
    because it was maintained by hand; this cannot.

    Full-line YAML comments are skipped: six workflows explain the
    `${{ secrets.NAME }}` syntax in prose, and a naive grep counts NAME as a
    secret.
    """
    found: dict[str, set[str]] = {}
    pattern = re.compile(r"\$\{\{\s*secrets\.([A-Z0-9_]+)\s*\}\}")
    for wf in sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml")):
        for line in wf.read_text().splitlines():
            if line.lstrip().startswith("#"):
                continue
            for name in pattern.findall(line):
                if name == "NAME":  # the placeholder used in documentation
                    continue
                found.setdefault(name, set()).add(wf.name)
    return found


# --------------------------------------------------------------------------
# audit
# --------------------------------------------------------------------------


def age_days(when: dt.datetime | None) -> int | None:
    if when is None:
        return None
    return (dt.datetime.now(dt.timezone.utc) - when).days


def cmd_audit(args) -> int:
    refs = referenced_secrets()
    repo_secrets = list_repo_secrets()
    org_secrets = list_org_secrets()
    org_readable = org_secrets is not None
    repo_readable = repo_secrets is not None

    errors: list[str] = []
    warnings: list[str] = []

    heading("Inventory")
    print(f"{'SECRET':<26} {'SCOPE':<5} {'AGE':>9}  {'DUE':<9} CONSUMED BY")
    for cred in REGISTRY:
        scope = actual_scope(cred, repo_secrets)
        if scope != cred.scope:
            warnings.append(
                f"{cred.name} is declared {cred.scope}-level in the registry but is "
                f"set at {scope} level - a {scope}-level secret shadows the other, "
                "so update the registry"
            )
        listing = repo_secrets if scope == REPO_SCOPE else org_secrets
        updated = (listing or {}).get(cred.name)
        age = age_days(updated)

        # "unreadable" and "absent" must never render the same. Collapsing them
        # is how a gate reports success for a check it never performed.
        if scope == ORG_SCOPE and not org_readable:
            age_s, due_s = dim("unknown"), dim("-")
        elif scope == REPO_SCOPE and not repo_readable:
            age_s, due_s = dim("unknown"), dim("-")
        elif age is None:
            age_s, due_s = red("absent"), "-"
        else:
            age_s = f"{age}d"
            if cred.cadence_days is None:
                due_s = dim("n/a")
            elif age >= cred.cadence_days:
                due_s = red("OVERDUE")
            elif age >= cred.cadence_days * 0.85:
                due_s = yellow("soon")
            else:
                due_s = green("ok")

        consumers = sorted(refs.get(cred.name, set()))
        consumed = ", ".join(c.replace(".yml", "") for c in consumers) or dim("nothing")
        print(f"{cred.name:<26} {scope:<5} {age_s:>9}  {due_s:<9} {consumed}")

        if cred.cadence_days is not None and age is not None and age >= cred.cadence_days:
            errors.append(f"{cred.name} is {age}d old (cadence {cred.cadence_days}d)")
        if not consumers:
            warnings.append(
                f"{cred.name} is in the registry but no workflow references it"
            )
        if (
            scope == REPO_SCOPE
            and repo_secrets is not None
            and cred.name not in repo_secrets
            and consumers
        ):
            errors.append(f"{cred.name} is referenced by {consumed} but does not exist")

    heading("Drift")
    known = set(BY_NAME) | AUTO_PROVIDED

    unknown = sorted(set(refs) - known)
    for name in unknown:
        errors.append(
            f"{name} is used by {', '.join(sorted(refs[name]))} but is not in the "
            "registry - it has no rotation plan"
        )

    if repo_secrets is not None:
        orphans = sorted(set(repo_secrets) - set(refs) - AUTO_PROVIDED)
        for name in orphans:
            errors.append(
                f"{name} exists as a repo secret but no workflow reads it "
                f"(last updated {repo_secrets[name].date()}) - delete it"
            )
    if org_readable:
        org_orphans = sorted(set(org_secrets) - set(refs))
        for name in org_orphans:
            warnings.append(f"{name} exists as an org secret but this repo does not read it")

    if not errors and not warnings:
        print(green("  no drift"))
    for w in warnings:
        print(f"  {yellow('WARN')} {w}")
    for e in errors:
        print(f"  {red('ERROR')} {e}")

    # ----------------------------------------------------------------------
    # Coverage
    #
    # Three of the five checks below need the Actions secrets API, and the
    # caller often cannot reach it: `GITHUB_TOKEN` has no `secrets` permission
    # at all (it is not one of the keys `permissions:` accepts), and the local
    # gh token has no `admin:org`. Those checks then do not run.
    #
    # A gate that skips checks silently is worse than one that does not exist,
    # because the green tick is read as "all of this was verified." So the run
    # states which of its checks were actually enforced and which were not, and
    # why - the same reason `check_edge_headers.py` asserts against the live
    # edge instead of trusting a clean `terraform plan`.
    # ----------------------------------------------------------------------
    heading("Coverage")
    no_repo = "needs the Actions secrets API (GITHUB_TOKEN cannot read it)"
    no_org = "needs admin:org"
    coverage = [
        ("referenced secret has a registry entry", True, ""),
        ("registry entry is consumed by a workflow", True, ""),
        ("repo secret exists / is not orphaned", repo_readable, no_repo),
        ("repo secret is within its rotation cadence", repo_readable, no_repo),
        ("org secret age and orphan status", org_readable, no_org),
    ]
    for label, enforced, why in coverage:
        if enforced:
            print(f"  {green('enforced')}     {label}")
        else:
            print(f"  {yellow('not checked')}  {label} - {why}")

    heading("Summary")
    print(f"  {len(REGISTRY)} registered, {len(refs)} referenced in "
          f"{len(list(WORKFLOW_DIR.glob('*.yml')))} workflows")
    print(f"  {len(errors)} error(s), {len(warnings)} warning(s), "
          f"{sum(1 for _, e, _ in coverage if not e)} check(s) not run")
    if errors and args.check:
        return 1
    return 0


def cmd_list(args) -> int:
    heading("Rotation registry")
    for c in REGISTRY:
        auto = c.driver.automation if c.driver else "n/a"
        cadence = f"{c.cadence_days}d" if c.cadence_days else "no cadence"
        print(f"\n{bold(c.name)}  [{c.scope}] [{c.sensitivity}] [{auto}] [{cadence}]")
        print(f"  {c.purpose}")
        if c.env_keys:
            print(dim(f"  mirrored into .env: {', '.join(c.env_keys)}"))
        if c.note:
            print(dim(f"  note: {c.note}"))
    return 0


# --------------------------------------------------------------------------
# verify (no rotation)
# --------------------------------------------------------------------------


def cmd_verify(args) -> int:
    """Probe credentials we hold a copy of locally.

    This can only cover what is in .env. Actions secrets are write-only - there
    is no API that returns a stored value - so a green `verify` says nothing
    about what CI holds. That distinction is the point: verification of the
    value CI will use happens inside `roll`, before the write.
    """
    ctx = Ctx(env={**read_env_file(), **os.environ})
    targets = args.names or [c.name for c in REGISTRY if c.env_keys and c.driver]
    rc = 0
    for name in targets:
        cred = BY_NAME.get(name)
        if not cred or not cred.driver:
            print(f"{red('skip')} {name}: not a rotatable credential")
            continue
        local = next((k for k in cred.env_keys if ctx.env.get(k)), None)
        if not local:
            print(f"{dim('skip')} {name}: no local copy in .env to test")
            continue
        heading(f"verify {name}")
        if not report(cred.driver.verify(ctx, ctx.env[local])):
            rc = 1
    return rc


# --------------------------------------------------------------------------
# roll
# --------------------------------------------------------------------------


def roll_one(cred: Credential, ctx: Ctx) -> bool:
    repo_secrets = list_repo_secrets()
    scope = actual_scope(cred, repo_secrets)
    heading(f"roll {cred.name}  [{scope}] [{cred.driver.automation}]")
    print(f"  {cred.purpose}")
    if scope != cred.scope:
        print(f"  {yellow('note')} registry says {cred.scope}-level, but it is set at "
              f"{scope} level - writing to {scope}, which is what CI reads")
    if cred.note:
        print(f"  {yellow('note')} {cred.note}")

    listing = repo_secrets if scope == REPO_SCOPE else list_org_secrets()
    before = (listing or {}).get(cred.name)

    if cred.driver.snapshot:
        key = "psi_old" if cred.name == "PSI_API_KEY" else "cf_old"
        ctx.scratch[key] = cred.driver.snapshot(ctx)

    # 1. mint
    print(f"\n{bold('1. mint')}")
    value = cred.driver.mint(ctx)
    print(f"  new value: {redact(value)}")

    # 2. verify - before anything depends on it
    print(f"\n{bold('2. verify')}")
    checks = cred.driver.verify(ctx, value)
    if not report(checks):
        failed = [c for c in checks if not c.ok]
        if any(c.kind == SCOPE for c in failed):
            print(red("\n  ABORT: the new credential is not scoped the way it should be."))
            print(red("  Nothing was written. The old credential is still live."))
        elif any(c.kind == NEGATIVE for c in failed):
            print(red("\n  ABORT: the negative control passed when it should have failed."))
            print(red("  The probe cannot tell a good credential from a bad one, so the"))
            print(red("  positive result is meaningless. Nothing was written."))
        else:
            print(red("\n  ABORT: the new credential does not work. Nothing was written."))
        return False
    print(green("  all checks passed"))

    # 3. write
    print(f"\n{bold('3. write')}")
    if scope == REPO_SCOPE:
        set_repo_secret(cred.name, value, ctx.dry_run)
    else:
        set_org_secret(cred.name, value, ctx.dry_run)
    for key in cred.env_keys:
        if key in read_env_file():
            if ctx.dry_run:
                print(f"  {yellow('dry-run')} would update .env {key}")
            else:
                write_env_key(key, value)

    # 4. confirm the write landed
    print(f"\n{bold('4. confirm')}")
    landed = confirm_write_landed(cred, scope, before, ctx.dry_run)
    print(landed.render())
    if not landed.ok:
        print(red("  The value was verified but the write did not land. Do not revoke."))
        return False

    # 5. revoke - last, and only now
    print(f"\n{bold('5. revoke old')}")
    if cred.driver.revoke:
        cred.driver.revoke(ctx, value)
    else:
        print(dim("  nothing to revoke (the provider replaced it in place)"))

    print(green(f"\n  {cred.name} rolled."))
    return True


def cmd_roll(args) -> int:
    ctx = Ctx(env={**read_env_file(), **os.environ}, dry_run=args.dry_run)

    if args.all:
        targets = [c for c in REGISTRY if c.rotatable]
    elif args.due:
        repo_secrets = list_repo_secrets() or {}
        org_secrets = list_org_secrets()
        targets = []
        for c in REGISTRY:
            if not c.rotatable or c.cadence_days is None:
                continue
            scope = actual_scope(c, repo_secrets)
            listing = repo_secrets if scope == REPO_SCOPE else (org_secrets or {})
            age = age_days(listing.get(c.name))
            if age is None:
                if scope == ORG_SCOPE and org_secrets is None:
                    print(dim(f"  {c.name}: age unknown (needs admin:org); not auto-selected"))
                continue
            if age >= c.cadence_days:
                targets.append(c)
        if not targets:
            print(green("Nothing is past its rotation cadence."))
            return 0
    else:
        targets = []
        for name in args.names:
            cred = BY_NAME.get(name)
            if not cred:
                print(red(f"unknown credential: {name}"))
                return 2
            if not cred.rotatable:
                print(red(f"{name} is an identifier, not a rotatable credential"))
                return 2
            targets.append(cred)

    if not targets:
        print("Nothing to do. Pass a name, --due or --all.")
        return 2

    print(bold(f"Rolling {len(targets)}: {', '.join(c.name for c in targets)}"))
    if args.dry_run:
        print(yellow("dry-run: nothing will be written or revoked"))

    failures = []
    for cred in targets:
        try:
            if not roll_one(cred, ctx):
                failures.append(cred.name)
        except RollAborted as e:
            print(red(f"\n  ABORT {cred.name}: {e}"))
            print(dim("  Nothing downstream was touched."))
            failures.append(cred.name)
        except KeyboardInterrupt:
            print(red(f"\n  interrupted during {cred.name}"))
            return 130

    heading("Result")
    for cred in targets:
        state = red("failed") if cred.name in failures else green("rolled")
        print(f"  {state}  {cred.name}")
    if failures:
        return 1
    print(dim("\n  Next scheduled run of each consuming workflow is the real "
              "end-to-end proof; the checks above cover the credential itself."))
    return 0


# --------------------------------------------------------------------------


def main() -> int:
    p = argparse.ArgumentParser(
        description="Audit and roll the long-lived credentials used by this repo's workflows.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="cmd")

    pa = sub.add_parser("audit", help="inventory, drift and rotation ages (default)")
    pa.add_argument("--check", action="store_true", help="exit 1 on drift or overdue")
    pa.set_defaults(func=cmd_audit)

    pl = sub.add_parser("list", help="show the registry and how each credential rolls")
    pl.set_defaults(func=cmd_list)

    pv = sub.add_parser("verify", help="probe credentials held locally in .env")
    pv.add_argument("names", nargs="*")
    pv.set_defaults(func=cmd_verify)

    pr = sub.add_parser("roll", help="rotate one or more credentials")
    pr.add_argument("names", nargs="*")
    pr.add_argument("--all", action="store_true", help="every rotatable credential")
    pr.add_argument("--due", action="store_true", help="only those past their cadence")
    pr.add_argument("--dry-run", action="store_true", help="mint and verify, write nothing")
    pr.set_defaults(func=cmd_roll)

    args = p.parse_args()
    if not args.cmd:
        args = p.parse_args(["audit"])
    return args.func(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
