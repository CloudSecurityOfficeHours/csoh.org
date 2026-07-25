# Edge Security Header Check

Asserts that the security headers csoh.org actually serves are the ones
[`infra/terraform/cloudflare/rules.tf`](../infra/terraform/cloudflare/rules.tf) declares.

Exits non-zero on any missing or drifted header. It is a CI gate, and it exists because
Terraform cannot enforce this particular resource.

## Quick Start

```bash
python3 tools/check_edge_headers.py                                  # checks https://csoh.org/
python3 tools/check_edge_headers.py --url https://csoh.org/about.html
```

Passing run:

```
Checking 8 security headers from infra/terraform/cloudflare/rules.tf against https://csoh.org/
  ok  Strict-Transport-Security
  ok  X-Content-Type-Options
  ok  X-Frame-Options
  ok  Referrer-Policy
  ok  Permissions-Policy
  ok  Content-Security-Policy
  ok  Cross-Origin-Opener-Policy
  ok  Cross-Origin-Resource-Policy

OK: all 8 headers at https://csoh.org/ match the repo.
```

Standard library only. No `pip install`, no Cloudflare API token: it just does a plain
`GET` and reads the response headers.

## Why this exists: the ruleset in Git is inert

The `cloudflare_ruleset.security_headers` resource (the `csoh-security-headers` ruleset
at Cloudflare) carries this, near the bottom of `rules.tf`:

```hcl
lifecycle {
  ignore_changes = [rules]
}
```

That is a deliberate workaround. The cloudflare **v4** provider returns the rule's
multi-header block in a non-deterministic order, which produces a perpetual
"Provider produced inconsistent result after apply" on every re-apply.

The cost is easy to miss: `rules` is the **only** meaningful attribute of a
`cloudflare_ruleset`. Ignoring it makes the resource inert after creation. You can
tighten the CSP in this repo, run `terraform apply`, get a clean plan, and ship
nothing. The edge keeps the old policy while the repo, the diff, and any reviewer
believe it changed.

That would be bad anywhere. It is worse here, because that ruleset is the **only**
source of these headers for the Azure origin, and was the only source for the AWS
origin until 2026-07-25:

| Origin | Sets these headers itself? |
|---|---|
| GCP / Cloud Run (nginx) | Yes, via [`nginx-security-headers.conf`](../nginx-security-headers.conf) |
| AWS / CloudFront | Yes, since `aws_cloudfront_response_headers_policy.security` was added to [`infra/terraform/aws/cloudfront.tf`](../infra/terraform/aws/cloudfront.tf) - but **only once `terraform -chdir=infra/terraform/aws apply` has run**; until then the distribution still serves no headers of its own |
| Azure Blob static website | **No.** Azure Blob static websites cannot emit custom response headers at all |

So the script closes the loop from the other end. Terraform cannot tell you the edge
drifted, so CI asks the edge directly. Drift from a forgotten apply, an ad-hoc
dashboard edit, or someone with the Cloudflare API token weakening a header now fails
the build instead of going unnoticed.

## What it checks

The 8 headers parsed out of the `set_security_headers` rule, by name and exact value:

`Strict-Transport-Security` · `X-Content-Type-Options` · `X-Frame-Options` ·
`Referrer-Policy` · `Permissions-Policy` · `Content-Security-Policy` ·
`Cross-Origin-Opener-Policy` · `Cross-Origin-Resource-Policy`

Nothing is configured in the script. The expected values are read from `rules.tf` at
run time, so editing a header value there is all it takes to change what CI demands.

How the comparison works:

1. **Narrow to the right rule.** The section starts at `ref = "set_security_headers"`
   so a future second rule in the same file cannot contribute headers.
2. **Parse each `headers { ... }` block** with the `HEADER_BLOCK` regex, keeping only
   blocks whose `operation` is `set`.
3. **Fetch the URL** and lowercase every response header name. A 4xx/5xx response is
   still asserted against rather than treated as an error: nginx sets these with
   `always`, so an error page carries them too.
4. **Compare with whitespace normalized** (`\s+` collapsed to a single space, then
   stripped), so reformatting a long CSP across lines does not fail CI.

## In CI

The `purge-cloudflare` job in [`deploy.yml`](../.github/workflows/deploy.yml) runs it
as the last step, right after "Verify live assets match their SRI hashes". Same idea,
applied to headers instead of asset bytes: the job `needs:` all three publishers, so by
the time it runs it is checking a fully-published site.

```yaml
- name: Verify live security headers match the repo
  run: python3 tools/check_edge_headers.py --url https://csoh.org/
```

That job historically had no checkout of its own (which is why the SRI step above it is
written as an inline heredoc). It now checks out the repo purely to get this script,
with `persist-credentials: false` - nothing in the job talks to git after the clone, so
the credential should not be left sitting in `.git/config`.

## When it fails

Read the failure message literally, because the obvious fix does not work. A real run
against production with `'unsafe-inline'` added to `script-src` in `rules.tf` (values
abridged here; the script prints them in full, exit status 1):

```
FAIL: 1 header(s) do not match what Git declares.

  - Content-Security-Policy: DRIFT
      repo: default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self'; ...
      edge: default-src 'self'; script-src 'self'; style-src 'self'; ...
```

`repo:` is what `rules.tf` declares, `edge:` is what csoh.org served.

**`terraform apply` will NOT fix this** while `ignore_changes = [rules]` is in place.
It will report a clean plan and change nothing. Two things actually work:

1. Edit the header in the **Cloudflare dashboard** so the edge matches the repo, or
2. Temporarily drop the `lifecycle` block for a single `terraform apply`, then put it
   back (expect the inconsistent-result error to reappear on the next re-apply).

A `MISSING` result for every header usually means you pointed `--url` at a bare origin
rather than at the Cloudflare edge. That is a real thing to check by hand, but it is
expected to fail for the Azure origin, which cannot set the headers at all.

## The parsing gotcha worth remembering

An earlier version of `parse_expected_headers()` bounded the section with a plain
substring search for `"lifecycle"`. The CSP's own explanatory comment in `rules.tf`
contains the phrase "the lifecycle block below", so the search stopped there and
silently dropped the last three headers: **CSP, COOP, and CORP** - precisely the ones
this check exists to protect. It still printed a confident pass.

The section end is now matched as an actual block opener:

```python
end_match = re.search(r"^\s*lifecycle\s*\{", text[start:], re.MULTILINE)
```

`parse_expected_headers()` exits with an error if it parses **zero** headers, but a
partial parse is the dangerous case and nothing catches it automatically. **If you
touch `HEADER_BLOCK` or the section bounds, assert the parsed count is 8** (or whatever
`rules.tf` declares at the time):

```bash
python3 tools/check_edge_headers.py | head -1   # must say "Checking 8 security headers"
```

Two smaller shape assumptions the regex bakes in: `name`, `operation`, and `value` each
sit on their own line and appear in that order, and `re.DOTALL` is deliberately not set.
Reordering those fields in `rules.tf` breaks the parse.

## Keeping the three copies in step

The same 8 headers are now declared in three places, and nothing cross-checks them
against each other:

- `infra/terraform/cloudflare/rules.tf` (the edge, and the source of truth this script reads)
- `infra/terraform/aws/cloudfront.tf` (`aws_cloudfront_response_headers_policy.security`)
- `nginx-security-headers.conf` (the GCP origin)

Change one, change all three. This script only asserts the first one against the live
edge; it will not notice an origin that has fallen behind.

## Delete this script when...

...the **cloudflare v5 provider** upgrade lands and `ignore_changes = [rules]` can be
removed from `rules.tf`. At that point Terraform manages the ruleset for real again,
`terraform plan` is the drift detector, and this check is redundant. Remove the script,
its `deploy.yml` step, and the checkout that step needs.

## See also

- [`UPDATE_SRI_README.md`](UPDATE_SRI_README.md) - the other "does the live site match the repo" gate in the same `purge-cloudflare` job
- [SECURITY.md](../SECURITY.md) - the multi-origin architecture these headers cover
