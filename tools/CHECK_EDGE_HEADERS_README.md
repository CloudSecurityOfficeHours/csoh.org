# Edge Security Header Check

Asserts that the security headers csoh.org actually serves are the ones
[`infra/terraform/cloudflare/rules.tf`](../infra/terraform/cloudflare/rules.tf) declares.

Exits non-zero on any missing or drifted header. It is a CI gate, and it exists because
Terraform cannot enforce this particular resource.

## Quick Start

```bash
python3 tools/check_edge_headers.py                                  # 40 samples of https://csoh.org/
python3 tools/check_edge_headers.py --url https://csoh.org/about.html
python3 tools/check_edge_headers.py --url https://<dist>.cloudfront.net/ --samples 1
```

Passing run (real output, 2026-07-26, about 12 seconds wall clock):

```
Checking 8 security headers from infra/terraform/cloudflare/rules.tf against https://csoh.org/
Sampling 40 cache-busted requests to reach all origins
  origins reached: aws=8, azure=17, gcp-or-unlabelled=15
  ok  Strict-Transport-Security
  ok  X-Content-Type-Options
  ok  X-Frame-Options
  ok  Referrer-Policy
  ok  Permissions-Policy
  ok  Content-Security-Policy
  ok  Cross-Origin-Opener-Policy
  ok  Cross-Origin-Resource-Policy

OK: all 8 headers match the repo across 40 request(s) to https://csoh.org/.
```

Two flags. `--url` points at any hostname: use an origin's own hostname to check that
origin directly instead of the edge. `--samples` sets how many cache-busted requests to
make, default 40, and the next section is entirely about why that number is not 1. Use
`--samples 1` when `--url` names a single origin, where there is nothing to sample.

Standard library only. No `pip install`, no Cloudflare API token: it just does plain
`GET`s and reads the response headers.

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
| AWS / CloudFront | Yes, via `aws_cloudfront_response_headers_policy.security` in [`infra/terraform/aws/cloudfront.tf`](../infra/terraform/aws/cloudfront.tf), added and applied on 2026-07-25. Before that apply the distribution served no headers of its own, and its `*.cloudfront.net` hostname is public |
| Azure Blob static website | **No.** Azure Blob static websites cannot emit custom response headers at all |

So the script closes the loop from the other end. Terraform cannot tell you the edge
drifted, so CI asks the edge directly. Drift from a forgotten apply, an ad-hoc
dashboard edit, or someone with the Cloudflare API token weakening a header now fails
the build instead of going unnoticed.

## Why 40 requests and not one

Until 2026-07-26 this gate made exactly one request, and that made it far weaker than it
looked. Read the table above again: the apex is a Cloudflare load balancer over three
origins, and **AWS and GCP now set these headers themselves**. An AWS-served or GCP-served
response therefore looks perfect whether the Cloudflare ruleset is correct, weakened, or
deleted outright. Only an **Azure**-served response actually exercises the ruleset, because
Azure Blob static websites cannot emit custom response headers at all.

One request that happens to land on AWS or GCP is not a check of the thing this script
exists to guard. It is a check of the origin that did not need guarding. The distribution
measured over 20 requests on 2026-07-26 was 10 GCP, 6 AWS, 4 Azure, so a single-request
gate reported green roughly four times in five even in the scenario where the edge ruleset
had been deleted - and the real-world failure it was missing would have shipped to about
one visitor in five. Azure's share is not fixed: the 40-sample run quoted above saw 17.

So the script now makes `--samples` requests (default 40), each with a unique
`?__hdrcheck=` cache-buster - a cached response would just re-confirm whichever origin
answered first - and prints which origins it reached:

```
  origins reached: aws=8, azure=17, gcp-or-unlabelled=15
```

Every failure is tagged with the origin that produced it, which is the diagnostic that
matters: a failure seen **only** on `origin=azure` means the Cloudflare ruleset is the
broken part, since Azure has nothing else to fall back on. A failure on all three is
more likely a bad value in `rules.tf` itself.

The default of 40 comes from measurement, not from a binomial calculation, because
Cloudflare's steering is not independent per request: it arrives in bursts. The numbers
recorded in the script's `DEFAULT_SAMPLES` comment, all from 2026-07-26: two consecutive
25-sample runs reached Azure **zero** times, and the next reached it 17 times. At 40
samples, five consecutive runs reached Azure 15, 15, 12, 7 and 11 times. Forty costs about
10 seconds and has so far always reached Azure; 25 demonstrably has not.

**This is sampling, not proof, and the script says so.** Nothing here can force Cloudflare
to route a request to a chosen origin. A run that never lands on Azure has not tested the
ruleset, so a passing run that saw no Azure response prints:

```
  ! warning: no request landed on the Azure origin, which is the only
    one relying on the Cloudflare ruleset. Consider raising --samples.
```

Treat that warning as "this run proved nothing about the edge" and re-run with a higher
`--samples`. The only deterministic alternative is reading the ruleset back through the
Cloudflare API, which needs a token with ruleset permissions; the deploy path deliberately
carries only a cache-purge token (see the two-tokens section in [`CLAUDE.md`](../CLAUDE.md)),
and giving CI the broader one to check a header would hand it the ability to rewrite one.

`--samples 1` remains correct when `--url` names a single origin hostname directly: there
is one origin, so there is nothing to sample.

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

No `--samples` there on purpose: CI gets the default 40, and the ~10 seconds it costs is
noise next to a deploy. If you ever add `--samples` to that step, adding a smaller number
is the one direction that silently weakens the gate.

That job historically had no checkout of its own (which is why the SRI step above it is
written as an inline heredoc). It now checks out the repo purely to get this script,
with `persist-credentials: false` - nothing in the job talks to git after the clone, so
the credential should not be left sitting in `.git/config`.

## When it fails

Read the failure message literally, because the obvious fix does not work. A real run
against production with `'unsafe-inline'` added to `script-src` in `rules.tf` (values
abridged here; the script prints them in full, exit status 1):

```
FAIL: 1 header problem(s) versus what Git declares.

  - [origin=azure] Content-Security-Policy: DRIFT
      repo: default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self'; ...
      edge: default-src 'self'; script-src 'self'; style-src 'self'; ...
```

`repo:` is what `rules.tf` declares, `edge:` is what csoh.org served. The `[origin=...]`
tag says which origin answered the request that produced the problem, and identical
problems are reported once however many samples hit them.

**`terraform apply` will NOT fix this** while `ignore_changes = [rules]` is in place.
It will report a clean plan and change nothing. Two things actually work:

1. Edit the header in the **Cloudflare dashboard** so the edge matches the repo, or
2. Temporarily drop the `lifecycle` block for a single `terraform apply`, then put it
   back (expect the inconsistent-result error to reappear on the next re-apply).

A `MISSING` result for every header, tagged `[origin=azure]`, is the signature of the
failure this gate is built for: the Azure origin serves no headers of its own, so the
edge ruleset has stopped applying.

The same all-`MISSING` result when you pointed `--url` at the Azure blob endpoint
directly, with `--samples 1`, is expected and means nothing is wrong - you bypassed the
edge. Pointing `--url` at the AWS or GCP origin directly should now **pass**, since both
set the headers themselves; that is a useful way to confirm the CloudFront policy and
`nginx-security-headers.conf` have not fallen behind, because nothing in CI checks those
two.

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

Change one, change all three. **CI checks only the first.** The other two are kept in
step by hand.

Sampling does not change that. The ruleset's `set` operation overwrites whatever the
origin sent, so a response that came back through the apex carries the edge's values no
matter which origin produced it - which is precisely why an edge failure shows up only on
Azure, and equally why a stale CloudFront policy or a stale `nginx-security-headers.conf`
is invisible from the apex. To check those two, aim `--url` at the origin hostname itself
with `--samples 1`, as described under [When it fails](#when-it-fails).

## Delete this script when...

...the **cloudflare v5 provider** upgrade lands and `ignore_changes = [rules]` can be
removed from `rules.tf`. At that point Terraform manages the ruleset for real again,
`terraform plan` is the drift detector, and this check is redundant. Remove the script,
its `deploy.yml` step, and the checkout that step needs.

## See also

- [`UPDATE_SRI_README.md`](UPDATE_SRI_README.md) - the other "does the live site match the repo" gate in the same `purge-cloudflare` job
- [SECURITY.md](../SECURITY.md) - the multi-origin architecture these headers cover
