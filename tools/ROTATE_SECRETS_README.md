# `tools/rotate_secrets.py`

Audit and roll every long-lived credential the workflows depend on, from this
machine.

```sh
python3 tools/rotate_secrets.py                  # audit (default)
python3 tools/rotate_secrets.py list             # registry + how each one rolls
python3 tools/rotate_secrets.py verify           # probe what .env holds, roll nothing
python3 tools/rotate_secrets.py roll PSI_API_KEY
python3 tools/rotate_secrets.py roll --due       # everything past its cadence
python3 tools/rotate_secrets.py roll --all
python3 tools/rotate_secrets.py roll CLOUDFLARE_API_TOKEN --dry-run
```

## Why this exists

Nearly everything in the deploy path is already credential-free. All three
clouds mint ~1-hour tokens per run via OIDC, and `csoh-ci` hands out ~1-hour
installation tokens. What remains is a short tail of secrets that genuinely
cannot federate, and that tail never gets rotated because nothing forces it:
no expiry warning, no failing check, no diff. The tokens just get older.

Two specific failure modes shaped the design, both of which have already
happened here.

**The inventory drifts, silently.** `SECURITY.md` carried a row for
`SSH_PRIVATE_KEY` marked "live but unreferenced - flagged for removal, still
present," re-confirmed by hand on 2026-07-26. It is not present; it had already
been deleted. A hand-maintained list of secrets is exactly as trustworthy as
the last time somebody diffed it against the API. This script does that diff on
every run, and fails rather than prints - `CLAUDE.md`'s "a silent count is a
failure mode," applied to the secret inventory.

**A rotation half-lands and nobody notices until CI breaks.** Writing a value
into an Actions secret gives no feedback whatsoever. `gh secret set` succeeds
against a typo, a truncated paste, a token created with the wrong permissions,
or the wrong scope entirely. You find out on the next scheduled run, or on the
next deploy. So nothing is written here until it has been proven against the
live API it will be used on.

## The order is the whole design

```
mint new  ->  verify new  ->  write secret  ->  confirm write  ->  revoke old
```

Every roll stops at the first failure. The window where both the old and new
credential are valid is deliberate: reversing any two of these steps is how you
end up with CI holding something nobody tested.

Step 4 is worth calling out. It re-reads the secret's `updated_at` and asserts
it moved. That does not prove the value is good - step 2 did that, before the
write - it proves the write landed *somewhere CI reads*, which `gh secret set`'s
exit code alone does not distinguish from a successful no-op against the wrong
scope.

## Every verification carries a control

`CLAUDE.md`'s DNS section states the rule this file leans on hardest:

> an instrument that reports "nothing is there" is indistinguishable from a
> broken instrument until you point it at something you know is there.

A check that a token works is worthless if the probe would have passed anyway.
So each credential is probed three ways:

| Kind | Question | Why it is there |
|---|---|---|
| `positive` | Does the exact operation CI performs succeed? | The obvious one, and the only one most tools do. |
| `negative` | Does a deliberately corrupted copy **fail**? | If a broken credential passes, the probe is measuring nothing and the positive result is meaningless. |
| `scope` | Is something the credential should be too narrow for **denied**? | Catches the over-scoped token, which is the failure that never announces itself. |

A credential that passes `positive` but fails `scope` is a worse outcome than a
broken one, and aborts the roll.

The `negative` control earns its place most obviously on
`CLAUDE_CODE_OAUTH_TOKEN`. `claude -p` will happily fall back to your logged-in
local session if the token in the environment is bad - in which case the
positive check passes for literally any string. The corrupted-token run is what
detects that, and if it succeeds the whole verification is discarded.

## What is automated, and what is not

Providers differ in whether they will let a script create a credential, and a
tool that pretends otherwise lies about what it did. Each entry declares its
own honest level:

| Credential | Scope | Level | Notes |
|---|---|---|---|
| `PSI_API_KEY` | repo | `AUTO` | `gcloud services api-keys create/delete`, restriction reproduced. End to end, no browser. |
| `CLOUDFLARE_API_TOKEN` | repo | `AUTO`* | *Only with a meta-token; see below. Otherwise guided. |
| `CSOH_CI_PRIVATE_KEY` | org | `GUIDED` | GitHub has no API to generate an App private key. |
| `CSOH_PAT` | org | `GUIDED` | GitHub has no API to create a fine-grained PAT. |
| `ZOOM_CLIENT_SECRET` | repo | `GUIDED` | Zoom has no API to regenerate an S2S secret. |
| `CLAUDE_CODE_OAUTH_TOKEN` | repo | `GUIDED` | `claude setup-token` is an interactive browser flow. |

`GUIDED` means the script prints the exact URL and the exact settings, takes the
value without echoing it, and then does the verify / write / confirm / revoke
half itself - which is the half that actually goes wrong. It never opens a
browser for you and never submits a form on your behalf.

### Making Cloudflare fully automatic

Cloudflare token CRUD needs **User -> API Tokens -> Edit**, which neither the
purge token (single permission: Zone -> Cache Purge) nor the Terraform token in
`.env` carries - the latter returns `9109 Unauthorized to access requested
resource` on `/user/tokens`, verified. To automate it, create a third token with
that one permission and add it to `.env`:

```sh
CLOUDFLARE_TOKENS_API_TOKEN=<a token with User -> API Tokens -> Edit>
```

With it present, `roll CLOUDFLARE_API_TOKEN` creates the new purge token,
verifies it, writes the secret, and deletes the old one without a browser.
Without it, the script prints the dashboard steps and takes a paste.

Note the deliberate wording in those steps: **create a new token, do not use
"Roll" on the existing one.** Rolling invalidates the value CI holds before the
replacement has been verified, and Actions secrets are write-only so there is no
undo. Same caution as `CLAUDE.md`'s Cloudflare section.

## Org-level secrets need a scope you probably do not have

`CSOH_CI_PRIVATE_KEY`, `CSOH_CI_CLIENT_ID` and `CSOH_PAT` live at the org. The
default `gh` token here carries `gist, read:org, repo, workflow`, so it can
neither read nor write them. The audit reports their age as **`unknown`**, not
as clean - reporting "no problems" about something it cannot see would be the
exact failure this script exists to catch.

To let it write them:

```sh
gh auth refresh -h github.com -s admin:org
```

That broadens a token sitting on your laptop, which is a real tradeoff, so the
script prints the command and does not run it. Without the scope, `roll` still
mints, verifies and revokes; it just hands you the value to paste into the org
settings page, and prints the URL.

## Scope is resolved from the API, not from the registry

A repo-level secret shadows an org-level one of the same name. If the registry
says org and the value is actually set on the repo, writing to the org updates
something nothing reads: `gh secret set` succeeds, the audit looks clean, CI
keeps using the old value. That is the same silent-no-op shape as the inert
Cloudflare ruleset in `CLAUDE.md`.

So the write target follows what the API reports, and `audit` warns when the
registry and reality disagree rather than papering over it. This is not
hypothetical - `ZOOM_*` were first declared org-level here on the strength of
`SECURITY.md`'s description, and are in fact repo-level. The audit caught it.

## The audit is assertive, not informational

`audit --check` exits 1 on any of:

- a secret referenced by a workflow that does not exist
- a secret that exists but no workflow reads (the `SSH_PRIVATE_KEY` class)
- a secret referenced in a workflow but absent from the registry, i.e. with no
  rotation plan
- anything past its cadence

The referenced set is **derived** by scanning `.github/workflows/*.yml` for
`${{ secrets.X }}`, never hand-listed - hand-listing is what drifted in the
first place. Full-line YAML comments are skipped, because six workflows explain
the `${{ secrets.NAME }}` syntax in prose and a naive grep counts `NAME` as a
secret.

### In CI

The `secret-audit` job in `lint.yml` runs `audit --check` on every push and PR.
It enforces less than a local run, and it says so rather than implying
otherwise.

Reading the Actions secrets API needs a `secrets` permission that `GITHUB_TOKEN`
cannot be granted - it is not one of the keys `permissions:` accepts - so on a
runner the script sees no `updated_at` for anything. The cadence check and the
orphaned-secret check therefore do not run in CI. They run locally, where `gh`
is authenticated as a human.

That is why every run prints a **Coverage** section marking each check
`enforced` or `not checked`, with the reason, and why the summary counts checks
not run alongside errors:

```
Coverage
--------
  enforced     referenced secret has a registry entry
  enforced     registry entry is consumed by a workflow
  not checked  repo secret exists / is not orphaned - needs the Actions secrets API (GITHUB_TOKEN cannot read it)
  not checked  repo secret is within its rotation cadence - needs the Actions secrets API (GITHUB_TOKEN cannot read it)
  not checked  org secret age and orphan status - needs admin:org
```

A gate that skips checks silently is worse than no gate: the green tick gets
read as "all of this was verified." Same failure shape as the inert Cloudflare
ruleset and the `'*.html'` path filter in `CLAUDE.md`.

The obvious fix - hand CI a PAT that can read secrets - is deliberately not
taken. Putting a long-lived credential into CI in order to audit long-lived
credentials is a bad trade, and it would immediately be the broadest secret in
the repo. What CI gates is the check that matters most anyway: **a secret added
to a workflow without a rotation plan fails the build.**

## `verify` cannot tell you what CI holds

`verify` probes credentials this machine has a copy of - which means whatever is
in `.env`, today just the Zoom set. Actions secrets are write-only; no API
returns a stored value. A green `verify` therefore says nothing about what CI
holds.

That distinction is the point, not a limitation to work around: verification of
the value CI will actually use happens inside `roll`, in the moment the new
value is in hand and before it is written anywhere.

## Adding a credential

Add a `Credential(...)` to `REGISTRY` with a `Driver` supplying `mint`, `verify`
and optionally `revoke` and `snapshot`. The verify function must return at least
one `positive` and one `negative` check, and a `scope` check wherever the
credential is supposed to be narrow. Then add the matching row to `SECURITY.md`'s
"Repository secrets" and "Rotation guidance" tables - `audit` will tell you when
the registry and the workflows disagree, but it cannot read English.

Until it is registered, `audit --check` fails on it, which is the intended
forcing function.
